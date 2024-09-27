from logging import exception
from typing import Optional

import os
import time

import win32gui
import win32api
import win32process
from pywinauto import Application

def get_app_path(hwnd) -> Optional[str]:
    """
     Get path to application. This is used to find the path to the application on the host machine.
     
     @param hwnd - HWND of the application. If you want to get the path to the main application use L { get_main_window }.
     
     @return Path to the application on the host machine or None if not found. Note that it may be different from the path that was passed to L { get_main_window }
    """
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
    """
     Get name of application. This is the same as : func : ` get_app_path ` but returns the basename rather than the full path
     
     @param hwnd - HWND to get application name for
     
     @return Application name or None if not found or cannot be determined ( in which case None is returned ) Note that it is possible to get application name from different locations
    """
    """Get application filename given hwnd."""
    path = get_app_path(hwnd)

    # Returns the path to the file or None if the path is None.
    if path is None:
        return None

    return os.path.basename(path)

def get_window_title(hwnd):
    """
     Get the title of a window. This is useful for displaying a window title in dialogs that are displayed on top of the main window.
     
     @param hwnd - HWND of the window to get the title of.
     
     @return A string containing the title of the window or None if there is no title associated with the window or if the window does not exist
    """
    return win32gui.GetWindowText(hwnd)

def get_active_window_handle():
    """
     Get the handle of the currently active window. This is useful for checking if there is an active window and if it's the case we need to do some cleanup on the process
     
     
     @return a handle or None if no
    """
    hwnd = win32gui.GetForegroundWindow()
    return hwnd

def get_current_tab_info_by_handle(handle) -> str:
    """
    Get current tab's address and search bar by handle. This is useful for debugging purposes. If you want to know the location of a tab use get_current_tab_info_by_handle ( handle )
    
    @param handle - handle of the tab to search for. It must be opened in the application
    
    @return url of the tab
    """

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
    """
     Get information about the current tab. This is a helper function to get the URL and browser name for the current tab
     
     @param browser_exe - The name of the browser
     @param handle - The handle of the tab
     
     @return The URL or None if not able to get the information ( not possible in Uia ) or the
    """
    try:
        app = Application(backend='uia')
        # Capitalize the first letter and remove .exe
        browser_name = browser_exe.capitalize().replace(".exe", "")
        app.connect(handle=handle)

        # Define the address bar labels for different browsers
        address_bar_labels = {
            "Vivaldi": "Search or enter an address",
            "Firefox": "Search with Google or enter address",
            "Opera": "Enter search or web address",
            "Chrome": "Address and search bar"
        }

        # Get the appropriate address bar label for the browser
        element_name = address_bar_labels.get(browser_name, "App bar")

        dlg = app.top_window()
        # Get the URL of the Edit button.
        if not "msedge" in browser_exe:
            url = dlg.child_window(title=element_name, control_type="Edit").get_value()
            return url

    except Exception as e:
        return None




# This function is called from the main loop.
if __name__ == "__main__":
    # This function is used to wait for the active window handle to be displayed.
    while True:
        hwnd = get_active_window_handle()
        print("Title:", get_window_title(hwnd))
        print("App:", get_app_name(hwnd))
        time.sleep(1.0)