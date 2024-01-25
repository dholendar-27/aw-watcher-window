import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from time import sleep

from aw_client import ActivityWatchClient
from aw_core.log import setup_logging
from aw_core.models import Event

from .config import parse_args
from .exceptions import FatalError
from .lib import get_current_window
from .macos_permissions import background_ensure_permissions

logger = logging.getLogger(__name__)

# run with LOG_LEVEL=DEBUG
log_level = os.environ.get("LOG_LEVEL")
# Set the log level to the current log level.
if log_level:
    logger.setLevel(logging.__getattribute__(log_level.upper()))


def kill_process(pid):
    """
     Kill a process by PID. This is a wrapper around os. kill that doesn't raise ProcessLookupError

     @param pid - PID of the process to
    """
    logger.info("Killing process {}".format(pid))
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.info("Process {} already dead".format(pid))


def main():
    """
     Main function for aw - watcher. Creates a bucket and waits for it to start. This is a blocking call
    """
    args = parse_args()

    # Raise an exception if DISPLAY environment variable is not set.
    if sys.platform.startswith("linux") and (
        "DISPLAY" not in os.environ or not os.environ["DISPLAY"]
    ):
        raise Exception("DISPLAY environment variable not set")

    setup_logging(
        name="aw-watcher-window",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )

    # Ensure permissions are available on the system.
    if sys.platform == "darwin":
        background_ensure_permissions()

    client = ActivityWatchClient(
        "aw-watcher-window", host=args.host, port=args.port, testing=args.testing
    )

    bucket_id = f"{client.client_name}"
    event_type = "currentwindow"

    client.create_bucket(bucket_id, event_type, queued=True)

    logger.info("aw-watcher-window started")

    sleep(1)  # wait for server to start
    with client:
        # This function is called by the swift strategy.
        if sys.platform == "darwin" and args.strategy == "swift":
            logger.info("Using swift strategy, calling out to swift binary")
            binpath = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "aw-watcher-window-macos"
            )

            try:
                p = subprocess.Popen(
                    [
                        binpath,
                        client.server_address,
                        bucket_id,
                        client.client_hostname,
                        client.client_name,
                    ]
                )
                # terminate swift process when this process dies
                signal.signal(signal.SIGTERM, lambda *_: kill_process(p.pid))
                p.wait()
            except KeyboardInterrupt:
                print("KeyboardInterrupt")
                kill_process(p.pid)
        else:
            heartbeat_loop(
                client,
                bucket_id,
                poll_time=args.poll_time,
                strategy=args.strategy,
                exclude_title=args.exclude_title,
            )


def heartbeat_loop(client, bucket_id, poll_time, strategy, exclude_title=False):
    """
     This is the heart of the activity watch. It polls the bucket_id every poll_time until it is stopped.

     @param client - The client to use for communication
     @param bucket_id - The id of the bucket to watch
     @param poll_time - The time to poll for changes in the bucket
     @param strategy - The strategy to use for the window ( s )
     @param exclude_title - If True the title will not be
    """
    # This function is a loop that loops over all the buckets and creates a new window and then polls the window.
    while True:
        # buckets = client.get_buckets()
        # if(buckets.get(bucket_id) is None):
        #     eventtype = "currentwindow"
        #     client.create_bucket_if_not_exist(bucket_id, eventtype)
        # else:
        # If parent process is running
        if os.getppid() == 1:
            logger.info("window-watcher stopped because parent process died")
            break

        current_window = None
        try:
            current_window = get_current_window(strategy)
            logger.debug(current_window)
        except (FatalError, OSError):
            # Fatal exceptions should quit the program
            try:
                logger.exception("Fatal error, stopping")
            except OSError:
                pass
            break
        except Exception:
            # Non-fatal exceptions should be logged
            try:
                # If stdout has been closed, this exception-print can cause (I think)
                #   OSError: [Errno 5] Input/output error
                # See: https://github.com/ActivityWatch/activitywatch/issues/756#issue-1296352264
                #
                # However, I'm unable to reproduce the OSError in a test (where I close stdout before logging),
                # so I'm in uncharted waters here... but this solution should work.
                logger.exception("Exception thrown while trying to get active window")
            except OSError:
                break

        # Fetch the next poll. If the window is not yet available on the next poll it will be ignored.
        if current_window is None:
            logger.debug("Unable to fetch window, trying again on next poll")
        else:
            # If exclude_title is set to excluded
            if exclude_title:
                current_window["title"] = "excluded"

            now = datetime.now(timezone.utc)
            current_window_event = Event(timestamp=now, data=current_window)

            # Set pulsetime to 1 second more than the poll_time
            # This since the loop takes more time than poll_time
            # due to sleep(poll_time).
            client.heartbeat(
                bucket_id, current_window_event, pulsetime=poll_time + 119.0, queued=True
            )

        sleep(poll_time)
