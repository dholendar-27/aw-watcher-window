import sys
import subprocess
import re
import logging
from subprocess import PIPE
from typing import List

logger = logging.getLogger(__name__)

# req_version is 3.5 due to usage of subprocess.run
# It would be nice to be able to use 3.4 as well since it's still common as of May 2016
req_version = (3, 5)
cur_version = sys.version_info

# Check if the current Python version is older than 3. 5 or higher is required.
if not cur_version >= req_version:
    logger.error("Your Python version is too old, 3.5 or higher is required.")
    exit(1)


def xprop_id(window_id) -> str:
    """
     Get Xprop ID for a window. This is a wrapper around xprop - id. The result is a string of UTF - 8 encoded binary data
     
     @param window_id - Window ID to look up
     
     @return String of UTF - 8 encoded binary data or None if not able to find it ( could be empty
    """
    cmd = ["xprop"]
    cmd.append("-id")
    cmd.append(window_id)
    p = subprocess.run(cmd, stdout=PIPE)
    return str(p.stdout, "utf8")


def xprop_root() -> str:
    """
     Get xprop root. This is useful for debugging. The output should be utf8 encoded so it can be parsed by : func : ` str `.
     
     
     @return ` ` str ` ` -- output of xprop - root command as utf8 encoded string. Example usage
    """
    cmd = ["xprop"]
    cmd.append("-root")
    p = subprocess.run(cmd, stdout=PIPE)
    return str(p.stdout, "utf8")


def get_active_window_id():
    """
     Get the ID of the active window. This is used to determine if we are running in XEP - 0040 or not.
     
     
     @return A string containing the ID of the active window or 0x0 if none is active ( in which case it is not possible
    """
    lines = xprop_root().split("\n")
    match="_NET_ACTIVE_WINDOW(WINDOW)"
    result = None
    # Find the first match in the list of lines.
    for line in lines:
        # Return the line that matches the match.
        if match in line:
            result = line
            break
    wid = "0x0"
    # Find the widening of the word
    if result:
        wids = re.findall("0x[0-9a-f]*", result)
        # Get the widest wideted wids.
        if len(wids) > 0:
            wid = wids[0]
    return wid


def get_window_ids():
    """
     Get list of window ids. This is used to determine which XProps are connected to and which have a window id that is the same as the one we are connected to.
     
     
     @return A list of window ids in the format [ 0x000 - 0x9a - f ]
    """
    lines = xprop_root().split("\n")
    client_list = next(filter(lambda x: "_NET_CLIENT_LIST(" in x, lines))
    window_ids = re.findall("0x[0-9a-f]*", client_list)
    return window_ids


def _extract_xprop_field(line):
    """
     Extracts XProp field from line. This is used to extract the name of the property that is stored in the xprop file
     
     @param line - line from the xprop file
     
     @return name of the property as a string or None if not found in the xprop file ( in which case the name is empty
    """
    return "".join(line.split("=")[1:]).strip(" \n")


def get_xprop_field(fieldname, xprop_output):
    """
     Extracts xprop fields from the output of xprop. This is a helper function to extract a list of xprop fields from the output of xprop.
     
     @param fieldname - The name of the field to extract.
     @param xprop_output - The output of xprop.
     
     @return A list of dictionaries where each dictionary contains the key and value of the field. The keys are the field names
    """
    return list(map(_extract_xprop_field, re.findall(fieldname + ".*\n", xprop_output)))


def get_xprop_field_str(fieldname, xprop_output) -> str:
    """
     Get field from xprop output and strip whitespace. This is useful for debugging the output of an xprop command
     
     @param fieldname - Name of the field to get
     @param xprop_output - Output of the xprop command
     
     @return String representation of the field or " unknown " if not found or empty string if no field is found
    """
    field = None
    try:
        field = get_xprop_field(fieldname, xprop_output)[0].strip('"')
    except IndexError:
        pass
    # Set the field to unknown.
    if not field:
        field = "unknown"
    return field


def get_xprop_field_strlist(fieldname, xprop_output) -> List[str]:
    """
     Get a list of strings from xprop output. This is a wrapper around get_xprop_field and strips whitespace before returning the list.
     
     @param fieldname - Name of the field to read. Must be a string or a list of strings.
     @param xprop_output - Output of the xprop command.
     
     @return List of strings read from the field as a list of strings. Each string is stripped of leading and trailing whitespace
    """
    return [s.strip('"') for s in get_xprop_field(fieldname, xprop_output)]


def get_xprop_field_int(fieldname, xprop_output) -> int:
    """
     Get integer xprop field. This is a wrapper around get_xprop_field to handle error cases
     
     @param fieldname - Name of the field to get
     @param xprop_output - Output of the xprop command
     
     @return Field value as an integer or - 1 if field doesn't exist in xprop_output or
    """
    field = None
    try:
        field = int(get_xprop_field(fieldname, xprop_output)[0])
    except IndexError:
        pass
    # Set field to 1 if not set.
    if not field:
        field = -1
    return field


def get_xprop_field_class(xprop_output) -> List[str]:
    """
     Get WM_CLASS field from xprop output. This is a list of class names separated by spaces
     
     @param xprop_output - The output of xprop.
     
     @return List [ str ] List of class names in format [ " class1 class2 " " class3
    """
    classname: List[str] = []
    try:
        classname = [c.strip('", ') for c in get_xprop_field("WM_CLASS", xprop_output)[0].split(',')]
    except IndexError:
        pass
    # Set classname to unknown.
    if not classname:
        classname = ["unknown"]
    return classname


def get_window(wid, active_window=False):
    """
     Get information about a window. This is a helper function for get_xprop_fields and get_xprop_fields_as_dict
     
     @param wid - ID of the window to get
     @param active_window - True if the window is active
     
     @return dictionary with the window's information as key / value pairs or None if not found or invalid ID
    """
    s = xprop_id(wid)
    window = {
        "id": wid,
        "active": active_window,
        "name": get_xprop_field_str("WM_NAME", s),
        "class": get_xprop_field_class(s),
        "desktop": get_xprop_field_int("WM_DESKTOP", s),
        "command": get_xprop_field("WM_COMMAND", s),
        "role": get_xprop_field_strlist("WM_WINDOW_ROLE", s),
        "pid": get_xprop_field_int("WM_PID", s),
    }

    return window


def get_windows(wids, active_window_id=None):
    """
     Get a list of : class : ` Window ` objects by id. This is a convenience function that calls
     
     @param wids - The ids of the windows to get
     @param active_window_id - The id of the window that should be active
     
     @return A list of : class : ` Window ` objects corresponding to the given ids or an empty list if none
    """
    return [get_window(wid, active_window=(wid == active_window_id)) for wid in wids]


# This function is called by the main module.
if __name__ == "__main__":
    from time import sleep
    logging.basicConfig(level=logging.INFO)
    # This function is used to wait for the active window to be displayed
    while True:
        sleep(1)
        print("Active window id: " + str(get_active_window_id()))
