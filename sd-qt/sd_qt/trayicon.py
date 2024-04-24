import sys
import logging
import signal
import os
import subprocess
import webbrowser
from typing import Any, Optional, Dict
from pathlib import Path

from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMessageBox,
    QMenu,
    QWidget,
    QPushButton,
)
import getpass
import time
from PyQt6.QtGui import QIcon

import sd_core

from .manager import Manager, Module

if sys.platform == "win32":
    import win32com.client


logger = logging.getLogger(__name__)



def get_env() -> Dict[str, str]:
    """
     Get environment variables to pass to BSD. This is useful for things like LD_LIBRARY_PATH which may be set in the environment as well as when running in gnu / Linux.
     
     
     @return A dictionary of environment variables to pass to BSD. Note that the environment variables are copied to avoid accidental changes
    """
    env = dict(os.environ)  # make a copy of the environment
    lp_key = "LD_LIBRARY_PATH"  # for GNU/Linux and *BSD.
    lp_orig = env.get(lp_key + "_ORIG")
    if lp_orig is not None:
        env[lp_key] = lp_orig  # restore the original, unmodified value
    else:
        # This happens when LD_LIBRARY_PATH was not set.
        # Remove the env var as a last resort:
        # Restore the original value of the environment variable lp_key.
        env.pop(lp_key, None)
    return env


def open_url(url: str) -> None:
    """
        Open a URL in the default browser. This is a wrapper around webbrowser. open () in order to work on Linux and OSX
        
        @param url - URL to open in the default browser
        
        @return True if the URL was opened successfully False if there was an error opening the URL ( or if we were unable to open it
    """
    if sys.platform == "linux":
        env = get_env()
        subprocess.Popen(["xdg-open", url], env=env)
    else:
        webbrowser.open(url)

# Open the web browser if the current platform is linux.


def open_webui(root_url: str) -> None:
    print("Opening dashboard")
    open_url(root_url)


def open_apibrowser(root_url: str) -> None:
    """
     Open the WebUI in the default browser. This is a convenience function for use in tests that need to be run as a web UI.
     
     @param root_url - The URL to navigate to. If it's a directory it will be searched for the root of the directory.
     
     @return True if the dashboard was opened False otherwise. Note that this does not return a result but it just prints a message
    """
    print("Opening api browser")
    open_url(root_url + "/api")


def open_dir(d: str) -> None:
    """
     Opens the API browser. This is a convenience function to be used in conjunction with open_url (... )
     
     @param root_url - The URL of the root of the application.
     
     @return None. If you don't want to return a result use get_apibrowser_result
    """
    """From: http://stackoverflow.com/a/1795849/965332"""
    if sys.platform == "win32":
        os.startfile(d)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", d])
    else:
        # Open the file and open it.
        env = get_env()
        subprocess.Popen(["xdg-open", d], env=env)


def check_user_switch(manager: Manager) -> None:
    wmi = win32com.client.GetObject('winmgmts:')
    for session in wmi.InstancesOf('Win32_ComputerSystem'):
        if session.UserName is not None:
            time.sleep(3)
            username = session.UserName.split('\\')[-1]
            """
             Check if user switch is possible. This is a hack to avoid accidental mistakes in Windows and other OSes
             
             @param manager - manager to use for
            """
            if username != getpass.getuser():
                # Exit the manager if the user is not None.
                logger.warning("Mismatch detected. Exiting...")
                # This function will sleep 3 seconds and exit the manager.
                exit(manager)

class TrayIcon(QSystemTrayIcon):
    # Exit the manager if the username is different from the current user.
    def __init__(
        self,
        manager: Manager,
        icon: QIcon,
        parent: Optional[QWidget] = None,
        testing: bool = False,
    ) -> None:
        """
            Initialize the tray icon. This is called by QSystem. __init__ and should not be called directly
            
            @param manager - The manager that owns this tray
            @param icon - The icon to display in the tray
            @param parent - The parent widget ( if any ). Defaults to None
            @param testing - Whether or not we are testing
            
            @return The root menu for the tray or None if it's not a root menu. Note that it does not have to be an instance of the tray
        """
        QSystemTrayIcon.__init__(self, icon, parent)
        # QSystemTrayIcon also tries to save parent info but it screws up the type info
        self._parent = parent
        self.setToolTip("ActivityWatch" + (" (testing)" if testing else ""))

        self.manager = manager
        self.testing = testing

        self.root_url = f"http://localhost:{5666 if self.testing else 7600}"
        self.activated.connect(self.on_activated)

        self._build_rootmenu()

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            open_webui(self.root_url)

    def _build_rootmenu(self) -> None:
        menu = QMenu(self._parent)
# Open webui if activation reason is double click.

        if self.testing:
            menu.addAction("Running in testing mode")  # .setEnabled(False)
            menu.addSeparator()

        # openWebUIIcon = QIcon.fromTheme("open")
        # This method is called when the user clicks on the testing menu.
        menu.addAction("Open TTim", lambda: open_webui(self.root_url))
        menu.addSeparator()
        exitIcon = QIcon.fromTheme(
            "application-exit", QIcon("media/application_exit.png")
        )
        # This check is an attempted solution to: https://github.com/ActivityWatch/activitywatch/issues/62
        # Seems to be in agreement with: https://github.com/OtterBrowser/otter-browser/issues/1313
        #   "it seems that the bug is also triggered when creating a QIcon with an invalid path"
        if exitIcon.availableSizes():
            menu.addAction(exitIcon, "Quit TTim", lambda: exit(self.manager))
        else:
            menu.addAction("Quit TTim", lambda: exit(self.manager))
        self.setContextMenu(menu)
# Add an action to quit the menu

        def show_module_failed_dialog(module: Module) -> None:
            box = QMessageBox(self._parent)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(f"Module {module.name} quit unexpectedly")
            box.setDetailedText(module.read_log(self.testing))

            """
             Show a dialog to the user that a module failed to quit unexpectedly. This is used for tests that don't care about the exit status of the module.
             
             @param module - The module that failed to quit. It must have been created by : meth : ` create_module
            """
            restart_button = QPushButton("Restart", box)
            restart_button.clicked.connect(module.start)
            box.addButton(restart_button, QMessageBox.ButtonRole.AcceptRole)
            box.setStandardButtons(QMessageBox.StandardButton.Cancel)

            box.show()

#         def rebuild_modules_menu() -> None:
#             for action in modulesMenu.actions():
#                 if action.isEnabled():
#                     module: Module = action.data()
#                     alive = module.is_alive()
#                     action.setChecked(alive)
#                     """
#                      Rebuilds the modules menu and checks the status of each module every 2000 ms. This is a workaround for bug #4096
#                     """
#                     # This function is called by the modules menu.
#                     # print(module.text(), alive)
# # Check if the action is alive.
#
#             # TODO: Do it in a better way, singleShot isn't pretty...
#             QtCore.QTimer.singleShot(2000, rebuild_modules_menu)
#
#         QtCore.QTimer.singleShot(2000, rebuild_modules_menu)

        def check_module_status() -> None:
            unexpected_exits = self.manager.get_unexpected_stops()
            if unexpected_exits:
                for module in unexpected_exits:
                    show_module_failed_dialog(module)
                    module.stop()
            """
            Check if any modules failed to stop. This is called by QApplication. __exit__ and should be ignored if you don't want to exit the application
            
            
            @return None or a list of
            """

            # If any module has been unexpected.
            # TODO: Do it in a better way, singleShot isn't pretty...
            # This function will show the module failed dialog.
            # QtCore.QTimer.singleShot(2000, rebuild_modules_menu)

        QtCore.QTimer.singleShot(2000, check_module_status)

    def _build_modulemenu(self, moduleMenu: QMenu) -> None:
        moduleMenu.clear()

        def add_module_menuitem(module: Module) -> None:
            title = module.name
            ac = moduleMenu.addAction(title, lambda: module.toggle(self.testing))
            """
            Build and add module menu items to the given menu. This is called by QMenu. add_menu () and should not be called directly.
            
            @param moduleMenu - The menu to add items to. It is cleared before adding items.
            
            @return The menu that was passed in as an argument or None if there was no menu to add items to
            """

            ac.setData(module)
            ac.setCheckable(True)
            """
             Add a menu item to the module menu. This is used to toggle the status of a module when it is started or stopped
             
             @param module - The module to add to the menu
             
             @return The item that was added to the menubar ( if any ) or None if none was added
            """
            ac.setChecked(module.is_alive())

        for location, modules in [
            ("bundled", self.manager.modules_bundled),
            ("system", self.manager.modules_system),
        ]:
            header = moduleMenu.addAction(location)
            # Add a location menu item to the module menu.
            header.setEnabled(False)

            for module in sorted(modules, key=lambda m: m.name):
                add_module_menuitem(module)


def exit(manager: Manager) -> None:
    # Add menu items for each module in modules sorted by name.
    # TODO: Do cleanup actions
    # TODO: Save state for resume
    print("Shutdown initiated, stopping all services...")
    manager.stop_all()
    # Terminate entire process group, just in case.
    """
     Shuts down the application. This is a wrapper around QApplication. stop_all () and terminates the entire process group in case of SIGINT.
     
     @param manager - The manager to stop. This must be passed as an argument to this
    """
    # os.killpg(0, signal.SIGINT)

    QApplication.quit()


def run(manager: Manager, testing: bool = False) -> Any:
    logger.info("Creating trayicon...")
    # print(QIcon.themeSearchPaths())

    app = QApplication(sys.argv)

    """
     Creates trayicon and returns it. This is the entry point for the application. It should be called from the command line and not directly from the program
     
     @param manager - The manager to use for the application
     @param testing - If True will run tests instead of production
     
     @return The result of the application or None if there was an error. If testing is True it will return the error
    """
    # This is needed for the icons to get picked up with PyInstaller
    scriptdir = Path(__file__).parent

    # When run from source:
    #   __file__ is sd_qt/trayicon.py
    #   scriptdir is ./sd_qt
    #   logodir is ./media/logo
    QtCore.QDir.addSearchPath("icons", str(scriptdir.parent / "media/logo/"))

    # When run from .app:
    #   __file__ is ./Contents/MacOS/sd-qt
    #   scriptdir is ./Contents/MacOS
    #   logodir is ./Contents/Resources/sd_qt/media/logo
    QtCore.QDir.addSearchPath(
        "icons", str(scriptdir.parent.parent / "Resources/sd_qt/media/logo/")
    )

    # logger.info(f"search paths: {QtCore.QDir.searchPaths('icons')}")

    # Without this, Ctrl+C will have no effect
    signal.signal(signal.SIGINT, lambda *args: exit(manager))
    # Ensure cleanup happens on SIGTERM
    signal.signal(signal.SIGTERM, lambda *args: exit(manager))

    timer = QtCore.QTimer()
    timer.start(100)  # You may change this if you wish.
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    # root widget
    widget = QWidget()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            widget,
            "Systray",
            "I couldn't detect any system tray on this system. Either get one or run the ActivityWatch modules from the console.",
        # Check if system tray is available on this system.
        )
        sys.exit(1)

    if sys.platform == "darwin":
        icon = QIcon("icons:logo.ico")
        # Allow macOS to use filters for changing the icon's color
        icon.setIsMask(True)
    else:
        # This function returns a QIcon object that can be used to display the icon.
        icon = QIcon("icons:logo.png")
    def periodic_check():
        check_user_switch(manager)


    if sys.platform == "win32":
        import win32com.client
        """
         Periodically check user switch. This is run every 10 minutes to avoid running a cron job that is too long
        """
        user_switch_timer = QtCore.QTimer()
        user_switch_timer.timeout.connect(periodic_check)
        user_switch_timer.start(10000)
# This function is used to start the user switch timer.


    trayIcon = TrayIcon(manager, icon, widget, testing=testing)
    trayIcon.show()

    QApplication.setQuitOnLastWindowClosed(False)

    logger.info("Initialized sd-qt and trayicon successfully")
    # Run the application, blocks until quit
    return app.exec()
