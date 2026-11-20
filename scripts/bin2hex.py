#!/usr/bin/env python3
"""Convert a raw binary into a byte-per-line hex file for $readmemh."""
import sys
data = open(sys.argv[1], "rb").read()
open(sys.argv[2], "w").write("".join("%02x\n" % b for b in data))
