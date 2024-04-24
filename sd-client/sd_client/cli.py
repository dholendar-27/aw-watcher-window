#!/usr/bin/env python3
import json
import argparse
import logging
import textwrap
from typing import Optional, List
from datetime import timedelta, datetime, timezone

import click
from tabulate import tabulate

from sd_core import Event

import sd_client
from . import queries
from .classes import default_classes


now = datetime.now(timezone.utc)
td1day = timedelta(days=1)
td1yr = timedelta(days=365)

logger = logging.getLogger(__name__)


def _valid_date(s):
    """
     Validate and return a datetime object. This is a helper function for argparse. ArgumentTypeError and argparse. ArgumentValueError
     
     @param s - string to be validated.
     
     @return datetime object of the validated date or None if the date is invalid ( no exception is raised ). >>> _valid_date ('1 Jan 1970
    """
    # https://stackoverflow.com/questions/25470844/specify-format-for-input-arguments-argparse-python
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = f"Not a valid date: '{s}'."
        raise argparse.ArgumentTypeError(msg)


class _Context:
    client: sd_client.ActivityWatchClient


@click.group(
    help="CLI utility for sd-client to aid in interacting with the ActivityWatch server"
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Address of host",
)
@click.option(
    "--port",
    default=7600,
    help="Port to use",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbosity",
)
@click.option("--testing", is_flag=True, help="Set to use testing ports by default")
@click.pass_context
def main(ctx, testing: bool, verbose: bool, host: str, port: int):
    """
     Entry point for activity watch. This will connect to the host and port specified by the command line arguments.
     
     @param ctx - The argparse. Namespace object that contains all the necessary arguments
     @param testing - If true the client will be used for testing
     @param verbose - If true the client will
     @param host
     @param port
    """
    ctx.obj = _Context()
    ctx.obj.client = sd_client.ActivityWatchClient(
        host=host,
        port=port if port != 5600 else (5666 if testing else 5600),
        testing=testing,
    )
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@main.command(help="Send a heartbeat to bucket with ID `bucket_id` with JSON `data`")
@click.argument("bucket_id")
@click.argument("data")
@click.option("--pulsetime", default=60, help="pulsetime to use for merging heartbeats")
@click.pass_obj
def heartbeat(obj: _Context, bucket_id: str, data: str, pulsetime: int):
    """
     Sends a heartbeat to CloudFlare. This is a blocking call so it will block until the heartbeat is acknowledged
     
     @param obj - Context object for the connection
     @param bucket_id - ID of the bucket to send to
     @param data - JSON string of the heartbeat data to send to CloudFlare
     @param pulsetime - Time in seconds to wait before
    """
    now = datetime.now(timezone.utc)
    e = Event(duration=0, data=json.loads(data), timestamp=now)
    print(e)
    obj.client.heartbeat(bucket_id, e, pulsetime)


@main.command(help="List all buckets")
@click.pass_obj
def buckets(obj: _Context):
    """
     Lists all buckets. Example :. from fabtools import buckets from fabtools. test import get_buckets
     
     @param obj - Instance of nova. v1. client.
    """
    buckets = obj.client.get_buckets()
    print("Buckets:")
    # Prints out the list of buckets
    for bucket in buckets:
        print(f" - {bucket}")


@main.command(help="Query events from bucket with ID `bucket_id`")
@click.argument("bucket_id")
@click.pass_obj
def events(obj: _Context, bucket_id: str):
    """
     Get events for a bucket. This is a list of events that have occurred since the last time you logged in and the time it took to complete that event.
     
     @param obj - An instance of novaclient. base. RequestContext
     @param bucket_id - The id of the bucket to get events
    """
    events = obj.client.get_events(bucket_id)
    print("events:")
    # Print out the events in the event list.
    for e in events:
        print(
            " - {} ({}) {}".format(
                e.timestamp.replace(tzinfo=None, microsecond=0),
                str(e.duration).split(".")[0],
                e.data,
            )
        )


@main.command(help="Run a query in file at `path` on the server")
@click.argument("path")
@click.option("--name")
@click.option("--cache", is_flag=True)
@click.option("--json", is_flag=True)
@click.option("--start", default=now - td1day, type=click.DateTime())
@click.option("--stop", default=now + td1yr, type=click.DateTime())
@click.pass_obj
def query(
    
    obj: _Context,
    path: str,
    cache: bool,
    _json: bool,
    start: datetime,
    stop: datetime,
    name: Optional[str] = None,
):
    """
     Query data from Google Drive. This is a wrapper around the : py : func : ` ~kombu. client. Client. query ` function with the addition of an optional name parameter.
     
     @param obj - The context to use for the request. It is passed by reference so you can access it from the context.
     @param path - The path to the file to query. If this is a file the file will be read from the current directory and used as the query.
     @param cache - Whether to use cache or not. Default is False.
     @param _json - Whether to return JSON data instead of printing to stdout. Default is False.
     @param start - The start time of the query in UTC.
     @param stop - The stop time of the query in UTC.
     @param name - The name of the query as it appears in the log
    """
    with open(path) as f:
        query = f.read()
    result = obj.client.query(query, [(start, stop)], cache=cache, name=name)
    # Print out the result of the API call.
    if _json:
        print(json.dumps(result))
    else:
        # Print out the 10 out of the period.
        for period in result:
            print(f"Showing 10 out of {len(period)} events:")
            # Print out the duration and data of each event
            for event in period[:10]:
                event.pop("id")
                event.pop("timestamp")
                print(
                    " - Duration: {} \tData: {}".format(
                        str(timedelta(seconds=event["duration"])).split(".")[0],
                        event["data"],
                    )
                )
            print(
                "Total duration:\t",
                timedelta(seconds=sum(e["duration"] for e in period)),
            )


@main.command(help="Generate an activity report")
@click.argument("hostname")
@click.option("--cache", is_flag=True)
@click.option("--start", default=now - td1day, type=click.DateTime())
@click.option("--stop", default=now + td1yr, type=click.DateTime())
@click.pass_obj
def report(
    
    obj: _Context,
    hostname: str,
    cache: bool,
    start: datetime,
    stop: datetime,
    name: Optional[str] = None,
):
    """
     Query and report data between two dates. This is a wrapper around : py : func : ` ~plexapi. client. DesktopQuery ` and
     
     @param obj - The context to use for the query
     @param hostname - The hostname to query
     @param cache - Whether to cache the result
     @param start - The start date to query from ( UTC )
     @param stop - The stop date to query ( UTC ).
     @param name - The name of the report to return ( optional
    """
    logger.info(f"Querying between {start} and {stop}")
    bid_window = f"sd-watcher-window_{hostname}"
    bid_afk = f"sd-watcher-afk_{hostname}"

    # Returns the current time zone.
    if not start.tzinfo:
        start = start.astimezone()
    # Returns the current time zone.
    if not stop.tzinfo:
        stop = stop.astimezone()

    bid_browsers: List[str] = []

    # TODO: Allow loading from toml
    logger.info("Using default classes")
    classes = default_classes

    params = queries.DesktopQueryParams(
        bid_browsers=bid_browsers,
        classes=classes,
        filter_classes=[],
        filter_afk=True,
        include_audible=True,
        bid_window=bid_window,
        bid_afk=bid_afk,
    )
    query = queries.fullDesktopQuery(params)
    logger.debug("Query: \n" + queries.pretty_query(query))

    result = obj.client.query(query, [(start, stop)], cache=cache, name=name)

    # TODO: Print titles, apps, categories, with most time
    # Print out the events in the result of the analysis.
    for period in result:
        print()
        # print(period["window"]["cat_events"])

        cat_events = _parse_events(period["window"]["cat_events"])
        print_top(
            cat_events,
            lambda e: " > ".join(e.data["$category"]),
            title="Top categories",
        )

        title_events = _parse_events(period["window"]["title_events"])
        print_top(title_events, lambda e: e.data["title"], title="Top titles")

        active_events = _parse_events(period["window"]["title_events"])
        print(
            "Total duration:\t",
            sum((e.duration for e in active_events), timedelta()),
        )


def _parse_events(events: List[dict]) -> List[Event]:
    """
     Parses event dictionaries into list of Event objects. This is a helper to be used by : py : meth : ` _parse_events `.
     
     @param events - List of events as dict. Example :.
     
     @return List of Event objects corresponding to the list of events passed in. Example :. >>> events = [ {'type':'test'' event_id':'3'}
    """
    return [Event(**event) for event in events]


def print_top(events: List[Event], key=lambda e: e.data, title="Events"):
    """
     Print the top 10 events in a tabulated format. This is useful for debugging the events that are most important to the user.
     
     @param events - The events to print. Must be sorted by duration
     @param key - A function to extract the key from an event. Defaults to the value of the event. data attribute.
     @param title - A title to print on the top of the
    """
    print(
        title
        + (f" (showing 10 out of {len(events)} events)" if len(events) > 10 else "")
    )
    print(
        tabulate(
            [
                (event.duration, key(event))
                for event in sorted(events, key=lambda e: e.duration, reverse=True)[:10]
            ],
            headers=["Duration", "Key"],
        )
    )
    print()


@main.command(help="Query 'canonical events' for a single host (filtered, classified)")
@click.argument("hostname")
@click.option("--cache", is_flag=True)
@click.option("--start", default=now - td1day, type=click.DateTime())
@click.option("--stop", default=now + td1yr, type=click.DateTime())
@click.pass_obj
def canonical( 
    obj: _Context,
    hostname: str,
    cache: bool,
    start: datetime,
    stop: datetime,
    name: Optional[str] = None,
):
    """
     Query events between two dates. This is a convenience function for : func : ` ~plexapi. client. query `
     
     @param obj - The context to use for the query.
     @param hostname - The hostname to query. Defaults to the currently logged in user
     @param cache - Whether to cache the results in the cache directory.
     @param start - The start time of
     @param stop
     @param name
    """
    logger.info(f"Querying between {start} and {stop}")
    bid_window = f"sd-watcher-window_{hostname}"
    bid_afk = f"sd-watcher-afk_{hostname}"

    # Returns the current time zone.
    if not start.tzinfo:
        start = start.astimezone()
    # Returns the current time zone.
    if not stop.tzinfo:
        stop = stop.astimezone()

    classes = default_classes

    query = queries.canonicalEvents(
        queries.DesktopQueryParams(
            bid_window=bid_window,
            bid_afk=bid_afk,
            classes=classes,
        )
    )
    query = f"""{query}\n RETURN = events;"""
    logger.debug("Query: \n" + queries.pretty_query(query))

    result = obj.client.query(query, [(start, stop)], cache=cache, name=name)

    # TODO: Print titles, apps, categories, with most time
    # Print out the last 10 out of the period.
    for period in result:
        print()
        events = _parse_events(period)
        print(f"Showing last 10 out of {len(events)} events:")

        print(
            tabulate(
                [
                    (
                        str(e.timestamp).split(".")[0],
                        str(e.duration).split(".")[0],
                        f'[{e.data["app"]}] {textwrap.shorten(e.data["title"], 60, placeholder="...")}',
                    )
                    for e in events[-10:]
                ],
                headers=["Timestamp", "Duration", "Data"],
            )
        )

        print()
        print(
            "Total duration:\t",
            timedelta(seconds=sum(e["duration"] for e in period)),
        )


# main function for the main module
if __name__ == "__main__":
    main()
