#!/usr/bin/env python3
"""Build the anchor set (spec §3.2, amended):
- OSM place nodes: city/town always; village if population >= 1000
- All tier-2/3 fantasy stations (station ids namespaced by file)
- Commercial airports (site/data/airports.json)
- Current-transit hubs: busiest Cal-ITP stops (n_arrivals >= HUB_MIN),
  deduped to >= 700 m spacing, capped to keep total anchors ~<= 4500.

Output: site/data/anchors.json  {anchors: [{id, name, lon, lat, kind}]}
Row shards later index anchors by array position.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"
OUT = ROOT / "site" / "data" / "anchors.json"

HUB_MIN_ARRIVALS = 120
HUB_SPACING_M = 700
TOTAL_CAP = 4500


def dist_m(a, b):
    c = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * c, (a[1] - b[1]) * 110540)


def main() -> None:
    anchors = []
    seen_names = set()

    # places
    for p in json.loads((CACHE / "places.json").read_text()):
        pop = int("".join(ch for ch in p["population"] if ch.isdigit()) or 0)
        if p["place"] in ("city", "town") or pop >= 1000:
            key = (p["name"], round(p["lon"], 1), round(p["lat"], 1))
            if not p["name"] or key in seen_names:
                continue
            seen_names.add(key)
            anchors.append({"id": f"pl-{len(anchors)}", "name": p["name"],
                            "lon": p["lon"], "lat": p["lat"], "kind": "place",
                            "pop": pop})

    # fantasy stations (tier 2/3)
    for f in sorted((ROOT / "network").glob("tier*.json")):
        spec = json.loads(f.read_text())
        for sid, meta in spec["stations"].items():
            anchors.append({"id": f"{f.stem}-{sid}", "name": meta["name"],
                            "lon": meta["coord"][0], "lat": meta["coord"][1],
                            "kind": f"station{spec['tier']}"})

    # airports
    ap = json.loads((ROOT / "site" / "data" / "airports.json").read_text())
    for a in ap["airports"]:
        anchors.append({"id": f"ap-{a['code']}", "name": a["name"],
                        "lon": a["lon"], "lat": a["lat"], "kind": "airport"})

    # transit hubs (busiest current stops, spaced)
    stops = json.loads((CACHE / "calitp_stops.json").read_text())
    stops.sort(key=lambda s: -(s["n_arrivals"] or 0))
    CELL = 0.01  # ~1 km grid for spacing checks
    grid = {}

    def cell(pt):
        return (int(pt[0] / CELL), int(pt[1] / CELL))

    def near(pt):
        cx, cy = cell(pt)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy), ()):
                    if dist_m(pt, q) < HUB_SPACING_M:
                        return True
        return False

    for a in anchors:
        grid.setdefault(cell((a["lon"], a["lat"])), []).append((a["lon"], a["lat"]))
    hubs = 0
    budget = TOTAL_CAP - len(anchors)
    for s in stops:
        if hubs >= budget or (s["n_arrivals"] or 0) < HUB_MIN_ARRIVALS:
            break
        pt = (s["lon"], s["lat"])
        if near(pt):
            continue
        grid.setdefault(cell(pt), []).append(pt)
        anchors.append({"id": f"hub-{hubs}", "name": s["name"] or "Transit hub",
                        "lon": s["lon"], "lat": s["lat"], "kind": "hub"})
        hubs += 1

    OUT.write_text(json.dumps({"anchors": anchors}))
    kinds = {}
    for a in anchors:
        kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
    print(f"{len(anchors)} anchors: {kinds}")


if __name__ == "__main__":
    main()
