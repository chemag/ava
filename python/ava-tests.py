#!/usr/bin/env python3

import argparse
import importlib
import os
import pandas as pd
import pathlib
import sys
import tempfile
import traceback
import google
from google.protobuf import text_format
import json

ava_common = importlib.import_module("ava-common")

# allow importing from subprojects
root_path = os.path.join(os.path.dirname(__file__), "..")
lib_path = os.path.join(root_path, "lib", "encapp", "scripts")
sys.path.insert(0, lib_path)

import encapp
import encapp_tool

ENCODED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi")
# TODO: figure out how to handle this. On osx the /usr/bin/time is not the GNU version.
GNU_TIME = True


def encapp_is_installed(android_serial, debug):
    # check whether it is already installed
    already_installed = encapp_tool.app_utils.install_ok(android_serial, debug)
    if already_installed:
        return
    encapp_tool.app_utils.install_app(android_serial, debug)


def list_codecs(ava_config):
    output_dict = {
        "testname": "list_codecs",
    }

    try:
        # 0. preparation
        # 0.1. ensure encapp is installed
        encapp_is_installed(ava_config.android_serial, ava_config.debug)

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


# TODO(chema): encapp should provide a plumbing output (not porcelain)
def parse_encapp_output(out):
    # 1. look for lines with "adb ... pull ..."
    candidate_files = []
    for line in out.splitlines():
        if b"adb" in line and b"pull" in line:
            items = [item.decode("ascii") for item in line.split(b" ")]
            if not "pull" in items:
                continue
            src = items[items.index("pull") + 1]
            dst = items[items.index("pull") + 2]
            filename = os.path.join(dst, os.path.basename(src))
            candidate_files.append(filename)
    assert (
        len(candidate_files) == 2
    ), f"error: need 2 candidate lines, found {len(candidate_files)}: {out}"
    # 2. get the output files
    encapp_output = {}
    for file in candidate_files:
        if os.path.splitext(file)[1] == ".json":
            encapp_output["json"] = file
        elif os.path.splitext(file)[1] == ".mp4":
            encapp_output["mp4"] = file
    return encapp_output


def video_to_yuv(input_filepath, output_filepath, pix_fmt):
    # lazy but let us skip transcodig if the target is already there...
    print("Convert video to yuv")
    if not os.path.exists(output_filepath):
        cmd = f"ffmpeg -y -loglevel error -hide_banner -i {input_filepath} -pix_fmt {pix_fmt} {output_filepath}"
        returncode, out, err, stats = ava_common.run(
            cmd, logfd=None, debug=1, gnu_time=GNU_TIME
        )
        if returncode != 0:
            print(f"Error: {err}")
            # raise Exception(f"Error: {stderr}")
    else:
        print("Warning, transcoded file exists, assuming it is correct")


def qp_bounds(ava_config):
    debug = ava_config.debug
    print("** run QP bounds **")

    test_ok = True
    all_output_dict = {
        "testname": "qp_bounds",
        "retcode": 0,
        "backtrace": "no exception",
        "results": [],
    }
    # try:
    if True:
        # 0. preparation
        # 0.1. ensure encapp is installed
        encapp_is_installed(ava_config.android_serial, ava_config.debug)

        # 0.2. get a (single) valid media file
        infile = ava_config.infile_list
        if isinstance(infile, list):
            # TODO: shoudl we do file iteration as well?
            infile = infile[0]

        """
        if os.path.splitext(infile)[1] in ENCODED_VIDEO_EXTENSIONS:
            infile_encoded = infile
            infile = tempfile.NamedTemporaryFile(
                prefix=f"ava.{os.path.basename(infile_encoded)}.", suffix=".y4m"
            ).name

            command = f"ffmpeg -i {infile_encoded} {infile}"
            debug = ava_config.debug
            returncode, out, err, stats = ava_common.run(
                command, logfd=None, debug=debug, gnu_time=GNU_TIME
            )
            assert returncode == 0, f"error: {out = } {err = }"
        """
        # 0.3. get a valid encoder name
        encoder_name = ava_config.encoder
        if ava_config.encoder is None:
            output_dict_list = list_codecs(ava_config)
            mime_type = "video/hevc"
            canonical_names = ava_common.encapp_get_encoder_name(
                output_dict_list, mime_type
            )
            assert (
                len(canonical_names) == 1
            ), f"error: found {mime_type} encoders: {canonical_names}"
            encoder_name = canonical_names[0]

        # 1. run encapp command
        model = "model"
        # device_workdir = "/data/data/com.facebook.encapp"
        device_workdir = "/sdcard"
        local_workdir = "/tmp"
        mediastore = local_workdir
        # configfile = os.path.join(root_path, "tests", "qp_bounds.20-25.pbtxt")
        print("Create test obbject")

        test_suite = encapp.tests_definitions.TestSuite()

        videoinfo = encapp.encapp_tool.ffutils.get_video_info(infile)
        # if we want to run a raw video i.e. nv12 it needs to be converted
        videoname = os.path.basename(infile)
        yuvfile = f"{videoname}.yuv"
        video_to_yuv(f"{infile}", f"{mediastore}/{yuvfile}", "nv12")
        files_to_push = [f"{mediastore}/{yuvfile}"]

        # build the tests.
        # run qp 0-5, 5-10 etc, at bitrates of 1M, 5M, 10M, 15M (for now)
        qpvals = [15, 20, 25, 30, 35, 40, 45, 50]
        bitrates = ["1M", "5M", "10M", "20M", "50M"]
        tests = []
        for valindex in range(len(qpvals) - 1):
            qpmin = qpvals[valindex]
            qpmax = qpvals[valindex + 1]
            print(f"qpmin: {qpmin}, qpmax: {qpmax}")
            for bitrate in bitrates:
                test = encapp.tests_definitions.Test()
                test.common.id = f"qp_{qpmin}-{qpmax}_{bitrate}"
                test.common.description = f"Check that boundaries for qp values are within {qpmin} and {qpmax}"
                # OK. The name resolution will not happen at this late stage.
                test.common.output_filename = f"qp.bound.{videoname}.qp{qpmin}-{qpmax}.{bitrate}bps"
                test.input.pix_fmt = encapp.tests_definitions.PixFmt.nv12
                test.configure.bitrate = bitrate
                test.configure.codec = ava_config.encoder

                test.input.framerate = int(round(float(videoinfo["framerate"]), 0))
                test.input.resolution = f"{videoinfo['width']}x{videoinfo['height']}"

                params = [
                    encapp.tests_definitions.Parameter(
                        key="video-qp-i-min",
                        type=encapp.tests_definitions.intType,
                        value=str(qpmin),
                    ),
                    encapp.tests_definitions.Parameter(
                        key="video-qp-p-min",
                        type=encapp.tests_definitions.intType,
                        value=str(qpmin),
                    ),
                    encapp.tests_definitions.Parameter(
                        key="video-qp-i-max",
                        type=encapp.tests_definitions.intType,
                        value=str(qpmax),
                    ),
                    encapp.tests_definitions.Parameter(
                        key="video-qp-p-max",
                        type=encapp.tests_definitions.intType,
                        value=str(qpmax),
                    ),
                ]

                test.configure.parameter.extend(params)
                test.input.filepath = f"{device_workdir}/{yuvfile}"
                tests.append(test)
        test_suite.test.extend(tests)
        print(text_format.MessageToString(test_suite))

        result = encapp.run_codec_tests(
            test_suite,
            files_to_push,
            model,
            ava_config.android_serial,
            mediastore,
            local_workdir,
            device_workdir=None,
            ignore_results=False,
            fast_copy=False,
            split=False,
            debug=debug,
        )

        returncode = not result[0]
        assert returncode == 0, f"error: {out = } {err = }"
        out = result[1]

        complete_output = []
        for file in out:
            jsonfile = None
            with open(file, "r") as f:
                jsonfile = json.load(f)

            directory = os.path.dirname(file)
            # Pull parameters
            test_text = json.dumps(jsonfile.get("test"))
            test_ = encapp.tests_definitions.Test()
            test_def = google.protobuf.json_format.Parse(test_text, test_)
            params = test_def.configure.parameter

            # We will not make any difference between p and i frames so (currently) all will have the same settings.
            for param in params:
                if param.key == "video-qp-i-min":
                    qp_set_min = int(param.value)
                elif param.key == "video-qp-i-max":
                    qp_set_max = int(param.value)

            output_dict = {
                "testname": f"qp_bounds: {qp_set_min}:{qp_set_max}",
                "retcode": 0,
            }
            mediafile = f"{directory}/{jsonfile.get('encodedfile')}"
            requested_bitrate = test_def.configure.bitrate
            bitrate = jsonfile.get(
                "meanbitrate"
            )  # or should we use the requested bitrate?

            # 2. parse QP_Y values
            # 2.1. qpextract only works on Annex B (.265) files
            h265_file = tempfile.NamedTemporaryFile(
                prefix=f"ava.{os.path.basename(mediafile)}.", suffix=".265"
            ).name
            ffmpeg_command = f"ffmpeg -i {mediafile} -c:v copy {h265_file}"
            returncode, out, err, stats = ava_common.run(
                ffmpeg_command, logfd=None, debug=debug, gnu_time=GNU_TIME
            )
            assert returncode == 0, f"error: {out = } {err = }"

            # 2.2. obtain QP_Y values
            qpextract_cmd = os.path.join(
                root_path, "lib", "libde265", "tools", "qpextract"
            )
            # TODO(chema): fix qpextract path
            # TODO: either on the command line or a setprop

            # TODO: This is only hevc!
            qpextract_cmd = "qpextract"
            qpy_file = tempfile.NamedTemporaryFile(
                prefix=f"ava.{os.path.basename(mediafile)}.", suffix=".qpy.csv"
            ).name
            qpy_command = f"{qpextract_cmd} --qpymode -i {h265_file} -o {qpy_file}"
            returncode, out, err, stats = ava_common.run(
                qpy_command, logfd=None, debug=debug, gnu_time=GNU_TIME
            )
            assert returncode == 0, f"error: {out = } {err = }"
            qpy_df = pd.read_csv(qpy_file)
            qp_min = -1
            qp_max = -1
            # TODO(chema): Note that we are combining I, P, and B frames. Fix it
            for qp in range(0, 64):
                if qpy_df[str(qp)].max() > 0:
                    # there is an element with this QP
                    if qp_min == -1:
                        qp_min = qp
                    if qp_max == -1 or qp > qp_max:
                        qp_max = qp
            # 2.3. check QP_Y values
            if qp_min < qp_set_min or qp_max > qp_set_max:
                print("\nTEST FAILED!!!\n")
                output_dict["retcode"] = -2
                output_dict["error"] = (
                    f"expected QP range: {qp_set_min}:{qp_set_max}\nfound QPY range: {qp_min}:{qp_max}\nbitrate: {bitrate}\nencoded_file: {mediafile}\nqpy_file: {qpy_file}"
                )
                test_ok = False
            else:
                output_dict["info"] = (
                    f"expected QP range: {qp_set_min}:{qp_set_max}\nfound QPY range: {qp_min}:{qp_max}\nbitrate: {bitrate}\nencoded_file: {mediafile}\nqpy_file: {qpy_file}"
                )
            complete_output.append(output_dict)
            # 3. parse QP_Cr and QP_Cb values
            # TODO(chema): write me

            # 4. clean up
            # local dir
            # device dir
            # TODO(chema): write me

    # except Exception as e:
    #    output_dict["retcode"] = -1
    #    output_dict["error"] = repr(e)
    #    output_dict["backtrace"] = traceback.format_exc()

    all_output_dict["results"] = complete_output
    if not test_ok:
        all_output_dict["retcode"] = -1

    return all_output_dict


AVA_TESTS = {
    "list_codecs": list_codecs,
    "qp_bounds": qp_bounds,
}
