#!/usr/bin/env python3
"""Replace placeholder station names with cross-street names.

Placeholders are infill ("Geary 3") and terminal ("Sunset North Terminal")
stations. For each, query Overpass for named streets within ~90 m (one
batched query per city) and rename to "<Corridor> & <Cross Street>",
skipping streets that belong to the corridor itself. Falls back to keeping
the placeholder when nothing is found.

Usage: python3 pipeline/name_stations.py [slug ...]
"""
import json
import math
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "site" / "data" / "network"
CACHE_DIR = ROOT / "pipeline" / "cache"

sys.path.insert(0, str(ROOT / "pipeline"))
from cities import CITIES  # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "ca-fantasy-transit/0.1 (github.com/kpthill/transit-fantasy)"}
PLACEHOLDER = re.compile(r"( \d+$)|( (North|South|East|West) Terminal$)")


def strip_dir(name: str) -> str:
    for pref in ("North ", "South ", "East ", "West "):
        if name.startswith(pref):
            return name[len(pref):]
    return name


def fetch_nearby(slug: str, points: list[tuple[float, float]]) -> dict:
    cache = CACHE_DIR / f"{slug}_crossstreets.json"
    if cache.exists():
        return json.loads(cache.read_text())
    clauses = "".join(
        f'way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified"]'
        f'["name"](around:90,{lat:.5f},{lon:.5f});\n'
        for lon, lat in points)
    query = f"[out:json][timeout:180];(\n{clauses});out tags geom;"
    for attempt in range(5):
        try:
            r = requests.post(OVERPASS, data={"data": query}, headers=UA, timeout=240)
            r.raise_for_status()
            data = r.json()
            cache.write_text(json.dumps(data))
            return data
        except Exception as e:  # noqa: BLE001
            print(f"  overpass attempt {attempt + 1} failed: {e}")
            time.sleep(8 * (attempt + 1))
    raise SystemExit("overpass failed")


def main() -> None:
    slugs = sys.argv[1:] or list(CITIES)
    for slug in slugs:
        cfg = CITIES[slug]
        path = OUT_DIR / f"tier1-{slug}.geojson"
        if not path.exists():
            continue
        fc = json.loads(path.read_text())
        coslat = math.cos(math.radians(cfg["center_lat"]))

        def m(lon, lat):
            return lon * 111320 * coslat, lat * 110540

        # corridor street names to exclude as "cross" streets, per corridor label
        corridor_names = {label: {strip_dir(n) for p in parts for n in p.get("names", [])}
                          for label, _, parts in cfg["corridors"]}

        todo = [f for f in fc["features"]
                if f["properties"]["ftype"] == "station" and PLACEHOLDER.search(f["properties"]["name"])]
        if not todo:
            print(f"{slug}: no placeholders")
            continue
        data = fetch_nearby(slug, [tuple(f["geometry"]["coordinates"]) for f in todo])
        ways = []
        for el in data.get("elements", []):
            if el.get("type") == "way" and "geometry" in el:
                nm = el["tags"].get("name", "")
                pts = [m(g["lon"], g["lat"]) for g in el["geometry"]]
                ways.append((nm, pts))

        renamed = 0
        used = {f["properties"]["name"] for f in fc["features"] if f["properties"]["ftype"] == "station"}
        for f in todo:
            lon, lat = f["geometry"]["coordinates"]
            px, py = m(lon, lat)
            corridor = re.sub(PLACEHOLDER, "", f["properties"]["name"])
            exclude = corridor_names.get(corridor, set())
            best = None
            for nm, pts in ways:
                base = strip_dir(nm)
                if base in exclude or base == corridor:
                    continue
                d = min(math.hypot(px - x, py - y) for x, y in pts)
                if d < 95 and (best is None or d < best[0]):
                    best = (d, base)
            if best:
                new = f"{corridor} & {best[1]}"
                if new in used:
                    continue
                used.add(new)
                f["properties"]["name"] = new
                renamed += 1
        path.write_text(json.dumps(fc) + "\n")
        print(f"{slug}: renamed {renamed}/{len(todo)} placeholder stations")


if __name__ == "__main__":
    main()
