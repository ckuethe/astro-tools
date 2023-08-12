#!/usr/bin/env python
# coding: utf-8
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 syn=python

from argparse import ArgumentParser, Namespace
import fitsio
from fitsio import FITS
from fitsio.hdu.image import ImageHDU

from glob import glob
import re
from typing import List

helptext = """
Headers one might want to patch with this tool:

TELESCOP
========
Ekos wrongly puts the mount here. The Electromagnetic Collector product should go here,
eg.  "Goldstone 30m", "SV503 70ED", "Askar V", "Celestron C11 Edge", "JWST". This is
where an electromagnetic rubber meets the astronomical road.

Note that multiple INSTRUMEnts may share a TELESCOPe depending on the signal path.

MOUNT
=====
The pointy bit which aims the EMC at the object. This could be absent or empty if not
tracked; or a descriptive string like "Goldstone", "Celestron Advanced VX", "JWST",
"Hubble ;)", "VLA sub-array 3"

CAMERA
======
Alias for INSTRUME

INSTRUME
========
Now that signal from the universe has reached our observatory, this is the device
with an ADC that turns electromagnetic radiation into numbers, eg. "HackRF",
"RTLSDRv3" (tuners), "NIRCam", "ZWO ASI 533MC PRO", "KAI-29050" (cameras), "RC-102",
"Chandra" (Ionizing radiation counters)

FOCALLEN, APTDIA
================
Mostly used to compute field of view for an optical system. Also affected by BINNING

BINNNING, DECIMATION
====================
Depending on the instrument, some resolution reduction in exchange for better SNR.

LENS
====
Supplementary header for a optical system, particularly for recording reducers, flatteners,
extenders, barlows, HyperStars... "SV193" or "Celestron 0.63x", perhaps.

FILTER
======
The Dwarf II has an integral IR-Cut filter, but is often used with a visible optical
filter such as "UHC", "L-eXtreme", "ZWO Dual Narrowband". Thus, multiple FILTER entries
may be present.

This would also be present in a radio telescope if you wanted to record any special RF
filters. Which Minicircuits HPF/LPF/BPF/NF are you using?

ORIGIN
======
DwarfII has "DWARFLAB" here. Use this for the software that created this file, eg "KStars 3.6.6"

EKOS-TR
========
I made this up based on what Ekos does. An Optical Train contains a bunch of
equipment. For the sake of simplicity I have my Optical Trains named after their
telescope, lens, and instrument: "SV503+SV193+ASI533" or "Askar V 80+1.2x 600mm",
"Orion Miniguide+ASI290MM". These are sufficient to coarsely classify images that
must be processed differently.

An all-in-one device such as the Dwarflab DwarfII or the ZWO Seestar S50 might have
the same value for both the MOUNT and TELESCOP headers since they are inseparable.

kvpairs are:
(?P<key>[A-Z][A-Z0-9_-]{,7})[/:=](?P<value>.+?)$

"""


def get_args() -> Namespace:
    ap = ArgumentParser(description="A very dangerous utility to bulk edit FITS headers")
    ap.add_argument(
        "-g",
        "--glob",
        type=str,
        default="*.fits",
        help="File pattern to match [%(default)s]",
    )
    ap.add_argument(
        "-k",
        "--kvpair",
        action="append",
        metavar="K=V",
        default=[],
        help="key-value pair, separated by '/', ':', or '='",
    )
    ap.add_argument(
        "--update",
        default=False,
        action="store_true",
        help="updates won't be written without this flag",
    )
    ap.add_argument(
        dest="files",
        metavar="FITS",
        nargs="*",
        help="Only operate on the specified files",
    )
    return ap.parse_args()


def drprint(d):
    "dictionary record print"
    for k, v in d.items():
        print(f"{k:8s} = {v}")
    print("")


def split_kvpairs(kv) -> list:
    "convert kvpair arg to a list of name and value dicts for header insertion"
    rv = []
    for x in kv:
        m = re.search("^(?P<name>[0-9A-Z_-]{,8})[/:=](?P<value>.+?)\s*$", x)
        if m and len(x) <= 81:
            rv.append(m.groupdict())
    return rv


def main():
    args = get_args()

    if not args.files:
        args.files = glob(args.glob)

    args.kvpairs = split_kvpairs(args.kvpair)

    iomode = "rw" if args.update else "r"
    for filename in args.files:
        with FITS(filename=filename, mode=iomode, trim_strings=True) as fitsfile:
            image: ImageHDU = fitsfile[0]
            existing_headers = image.read_header_list()
            print(f"{filename}:")
            for kv in args.kvpairs:
                if args.update:
                    image.write_key(name=kv["name"], value=kv["value"])

                print(f"    {kv}")
            print()
            fitsfile.close()


if __name__ == "__main__":
    main()
