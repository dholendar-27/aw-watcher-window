import os
import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)
script = None


def compileScript():
    """
     Compiles JXA script and caches the result. Resources. This is useful for performance purposes. If you want to run a script that does not require a language you can use L { compileScript }
     
     
     @return a compiled script or
    """

    # use a global variable to cache the compiled script for performance
    global script
    # Returns the script to be executed.
    if script:
        return script

    from OSAKit import OSAScript, OSALanguage

    scriptPath = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "printAppStatus.jxa"
    )
    with open(scriptPath) as f:
        scriptContents = f.read()

        # remove shebang line
        # Returns the script contents of the script.
        if scriptContents.split("\n")[0].startswith("#"):
            scriptContents = "\n".join(scriptContents.split("\n")[1:])

    script = OSAScript.alloc().initWithSource_language_(
        scriptContents, OSALanguage.languageForName_("JavaScript")
    )
    success, err = script.compileAndReturnError_(None)

    # should only occur if jxa was modified incorrectly
    # if success is true raise an exception
    if not success:
        raise Exception(f"error compiling jxa script: {err['NSLocalizedDescription']}")

    return script


def getInfo() -> Dict[str, str]:
    """
     Get information about jxa. This is a wrapper around compileScript and executeAndReturnError_.
     
     
     @return Dictionary with the following keys : ns_localized : A human readable name of the object. ns_localizedFailureReason : A descriptive error message
    """
    script = compileScript()

    result, err = script.executeAndReturnError_(None)

    # error structure for the error.
    if err:
        # error structure:
        # {
        #     NSLocalizedDescription = "Error: Error: Can't get object.";
        #     NSLocalizedFailureReason = "Error: Error: Can't get object.";
        #     OSAScriptErrorBriefMessageKey = "Error: Error: Can't get object.";
        #     OSAScriptErrorMessageKey = "Error: Error: Can't get object.";
        #     OSAScriptErrorNumberKey = "-1728";
        #     OSAScriptErrorRangeKey = "NSRange: {0, 0}";
        # }

        raise Exception(f"jxa error: {err['NSLocalizedDescription']}")

    return json.loads(result.stringValue())


# This function is called by the main class.
if __name__ == "__main__":
    print(getInfo())
    print("Waiting 5 seconds...")
    import time

    time.sleep(5)
    print(getInfo())
