#!/usr/bin/env python3
"""Merge matrix chunks and emit per-anchor row shards for the site.

Input (pipeline/cache/):
  chunks/drive_offpeak_{lo}_{hi}.bin, chunks/drive_peak_*.bin
  matrix_transit_offpeak.bin, matrix_transit_peak.bin
Output: site/data/rows/{i}.bin = uint16 x 4n:
  [driveOff row][drivePeak row][transitOff row][transitPeak row]
"""
import json
import re
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"
OUT = ROOT / "site" / "data" / "rows"


def load_drive(profile, n):
    mat = array("H", [65535] * (n * n))
    pat = re.compile(rf"drive_{profile}_(\d+)_(\d+)\.bin")
    found = 0
    for f in sorted((CACHE / "chunks").glob(f"drive_{profile}_*.bin")):
        m = pat.match(f.name)
        lo, hi = int(m.group(1)), int(m.group(2))
        chunk = array("H")
        chunk.frombytes(f.read_bytes())
        mat[lo * n:hi * n] = chunk
        found += hi - lo
    print(f"drive_{profile}: {found}/{n} rows from chunks")
    return mat


def load_transit(period, n):
    mat = array("H", [65535] * (n * n))
    pat = re.compile(rf"transit_{period}_(\d+)_(\d+)\.bin")
    found = 0
    for f in sorted((CACHE / "chunks").glob(f"transit_{period}_*.bin")):
        m = pat.match(f.name)
        lo, hi = int(m.group(1)), int(m.group(2))
        chunk = array("H")
        chunk.frombytes(f.read_bytes())
        mat[lo * n:hi * n] = chunk
        found += hi - lo
    print(f"transit_{period}: {found}/{n} rows from chunks")
    return mat


def main() -> None:
    anchors = json.loads((ROOT / "site" / "data" / "anchors.json").read_text())["anchors"]
    n = len(anchors)
    d_off = load_drive("offpeak", n)
    d_peak = load_drive("peak", n)
    t_off = load_transit("offpeak", n)
    t_peak = load_transit("peak", n)
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        row = array("H")
        for mat in (d_off, d_peak, t_off, t_peak):
            row.extend(mat[i * n:(i + 1) * n])
        (OUT / f"{i}.bin").write_bytes(row.tobytes())
    print(f"wrote {n} shards of {8 * n} bytes each")


if __name__ == "__main__":
    main()
