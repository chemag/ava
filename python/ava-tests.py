#!/usr/bin/env python3

import argparse
import importlib
import os
import pandas as pd
import pathlib
import sys
import tempfile
import traceback

ava_common = importlib.import_module("ava-common")

# allow importing from subprojects
root_path = os.path.join(os.path.dirname(__file__), "..")
lib_path = os.path.join(root_path, "lib", "encapp", "scripts")
sys.path.insert(0, lib_path)

import encapp
import encapp_tool

ENCODED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi")


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


def qp_bounds(ava_config):
    output_dict = {
        "testname": "qp_bounds:20-25",
        "retcode": 0,
    }

    try:
        # 0. preparation
        # 0.1. ensure encapp is installed
        encapp_is_installed(ava_config.android_serial, ava_config.debug)

        # 0.2. get a (single) valid media file
        infile = ava_config.infile_list[0]
        if os.path.splitext(infile)[1] in ENCODED_VIDEO_EXTENSIONS:
            infile_encoded = infile
            infile = tempfile.NamedTemporaryFile(
                prefix=f"ava.{os.path.basename(infile_encoded)}.", suffix=".y4m"
            ).name
            command = f"ffmpeg -i {infile_encoded} {infile}"
            debug = ava_config.debug
            returncode, out, err, stats = ava_common.run(
                command, logfd=None, debug=debug, gnu_time=True
            )
            assert returncode == 0, f"error: {out = } {err = }"

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
        configfile = os.path.join(root_path, "tests", "qp_bounds.20-25.pbtxt")
        bitrate = "20Mbps"
        input_pix_fmt = "nv12"
        ## TODO(chema): fix encapp access through python API
        # options = argparse.Namespace(
        #    replace={},
        #    videofile=infile,
        #    codec=encoder_name,
        #    bitrate=None,
        #    framerate=None,
        #    resolution='',
        #    multiply='',
        #    pix_fmt="nv12",
        #    local_workdir=f'{local_workdir}',
        #    configfile=[configfile,],
        #    ignore_results=False,
        #    fast_copy=False,
        #    split=False,
        #    separate_sources=False,
        #    mediastore=None,
        #    dry_run=False,
        #    width_align=-1,
        #    height_align=-1,
        #    dim_align=None,
        #    raw=False,
        #    source_dir=None,
        #    quality=False,
        #    shuffle=False,
        #    version=False,
        #    debug=ava_config.debug,
        #    quiet=False,
        #    serial=ava_config.android_serial,
        #    install=False,
        #    idb=False,
        #    bundleid=None,
        #    device_workdir={device_workdir},
        #    run_cmd=None,
        #    desc='testing',
        # )
        # result_ok, result_json = encapp.codec_test(options, model, ava_config.android_serial, ava_config.debug)

        command = f"lib/encapp/scripts/encapp.py -ddd run {configfile} --serial {ava_config.android_serial} --device-workdir {device_workdir} -e input.pix_fmt {input_pix_fmt} -i {infile} --codec {encoder_name} --bitrate {bitrate} --local-workdir {local_workdir}"
        debug = ava_config.debug
        returncode, out, err, stats = ava_common.run(
            command, logfd=None, debug=debug, gnu_time=True
        )
        assert returncode == 0, f"error: {out = } {err = }"
        encapp_files = parse_encapp_output(out)
        # 2. parse QP_Y values
        # 2.1. qpextract only works on Annex B (.265) files
        h265_file = tempfile.NamedTemporaryFile(
            prefix=f"ava.{os.path.basename(encapp_files['mp4'])}.", suffix=".265"
        ).name
        ffmpeg_command = f"ffmpeg -i {encapp_files['mp4']} -c:v copy {h265_file}"
        returncode, out, err, stats = ava_common.run(
            ffmpeg_command, logfd=None, debug=debug, gnu_time=True
        )
        assert returncode == 0, f"error: {out = } {err = }"

        # 2.2. obtain QP_Y values
        qpextract_cmd = os.path.join(root_path, "build", "lib", "libde265", "qpextract")
        qpy_file = tempfile.NamedTemporaryFile(
            prefix=f"ava.{os.path.basename(encapp_files['mp4'])}.", suffix=".qpy.csv"
        ).name
        qpy_command = f"{qpextract_cmd} --qpymode -i {h265_file} -o {qpy_file}"
        returncode, out, err, stats = ava_common.run(
            qpy_command, logfd=None, debug=debug, gnu_time=True
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
        if qp_min < 20 or qp_max > 25:
            output_dict["retcode"] = -2
            output_dict["error"] = (
                f"expected QP range: 20:25\nfound QPY range: {qp_min}:{qp_max}\nbitrate: {bitrate}\nencoded_file: {encapp_files['mp4']}\nqpy_file: {qpy_file}"
            )
        else:
            output_dict["info"] = (
                f"expected QP range: 20:25\nfound QPY range: {qp_min}:{qp_max}\nbitrate: {bitrate}\nencoded_file: {encapp_files['mp4']}\nqpy_file: {qpy_file}"
            )
        # 3. parse QP_Cr and QP_Cb values
        # TODO(chema): write me

        # 4. clean up
        # local dir
        # device dir
        # TODO(chema): write me

    except Exception as e:
        output_dict["retcode"] = -1
        output_dict["error"] = repr(e)
        output_dict["backtrace"] = traceback.format_exc()

    return output_dict


AVA_TESTS = {
    "list_codecs": list_codecs,
    "qp_bounds": qp_bounds,
}
