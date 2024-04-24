import ctypes
import time
from ctypes import POINTER, WINFUNCTYPE, Structure  # type: ignore
from ctypes.wintypes import BOOL, DWORD, UINT


class LastInputInfo(Structure):
    _fields_ = [("cbSize", UINT), ("dwTime", DWORD)]


def _getLastInputTick() -> int:
    """
     Get the time in milliseconds since the last call to L { _setInputTick }. This is useful for detecting when to stop the input and to avoid timing issues in the middle of a program that is running on a Windows machine.
     
     
     @return The time in milliseconds since the last call to L { _setInputTick } or - 1 if there is no input
    """
    prototype = WINFUNCTYPE(BOOL, POINTER(LastInputInfo))
    paramflags = ((1, "lastinputinfo"),)
    c_GetLastInputInfo = prototype(("GetLastInputInfo", ctypes.windll.user32), paramflags)  # type: ignore

    lastinput = LastInputInfo()
    lastinput.cbSize = ctypes.sizeof(LastInputInfo)
    assert 0 != c_GetLastInputInfo(lastinput)
    return lastinput.dwTime


def _getTickCount() -> int:
    """
     Get the number of ticks since the last call to L { _setTickCount }. This is useful for checking if we are running in debug mode or not.
     
     
     @return The number of ticks since the last call to L { _setTickCount } or - 1 if there was an error
    """
    prototype = WINFUNCTYPE(DWORD)
    paramflags = ()
    c_GetTickCount = prototype(("GetTickCount", ctypes.windll.kernel32), paramflags)  # type: ignore
    return c_GetTickCount()


def seconds_since_last_input():
    """
     Returns the number of seconds since the last input was received. This is useful for measuring how long a user has interacted with the game in order to get the time spent in the input.
     
     
     @return The number of seconds since the last input was received as a floating point number in milli - seconds
    """
    seconds_since_input = (_getTickCount() - _getLastInputTick()) / 1000
    return seconds_since_input


# This function is called by the main script.
if __name__ == "__main__":
    # This function is a blocking call to print seconds_since_last_input
    while True:
        time.sleep(1)
        print(seconds_since_last_input())
