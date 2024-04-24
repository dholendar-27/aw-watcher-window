import os
import sys
import tempfile
import ctypes
from sd_qt.main import main
def show_error_message():
    ctypes.windll.user32.MessageBoxW(0, "TTim is already running.", "TTim.exe", 0x10)

tempdir = tempfile.gettempdir()
lockfile = os.sep.join([tempdir, 'myapp.lock'])
try:
    if os.path.isfile(lockfile):
        os.unlink(lockfile)
except WindowsError as e: # Should give you smth like 'WindowsError: [Error 32] The process cannot access the file because it is being used by another process..'   
    ctypes.windll.user32.MessageBoxW(0,
                                         "TTim is already running.",
                                         "TTim.exe",
                                         0x10)
    sys.exit(0)

with open(lockfile, 'wb') as lockfileobj:
    # run your app's main here
    main()
os.unlink(lockfile)
