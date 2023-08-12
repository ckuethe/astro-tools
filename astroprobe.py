#!/usr/bin/env python3
# coding: utf-8
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 syn=python

from math import nan
import json
import re
from subprocess import run
from tempfile import mkdtemp
from os import listdir, unlink, removedirs
from os.path import join as pjoin
from time import monotonic
import logging
import argparse
from sys import stderr
from typing import Any, Dict
import fitsio

logger = logging.getLogger(__file__)


def get_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="identify an image by plate solving")
    ap.add_argument("-v", "--verbose", default=0, action="count")
    # ap.add_argument("-a", "--astrometry-arg", action="append", default=[])
    ap.add_argument("-o", "--output", default="/dev/stdout")
    ap.add_argument("-R", "--ra", type=float)
    ap.add_argument("-D", "--dec", type=float)
    ap.add_argument("-L", "--scale-low", type=float, default=1)
    ap.add_argument("-H", "--scale-high", type=float, default=2)
    ap.add_argument("--test-file", default=False, action="store_true")
    ap.add_argument("--save-temps", default=False, action="store_true")
    ap.add_argument(nargs="+", dest="files")
    return ap.parse_args()


def rm_rf(d):
    # I should rewrite this to either be recursive or use os.walk
    for f in listdir(d):
        try:
            unlink(pjoin(d, f))
        except (OSError, IOError):
            pass
    try:
        removedirs(d)
    except (OSError, IOError):
        pass


def parse_buf(b: str) -> Dict[str, Any]:
    rv = dict()
    rv["fov"] = [float(x) for x in re.search(r"Field size: ([0-9.]+) x ([0-9.]+)", b).groups()]
    tmp = re.search(r"Field center: \(RA,Dec\) = \(([0-9.-]+), ([0-9.-]+)\) deg.", b).groups()
    rv["field_center"] = dict(zip(["ra", "dec"], [float(x) for x in tmp]))
    rv["arcsec_pp"] = float(re.search(r"pixel scale ([0-9.]+) arcsec/pix", b).group(1))
    rv["constellations"] = re.findall(r"[Tt]he constellation (.+)", b)
    rv["stars"] = re.findall(r"The star (.+)", b)
    rv["ic"] = re.findall(r"(IC \d+.*)", b)
    rv["ngc"] = re.findall(r"(NGC \d+.*)", b)
    try:
        rv["index"] = re.search(r"Field \d+: solved with index index-([a-z0-9-]+).\S+endian.fits.", b).group(1)
    except AttributeError:
        pass
    return rv


def solve_image(img: str, save_temps: bool = False, solver_debug: bool = False, **kwargs) -> str:
    """
    wrapper for astronomy.net solve-field

    Pretty much any command line parameter to solve-field can be specified, eg.

    long_kw_param=2 -> "--long-kw-param 2"

    L=True -> "-L"

    Of particular interest:

    - scale_low (--scale-low)
    - scale_high (--scale-high)
    - cpulimit
    - sigma
    - depth

    """

    wd = mkdtemp(prefix="astrometry_", dir="/tmp")
    solver_args = ["solve-field", "--dir", wd, "--temp-dir", wd]

    for k, v in kwargs.items():
        k = k.replace("_", "-")
        d = "-" if len(k) == 1 else "--"
        if v is True:
            solver_args.append(d + k)
        else:
            solver_args.extend([d + k, str(v)])

    solver_args.append(img)
    try:
        fits_header = dict(fitsio.read_header(img))
    except OSError:
        fits_header = dict()

    logger.debug("Astrometry command:" + " ".join(solver_args))
    t1 = monotonic()
    solver_out = run(solver_args, capture_output=True, text=True).stdout
    t2 = monotonic()
    if save_temps:
        with open(pjoin(wd, "solver.txt"), "w") as ofd:
            ofd.write(solver_out)
    else:
        rm_rf(wd)

    if solver_debug:
        print("\n\n\n", solver_out, "\n\n\n")

    m = re.search("simplexy: found (\d+) sources", solver_out)
    rv = {
        "file": img,
        "solve_time": round(t2 - t1, 3),
        "solved": False,
    }

    try:
        rv["hdr"] = {
            "loc": {
                "dec": fits_header["DEC"],
                "ra": fits_header["RA"],
            },
            "obj": fits_header.get("OBJECT", ""),
            "fov": [
                round(fits_header["NAXIS1"] * fits_header["SECPIX1"] / 3600, 6),
                round(fits_header["NAXIS2"] * fits_header["SECPIX2"] / 3600, 6),
            ],
        }
    except KeyError:
        pass

    if m:
        rv["sources"] = int(m.group(1))

    if "Did not solve" in solver_out:
        logging.warning(f"Unable to solve {img}")
    else:
        rv["solved"] = True
        rv.update(parse_buf(solver_out))
    return rv


def main():
    args = get_args()
    lvl = logging.WARNING
    if args.verbose:
        lvl = logging.DEBUG if args.verbose > 1 else logging.INFO
    logger.setLevel(lvl)
    logging.basicConfig()
    solver_results = []

    for f in args.files:
        solve_res = dict()
        if args.test_file:
            with open(f) as ifd:
                solve_res = parse_buf(ifd.read())
                solve_res["file"] = f
                solve_res["solve_time"] = 0.0
        else:
            solve_res = solve_image(f, save_temps=args.save_temps, solver_debug=args.verbose > 2, guess_scale=True)

        if args.verbose:
            logger.info(solve_res)

        if solve_res["solved"] or args.verbose > 1:
            solver_results.append(solve_res)

    with open(args.output, "w") as ofd:
        json.dump(solver_results, ofd, sort_keys=True, indent=2)


if __name__ == "__main__":
    main()
