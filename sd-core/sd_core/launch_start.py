import os
import subprocess
import sys


if sys.platform == "win32":
    import winreg

if sys.platform == "win32":
    file_path = os.path.abspath(__file__)
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    app_path = os.path.join(_module_dir, 'sd-qt.exe')
if sys.platform == "darwin":
    app_path = "/Applications/TTim.app"
    app_name = "TTim"


def launch_app():
    cmd = f"osascript -e 'tell application \"System Events\" to make login item at end with properties {{path:\"{app_path}\", hidden:false}}'"
    subprocess.run(cmd, shell=True)


def delete_launch_app():
    cmd = f"osascript -e 'tell application \"System Events\" to delete login item \"{app_name}\"'"
    subprocess.run(cmd, shell=True)


def get_login_items():
    data = []
    cmd = "osascript -e 'tell application \"System Events\" to get the name of every login item'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    data = result.stdout.strip().split(", ")
    if "TTim" in data:
        return True
    return False


def check_startup_status():
    if sys.platform == "darwin":
        return get_login_items()
    elif sys.platform == "win32":
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        with winreg.OpenKey(
                key=winreg.HKEY_CURRENT_USER,
                sub_key=key_path,
                reserved=0,
                access=winreg.KEY_READ,
        ) as key:
            try:
                value, _ = winreg.QueryValueEx(key, "TTim")
                return True
            except FileNotFoundError:
                return False


    # Windows

def set_autostart_registry(autostart: bool = True) -> bool:
    """
    Create/update/delete Windows autostart registry key

    :param app_name:    A string containing the name of the application
    :param app_path:    A string specifying the application path
    :param autostart:   True - create/update autostart key / False - delete autostart key
    :return:            True - Success / False - Error, app name doesn't exist
    """
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    with winreg.OpenKey(
            key=winreg.HKEY_CURRENT_USER,
            sub_key=key_path,
            reserved=0,
            access=winreg.KEY_ALL_ACCESS,
    ) as key:
        try:
            if autostart:
                winreg.SetValueEx(key, "TTim", 0, winreg.REG_SZ, app_path)
            else:
                winreg.DeleteValue(key, "TTim")
        except OSError:
            return False
    return True
