import logging
import os
import platform
from datetime import datetime, timedelta, timezone
from time import sleep

from sd_client import ActivityWatchClient
from sd_core.models import Event

from .config import load_config

system = platform.system()

# This function is used to handle the platform specific functionality.
if system == "Windows":
    # noreorder
    from .windows import seconds_since_last_input  # fmt: skip
elif system == "Darwin":
    # noreorder
    from .macos import seconds_since_last_input  # fmt: skip
elif system == "Linux":
    # noreorder
    from .unix import seconds_since_last_input  # fmt: skip
else:
    raise Exception(f"Unsupported platform: {system}")


logger = logging.getLogger(__name__)
td1ms = timedelta(milliseconds=1)


class Settings:
    def __init__(self, config_section, timeout=None, poll_time=None):
        """
         Initialize the class with values from config section. This is called by __init__ and should not be called directly

         @param config_section - section from which to read configuration
         @param timeout - timeout in seconds to wait for input activity to arrive
         @param poll_time - time in seconds to wait for input activity
        """
        # Time without input before we're considering the user as AFK
        self.timeout = timeout or config_section["timeout"]
        # How often we should poll for input activity
        self.poll_time = poll_time or config_section["poll_time"]

        assert self.timeout >= self.poll_time


class AFKWatcher:
    def __init__(self, args, testing=False):
        """
         Initialize the object by reading settings from config. py and instantiating the ActivityWatchClient. This is called by __init__ and should not be called directly

         @param args - Arguments passed to the command
         @param testing - Whether or not we are testing ( default False
        """
        # Read settings from config
        self.settings = Settings(
            load_config(testing), timeout=args.timeout, poll_time=args.poll_time
        )

        self.client = ActivityWatchClient(
            "sd-watcher-afk", host=args.host, port=args.port, testing=testing
        )
        self.bucketname = "{}".format(
            self.client.client_name
        )

    def ping(self, afk: bool, timestamp: datetime, duration: float = 0):
        """
         Send a heartbeat to the bucket. This is used to determine if we are up or down. If afk is True the event will be marked as " AFK " otherwise it's " NOT - AFK ".

         @param afk - True if the event is an AFE
         @param timestamp - Unix timestamp of the event
         @param duration - Time in seconds to wait before sending the event
        """
        data = {"status": "afk" if afk else "not-afk", "app" : "afk", "title" : "Idle time"}
        e = Event(timestamp=timestamp, duration=duration, data=data)
        pulsetime = self.settings.timeout + self.settings.poll_time
        self.client.heartbeat(self.bucketname, e, pulsetime=pulsetime, queued=True)

    def run(self):
        """
         Start afk checking loop to check for changes in AFK bucket. This is called in a seperate thread
        """
        logger.info("sd-watcher-afk started")

        # Initialization
        sleep(1)

        eventtype = "afkstatus"
        self.client.create_bucket(self.bucketname, eventtype, queued=True)

        # Start afk checking loop
        with self.client:
            self.heartbeat_loop()

    def heartbeat_loop(self):
        """
         This is the heart of the process. It checks to see if AFK is running and if it is it will start the
        """
        afk = False
        # A loop that will wait for a new bucket to be created and send a heartbeat if the event is AFK or not.
        while True:
            try:
                # buckets = self.client.get_buckets()
                # if(buckets.get(self.bucketname) is None):
                #     eventtype = "afkstatus"
                #     self.client.create_bucket_if_not_exist(self.bucketname, eventtype)
                # else:
                # If the parent process is running on the current process.
                if system in ["Darwin", "Linux"] and os.getppid() == 1:
                    # TODO: This won't work with PyInstaller which starts a bootloader process which will become the parent.
                    #       There is a solution however.
                    #       See: https://github.com/ActivityWatch/sd-qt/issues/19#issuecomment-316741125
                    logger.info("afkwatcher stopped because parent process died")
                    break

                now = datetime.now(timezone.utc)
                seconds_since_input = seconds_since_last_input()
                last_input = now - timedelta(seconds=seconds_since_input)
                logger.debug(f"Seconds since last input: {seconds_since_input}")

                # print(f'afk status@{datetime.now()}: {afk} seconds_since_input: {seconds_since_input}')

                # If no longer AFK
                # Ping if the current event is AFK or Became AFK
                if afk and seconds_since_input < self.settings.timeout:
                    logger.info("No longer AFK")
                    self.ping(afk, timestamp=last_input)
                    afk = False
                    # ping with timestamp+1ms with the next event (to ensure the latest event gets retrieved by get_event)
                    self.ping(afk, timestamp=last_input + td1ms)
                # If becomes AFK
                elif not afk and seconds_since_input >= self.settings.timeout:
                    logger.info("Became AFK")
                    self.ping(afk, timestamp=last_input)
                    afk = True
                    # ping with timestamp+1ms with the next event (to ensure the latest event gets retrieved by get_event)
                    self.ping(
                        afk, timestamp=now
                    )
                # Send a heartbeat if no state change was made
                else:
                    # ping the current time and the last input
                    if afk:
                        self.ping(
                            afk, timestamp=now
                        )
                    else:
                        self.ping(afk, timestamp=last_input)

                sleep(self.settings.poll_time)

            except KeyboardInterrupt:
                logger.info("sd-watcher-afk stopped by keyboard interrupt")
                break
