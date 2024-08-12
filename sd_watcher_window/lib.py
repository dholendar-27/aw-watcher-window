import sys
from typing import Optional

from .exceptions import FatalError


def get_current_window_linux() -> Optional[dict]:
    """
     Get information about the current window on Linux. This is useful for debugging purposes. The return value is a dictionary with the following keys.
     
     
     @return A dictionary with the following keys. app : The class of the window. title : The window title
    """
    from . import xlib

    window = xlib.get_current_window()

    # Returns the class and name of the window.
    if window is None:
        cls = "unknown"
        name = "unknown"
    else:
        cls = xlib.get_window_class(window)
        name = xlib.get_window_name(window)

    return {"app": cls, "title": name}


def get_current_window_macos(strategy: str) -> Optional[dict]:
    """
     Get information about macOS. This is a wrapper around jxa / applescript to allow different behaviours to be run
     
     @param strategy - the name of the strategy
     
     @return a dictionary that contains the
    """
    # TODO should we use unknown when the title is blank like the other platforms?

    # `jxa` is the default & preferred strategy. It includes the url + incognito status
    # Returns information about the current platform.
    if strategy == "jxa":
        from . import macos_jxa

        return macos_jxa.getInfo()
    elif strategy == "applescript":
        from . import macos_applescript

        return macos_applescript.getInfo()
    else:
        raise FatalError(f"invalid strategy '{strategy}'")


def get_current_window_windows() -> Optional[dict]:
    """
     Get information about the currently active window. This is useful for debugging and to provide a way to know what kind of window we are working with.
     
     
     @return A dictionary with the following keys : app : The name of the application. title : The title of the window. url : The URL of the current tab
    """
    from . import windows

    window_handle = windows.get_active_window_handle()
    app = windows.get_app_name(window_handle)
    title = windows.get_window_title(window_handle)

    # Set the app to unknown.
    if app is None:
        app = "unknown"
    # Set title to unknown.
    if title is None:
        title = "unknown"

    # Returns a dictionary with app title url
    if "chrome" in app or "firefox" in app or "opera" in app:
        url = windows.get_current_tab_info(browser_exe=app.split("*")[0], handle=window_handle)
        return {"app": app, "title": title, "url": url}

    return {"app": app, "title": title}


def get_current_window(strategy: Optional[str] = None) -> Optional[dict]:
    """
     Get information about the current window. This is a wrapper around get_current_window_macos () for different platforms
     
     @param strategy - a string to be used as a strategy
     
     @return a dictionary with keys : window_id : the id of the
    """
    """
    :raises FatalError: if a fatal error occurs (e.g. unsupported platform, X server closed)
    """

    # Returns the current window for the current platform.
    if sys.platform.startswith("linux"):
        return get_current_window_linux()
    elif sys.platform == "darwin":
        # Raises FatalError if macOS strategy is not specified.
        if strategy is None:
            raise FatalError("macOS strategy not specified")
        return get_current_window_macos(strategy)
    elif sys.platform in ["win32", "cygwin"]:
        return get_current_window_windows()
    else:
        raise FatalError(f"Unknown platform: {sys.platform}")
