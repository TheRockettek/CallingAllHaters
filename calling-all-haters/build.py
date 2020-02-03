import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["asyncio", "jinja2", "copy", "functools", "hashlib", "htmlmin", "hmac", "json", "logging", "os", "random", "sqlite3", "socket", "time", "traceback", "uuid", "datetime", "enum", "quart", "utils", "compress"]}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(  name = "calling-all-haters",
        version = "0.1",
        description = "Calling all haters",
        options = {"build_exe": build_exe_options},
        executables = [Executable("app.py")])
