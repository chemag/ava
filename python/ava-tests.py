#!/usr/bin/env python3

import importlib
import os
import pathlib
import sys
import tempfile

ava_common = importlib.import_module("ava-common")

# allow importing from subprojects
lib_path = os.path.join(os.path.dirname(__file__), "..", "lib", "encapp", "scripts")
sys.path.insert(0, lib_path)

import encapp


def list_codecs(ava_config):
    output_dict = {
        "testname": "list_codecs",
    }

    try:
        # 0. ensure encapp is installed
        # XXX

        # 1. run encapp command
        model = "model"
        device_workdir = "/sdcard"
        outfile = encapp.list_codecs(
            ava_config.android_serial, model, device_workdir, debug=ava_config.debug
        )
        # 2. read and clean up the output file (json)
        codec_list_dict = encapp.read_json_file(outfile, ava_config.debug)
        pathlib.Path.unlink(outfile)
        # 3. write output
        output_dict["retcode"] = 0
        output_dict["results"] = codec_list_dict

    except Exception as e:
        output_dict["retcode"] = -1
        output_dict["error"] = repr(e)

    return output_dict


def list_codecs_bash(ava_config):
    # 0. ensure encapp is installed

    # 1. run encapp list
    command = f"lib/encapp/scripts/encapp.py list --serial {ava_config.android_serial}"
    debug = ava_config.debug
    returncode, out, err, stats = ava_common.run(
        command, logfd=None, debug=debug, gnu_time=True
    )
    assert returncode == 0, f"error: {out = } {err = }"
    # 2. read and clean up the output file (json)
    # 3. write output


AVA_TESTS = {"list_codecs": list_codecs}
