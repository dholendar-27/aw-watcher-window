"""
Common queries.

Most of these are from: https://github.com/ActivityWatch/sd-webui/blob/master/src/queries.ts
"""

import json
import re
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from typing import List, Union, Tuple, Optional
from typing_extensions import TypeGuard

import sd_client


class EnhancedJSONEncoder(json.JSONEncoder):
    """For encoding dataclasses into JSON"""

    def default(self, o):
        """
         Convert an object to a dictionary. This is a wrapper around the : meth : ` ~dataclasses. asdict ` method to allow dataclass objects to be converted to dictionaries
         
         @param o - The object to be converted
         
         @return The object converted to a dictionary or ` None ` if not a dataclass object ( for example a string
        """
        # Convert object to a dictionary of data classes.
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


"""
Do these dataclasses look confusing?
Read up on dataclass inheritance: https://stackoverflow.com/a/53085935/965332
"""


@dataclass
class _QueryParamsDefaultsBase:
    bid_browsers: List[str] = field(default_factory=list)
    classes: List[Tuple[List[str], dict]] = field(default_factory=list)
    filter_classes: List[List[str]] = field(default_factory=list)
    filter_afk: bool = True
    include_audible: bool = True


@dataclass
class QueryParams(_QueryParamsDefaultsBase):
    pass


@dataclass
class _DesktopQueryParamsBase:
    bid_window: str
    bid_afk: str


@dataclass
class DesktopQueryParams(QueryParams, _DesktopQueryParamsBase):
    pass


@dataclass
class _AndroidQueryParamsBase:
    bid_android: str


@dataclass
class AndroidQueryParams(QueryParams, _AndroidQueryParamsBase):
    pass


def isDesktopParams(params: QueryParams) -> TypeGuard[DesktopQueryParams]:
    """
     Check if a query params is a DesktopQueryParams. This is used to ensure that we don't accidentally send a query that is sent to a user in an unauthenticated context.
     
     @param params - The query params to check. May be None.
     
     @return True if params is a DesktopQueryParams False otherwise. >>> from pytest. fixture import get >>> type = get () Traceback ( most recent call last ) : NoSuchObject
    """
    return isinstance(params, DesktopQueryParams)


def isAndroidParams(params: QueryParams) -> TypeGuard[AndroidQueryParams]:
    """
     Check if query params is AndroidQueryParams. This is a type guard to avoid type clashes with other types that inherit from AndroidQueryParams
     
     @param params - The query params to check
     
     @return True if params is an instance of AndroidQueryParams False otherwise ( for example if params is None or not a subclass
    """
    return isinstance(params, AndroidQueryParams)


def canonicalEvents(params: Union[DesktopQueryParams, AndroidQueryParams]) -> str:
    """
     Generate code to fetch events and / or filter by class. This is used by : func : ` get_events ` and : func : ` get_events_and_filter `
     
     @param params - query parameters for events.
     
     @return code to fetch events and / or filter by class ( s ) as a string. The code can be run in a shell
    """
    # Needs escaping for regex patterns like '\w' to work (JSON.stringify adds extra unnecessary escaping)
    classes_str = json.dumps(params.classes, cls=EnhancedJSONEncoder)
    classes_str = re.sub(r"\\\\", r"\\", classes_str)

    cat_filter_str = json.dumps(params.filter_classes)

    # For simplicity, we assume that bid_window and bid_android are exchangeable (note however it needs special treatment)
    bid_window = (
        params.bid_window
        if isinstance(params, DesktopQueryParams)
        else params.bid_android
    )

    return "\n".join(
        [
            # Fetch window/app events
            f'events = flood(query_bucket(find_bucket("{bid_window}")));',
            # On Android, merge events to avoid overload of events
            'events = merge_events_by_keys(events, ["app"]);'
            if isAndroidParams(params)
            else "",
            # Fetch not-afk events
            f"""
            not_afk = flood(query_bucket(find_bucket("{params.bid_afk}")));
            not_afk = filter_keyvals(not_afk, "status", ["not-afk"]);
            """
            if isDesktopParams(params)
            else "",
            # Fetch browser events
            (
                browserEvents(params)
                if isDesktopParams(params)
                else ""
                + (  # Include focused and audible browser events as indications of not-afk
                    """
            audible_events = filter_keyvals(browser_events, "audible", [true]);
            not_afk = period_union(not_afk, audible_events);
            """
                    if params.include_audible
                    else ""
                )
                if params.bid_browsers
                else ""
            ),
            # Filter out window events when the user was afk
            "events = filter_period_intersect(events, not_afk);"
            if isDesktopParams(params) and params.filter_afk
            else "",
            # Categorize
            f"events = categorize(events, {classes_str});" if params.classes else "",
            # Filter out selected categories
            f"events = filter_keyvals(events, '$category', {cat_filter_str});"
            if params.filter_classes
            else "",
        ]
    )


def pretty_query(query: str) -> str:
    """
     Formats query for display. This is used to make queries human readable. The query is split on newlines and each line is separated by a newline.
     
     @param query - The query to format. Must be a string of one or more lines.
     
     @return The query formatted as a string of one or more lines. If there are no lines in the query it is returned as is
    """
    return "\n".join([line.strip() for line in query.split("\n") if line.strip()])


def _browser_in_buckets(browser: str, browserbuckets: List[str]) -> Optional[str]:
    """
     Check if browser is in one of the buckets. This is used to detect browser's presence in a list of buckets
     
     @param browser - the browser we want to check
     @param browserbuckets - the list of buckets to check against.
     
     @return the bucket that browser belongs to or None if it isn't in one of the buckets ( in which case browser is returned
    """
    # Return the bucket that is in browserbuckets.
    for bucket in browserbuckets:
        # Return the bucket if it s in the bucket.
        if browser in bucket:
            return bucket
    return None


def browsersWithBuckets(browserbuckets: List[str]) -> List[Tuple[str, str]]:
    """
     Returns a list of browser names and bucket IDs that are in the list of buckets. This is useful for checking if a user has access to an app that's listed in a bucket and which bucket they want to use.
     
     @param browserbuckets - A list of buckets to look for.
     
     @return A list of ( browserName bucketId ) pairs for which a bucket could be found or None if no browser was
    """
    """Returns a list of (browserName, bucketId) pairs for found browser buckets"""
    browsername_to_bucketid: List[Tuple[str, Optional[str]]] = [
        (browserName, _browser_in_buckets(browserName, browserbuckets))
        for browserName in browser_appnames
    ]

    # Only return browsers for which a bucket could be found
    return [t for t in browsername_to_bucketid if t[1]]  # type: ignore


def browserEvents(params: DesktopQueryParams) -> str:
    """
     Returns a list of events that were made by each browser. It is possible to have multiple browsers in one call to this function
     
     @param params - Desktop query parameters ( bid_browsers bid_browsers )
     
     @return String of JavaScript code to run in browser events ( ordered by timestamp ) in chronological order ( oldest to newest
    """
    """Returns a list of active browser events (where the browser was the active window) from all browser buckets"""
    code = "browser_events = [];"

    # Generates code for the events.
    for browserName, bucketId in browsersWithBuckets(params.bid_browsers):
        browser_appnames_str = json.dumps(browser_appnames[browserName])
        code += f"""
          events_{browserName} = flood(query_bucket("{bucketId}"));
          window_{browserName} = filter_keyvals(events, "app", {browser_appnames_str});
          events_{browserName} = filter_period_intersect(events_{browserName}, window_{browserName});
          events_{browserName} = split_url_events(events_{browserName});
          browser_events = concat(browser_events, events_{browserName});
          browser_events = sort_by_timestamp(browser_events);
        """
    return code


browser_appnames = {
    "chrome": [
        # Chrome
        "Google Chrome",
        "Google-chrome",
        "chrome.exe",
        "google-chrome-stable",
        # Chromium
        "Chromium",
        "Chromium-browser",
        "Chromium-browser-chromium",
        "chromium.exe",
        # Pre-releases
        "Google-chrome-beta",
        "Google-chrome-unstable",
        # Brave (should this be merged with the brave entry?)
        "Brave-browser",
    ],
    "firefox": [
        "Firefox",
        "Firefox.exe",
        "firefox",
        "firefox.exe",
        "Firefox Developer Edition",
        "firefoxdeveloperedition",
        "Firefox-esr",
        "Firefox Beta",
        "Nightly",
    ],
    "opera": ["opera.exe", "Opera"],
    "brave": ["brave.exe"],
    "edge": [
        "msedge.exe",  # Windows
        "Microsoft Edge",  # macOS
    ],
    "vivaldi": ["Vivaldi-stable", "Vivaldi-snapshot", "vivaldi.exe"],
}

default_limit = 100


def querystr_to_array(querystr: str) -> List[str]:
    """
     Convert query string to list of strings. This is used to create a list of strings from a query string
     
     @param querystr - query string to convert to list
     
     @return list of strings in query string separated by space ( s ) e. g. " a b c
    """
    return [line + ";" for line in querystr.split(";") if line]


def escape_doublequote(s: str) -> str:
    """
     Escape double quotes in a string. This is useful for quoting strings that are meant to be used as part of a query such as SELECT or EXPLAIN.
     
     @param s - The string to escape. It is assumed that the string is quoted before it is passed to this function.
     
     @return The string with double quotes escaped as necessary. >>> escape_doublequote ('SELECT')'SELECT
    """
    return re.sub('/"/g', '\\"', s)


def fullDesktopQuery(
    
    params: DesktopQueryParams,
) -> str:
    """
     Generate a URL to query desktop. This is used for the URL generation and also for the Google Apps API
     
     @param params - Desktop query parameters to use
     
     @return URL to query desktop with query parameters ( URL + browser events ) and Google Apps API ( browser events
    """
    # Escape `"`
    params.bid_window = escape_doublequote(params.bid_window)
    params.bid_afk = escape_doublequote(params.bid_afk)
    params.bid_browsers = [escape_doublequote(bucket) for bucket in params.bid_browsers]

    return (
        f"""
      {canonicalEvents(params)}
      title_events = sort_by_duration(merge_events_by_keys(events, ["app", "title"]));
      app_events   = sort_by_duration(merge_events_by_keys(title_events, ["app"]));
      cat_events   = sort_by_duration(merge_events_by_keys(events, ["$category"]));
      app_events  = limit_events(app_events, {default_limit});
      title_events  = limit_events(title_events, {default_limit});
      duration = sum_durations(events);
      """  # Browser events are retrieved in canonicalQuery
        + f"""
      browser_events = split_url_events(browser_events);
      browser_urls = merge_events_by_keys(browser_events, ["url"]);
      browser_urls = sort_by_duration(browser_urls);
      browser_urls = limit_events(browser_urls, {default_limit});
      browser_domains = merge_events_by_keys(browser_events, ["$domain"]);
      browser_domains = sort_by_duration(browser_domains);
      browser_domains = limit_events(browser_domains, {default_limit});
      browser_duration = sum_durations(browser_events);
      """
        + """
      RETURN = {
          "events": events,
          "window": {
              "app_events": app_events,
              "title_events": title_events,
              "cat_events": cat_events,
              "active_events": not_afk,
              "duration": duration
          },
          "browser": {
              "domains": browser_domains,
              "urls": browser_urls,
              "duration": browser_duration
          }
      };
      """
    )


def test_fullDesktopQuery():
    """
     Test full desktop query with time period. We're using this to test the event watcher and not the window
    """
    params = DesktopQueryParams(
        bid_window="sd-watcher-window_",
        bid_afk="sd-watcher-afk_",
    )
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=7)
    end = now
    timeperiods = [(start, end)]
    query = fullDesktopQuery(params)

    sdc = sd_client.ActivityWatchClient("test")
    res = sdc.query(query, timeperiods)[0]
    events = res["events"]
    print(len(events))


# This is a test_fullDesktopQuery function.
if __name__ == "__main__":
    test_fullDesktopQuery()
