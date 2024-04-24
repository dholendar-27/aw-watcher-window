"""
Listeners for aggregated keyboard and mouse events.

This is used for AFK detection on Linux, as well as used in sd-watcher-input to track input activity in general.

NOTE: Logging usage should be commented out before committed, for performance reasons.
"""

import logging
import threading
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import Dict, Any

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class EventFactory(metaclass=ABCMeta):
    def __init__(self) -> None:
        """
         Initialize the object. This is called by __init__ and should not be called directly. Use this instead.
         
         
         @return An instance of : class : ` threading. Event ` or None if there is no event to start
        """
        self.new_event = threading.Event()
        self._reset_data()

    @abstractmethod
    def _reset_data(self) -> None:
        """
         Reset the event data to an empty dictionary. This is called when we have a new event to be sent to the event_data field of the model.
         
         
         @return True if successful False otherwise ( for testing purposes not to throw exceptions in this case ). Note that it is possible for the user to override this
        """
        self.event_data: Dict[str, Any] = {}

    def next_event(self) -> dict:
        """
         Returns the next event to be built and resets the internal state. This is a low - level method that should be called by subclasses to build the next event in the event queue.
         
         
         @return A dictionary containing the event data for the next event that can be used to build the next event or None if there are no more events
        """
        """Returns an event and prepares the internal state so that it can start to build a new event"""
        self.new_event.clear()
        data = self.event_data
        # self.logger.debug(f"Event: {data}")
        self._reset_data()
        return data

    def has_new_event(self) -> bool:
        """
         Check if there is a new event. This is a property to avoid having to re - read the event when it is read from the file.
         
         
         @return True if there is a new event False otherwise ( not set by the user ). Note that the event will be deleted after the user has finished reading
        """
        return self.new_event.is_set()


class KeyboardListener(EventFactory):
    def __init__(self):
        """
         Initialize the event factory and set the logger to the keyboard logger. This is called by __init__
        """
        EventFactory.__init__(self)
        self.logger = logger.getChild("keyboard")

    def start(self):
        """
         Start listening for keystrokes. This is called by pynput. main () and should not be called externally
        """
        from pynput import keyboard

        listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        listener.start()

    def _reset_data(self):
        """
         Reset data to default values before sending to event_handler. This is called when an event is received
        """
        self.event_data = {"presses": 0}

    def on_press(self, key):
        """
         Callback for key press events. Increments the count of presses and sets the new event.
         
         @param key - The key that was pressed ( int ). This is used to determine whether or not the event was handled
        """
        # self.logger.debug(f"Press: {key}")
        self.event_data["presses"] += 1
        self.new_event.set()

    def on_release(self, key):
        """
         Callback for key release. It is called when user releases a key on the window. The key is passed to this callback as a parameter
         
         @param key - Key that was released
        """
        # Don't count releases, only clicks
        # self.logger.debug(f"Release: {key}")
        pass


class MouseListener(EventFactory):
    def __init__(self):
        """
         Initialize the event factory and its logger. This is called by __init__ and should not be called directly
        """
        EventFactory.__init__(self)
        self.logger = logger.getChild("mouse")
        self.pos = None

    def _reset_data(self):
        """
         Reset data to default values. This is called when the user clicks outside the window or scrolls out
        """
        self.event_data = defaultdict(int)
        self.event_data.update(
            {"clicks": 0, "deltaX": 0, "deltaY": 0, "scrollX": 0, "scrollY": 0}
        )

    def start(self):
        """
         Start listening for mouse events. This is called by pynput. main () and should not be called externally
        """
        from pynput import mouse

        listener = mouse.Listener(
            on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll
        )
        listener.start()

    def on_move(self, x, y):
        """
         Called when the mouse is moved. This is a callback for the event_loop and should be used as a place holder
         
         @param x - x coordinate of the mouse
         @param y - y coordinate of the mouse ( relative to parent
        """
        newpos = (x, y)
        # self.logger.debug("Moved mouse to: {},{}".format(x, y))
        # Set the current position to the new position.
        if not self.pos:
            self.pos = newpos

        delta = tuple(self.pos[i] - newpos[i] for i in range(2))
        self.event_data["deltaX"] += abs(delta[0])
        self.event_data["deltaY"] += abs(delta[1])

        self.pos = newpos
        self.new_event.set()

    def on_click(self, x, y, button, down):
        """
         Callback for click events. This is called when a mouse button is pressed or released. The event is stored in : attr : ` new_event `
         
         @param x - The x coordinate of the click
         @param y - The y coordinate of the click
         @param button - The button pressed ( 0 = left 1 = right )
         @param down - True if the click was released False if it was
        """
        # self.logger.debug(f"Click: {button} at {(x, y)}")
        # Only count presses, not releases
        # Add click to the new event
        if down:
            self.event_data["clicks"] += 1
            self.new_event.set()

    def on_scroll(self, x, y, scrollx, scrolly):
        """
         Called when the user scrolls. This is a callback from pygame. py to allow the user to update the state of the game on scroll
         
         @param x - The x coordinate of the scroll
         @param y - The y coordinate of the scroll
         @param scrollx - The amount of scroll in the x direction
         @param scrolly - The amount of scroll in the y
        """
        # self.logger.debug(f"Scroll: {scrollx}, {scrolly} at {(x, y)}")
        self.event_data["scrollX"] += abs(scrollx)
        self.event_data["scrollY"] += abs(scrolly)
        self.new_event.set()
