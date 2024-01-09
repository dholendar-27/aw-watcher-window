from logging import exception
from typing import Optional

import os
import time

import win32gui
import win32api
import win32process
from pywinauto import Application

def get_app_path(hwnd) -> Optional[str]:
    """Get application path given hwnd."""
    path = None

    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = win32api.OpenProcess(0x0400, False, pid) # PROCESS_QUERY_INFORMATION = 0x0400

    try:
        path = win32process.GetModuleFileNameEx(process, 0)
    finally:
        win32api.CloseHandle(process)

    return path

def get_app_name(hwnd) -> Optional[str]:
    """Get application filename given hwnd."""
    path = get_app_path(hwnd)

    if path is None:
        return None

    return os.path.basename(path)

def get_window_title(hwnd):
    return win32gui.GetWindowText(hwnd)

def get_active_window_handle():
    hwnd = win32gui.GetForegroundWindow()
    return hwnd

def get_current_tab_info_by_handle(handle) -> str:

    try:
        app = Application().connect(handle=handle)
        element_name="Address and search bar"
        dlg = app.top_window()
        url = dlg.child_window(title=element_name, control_type="Edit").get_value()
        return url
    except Exception as e:
        print(e)
        return None

def get_current_tab_info(browser_exe: str, handle: str) -> str:
    try:
        app = Application(backend='uia')
        # Capitalize the first letter and remove .exe
        browser_name = browser_exe.capitalize().replace(".exe", "")
        app.connect(handle=handle)

        # Define the address bar labels for different browsers
        address_bar_labels = {
            "Vivaldi": "Search or enter an address",
            "Firefox": "Search with Google or enter address",
            "Opera": "Address field",
            "Chrome": "Address and search bar"
        }

        # Get the appropriate address bar label for the browser
        element_name = address_bar_labels.get(browser_name, "App bar")

        dlg = app.top_window()
        if "msedge" in browser_exe:
            wrapper = dlg.child_window(title=element_name, control_type="ToolBar")
            url = wrapper.descendants(control_type='Edit')[0]
            return url.get_value()
        else:
            url = dlg.child_window(title=element_name, control_type="Edit").get_value()
            return url
    except Exception as e:
        return None




if __name__ == "__main__":
    while True:
        hwnd = get_active_window_handle()
        print("Title:", get_window_title(hwnd))
        print("App:", get_app_name(hwnd))
        time.sleep(1.0)