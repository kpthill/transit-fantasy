#!/usr/bin/env python3
"""Compile authored network definition files into GeoJSON for the site.

Authored format (network/*.json):
{
  "tier": 3,
  "stations": {"id": {"name": "...", "coord": [lon, lat]}, ...},
  "lines": [
    {"id": "...", "name": "...", "headway": "15 min",
     "route": [{"station": "id"} | {"via": [lon, lat]}, ...]}
  ]
}

Output: one FeatureCollection per input file, LineString per line plus one
Point per station (with the list of lines serving it), written to
site/data/network/<name>.geojson. Also refreshes index.json group file lists
based on what exists.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NETWORK_DIR = ROOT / "network"
OUT_DIR = ROOT / "site" / "data" / "network"


def compile_file(path: Path) -> dict:
    spec = json.loads(path.read_text())
    stations = spec["stations"]
    features = []
    lines_by_station: dict[str, list[str]] = {}

    for line in spec["lines"]:
        coords = []
        for step in line["route"]:
            if "station" in step:
                sid = step["station"]
                if sid not in stations:
                    sys.exit(f"{path.name}: line {line['id']} references unknown station {sid!r}")
                coords.append(stations[sid]["coord"])
                lines_by_station.setdefault(sid, []).append(line["name"])
            else:
                coords.append(step["via"])
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "ftype": "line",
                "id": line["id"],
                "name": line["name"],
                "tier": spec["tier"],
                "headway": line.get("headway"),
            },
        })

    for sid, meta in stations.items():
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": meta["coord"]},
            "properties": {
                "ftype": "station",
                "id": sid,
                "name": meta["name"],
                "tier": spec["tier"],
                "lines": lines_by_station.get(sid, []),
            },
        })

    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(NETWORK_DIR.glob("*.json")):
        out = OUT_DIR / f"{path.stem}.geojson"
        out.write_text(json.dumps(compile_file(path)) + "\n")
        print(f"{path.name} -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
