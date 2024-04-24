import configparser
import os
import signal
import sys
import logging
import subprocess
import platform
from pathlib import Path
from glob import glob
from time import sleep
from typing import Optional, List, Hashable, Set, Iterable
from sd_core.dirs import get_data_dir
import psutil

import sd_core

logger = logging.getLogger(__name__)

# The path of sd_qt
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    _module_dir = os.path.dirname(sys.executable)
else:
    # Running as a script or API
    _module_dir = os.path.dirname(os.path.realpath(__file__))

# The path of the sd-qt executable (when using PyInstaller)
_parent_dir = os.path.abspath(os.path.join(_module_dir, os.pardir))

file_path = get_data_dir("sd-server")
config_file_path = os.path.join(file_path, "process.ini")


def _log_modules(modules: List["Module"]) -> None:
    """
     Log the modules to the log. This is a helper for : func : ` _log_modules `.
     
     @param modules - A list of modules to log. Each module is a : class : ` pyflink. module. Module ` object.
     
     @return None. If you want to skip logging pass an empty list
    """
    # Debugging of all modules in the module list
    for m in modules:
        logger.debug(f" - {m.name} at {m.path}")


ignored_filenames = ["sd-cli", "sd-client", "sd-qt", "sd-qt.desktop", "sd-qt.spec"]
auto_start_modules = ["sd-server"]


def filter_modules(modules: Iterable["Module"]) -> Set["Module"]:
    """
     Filter modules to remove ignored ones. This is used in : func : ` get_modules ` to avoid a list of modules that are not part of the list of modules returned by this function.
     
     @param modules - The modules to filter. Must be a set of modules.
     
     @return The set of modules that are not ignored by this
    """
    # Remove things matching the pattern which is not a module
    # Like sd-qt itself, or sd-cli
    return {m for m in modules if m.name not in ignored_filenames}


def initialize_ini_file():
    """
     Initialize the INI file with default values if it doesn't exist. This is done by adding sections and default values for each module
    """
    """
    Initialize the INI file with default values if it doesn't exist.
    """
    # Initialize the INI file with default values.
    if not os.path.exists(config_file_path):
        config = configparser.ConfigParser()
        # Adding sections and default values for each module
        config['sd-server'] = {'status': 'False', 'pid': 0}
        config['sd-watcher-afk'] = {'status': 'False', 'pid': 0}
        config['sd-watcher-window'] = {'status': 'False', 'pid': 0}

        with open(config_file_path, 'w') as configfile:
            config.write(configfile)
        logger.info("Initialized new INI file with default values.")


def is_executable(path: str, filename: str) -> bool:
    """
     Checks if a file is executable. This is a helper function for L { os. path. isfile } and L { os. path. access }
     
     @param path - Path to the file to check
     @param filename - Name of the file to check ( without extension )
     
     @return True if the file is executable False if it is
    """
    # Return true if the path is a file.
    if not os.path.isfile(path):
        return False
    # On windows all files ending with .exe are executables
    # Returns true if the file is a. desktop file.
    if platform.system() == "Windows":
        return filename.endswith(".exe")
    # On Unix platforms all files having executable permissions are executables
    # We do not however want to include .desktop files
    else:  # Assumes Unix
        # Return true if the path is a valid file.
        if not os.access(path, os.X_OK):
            return False
        # Return true if the filename ends with. desktop
        if filename.endswith(".desktop"):
            return False
        return True


def _discover_modules_in_directory(path: str) -> List["Module"]:
    """
     Discover modules in given directory path and recursively in subdirs matching sd - *
     
     @param path - Path to directory to search
     
     @return List of modules found
    """
    """Look for modules in given directory path and recursively in subdirs matching sd-*"""
    modules = []
    matches = glob(os.path.join(path, "sd-*"))
    # Find all modules in matches.
    for path in matches:
        basename = os.path.basename(path)
        # Add a module to the modules list.
        if is_executable(path, basename) and basename.startswith("sd-"):
            name = _filename_to_name(basename)
            modules.append(Module(name, Path(path), "bundled"))
        elif os.path.isdir(path) and os.access(path, os.X_OK):
            modules.extend(_discover_modules_in_directory(path))
        else:
            logger.warning(f"Found matching file but was not executable: {path}")
    return modules


def _filename_to_name(filename: str) -> str:
    """
     Convert a filename to a file name. This is used to make filenames consistent across platforms.
     
     @param filename - The filename to convert. Must be a valid filename.
     
     @return The filename with all. exe characters replaced by spaces
    """
    return filename.replace(".exe", "")


def _discover_modules_bundled() -> List["Module"]:
    """
     Discover bundled modules and return them. This is a wrapper around _discover_modules_in_directory to search the modules in a variety of locations.
     
     
     @return List [ Module ] A list of modules that are found
    """
    search_paths = [_module_dir, _parent_dir]
    # Add macos directory to search paths.
    if platform.system() == "Darwin":
        macos_dir = os.path.abspath(os.path.join(_parent_dir, os.pardir, "MacOS"))
        search_paths.append(macos_dir)
    # logger.debug(f"Searching for bundled modules in: {search_paths}")

    modules: List[Module] = []
    # Find all modules in search_paths in the search paths.
    for path in search_paths:
        modules += _discover_modules_in_directory(path)

    modules = list(filter_modules(modules))
    logger.info(f"Found {len(modules)} bundled modules")
    _log_modules(modules)
    return modules


def _discover_modules_system() -> List["Module"]:
    """
     Find all modules in the system PATH This is a helper function to get a list of all modules that are installed on the system.
     
     
     @return List [ Module ] : List of Module objects that are
    """
    """Find all sd- modules in PATH"""
    search_paths = os.get_exec_path()

    # Needed because PyInstaller adds the executable dir to the PATH
    # Remove the parent directory from search paths.
    if _parent_dir in search_paths:
        search_paths.remove(_parent_dir)

    # logger.debug(f"Searching for system modules in PATH: {search_paths}")
    modules: List["Module"] = []
    paths = [p for p in search_paths if os.path.isdir(p)]
    # List all the modules in the paths.
    for path in paths:
        try:
            ls = os.listdir(path)
        except PermissionError:
            logger.warning(f"PermissionError while listing {path}, skipping")
            continue

        # Add modules to modules list.
        for basename in ls:
            # If basename starts with sd or if basename starts with sd
            if not basename.startswith("sd-"):
                continue
            # Check if the basename is executable.
            if not is_executable(os.path.join(path, basename), basename):
                continue
            name = _filename_to_name(basename)
            # Only pick the first match (to respect PATH priority)
            # Add a module to the list of modules.
            if name not in [m.name for m in modules]:
                modules.append(Module(name, Path(path) / basename, "system"))

    modules = list(filter_modules(modules))
    logger.info(f"Found {len(modules)} system modules")
    _log_modules(modules)
    return modules


def read_update_ini_file(modules, key, new_value=None):
    """
    Read and optionally update data in an INI file.

    Args:
        file_path (str): The path to the INI file.
        section (str): The section in the INI file.
        key (str): The key within the section.
        new_value (str, optional): The new value to set for the key (if None, no update is performed).

    Returns:
        str: The current value of the key in the specified section.
    """
    config = configparser.ConfigParser()
    config.read(config_file_path)

    # Read data from the INI file
    current_value = config.get(modules, key)

    if new_value is not None:
        # Update data in the INI file if new_value is provided
        config.set(modules, key, new_value)
        with open(config_file_path, 'w') as configfile:
            config.write(configfile)

    return current_value


class Module:
    def __init__(self, name: str, path: Path, type: str) -> None:
        """
         Initialize the instance. This is the entry point for the class. It sets the name of the configuration file and the path to the configuration file
         
         @param name - The name of the configuration file
         @param path - The path to the configuration file ( must be a directory )
         @param type - The type of the configuration file ( system or bundled
        """
        self.name = name
        self.path = path
        assert type in ["system", "bundled"]
        self.type = type
        self.config_file_path = config_file_path
        self.started = False
        initialize_ini_file()

    def _read_pid(self) -> Optional[int]:
        """
         Read PID from config file. This is used to determine the PID of the process that will be launched
         
         
         @return The PID or None if not
        """
        config = configparser.ConfigParser()
        config.read(self.config_file_path)
        try:
            return int(config.get(self.name, 'pid'))
        except Exception as e:
            logger.error(f"Error reading PID for {self.name}: {e}")
            return None

    def _write_pid(self, pid: int):
        """
         Write PID to config file. This is used to set the PID of the daemon to be used when running the command
         
         @param pid - PID to be written
        """
        config = configparser.ConfigParser()
        config.read(self.config_file_path)
        # Add a section to the config if it doesn t already exist.
        if not config.has_section(self.name):
            config.add_section(self.name)
        config.set(self.name, 'pid', str(pid))
        with open(self.config_file_path, 'w') as configfile:
            config.write(configfile)
        logger.debug(f"PID for {self.name} written to file: {pid}")

    def _update_status_in_ini(self, status: bool):
        """
         Update status in INI file. This is used to enable / disable / update the status of the job
         
         @param status - True if job is
        """
        config = configparser.ConfigParser()
        config.read(self.config_file_path)
        # Add a section to the config if it doesn t already exist.
        if not config.has_section(self.name):
            config.add_section(self.name)
        config.set(self.name, 'status', 'True' if status else 'False')
        with open(self.config_file_path, 'w') as configfile:
            config.write(configfile)

    def _is_process_running(self, pid: int) -> bool:
        """
         Check if a process is running. This is a wrapper around psutil. Process. is_running ()
         
         @param pid - Process ID to check.
         
         @return True if process is running False otherwise. Note that None is considered to be a process
        """
        # Returns true if pid is None or 0
        if pid is None or pid <= 0:
            return False

        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def start(self):
        """
         Start the process if it isn't already running. This is a blocking call
         
         
         @return True if the process was
        """
        pid = self._read_pid()
        # Check if process is running
        if pid and self._is_process_running(pid):
            logger.info(f"{self.name} is already running")
            return
        exec_cmd = [str(self.path)]
        self.started = True
        logger.info(f"Starting {self.name}")
        startupinfo = None
        # This function is called by the main bundle when the OS is running on the OS X.
        if sys.platform == "win32" or sys.platform == "cygwin":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        elif sys.platform == "darwin":
            logger.info("macOS: Disable dock icon")
            import AppKit
            AppKit.NSBundle.mainBundle().infoDictionary()["LSBackgroundOnly"] = "1"

        self._process = subprocess.Popen(
            exec_cmd, universal_newlines=True, startupinfo=startupinfo
        )
        self._write_pid(self._process.pid)
        self._update_status_in_ini(True)

    def stop(self):
        """
         Stop the process if it is running and update status in INI file to
        """
        pid = self._read_pid()
        # Stop the process and update the status to False
        if pid and self._is_process_running(pid):
            try:
                process = psutil.Process(pid)
                process.terminate()  # or process.kill() if terminate does not work
                logger.info(f"Stopped {self.name}")
                self.started = False
                self._update_status_in_ini(False)  # Update status to False when stopped
                self._write_pid(0)  # Remove the PID from the INI file
            except psutil.Error as e:
                logger.error(f"Error stopping {self.name}: {e}")
        else:
            logger.info(f"{self.name} is not running or PID is invalid")

    def is_alive(self) -> bool:
        """
         Check if the process is running. This is the same as running but without the need to wait for it to finish
         
         
         @return True if the process
        """
        pid = self._read_pid()
        # Returns true if pid is zero or None.
        if pid == 0 or pid is None:
            return False

        # Check if a process with this PID exists
        # Return True if pid exists.
        if not psutil.pid_exists(pid):
            return False

        # Validate if the process is the correct one
        try:
            proc = psutil.Process(pid)
            # You can add more checks here if needed, like comparing process names
            return proc.is_running()
        except psutil.NoSuchProcess:
            return False

    def toggle(self, testing: bool) -> None:
        """
         Toggle the state of the daemon. This is a no - op if the daemon is already running
         
         @param testing - True if testing False if not
         
         @return True if the daemon was toggled False if
        """
        # Stop the game if the game is started.
        if self.started:
            self.stop()
        else:
            self.start()

    def read_log(self, testing: bool) -> str:
        """Useful if you want to retrieve the logs of a module"""
        log_path =sd_core.log.get_latest_log_file(self.name, testing)
        if log_path:
            with open(log_path) as f:
                return f.read()
        else:
            return "No log file found"


class Manager:
    def __init__(self, testing: bool = False) -> None:
        """
         Initialize the module. This is the entry point for the module to be used
         
         @param testing - If True the module is testing
         
         @return True if initialization was successful False if it was not
        """
        self.modules: List[Module] = []
        self.testing = testing

        self.discover_modules()

    @property
    def modules_system(self) -> List[Module]:
        """
         Get a list of modules that are system modules. This is useful for determining which modules are part of a program and which aren't.
         
         
         @return List [ Module ] -- List of system modules in
        """
        return [m for m in self.modules if m.type == "system"]

    @property
    def modules_bundled(self) -> List[Module]:
        """
         Get list of bundled modules. This is used to determine if we are running in a sandbox and need to re - install it if it's not.
         
         
         @return List [ Module ] : List of bundled modules
        """
        return [m for m in self.modules if m.type == "bundled"]

    def discover_modules(self) -> None:
        """
         Discover and populate self. modules. This is a blocking call until all modules are discovered.
         
         
         @return True if at least one module was discovered False otherwise
        """
        # These should always be bundled with sd-qt
        modules = set(_discover_modules_bundled())
        modules |= set(_discover_modules_system())
        modules = filter_modules(modules)

        # update one by one
        # Add modules to the list of modules.
        for m in modules:
            # Add a module to the list of modules.
            if m not in self.modules:
                self.modules.append(m)

    def get_unexpected_stops(self) -> List[Module]:
        """
         Get a list of modules that have stopped. This is useful for debugging and to avoid having to wait for a module to stop before it is actually stopped.
         
         
         @return A list of modules that have stopped but are not
        """
        return list(filter(lambda x: x.started and not x.is_alive(), self.modules))

    def start(self, module_name: str) -> None:
        """
         Start a module by name. This is a no - op if the module doesn't exist
         
         @param module_name - The name of the module to start
         
         @return The module that was started or None if it could not be
        """
        # NOTE: Will always prefer a bundled version, if available. This will not affect the
        #       sd-qt menu since it directly calls the module's start() method.
        bundled = [m for m in self.modules_bundled if m.name == module_name]
        system = [m for m in self.modules_system if m.name == module_name]
        # Start the manager. If bundled or system are not found start the manager.
        if bundled:
            bundled[0].start()
        elif system:
            system[0].start()
        else:
            logger.error(f"Manager tried to start nonexistent module {module_name}")

    def autostart(self, autostart_modules: List[str]) -> None:
        """
         Autostart modules in a way that works in both bundled and non - bundled
         
         @param autostart_modules - list of modules to autost
        """
        # NOTE: Currently impossible to autostart a system module if a bundled module with the same name exists

        # We only want to autostart modules that are both in found modules and are asked to autostart.
        # Check if all modules are autostart modules.
        for name in autostart_modules:
            # Check if module is in the list of modules
            if name not in [m.name for m in self.modules]:
                logger.error(f"Module {name} not found")
        autostart_modules = list(set(autostart_modules))

        # Start sd-server-rust first
        # Start the autostart modules if they are available.
        if "sd-server-rust" in autostart_modules:
            self.start("sd-server-rust")
        elif "sd-server" in autostart_modules and "sd-server" in auto_start_modules:
            self.start("sd-server")

        autostart_modules = list(
            set(autostart_modules) - {"sd-server"}
        )
        # Start all modules that are auto started.
        for name in autostart_modules:
            # Start the module if it is not already started.
            if name in auto_start_modules:
                self.start(name)

    def stop(self, module_name: str) -> None:
        """
         Stop a module by name. This is a no - op if the module doesn't exist
         
         @param module_name - The name of the module to stop
         
         @return None on success error code on failure See : py : meth : ` Manager. stop
        """
        # Stop all modules in the manager.
        for m in self.modules:
            # Stop the module if it is a module.
            if m.name == module_name:
                m.stop()
                break
        else:
            logger.error(f"Manager tried to stop nonexistent module {module_name}")

    def stop_all(self) -> None:
        """
         Stop all servers and their modules. This is useful for tests that want to clean up after a server has been stopped.
         
         
         @return None on success None on failure ( no exception raised
        """
        server_module_name = "sd-server"
        server_module = None

        # Find 'sd-server' module and temporarily exclude it from the stop process
        # This method will stop the server module if it is alive.
        for module in self.modules:
            # This method is called by the server when the module is alive.
            if module.name == server_module_name:
                server_module = module
            elif module.is_alive():
                module.stop()

        # Finally, stop 'sd-server' if it's running
        # Stop the server module if it is alive.
        if server_module and server_module.is_alive():
            server_module.stop()

    def print_status(self, module_name: Optional[str] = None) -> None:
        """
         Print status of modules. If module_name is specified print status of module with that name
         
         @param module_name - name of module to print status of
         
         @return None if nothing was printed otherwise returns the number of
        """
        header = "name                status      type"
        # Prints the status of all modules in the module list
        if module_name:
            # find module
            module = next((m for m in self.modules if m.name == module_name), None)
            # Print the module status.
            if module:
                logger.info(header)
                self._print_status_module(module)
            else:
                logger.error(f"Module {module_name} not found")
        else:
            logger.info(header)
            # Print all the modules in the list of modules.
            for module in self.modules:
                self._print_status_module(module)

    def _print_status_module(self, module: Module) -> None:
        """
         Print status of module. This is a helper method for _get_status_module and _get_status_module_by_name.
         
         @param module - The module to print status for. It must be an instance of Module
         
         @return None for backwards compatibility
        """
        logger.info(
            f"{module.name:18}  {'running' if module.is_alive() else 'stopped' :10}  {module.type}"
        )

    def status(self):
        """
         Get information about the status of the watch. This is a list of dictionaries that contain the following keys.
         
         
         @return A list of dictionaries. Each dictionary contains the following keys
        """
        modules_list = []
        # Serialize module data
        # Add module info to the list of modules
        for m in self.modules:
            module_info = {
                "watcher_name": m.name,  # Replace with the actual attribute or property name
                "Watcher_status": m.is_alive(),  # Replace with the actual method or property
                "Watcher_location": str(m)  # Convert module object to a string
            }
            modules_list.append(module_info)
        return modules_list

    def module_status(self, module_name: Optional[str] = None) -> dict:
        """
         Print status of modules. If module_name is specified print status of module with that name

         @param module_name - name of module to print status of

         @return None if nothing was printed otherwise returns the number of
        """
        status = {}
        # Prints the status of all modules in the module list
        if module_name:
            # find module
            module = next((m for m in self.modules if m.name == module_name), None)
            # Print the module status.
            if module:
                status['module_name'] = module.name
                status['is_alive'] = module.is_alive()
                return status
            else:
                logger.error(f"Module {module_name} not found")

    def stop_modules(self, module_name: str) -> str:
        """
         Stop a module by name. This is a no - op if the module doesn't exist
         
         @param module_name - The name of the module to stop
         
         @return A message explaining what went wrong or None if everything went
        """
        # Stop the manager. Returns a string describing the manager stopped.
        for m in self.modules:
            # Stop the module if it is not already stopped.
            if m.name == module_name:
                m.stop()
                return f"Module {module_name} is stopped"
        else:
            return f"Manager tried to stop nonexistent module {module_name}"


def main_test():
    manager = Manager()
    for module in manager.modules:
        module.start(testing=True)
        sleep(2)
        assert module.is_alive()
        module.stop()


if __name__ == "__main__":
    main_test()
