#!/usr/bin/env python
# coding: utf-8
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 syn=python

import argparse
import fitsio
import json
from math import nan


def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-a", "--average", type=str, help="Column to average")
    ap.add_argument("-S", "--sum", type=str, help="Column to add")
    ap.add_argument("-k", "--column", action="append", default=[])
    ap.add_argument("-j", "--json", default=False, action="store_true")
    ap.add_argument("-s", "--summary", default=False, action="store_true")
    ap.add_argument("-v", "--verbose", default=False, action="store_true")
    ap.add_argument(dest="files", metavar="FILE", nargs="+")
    return ap.parse_args()


def rprint(d):
    for k, v in d.items():
        print(f"{k:8s} = {v}")
    print("")


def main():
    args = get_args()
    if args.summary:
        args.column = ["EXPTIME", "CCD-TEMP", "OFFSET", "GAIN", "INSTRUME", "NAXIS", "NAXIS1", "NAXIS2"]
    accumulator = []
    records = []
    for filename in args.files:
        fileheader = dict(fitsio.read_header(filename))
        rdict = {"FILENAME": filename}  # so that FILENAME comes first
        if args.column:
            for k in list(fileheader.keys()):
                if k not in args.column:
                    del fileheader[k]

        rdict.update(fileheader)
        records.append(rdict)
        accumulator.append(rdict.get(args.average, nan))

    if args.verbose or args.summary:
        if args.json:
            print(json.dumps(records, sort_keys=True, indent=2))
        else:
            for r in records:
                rprint(r)

    if args.average:
        avg = sum(accumulator) / len(args.files)
        print(f"Average {args.average} = {avg:.2f}")

    if args.sum:
        avg = sum(accumulator)
        print(f"Average {args.sum} = {avg:.2f}")


if __name__ == "__main__":
    main()
