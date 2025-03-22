#!/usr/bin/env python3

"""ava.py module description.

This is a tool to run ava tests.
"""


import argparse
import importlib
import itertools
import json
import os
import sys
import tempfile

ava_common = importlib.import_module("ava-common")
ava_tests = importlib.import_module("ava-tests")
ava_version = importlib.import_module("ava-version")

# allow importing from subprojects
lib_path = os.path.join(os.path.dirname(__file__), "..", "lib", "encapp", "scripts")
sys.path.insert(0, lib_path)


default_values = {
    "debug": 0,
    "dry_run": False,
    "android_serial": None,
    "encoder": None,
    "test": None,
    "test_list": False,
    "infile_list": None,
    "outfile": None,
}


TEST_INPUT_MP4 = "vid/johnny.1280x720.60fps.264.mp4"


class AvaConfig:
    def __init__(self, options):
        self.debug = options.debug
        self.dry_run = options.dry_run
        self.android_serial = ava_common.get_android_serial(options.android_serial)
        self.encoder = options.encoder
        self.test = options.test
        self.infile_list = options.infile_list
        if self.infile_list is None:
            self.infile_list = [
                TEST_INPUT_MP4,
            ]
        self.outfile = options.outfile

    def __repr__(self):
        out = ""
        out += f"debug: {self.debug}\n"
        out += f"dry_run: {self.dry_run}\n"
        out += f"android_serial: {self.android_serial}\n"
        out += f"test: {self.test}\n"
        out += f"infile_list: {self.infile_list}\n"
        out += f"outfile: {self.outfile}\n"
        return out


def get_options(argv):
    """Generic option parser.

    Args:
        argv: list containing arguments

    Returns:
        Namespace - An argparse.ArgumentParser-generated option object
    """
    # init parser
    # usage = 'usage: %prog [options] arg1 arg2'
    # parser = argparse.OptionParser(usage=usage)
    # parser.print_help() to get argparse.usage (large help)
    # parser.print_usage() to get argparse.usage (just usage line)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=ava_version.__version__,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        dest="debug",
        default=default_values["debug"],
        help="Increase verbosity (use multiple times for more)",
    )
    parser.add_argument(
        "--quiet",
        action="store_const",
        dest="debug",
        const=-1,
        help="Zero verbosity",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        default=default_values["dry_run"],
        help="Dry run",
    )
    parser.add_argument(
        "-s",
        "--android-serial",
        action="store",
        type=str,
        dest="android_serial",
        default=default_values["android_serial"],
        help="Device serial number (overrides $ANDROID_SERIAL)",
    )
    parser.add_argument(
        "--encoder",
        action="store",
        type=str,
        dest="encoder",
        default=default_values["encoder"],
        help="Encoder Name",
    )
    parser.add_argument(
        "--test",
        action="store",
        type=str,
        dest="test",
        default=default_values["test"],
        help="Run a specific test",
    )
    parser.add_argument(
        "--test-list",
        action="store_true",
        dest="test_list",
        default=default_values["test_list"],
        help="List all tests",
    )
    parser.add_argument(
        dest="infile_list",
        type=str,
        nargs="?",
        default=default_values["infile_list"],
        metavar="input-file-list",
        help="input file list",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        action="store",
        dest="outfile",
        type=str,
        default=default_values["outfile"],
        metavar="output-file",
        help="output file",
    )
    # do the parsing
    options = parser.parse_args(argv[1:])
    return options


def main(argv):
    # parse options
    options = get_options(argv)
    # get outfile
    if options.outfile is None or options.outfile == "-":
        options.outfile = "/dev/fd/1"
    # print results
    if options.debug > 0:
        print(f"debug: {options}")
    # create configuration
    ava_config = AvaConfig(options)

    if options.test_list:
        # list all existing tests
        print("list of available tests")
        for name in ava_tests.AVA_TESTS:
            print(f"* {name}")

    elif options.test is not None:
        # ensure the test exists
        assert (
            options.test in ava_tests.AVA_TESTS
        ), f"error: unknown test {options.test}"
        # run a specific test
        results_dict = ava_tests.AVA_TESTS[options.test](ava_config)
        # write results in outfile
        results_json = json.dumps(results_dict, indent=4)
        with open(options.outfile, "w") as fd:
            fd.write(results_json)


if __name__ == "__main__":
    # at least the CLI program name: (CLI) execution
    main(sys.argv)
