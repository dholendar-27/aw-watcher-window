import argparse
import sys

from sd_core.config import load_config_toml

default_config = """
[sd-watcher-afk]
timeout = 300
poll_time = 5

[sd-watcher-afk-testing]
timeout = 20
poll_time = 1
""".strip()


def load_config(testing: bool):
    """
     Load configuration from TOML file. This is a wrapper around load_config_toml that allows to specify whether or not we are testing

     @param testing - True if we are testing

     @return A dictionary of config
    """
    section = "sd-watcher-afk" + ("-testing" if testing else "")
    return load_config_toml("sd-watcher-afk", default_config)[section]


def parse_args():
    """
     Parse command line arguments. This is called from main () to parse the command line arguments. If you want to override this call super (). parse_args ()


     @return a tuple of ( parser args
    """
    # get testing in a dirty way, because we need it for the config lookup
    testing = "--testing" in sys.argv
    config = load_config(testing)

    default_poll_time = config["poll_time"]
    default_timeout = config["timeout"]

    parser = argparse.ArgumentParser(
        description="A watcher for keyboard and mouse input to detect AFK state."
    )
    parser.add_argument("--host", dest="host")
    parser.add_argument("--port", dest="port")
    parser.add_argument(
        "--testing", dest="testing", action="store_true", help="run in testing mode"
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="run with verbose logging",
    )
    parser.add_argument(
        "--timeout", dest="timeout", type=float, default=default_timeout
    )
    parser.add_argument(
        "--poll-time", dest="poll_time", type=float, default=default_poll_time
    )
    parsed_args = parser.parse_args()
    return parsed_args
