from Quartz.CoreGraphics import (CGEventSourceSecondsSinceLastEventType,
                                 kCGEventSourceStateHIDSystemState,
                                 kCGAnyInputEventType)


def seconds_since_last_input() -> float:
    """
     Return the number of seconds since the last input event. This is used to determine when to stop the event loop and not to detect a situation where an application is shutting down.
     
     
     @return The number of seconds since the last input event ( 0. 0 - 1. 0 ) in nan
    """
    return CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateHIDSystemState, kCGAnyInputEventType)


# Print the time since last input.
if __name__ == "__main__":
    from time import sleep
    # Sleeps for a time to be run
    while True:
        sleep(1)
        print(seconds_since_last_input())
