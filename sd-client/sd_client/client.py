import functools
import json
import logging
import os
import socket
import threading
from collections import namedtuple
from datetime import datetime
from time import sleep
from sd_core.cache import *
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)
from sd_core.util import load_key
import jwt
import keyring
from .persistqueue import SQLiteQueue
import requests as req
from sd_core.dirs import get_data_dir
from sd_core.models import Event
from sd_transform.heartbeats import heartbeat_merge
from .persistqueue.exceptions import Empty
from .config import load_config
from .singleinstance import SingleInstance

# FIXME: This line is probably badly placed
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _log_request_exception(e: req.RequestException):
    """
     Log exception that occurred during request. This is a helper to avoid logging the exception in production
     
     @param e - exception that occurred during
    """
    logger.warning(str(e))
    try:
        d = e.response.json() if e.response else None
        logger.warning(f"Error message received: {d}")
    except json.JSONDecodeError:
        pass


def _dt_is_tzaware(dt: datetime) -> bool:
    """
     Check if a datetime is timezone aware. This is used to determine if we are dealing with time zones that aren't in the timezone - aware form ( as opposed to local time )
     
     @param dt - The datetime to check.
     
     @return True if the datetime is timezone aware False otherwise. >>> datetime. tzinfo ( datetime. utcnow ()
    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def always_raise_for_request_errors(f: Callable[..., req.Response]):
    """
     Decorator that ensures that requests. Response. raise_for_status is called even if there are errors.
     
     @param f - the function to be decorated. This is a function that takes a request and returns a : class : ` req. Response `.
     
     @return the result of f ( which may or may not be the same
    """
    @functools.wraps(f)
    def g(*args, **kwargs):
        """
         Wrapper around request. get that catches exceptions and rethrows them. This is useful for things like getting a file or uploading a file to S3.
         
         
         @return The result of the request wrapped in a Request object
        """
        r = f(*args, **kwargs)
        try:
            r.raise_for_status()
        except req.RequestException as e:
            _log_request_exception(e)
            raise e
        return r

    return g

def _generate_token():
    """
     Generate a token to be used for authenticating with TTim. This is a wrapper around jwt. encode which returns a JSON Web Token instead of a string.
     
     
     @return JWT or None if there is no token to be
    """
    cache_key = "TTim"
    cached_credentials = cache_user_credentials(cache_key,"SD_KEYS")
    # Returns a JWT encoded string with the cached credentials.
    if cached_credentials:
        user_key = cached_credentials.get("user_key")
        # Returns the JWT encoded user_key or None if user_key is not set.
        if user_key:
            return jwt.encode({"user": "watcher", "email": cached_credentials.get("email"),
                                            "phone": cached_credentials.get("phone")}, user_key, algorithm="HS256")
        else: return None


class ActivityWatchClient:
    def __init__(
            self,
            client_name: str = "unknown",
            testing=False,
            host=None,
            port=None,
            protocol="http",
    ) -> None:
        """
        A handy wrapper around the sd-server REST API. The recommended way of interacting with the server.

        Can be used with a `with`-statement as an alternative to manually calling connect and disconnect in a try-finally clause.

        :Example:

        .. literalinclude:: examples/client.py
            :lines: 7-
        """
        self.testing = testing

        self.client_name = client_name
        self.client_hostname = socket.gethostname()

        _config = load_config()
        server_config = _config["server" if not testing else "server-testing"]
        client_config = _config["client" if not testing else "client-testing"]

        server_host = host or server_config["hostname"]
        server_port = port or server_config["port"]
        self.server_address = "{protocol}://{host}:{port}".format(
            protocol=protocol, host=server_host, port=server_port
        )

        self.instance = SingleInstance(
            f"{self.client_name}-at-{server_host}-on-{server_port}"
        )

        self.commit_interval = client_config["commit_interval"]

        self.request_queue = RequestQueue(self)
        # Dict of each last heartbeat in each bucket
        self.last_heartbeat = {}  # type: Dict[str, Event]

    #
    #   Get/Post base requests
    #

    def _url(self, endpoint: str):
        """
         Generate URL for API. This is used to generate API URLs for an API that does not require authentication
         
         @param endpoint - Endpoint to generate URL for
         
         @return Full URL for API with server_address and api
        """
        return f"{self.server_address}/api/0/{endpoint}"

    @always_raise_for_request_errors
    def _get(self, endpoint: str, params: Optional[dict] = None) -> req.Response:
        """
         Make a GET request to Cobbler and return the response. This is a helper for getting data from the Cobbler API
         
         @param endpoint - The endpoint to send the request to
         @param params - A dictionary of key value pairs to send with the request
         
         @return A : class : ` Response ` object that can be used to inspect the
        """
        headers = {"Content-type": "application/json", "charset": "utf-8", "Authorization" : _generate_token()}
        return req.get(self._url(endpoint), params=params, headers=headers)

    @always_raise_for_request_errors
    def _post(
            self,
            endpoint: str,
            data: Union[List[Any], Dict[str, Any]],
            params: Optional[dict] = None,
    ) -> req.Response:
        """
             Send a POST request to the API. This is a helper for : meth : ` _get ` and
             
             @param endpoint - The endpoint to send the request to.
             @param data - The data to send in the request. Can be a list of dicts or a single dict.
             @param params - A dictionary of key / value pairs that will be included in the request's query string.
             
             @return The response from the server or None if something went wrong
        """
        headers = {"Content-type": "application/json", "charset": "utf-8", "Authorization" : _generate_token()}
        return req.post(
            self._url(endpoint),
            data=bytes(json.dumps(data), "utf8"),
            headers=headers,
            params=params,
        )

    @always_raise_for_request_errors
    def _delete(self, endpoint: str, data: Any = dict()) -> req.Response:
        """
         Send a DELETE request to Cobbler. This is a helper method for : meth : ` delete_and_recover `.
         
         @param endpoint - The endpoint to send the request to. E. g.
         @param data - The data to send as the body of the request.
         
         @return A : class : ` req. Response ` object
        """
        headers = {"Content-type": "application/json", "Authorization" : _generate_token()}
        return req.delete(self._url(endpoint), data=json.dumps(data), headers=headers)

    def get_info(self):
        """
         Get information about the test. This is a GET request to the / v1 / info endpoint.
         
         
         @return A dict containing the hostname and test data for the
        """
        """Returns a dict currently containing the keys 'hostname' and 'testing'."""
        endpoint = "info"
        headers = {"Content-type": "application/json", "charset": "utf-8", "Authorization" : _generate_token()}
        return self._get(endpoint,headers=headers).json()

    #
    #   Event get/post requests
    #

    def get_event(
            self,
            bucket_id: str,
            event_id: int,
    ) -> Optional[Event]:
        """
             Get an event by bucket and event id. This is a low - level method to retrieve an event from the API.
             
             @param bucket_id - The ID of the bucket. Must be unique.
             @param event_id - The ID of the event. Must be unique.
             
             @return The event or None if not found. Raises APIError if there is a problem
        """
        endpoint = f"buckets/{bucket_id}/events/{event_id}"
        try:
            event = self._get(endpoint).json()
            return Event(**event)
        except req.exceptions.HTTPError as e:
            # If the response is not a 404 return None.
            if e.response and e.response.status_code == 404:
                return None
            else:
                raise

    def get_events(
            self,
            bucket_id: str,
            limit: int = -1,
            start: Optional[datetime] = None,
            end: Optional[datetime] = None,
    ) -> List[Event]:
        """
             Get events associated with a bucket. This is a low - level method for getting events from an S3 bucket.
             
             @param bucket_id - The ID of the bucket to retrieve events from.
             @param limit - The maximum number of events to return. Defaults to - 1 which returns all events.
             @param start - The start date for events to retrieve. Defaults to the current date.
             @param end - The end date for events to retrieve. Defaults to the current date.
             
             @return A list of : class : ` Event ` objects
        """
        endpoint = f"buckets/{bucket_id}/events"

        params = dict()  # type: Dict[str, str]
        # Set the limit parameter.
        if limit is not None:
            params["limit"] = str(limit)
        # Set the start date in ISO 8601 format.
        if start is not None:
            params["start"] = start.isoformat()
        # Set the end of the output.
        if end is not None:
            params["end"] = end.isoformat()

        events = self._get(endpoint, params=params).json()
        return [Event(**event) for event in events]

    def insert_event(self, bucket_id: str, event: Event) -> None:
        """
         Insert an event into a bucket. This is a convenience method for inserting an event into a bucket.
         
         @param bucket_id - The ID of the bucket to insert the event into.
         @param event - The event to insert. Must be serializable to JSON
        """
        endpoint = f"buckets/{bucket_id}/events"
        data = [event.to_json_dict()]
        self._post(endpoint, data)

    def insert_events(self, bucket_id: str, events: List[Event]) -> None:
        """
         Insert events into a bucket. This is a convenience method for making POST requests to the ` / buckets / { bucket_id } / events ` endpoint.
         
         @param bucket_id - The ID of the bucket to insert into.
         @param events - A list of : class : ` Event ` objects to insert.
         
         @return The response from the server or None if something goes wrong
        """
        endpoint = f"buckets/{bucket_id}/events"
        data = [event.to_json_dict() for event in events]
        self._post(endpoint, data)

    def delete_event(self, bucket_id: str, event_id: int) -> None:
        """
         Delete an event from a bucket. This is equivalent to calling : meth : ` delete_event_from_bucket ` followed by
         
         @param bucket_id - ID of bucket to delete event from
         @param event_id - ID of event to delete
         
         @return True if successful False if not ( exception raised from requests library
        """
        endpoint = f"buckets/{bucket_id}/events/{event_id}"
        self._delete(endpoint)

    def get_eventcount(
            self,
            bucket_id: str,
            limit: int = -1,
            start: Optional[datetime] = None,
            end: Optional[datetime] = None,
    ) -> int:
        """
             Get number of events in a bucket. This is useful for determining how many events have been added since the last check and so on
             
             @param bucket_id - The ID of the bucket to query
             @param limit - The maximum number of events to return - 1 for unlimited
             @param start - The start date for the time range in ISO 8601 format
             @param end - The end date for the time range in ISO 8601 format
             
             @return The number of events in the bucket between start and
            """
        endpoint = f"buckets/{bucket_id}/events/count"

        params = dict()  # type: Dict[str, str]
        # Set the start date in ISO 8601 format.
        if start is not None:
            params["start"] = start.isoformat()
        # Set the end of the output.
        if end is not None:
            params["end"] = end.isoformat()

        response = self._get(endpoint, params=params)
        return int(response.text)

    def heartbeat(
            self,
            bucket_id: str,
            event: Event,
            pulsetime: float,
            queued: bool = False,
            commit_interval: Optional[float] = None,
    ) -> None:
        """
        Args:
            bucket_id: The bucket_id of the bucket to send the heartbeat to
            event: The actual heartbeat event
            pulsetime: The maximum amount of time in seconds since the last heartbeat to be merged with the previous heartbeat in sd-server
            queued: Use the sd-client queue feature to queue events if client loses connection with the server
            commit_interval: Override default pre-merge commit interval

        NOTE: This endpoint can use the failed requests retry queue.
              This makes the request itself non-blocking and therefore
              the function will in that case always returns None.
        """

        endpoint = f"buckets/{bucket_id}/heartbeat?pulsetime={pulsetime}"
        _commit_interval = commit_interval or self.commit_interval

        if queued:
            # Pre-merge heartbeats
            if bucket_id not in self.last_heartbeat:
                self.last_heartbeat[bucket_id] = event
                return None

            last_heartbeat = self.last_heartbeat[bucket_id]

            merge = heartbeat_merge(last_heartbeat, event, pulsetime)

            if merge:
                # If last_heartbeat becomes longer than commit_interval
                # then commit, else cache merged.
                diff = (last_heartbeat.duration).total_seconds()
                if diff >= _commit_interval:
                    data = merge.to_json_dict()
                    self.request_queue.add_request(endpoint, data)
                    self.last_heartbeat[bucket_id] = event
                else:
                    self.last_heartbeat[bucket_id] = merge
            else:
                data = last_heartbeat.to_json_dict()
                self.request_queue.add_request(endpoint, data)
                self.last_heartbeat[bucket_id] = event
        else:
            self._post(endpoint, event.to_json_dict())

    #
    #   Bucket get/post requests
    #

    def get_buckets(self) -> dict:
        """
         Get list of buckets. This is a GET request to the ` ` / buckets ` ` endpoint.
         
         
         @return ` ` dict ` ` with bucket information. code - block ::
        """
        return self._get("buckets/").json()

    def create_bucket_if_not_exist(self, bucket_id: str, event_type: str):
        """
         Create a bucket if it does not exist. This is a blocking call and will return immediately
         
         @param bucket_id - The id of the bucket to create
         @param event_type - The type of event to create ( add delete
        """
        self.request_queue._reset()
        endpoint = f"buckets/{bucket_id}"
        data = {
            "client": self.client_name,
            "hostname": self.client_hostname,
            "type": event_type,
        }
        self._post(endpoint, data)


    def create_bucket(self, bucket_id: str, event_type: str, queued=False):
        """
         Create a bucket on the GCP server. This is a low - level method to create a bucket and register it for event delivery.
         
         @param bucket_id - The ID of the bucket to create.
         @param event_type - The type of event that will be fired on the bucket.
         @param queued - If True the bucket will be queued for delivery
        """
        # Register a bucket with the client.
        if queued:
            self.request_queue.register_bucket(bucket_id, event_type)
        else:
            endpoint = f"buckets/{bucket_id}"
            data = {
                "client": self.client_name,
                "hostname": self.client_hostname,
                "type": event_type,
            }
            self._post(endpoint, data)

    def delete_bucket(self, bucket_id: str, force: bool = False):
        """
         Delete a bucket. This is a soft delete so you don't have to worry about it being in use
         
         @param bucket_id - The ID of the bucket to delete
         @param force - If True the bucket will be deleted even if it has
        """
        self._delete(f"buckets/{bucket_id}" + ("?force=1" if force else ""))

    # @deprecated
    def setup_bucket(self, bucket_id: str, event_type: str):
        """
         Sets up a bucket to receive events. This is a convenience method for creating a bucket that will be queued for processing by the event handler.
         
         @param bucket_id - The ID of the bucket to create.
         @param event_type - The type of event that will be passed to the handler
        """
        self.create_bucket(bucket_id, event_type, queued=True)

    # Import & export

    def export_all(self) -> dict:
        """
         Export all data to JSON. This is a low - level method and should not be used on production use.
         
         
         @return a dictionary containing the data in JSON format : { status : {'ok': true'error': [ description ]
        """
        return self._get("export").json()

    def export_bucket(self, bucket_id) -> dict:
        """
         Export a bucket to a zip file. This is a POST request to the ` / buckets / { id } / export ` endpoint
         
         @param bucket_id - ID of the bucket to export
         
         @return ` ` dict ` ` with the following structure :: {'zip_file': zip_file_path
        """
        return self._get(f"buckets/{bucket_id}/export").json()

    def import_bucket(self, bucket: dict) -> None:
        """
         Import a bucket into S3. This is a blocking call and will return after the import has completed
         
         @param bucket - The bucket to import.
         
         @return True if success False if not. Raises APIError if there is a problem
        """
        endpoint = "import"
        self._post(endpoint, {"buckets": {bucket["id"]: bucket}})

    #
    #   Query (server-side transformation)
    #

    def query(
            self,
            query: str,
            timeperiods: List[Tuple[datetime, datetime]],
            name: Optional[str] = None,
            cache: bool = False,
    ) -> List[Any]:
        """
             The query to run. Must be delimited by newlines. Each timeperiod is a tuple of start and stop datetimes.
             
             @param timeperiods - A list of tuples of start and stop datetimes
             @param name - If provided the query will be restricted to this name
             @param cache - Whether to cache the query for future requests.
             
             @return A list of results from the query. Each result is a dict
            """
        endpoint = "query/"
        params = {}  # type: Dict[str, Any]
        # Set the cache parameter to the query name
        if cache:
            # This method is not allowed to do caching without a query name
            if not name:
                raise Exception(
                    "You are not allowed to do caching without a query name"
                )
            params["name"] = name
            params["cache"] = int(cache)

        # Check that datetimes have timezone information
        # Check if start and stop timeperiods are timezone aware.
        for start, stop in timeperiods:
            try:
                assert _dt_is_tzaware(start)
                assert _dt_is_tzaware(stop)
            except AssertionError:
                raise ValueError("start/stop needs to have a timezone set")

        data = {
            "timeperiods": [
                "/".join([start.isoformat(), end.isoformat()])
                for start, end in timeperiods
            ],
            "query": query.split("\n"),
        }
        response = self._post(endpoint, data, params=params)
        return response.json()

    #
    # Settings
    #

    def get_setting(self, key=None) -> dict:
        """
         Get settings from the server. If key is specified return the value for that setting
         
         @param key - Key to get ( optional )
         
         @return Dictionary of settings or all settings if key is not
        """
        # TODO: explicitly fetch key from server, instead of fetching all settings
        settings = self._get("settings").json()
        # Get the value of the settings.
        if key:
            return settings.get(key, None)
        return settings

    def set_setting(self, key: str, value: str) -> None:
        """
         Set a setting. This is a shortcut for POST / settings / { key }
         
         @param key - The key of the setting to set
         @param value - The value of the setting
         
         @return True if successful False
        """
        self._post(f"settings/{key}", value)

    #
    #   Connect and disconnect
    #

    def __enter__(self):
        """
         Called before __enter__ to connect to the server. This is a no - op if you don't have a connection to the server.
         
         
         @return The : class : ` Server ` object for chaining
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
         Called when exception is raised. Disconnect from RabbitMQ and raise : exc : ` ~exceptions. ConnectionError `
         
         @param exc_type - Type of exception that was raised.
         @param exc_val - Value of exception that was raised.
         @param exc_tb - Traceback of exception that was raised
        """
        self.disconnect()

    def connect(self):
        """
         Connect to the server. This is called when the server is ready to accept requests
        """
        # Start the request queue if it is not already running.
        if not self.request_queue.is_alive():
            self.request_queue.start()

    def disconnect(self):
        """
         Disconnect from server and wait for request to finish. This is called by : meth : ` disconnect
        """
        self.request_queue.stop()
        self.request_queue.join()

        # Throw away old thread object, create new one since same thread cannot be started twice
        self.request_queue = RequestQueue(self)


QueuedRequest = namedtuple("QueuedRequest", ["endpoint", "data"])
Bucket = namedtuple("Bucket", ["id", "type"])


class RequestQueue(threading.Thread):
    """Used to asynchronously send heartbeats.

    Handles:
        - Cases where the server is temporarily unavailable
        - Saves all queued requests to file in case of a server crash
    """

    VERSION = 1  # update this whenever the queue-file format changes

    def __init__(self, client: ActivityWatchClient) -> None:
        """
         Initializes the activity watch thread. Initializes the connection to the queue and starts the thread
         
         @param client - The client to use for
        """
        threading.Thread.__init__(self, daemon=True)

        self.client = client

        self.connected = False
        self._stop_event = threading.Event()

        # Buckets that will have events queued to them, will be created if they don't exist
        self._registered_buckets = []  # type: List[Bucket]

        self._attempt_reconnect_interval = 10

        # Setup failed queues file
        data_dir = get_data_dir("sd-client")
        queued_dir = os.path.join(data_dir, "queued")
        # Create a directory if it doesn t exist.
        if not os.path.exists(queued_dir):
            os.makedirs(queued_dir)

        cache_key = "TTim"
        cached_credentials = cache_user_credentials(cache_key,"SD_KEYS")
        # If cache_user_credentials is set to True the user credentials are cached and stored in the cache file.
        if cache_user_credentials:
            user_email = cached_credentials.get("email")

            persistqueue_path = os.path.join(
                queued_dir,
                "{}{}.{}.v{}.persistqueue".format(
                    self.client.client_name,
                    "-testing" if client.testing else "",
                    user_email,
                    self.VERSION,
                ),
            )

            logger.debug(f"queue path '{persistqueue_path}'")

            self._persistqueue = SQLiteQueue(
                persistqueue_path, multithreading=True, auto_commit=False, passwd='test123@'
            )
            self._current = None  # type: Optional[QueuedRequest]

    def _reset(self) -> None:
        """
         Reset the persist queue to the initial state. This is called when we have a change in the persistence queue
         
         
         @return True if there is a
        """
        self._persistqueue.empty()
        self._current = None

    def _get_next(self) -> Optional[QueuedRequest]:
        """
         Get the next request from the persist queue. This is called by : meth : ` _task_done ` to ensure that there is at least one request in the queue.
         
         
         @return The next request or None if none are available ( in which case the queue is empty
        """
        # self._current will always hold the next not-yet-sent event,
        # until self._task_done() is called.
        # Returns the current object or None if there is no current object.
        if not self._current:
            try:
                self._current = self._persistqueue.get(block=False)
            except Empty:
                return None
        return self._current

    def _task_done(self) -> None:
        """
         Called when task is done. This is the last step in the persist queue's _task_done method.
         
         
         @return ` ` None ` ` to indicate that there are no more
        """
        self._current = None
        self._persistqueue.task_done()

    def _create_buckets(self) -> None:
        """
         Create buckets if they don't exist. This is called when the user clicks the Create button in the Google Drive.
         
         
         @return None on success error code on failure. Note that the return value is ignored
        """
        # Create all registered buckets.
        for bucket in self._registered_buckets:
            self.client.create_bucket(bucket.id, bucket.type)

    def _try_connect(self) -> bool:
        """
         Try to connect to sd - server. If connection fails create buckets and return True
         
         
         @return True if connection succeeds
        """
        try:  # Try to connect
            db_key = ""
            cache_key = "TTim"
            cached_credentials = cache_user_credentials(cache_key,"SD_KEYS")
            # Returns the encrypted db_key if the cached credentials are cached.
            if cached_credentials != None:
                db_key = cached_credentials.get("encrypted_db_key")
            else:
                db_key == None
            key = load_key("user_key")
            # True if the database key is None or the key is None.
            if db_key == None or key == None:
                self.connected = False
                return self.connected
            self._create_buckets()
            self.connected = True
            logger.info(
                "Connection to sd-server established by {}".format(
                    self.client.client_name
                )
            )
        except req.RequestException:
            self.connected = False

        return self.connected

    def wait(self, seconds) -> bool:
        """
         Wait for the thread to stop. This is a wrapper around : meth : ` threading. Event. wait `
         
         @param seconds - Number of seconds to wait.
         
         @return True if the thread stopped False otherwise. >>> thread. wait ( 0 ) Traceback ( most recent call last ) : ThreadUninterruptible :
        """
        return self._stop_event.wait(seconds)

    def should_stop(self) -> bool:
        """
         Check if the thread should stop. This is used to prevent deadlock when multiple threads are trying to run the test in parallel.
         
         
         @return True if the thread should stop False otherwise. Note that it is possible that the thread has already stopped
        """
        return self._stop_event.is_set()

    def _dispatch_request(self) -> None:
        """
         Dispatch next request from queue. This is a blocking method and should be called in a thread to avoid blocking the caller
         
         
         @return None if there are no requests to
        """
        request = self._get_next()
        # wait for the queue to be empty
        if not request:
            self.wait(0.2)  # seconds to wait before re-polling the empty queue
            return

        try:
            self.client._post(request.endpoint, request.data)
        except req.exceptions.ConnectTimeout:
            # Triggered by:
            #   - server not running (connection refused)
            #   - server not responding (timeout)
            # Safe to retry according to requests docs:
            #   https://requests.readthedocs.io/en/latest/api/#requests.ConnectTimeout

            self.connected = False
            logger.warning(
                "Connection refused or timeout, will queue requests until connection is available."
            )
            # wait a bit before retrying, so we don't spam the server (or logs), see:
            #  - https://github.com/ActivityWatch/activitywatch/issues/815
            #  - https://github.com/ActivityWatch/activitywatch/issues/756#issuecomment-1266662861
            sleep(0.5)
            return
        except req.RequestException as e:
            # This method is used to retry the request.
            if e.response and e.response.status_code == 400:
                # HTTP 400 - Bad request
                # Example case: https://github.com/ActivityWatch/activitywatch/issues/815
                # We don't want to retry, because a bad payload is likely to fail forever.
                logger.error(f"Bad request, not retrying: {request.data}")
            elif e.response and e.response.status_code == 500:
                # HTTP 500 - Internal server error
                # It is possible that the server is in a bad state (and will recover on restart),
                # in which case we want to retry. I hope this can never caused by a bad payload.
                logger.error(f"Internal server error, retrying: {request.data}")
                sleep(0.5)
                return
            else:
                logger.exception(f"Unknown error, not retrying: {request.data}")
        except Exception:
            logger.exception(f"Unknown error, not retrying: {request.data}")

        # Mark the request as done
        self._task_done()

    def run(self) -> None:
        """
         Main loop of the thread. Connects to the server and dispatches requests until connection is lost
        """
        self._stop_event.clear()
        # Connect to server and dispatch requests.
        while not self.should_stop():
            # Connect
            # Try to connect to the server.
            while not self._try_connect():
                logger.warning(
                    "Not connected to server, {} requests in queue".format(
                        self._persistqueue.qsize()
                    )
                )
                # Wait for the attempt to reconnect.
                if self.wait(self._attempt_reconnect_interval):
                    break

            # Dispatch requests until connection is lost or thread should stop
            # Dispatches requests to the server.
            while self.connected and not self.should_stop():
                self._dispatch_request()

    def stop(self) -> None:
        """
         Stop the timer. This is a no - op if the timer is already stopped.
         
         
         @return ` ` None ` ` in all cases ( always
        """
        self._stop_event.set()

    def add_request(self, endpoint: str, data: dict) -> None:
        """
         Add a request to the queue. This is a blocking call. If you want to wait for a response use
         
         @param endpoint - The endpoint to send the request to
         @param data - The data to send to the endpoint. Must be a dict
         
         @return The id of the
        """
        """
        Add a request to the queue.
        NOTE: Only supports heartbeats
        """
        assert "/heartbeat" in endpoint
        assert isinstance(data, dict)
        self._persistqueue.put(QueuedRequest(endpoint, data))

    def register_bucket(self, bucket_id: str, event_type: str) -> None:
        """
         Register a bucket to be notified of events. This is a convenience method for subclasses to register their own buckets and to avoid having to re - register them every time they are called
         
         @param bucket_id - The ID of the bucket
         @param event_type - The type of event that triggered this bucket
         
         @return The newly registered : class : ` Bucket ` object
        """
        self._registered_buckets.append(Bucket(bucket_id, event_type))