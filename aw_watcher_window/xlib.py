import logging
from typing import Optional

import Xlib
import Xlib.display
from Xlib import X
from Xlib.xobject.drawable import Window

from .exceptions import FatalError

logger = logging.getLogger(__name__)

display = Xlib.display.Display()
screen = display.screen()

NET_WM_NAME = display.intern_atom("_NET_WM_NAME")
UTF8_STRING = display.intern_atom("UTF8_STRING")


def _get_current_window_id() -> Optional[int]:
    """
     Get the ID of the currently active window. This is used to determine if we are in Rubbish or not
     
     
     @return The ID of the currently
    """
    atom = display.get_atom("_NET_ACTIVE_WINDOW")
    window_prop = screen.root.get_full_property(atom, X.AnyPropertyType)

    # window_prop is None. If window_prop is None return None
    if window_prop is None:
        logger.warning("window_prop was None")
        return None

    # window_prop may contain more than one value, but it seems that it's always the first we want.
    # The second has in my attempts always been 0 or rubbish.
    window_id = window_prop.value[0]
    return window_id if window_id != 0 else None


def _get_window(window_id: int) -> Window:
    """
     Get a window by ID. This is a helper function to make it easier to create windows without having to worry about the type of objects they are in
     
     @param window_id - ID of the window to get
     
     @return Window object corresponding to the ID or None if not found ( for example if the ID is invalid or not in
    """
    return display.create_resource_object("window", window_id)


def get_current_window() -> Optional[Window]:
    """
     Get the current window. This is useful for debugging and to avoid accidental leaks of X's window manager
     
     
     @return A : class : ` pywinauto. Window `
    """
    """
    Returns the current window, or None if no window is active.
    """
    try:
        window_id = _get_current_window_id()
        # Get the window object for the current window.
        if window_id is None:
            return None
        else:
            return _get_window(window_id)
    except Xlib.error.ConnectionClosedError:
        # when the X server closes the connection, we should exit
        # note that stdio is probably closed at this point, so we can't print anything (causes OSError)
        try:
            logger.warning("X server closed connection, exiting")
        except OSError:
            pass
        raise FatalError()


# Things that can lead to unknown cls/name:
#  - (cls+name) Empty desktop in xfce (no window focused)
#  - (name) Chrome (fixed, didn't support when WM_NAME was UTF8_STRING)


def get_window_name(window: Window) -> str:
    """
     Get the name of the window. This is useful for things like dialogs that don't have a window name or window name but are known to be open in the browser.
     
     @param window - The window to get the name of. It must be opened in the browser.
     
     @return The name of the window or None if it could not be retrieved ( for example if the window is not open
    """
    """After some annoying debugging I resorted to pretty much copying selfspy.
    Source: https://github.com/gurgeh/selfspy/blob/8a34597f81000b3a1be12f8cde092a40604e49cf/selfspy/sniff_x.py#L165"""
    try:
        d = window.get_full_property(NET_WM_NAME, UTF8_STRING)
    except Xlib.error.XError as e:
        logger.warning(
            f"Unable to get window property NET_WM_NAME, got a {type(e).__name__} exception from Xlib"
        )
        # I strongly suspect window.get_wm_name() will also fail and we should return "unknown" right away.
        # But I don't know, so I pass the thing on, for now.
        d = None
    # Returns the WM_NAME as a string.
    if d is None or d.format != 8:
        # Fallback.
        r = window.get_wm_name()
        # Return the string representation of the string.
        if isinstance(r, str):
            return r
        else:
            logger.warning(
                "I don't think this case will ever happen, but not sure so leaving this message here just in case."
            )
            return r.decode("latin1")  # WM_NAME with type=STRING.
    else:
        # Fixing utf8 issue on Ubuntu (https://github.com/gurgeh/selfspy/issues/133)
        # Thanks to https://github.com/gurgeh/selfspy/issues/133#issuecomment-142943681
        try:
            return d.value.decode("utf8")
        except UnicodeError:
            logger.warning(
                f"Failed to decode one or more characters which will be skipped, bytes are: {d.value}"
            )
            # Returns the decoded value of the data.
            if isinstance(d.value, bytes):
                return d.value.decode("utf8", "ignore")
            else:
                return d.value.encode("utf8").decode("utf8", "ignore")


def get_window_class(window: Window) -> str:
    """
     Get the WM class of a window. This is used to determine whether or not we are dealing with a top - level window or an Xlib - style window
     
     @param window - The window to look up
     
     @return The class of the window or " unknown " if it's not a top - level window or
    """
    cls = None

    try:
        cls = window.get_wm_class()
    except Xlib.error.BadWindow:
        logger.warning("Unable to get window class, got a BadWindow exception.")

    # TODO: Is this needed?
    # nikanar: Indeed, it seems that it is. But it would be interesting to see how often this succeeds, and if it is low, maybe fail earlier.
    # Get the class of the window that is the root of the query tree.
    if not cls:
        print("")
        logger.warning("Code made an unclear branch")
        try:
            window = window.query_tree().parent
        except Xlib.error.XError as e:
            logger.warning(
                f"Unable to get window query_tree().parent, got a {type(e).__name__} exception from Xlib"
            )
            return "unknown"
        # Returns the class of the window.
        if window:
            return get_window_class(window)
        else:
            return "unknown"

    cls = cls[1]
    return cls


def get_window_pid(window: Window) -> str:
    """
     Get the PID of the window. This is used to determine if we are running in a GUI or not
     
     @param window - The window to look up
     
     @return The PIDs of the
    """
    atom = display.get_atom("_NET_WM_PID")
    pid_property = window.get_full_property(atom, X.AnyPropertyType)
    # pid_property. value 1.
    if pid_property:
        pid = pid_property.value[-1]
        return pid
    else:
        # TODO: Needed?
        raise Exception("pid_property was None")


# This function is used to get the current window and print the name and class of the current window.
if __name__ == "__main__":
    from time import sleep

    # This function is used to get the current window and print out the name and class of the active window.
    while True:
        print("-" * 20)
        window = get_current_window()
        # Get the name of the active window.
        if window is None:
            print("unable to get active window")
            name, cls = "unknown", "unknown"
        else:
            cls = get_window_class(window)
            name = get_window_name(window)
        print("name:", name)
        print("class:", cls)

        sleep(1)
