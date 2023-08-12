#!/usr/bin/env python
# coding: utf-8
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 syn=python

import argparse
import fitsio
from glob import glob
import os
from textwrap import dedent

SCOPE_MAP = {
    # Askar V, 60mm objective
    "60:270": "a5_60r",
    "60:360": "a5_60f",
    "60:446": "a5_60x",
    # Askar V, 80mm objective
    "80:385": "a5_80r",
    "80:495": "a5_80f",
    "80:600": "a5_80x",
    # SVBony SV503, 70mm
    "70:336": "sv503r",
    "70:420": "sv503",
    # Dwarflab Dwarf II, 20mm f/6
    "20:100": "dwarf2",
}

# Dwarf = 1.45um, 3840x2160 (1920x1080, bin2)
# 50.27mm fl; 20, 25mm obj?

DEFAULT_FORMAT = "{SCOPE}/{OBJECT}_{FILTER}"

# These are worth keeping from the source header
SRC_COLUMNS = [
    # Hardware
    "TELESCOP",
    "INSTRUME",
    "CAMERA",
    "LENS",
    "FILTER",
    # Image Parameters
    "APTDIA",
    "FOCALLEN",
    "FRAME",  # Light, dark, flat, bias, ...
    "DATE-OBS",
    "OBJECT",
    "EXPOSURE",
    "EXP",
    "EXPTIME",
    "XPOSURE",
    # Sensor
    "GAIN",
    "CCD-TEMP",
    "NAXIS1",
    "NAXIS2",
    "PIXSIZE1",
    "PIXSIZE2",
    "BINNING",
    "XBINNING",
    "YBINNING",
    # Position
    "SITELAT",
    "SITELONG",
    "RA",
    "DEC",
    "OBJCTRA",
    "OBJCTDEC",
]

# These get deleted because they're used to compute a different output token
# Mostly pairs, that get turned into a tuple
DELETE_COLS = [
    "OBJCTRA",
    "OBJCTDEC",
    "RA",
    "DEC",
    "SITELAT",
    "SITELONG",
    "PIXSIZE1",
    "PIXSIZE2",
    "NAXIS1",
    "NAXIS2",
    "XBINNING",
    "YBINNING",
]


def list_tokens():
    msg = """
    Tokens are derived from the FITS header, and may be specified case-insensitively.
    Use the "-v" flag to view the header key-value pairs which may be interpolated.
    Spaces are replaced by underscores, standard f-string formats apply.

    INSTRUME = Instrument (camera) used for this image
    TELESCOP = Mount holding the instrument. Bogus, IMO.
    EXPTIME  = Integration time
    CCD-TEMP = Sensor temperature
    GAIN     = Sensor gain
    FILTER   = Filter used
    FOCALLEN = Effective focal length (eg. real length x reducer/extender/barlow...)
    APTDIA   = Optical aperture
    SCOPE    = Short name of the instrument
    OBJECT   = User provided object name
    SITE     = (latitude,longitude)
    RADEC    = (ra_degrees, dec_degrees)
    OBJRADEC = (ra_hrs:min:sec.ss, dec_deg:min:sec.ss)
    PIXSIZE  = pixel size in um. will be (x,y) if pixels are not square
    BINNING  = HxV, eg. 1x1, 2x2, .. not sure if H and V binning will ever be unequal
    IMGSIZE  = WxH, eg. 3008x3008, 1920x1080, 2048x1536, ...
    """
    print(dedent(msg))
    exit(0)


def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", default=False, action="store_true")
    ap.add_argument(
        "--glob",
        default="*.fits",
        help="A glob(3) pattern used to match files to process. [%(default)s]",
    )
    ap.add_argument("-i", "--srcdir", default=".", help="Directory from which to read files: [%(default)s]")
    ap.add_argument("-o", "--outdir", default=DEFAULT_FORMAT, help="Output path format: [%(default)s]")
    ap.add_argument("-l", "--list-tokens", default=False, action="store_true")
    ap.add_argument("-v", "--verbose", default=False, action="store_true")
    ap.add_argument(
        dest="files",
        metavar="FILE",
        nargs="*",
        help="Files to process. If no files are given, the glob and srcdir will be used",
    )
    return ap.parse_args()


def rprint(d):
    for k, v in d.items():
        print(f"{k:8s} = {v}")
    print("")


def main():
    args = get_args()
    if args.list_tokens:
        list_tokens()

    records = []

    if not args.files:
        args.files = glob(args.glob, root_dir=args.srcdir, recursive=False)
    for filename in args.files:
        # XXX this is lossy
        fileheader = fitsio.read_header(os.path.join(args.srcdir, filename))
        rdict = {"FILENAME": filename}  # so that FILENAME comes first
        for x in fileheader.records():
            # print(x)
            if x["name"] in SRC_COLUMNS:
                rdict[x["name"]] = x["value"]

        rdict.update(fileheader)

        ix = f"{float(rdict.get('APTDIA',0)):.0f}:{float(rdict.get('FOCALLEN', 0)):.0f}"

        rdict["SCOPE"] = SCOPE_MAP.get(ix, "unknown")

        try:
            rdict["SITE"] = (rdict["SITELAT"], rdict["SITELONG"])
        except KeyError:
            pass

        rdict["RADEC"] = (rdict["RA"], rdict["DEC"])
        try:
            rdict["OBJRADEC"] = (rdict["OBJCTRA"].replace(" ", ":"), rdict["OBJCTDEC"].replace(" ", ":"))
        except KeyError:
            pass

        try:
            if rdict["PIXSIZE1"] == rdict["PIXSIZE2"]:
                rdict["PIXSIZE"] = rdict["PIXSIZE1"]
            else:
                rdict["PIXSIZE"] = (rdict["PIXSIZE1"], rdict["PIXSIZE1"])
        except KeyError:
            pass

        # nonstandard headers
        for f in ["EXP", "EXPOSURE", "XPOSURE"]:
            if rdict.get(f):
                rdict["EXPTIME"] = rdict[f]
                del rdict[f]

        if rdict.get("BINNING") is None:
            rdict["BINNING"] = f'{rdict["XBINNING"]}x{rdict["YBINNING"]}'
        else:
            rdict["BINNING"] = rdict["BINNING"].replace("*", "x")
        rdict["IMGSIZE"] = (rdict["NAXIS1"], rdict["NAXIS2"])

        # for k in DELETE_COLS:
        #     try:
        #         del rdict[k]
        #     except KeyError:
        #         pass

        # print(f"output format: {args.outdir}")
        nf = args.outdir.format(**rdict).replace(" ", "_")
        # print(nf)
        records.append(rdict)

        if args.verbose:
            for r in records:
                rprint(r)

        if args.move:
            os.makedirs(nf, exist_ok=True)
            os.rename(filename, os.path.join(nf, filename))
        print(f"os.rename('{filename}', '{nf}/{filename}')")


if __name__ == "__main__":
    main()
