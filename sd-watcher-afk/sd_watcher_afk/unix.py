import logging
from datetime import datetime
from time import sleep

from .listeners import KeyboardListener, MouseListener


class LastInputUnix:
    def __init__(self):
        """
         Initialize the class. This is called by __init__ and should not be called directly by user code
        """
        self.logger = logging.getLogger(__name__)
        # self.logger.setLevel(logging.DEBUG)

        self.mouseListener = MouseListener()
        self.mouseListener.start()

        self.keyboardListener = KeyboardListener()
        self.keyboardListener.start()

        self.last_activity = datetime.now()

    def seconds_since_last_input(self) -> float:
        """
         Get / Clear events since last input. This is useful for determining how long the user has interacted with the input window in seconds.
         
         
         @return The number of seconds since last input was received or 0 if there was no input to the window in
        """
        # TODO: This has a delay of however often it is called.
        #       Could be solved by creating a custom listener.
        now = datetime.now()
        # Get and clear events for the mouse and keyboard events.
        if self.mouseListener.has_new_event() or self.keyboardListener.has_new_event():
            self.logger.debug("New event")
            self.last_activity = now
            # Get/clear events
            self.mouseListener.next_event()
            self.keyboardListener.next_event()
        return (now - self.last_activity).total_seconds()


_last_input_unix = None


def seconds_since_last_input():
    """
     Returns the number of seconds since the last input. This is useful for debugging purposes. If you want to check how long a user has entered something in the past use seconds_since_last_input ( 0 ).
     
     
     @return The number of seconds since the last input or None if there was no input in the past or the user hasn't interacted with
    """
    global _last_input_unix

    # Set the last input unix timestamp.
    if _last_input_unix is None:
        _last_input_unix = LastInputUnix()

    return _last_input_unix.seconds_since_last_input()


# This function is called by the main module.
if __name__ == "__main__":
    # Sleeps for a time to be run
    while True:
        sleep(1)
        print(seconds_since_last_input())
