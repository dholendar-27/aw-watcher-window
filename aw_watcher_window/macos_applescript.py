from typing import Dict
from Foundation import NSAppleScript

# the applescript version of the macos strategy is kept here until the jxa
# approach is proven out in production environments
# https://github.com/ActivityWatch/aw-watcher-window/pull/52

source = """
global frontApp, frontAppName, windowTitle

set windowTitle to ""
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set frontAppName to name of frontApp
    tell process frontAppName
        try
            tell (1st window whose value of attribute "AXMain" is true)
                set windowTitle to value of attribute "AXTitle"
            end tell
        end try
    end tell
end tell

return frontAppName & "
" & windowTitle
"""

script = None


def getInfo() -> Dict[str, str]:
    """
     Get information about Apple. This is a helper function to make it easier to use in tests.
     
     
     @return A dictionary with app and title keys. The keys are " app " and " title " which are the name of the app
    """
    # Cache compiled script
    global script
    # Initialize the script object with the source.
    if script is None:
        script = NSAppleScript.alloc().initWithSource_(source)

    # Call script
    result, errorinfo = script.executeAndReturnError_(None)
    # If errorinfo is set to true raise an exception.
    if errorinfo:
        raise Exception(errorinfo)
    output = result.stringValue()

    # Ensure there's no extra newlines in the output
    assert len(output.split("\n")) == 2

    app = getApp(output)
    title = getTitle(output)

    return {"app": app, "title": title}


def getApp(info: str) -> str:
    """
     Extracts the app name from the info string. This is used to determine the name of the application that is running.
     
     @param info - The info string from the command line. Should be of the form " app_name \ n "
     
     @return The app name as
    """
    return info.split('\n')[0]


def getTitle(info: str) -> str:
    """
     Extracts the title from the info string. This is used to determine the page title in the list of pages
     
     @param info - the info string from the web page
     
     @return the title of the page as a string ( without the tab and line breaks in the info string if there is a tab
    """
    return info.split('\n')[1]


# Print info about the module.
if __name__ == "__main__":
    info = getInfo()
    print(info)
