#!/usr/bin/env python3

import os
import re
import subprocess
import sys
import tempfile


def get_device_workdir():
    return "/sdcard"


def get_local_workdir(local_workdir):
    if local_workdir is None:
        # choose a random dir
        tempdir = tempfile.gettempdir()
        local_workdir = tempfile.mkdtemp(prefix="ava.tmp.", dir=tempdir)
    # prepare the local working directory to pull the files in
    if not os.path.exists(local_workdir):
        os.mkdir(local_workdir)
    return local_workdir


def get_android_serial(android_serial):
    if android_serial is not None:
        return android_serial
    elif "ANDROID_SERIAL" in os.environ:
        # read serial number from ANDROID_SERIAL env variable
        return os.environ["ANDROID_SERIAL"]
    else:
        return None


def run(command, **kwargs):
    debug = kwargs.get("debug", 0)
    dry_run = kwargs.get("dry_run", False)
    env = kwargs.get("env", None)
    stdin = subprocess.PIPE if kwargs.get("stdin", False) else None
    bufsize = kwargs.get("bufsize", 0)
    universal_newlines = kwargs.get("universal_newlines", False)
    default_close_fds = True if sys.platform == "linux2" else False
    close_fds = kwargs.get("close_fds", default_close_fds)
    shell = kwargs.get("shell", type(command) in (type(""), type("")))
    logfd = kwargs.get("logfd", sys.stdout)
    if debug > 0:
        print(f"$ {command}", file=logfd)
    if dry_run:
        return 0, b"stdout", b"stderr"
    gnu_time = kwargs.get("gnu_time", False)
    if gnu_time:
        # GNU /usr/bin/time support
        command = f"/usr/bin/time -v {command}"

    p = subprocess.Popen(  # noqa: E501
        command,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=bufsize,
        universal_newlines=universal_newlines,
        env=env,
        close_fds=close_fds,
        shell=shell,
    )
    # wait for the command to terminate
    if stdin is not None:
        out, err = p.communicate(stdin)
    else:
        out, err = p.communicate()
    returncode = p.returncode
    # clean up
    del p
    if gnu_time:
        # make sure the stats are there
        GNU_TIME_BYTES = b"\n\tUser time"
        assert GNU_TIME_BYTES in err, "error: cannot find GNU time info in stderr"
        gnu_time_str = err[err.index(GNU_TIME_BYTES) :].decode("ascii")
        gnu_time_stats = gnu_time_parse(gnu_time_str, logfd, debug)
        err = err[0 : err.index(GNU_TIME_BYTES) :]
        return returncode, out, err, gnu_time_stats
    # return results
    return returncode, out, err, None


GNU_TIME_DEFAULT_KEY_DICT = {
    "Command being timed": "command",
    "User time (seconds)": "usertime",
    "System time (seconds)": "systemtime",
    "Percent of CPU this job got": "cpu",
    "Elapsed (wall clock) time (h:mm:ss or m:ss)": "elapsed",
    "Average shared text size (kbytes)": "avgtext",
    "Average unshared data size (kbytes)": "avgdata",
    "Average stack size (kbytes)": "avgstack",
    "Average total size (kbytes)": "avgtotal",
    "Maximum resident set size (kbytes)": "maxrss",
    "Average resident set size (kbytes)": "avgrss",
    "Major (requiring I/O) page faults": "major_pagefaults",
    "Minor (reclaiming a frame) page faults": "minor_pagefaults",
    "Voluntary context switches": "voluntaryswitches",
    "Involuntary context switches": "involuntaryswitches",
    "Swaps": "swaps",
    "File system inputs": "fileinputs",
    "File system outputs": "fileoutputs",
    "Socket messages sent": "socketsend",
    "Socket messages received": "socketrecv",
    "Signals delivered": "signals",
    "Page size (bytes)": "page_size",
    "Exit status": "status",
}


GNU_TIME_DEFAULT_VAL_TYPE = {
    "int": [
        "avgtext",
        "avgdata",
        "avgstack",
        "avgtotal",
        "maxrss",
        "avgrss",
        "major_pagefaults",
        "minor_pagefaults",
        "voluntaryswitches",
        "involuntaryswitches",
        "swaps",
        "fileinputs",
        "fileoutputs",
        "socketsend",
        "socketrecv",
        "signals",
        "page_size",
        "status",
        "usersystemtime",
    ],
    "float": [
        "usertime",
        "systemtime",
    ],
    "timedelta": [
        "elapsed",
    ],
    "percent": [
        "cpu",
    ],
}


def gnu_time_parse(gnu_time_str, logfd, debug):
    gnu_time_stats = {}
    for line in gnu_time_str.split("\n"):
        if not line:
            # empty line
            continue
        # check if we know the line
        line = line.strip()
        for key1, key2 in GNU_TIME_DEFAULT_KEY_DICT.items():
            if line.startswith(key1):
                break
        else:
            # unknown key
            print(f"warn: unknown gnutime line: {line}", file=logfd)
            continue
        val = line[len(key1) + 1 :].strip()
        # fix val type
        if key2 in GNU_TIME_DEFAULT_VAL_TYPE["int"]:
            val = int(val)
        elif key2 in GNU_TIME_DEFAULT_VAL_TYPE["float"]:
            val = float(val)
        elif key2 in GNU_TIME_DEFAULT_VAL_TYPE["percent"]:
            val = float(val[:-1])
        elif key2 in GNU_TIME_DEFAULT_VAL_TYPE["timedelta"]:
            # '0:00.02'
            timedelta_re = r"((?P<min>\d+):(?P<sec>\d+).(?P<centisec>\d+))"
            res = re.search(timedelta_re, val)
            timedelta_sec = int(res.group("min")) * 60 + int(res.group("sec"))
            timedelta_centisec = int(res.group("centisec"))
            timedelta_sec += timedelta_centisec / 100.0
            val = timedelta_sec
        gnu_time_stats[key2] = val
    gnu_time_stats["usersystemtime"] = (
        gnu_time_stats["usertime"] + gnu_time_stats["systemtime"]
    )
    return gnu_time_stats


def encapp_get_encoder_name(output_dict, mime_type):
    filtered_canonical_names = [
        encoder["canonical_name"]
        for encoder in output_dict["results"]["encoders"]
        if encoder.get("is_encoder", True)
        and encoder.get("is_hardware_accelerated", True)
        and encoder.get("media_type", {}).get("mime_type") == mime_type
    ]
    return filtered_canonical_names
