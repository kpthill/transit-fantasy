#!/usr/bin/env python3
"""Build site/data/network.json — the client-side fantasy-network router's
data: tier-2/3 station graph with per-segment run times from the speed
profile integrator, line headways, and tier-1 grid metadata for the
analytic model.

Speed profile (spec §2, notes/002): accel/decel 0.5 m/s² comfort standard;
vmax tier3 = 300 km/h (avg of 300–320 design), tier2 = 200 km/h. Per-stop
dwell+throat: tier3 3 min, tier2 1.5 min charged per intermediate stop.
Grade/curve speed reductions are NOT modeled segment-by-segment (folded
into the conservative vmax averages) — documented simplification.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data" / "network"
OUT = ROOT / "site" / "data" / "network.json"

PROFILE = {2: {"vmax": 200 / 3.6, "dwell": 1.5}, 3: {"vmax": 300 / 3.6, "dwell": 3.0}}
ACCEL = 0.5

# tier-1 analytic model constants (derived once from the same profile:
# 1 km spacing, vmax 80 km/h, accel 1.0, dwell 25 s → ~38 km/h effective)
TIER1 = {"effective_kmh": 38, "headway_min": 1.0, "transfer_min": 2.5,
         "walk_kmh": 4.8, "detour": 1.3}


def dist_m(a, b):
    c = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * c, (a[1] - b[1]) * 110540)


def seg_minutes(meters, tier):
    p = PROFILE[tier]
    v, a = p["vmax"], ACCEL
    d_ramp = v * v / a  # accel + decel distance combined
    if meters >= d_ramp:
        t = (meters - d_ramp) / v + 2 * v / a
    else:
        t = 2 * math.sqrt(meters / a)
    return t / 60


def parse_headway(h):
    if not h:
        return 15.0
    h = h.strip()
    if h.endswith("s"):
        return float(h.split()[0]) / 60
    return float(h.split()[0])


def main() -> None:
    stations = {}   # id -> {name, lon, lat, tier}
    edges = []
    lines = {}

    for path in sorted(DATA.glob("tier[23]*.geojson")):
        fc = json.loads(path.read_text())
        feats = fc["features"]
        st = {f["properties"]["id"]: f for f in feats if f["properties"]["ftype"] == "station"}
        for sid, f in st.items():
            gid = f"{path.stem}:{sid}"
            lon, lat = f["geometry"]["coordinates"]
            stations[gid] = {"name": f["properties"]["name"], "lon": lon, "lat": lat,
                             "tier": f["properties"]["tier"]}
        # station order along each line comes from the authored route
        spec = json.loads((ROOT / "network" / f"{path.stem}.json").read_text())
        for line in spec["lines"]:
            tier = spec["tier"]
            lines[line["name"]] = {"headway": parse_headway(line.get("headway")), "tier": tier}
            seq = [s["station"] for s in line["route"] if "station" in s]
            # geometry arc between stations from the compiled feature
            geom = next((f["geometry"]["coordinates"] for f in feats
                         if f["properties"]["ftype"] == "line" and f["properties"]["id"] == line["id"]), None)
            for a, b in zip(seq, seq[1:]):
                ca = spec["stations"][a]["coord"]
                cb = spec["stations"][b]["coord"]
                meters = arc_between(geom, ca, cb) if geom else dist_m(ca, cb)
                mins = seg_minutes(meters, tier) + PROFILE[tier]["dwell"]
                edges.append({"a": f"{path.stem}:{a}", "b": f"{path.stem}:{b}",
                              "min": round(mins, 1), "line": line["name"], "tier": tier})

    # merge co-located stations across files (same coords ~= same station)
    merged = {}
    alias = {}
    for gid, s in stations.items():
        key = (round(s["lon"], 3), round(s["lat"], 3))
        if key in merged:
            alias[gid] = merged[key]
        else:
            merged[key] = gid
            alias[gid] = gid
    for e in edges:
        e["a"] = alias[e["a"]]
        e["b"] = alias[e["b"]]
    keep = {alias[g] for g in stations}
    stations = {g: s for g, s in stations.items() if g in keep}

    grids = []
    for path in sorted(DATA.glob("tier1-*.geojson")):
        fc = json.loads(path.read_text())
        pts = [f["geometry"]["coordinates"] for f in fc["features"]
               if f["properties"]["ftype"] == "station"]
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        grids.append({"slug": path.stem, "bbox": [min(lons), min(lats), max(lons), max(lats)],
                      "file": f"network/{path.name}"})

    OUT.write_text(json.dumps({
        "stations": stations, "edges": edges, "lines": lines,
        "grids": grids, "tier1": TIER1,
    }))
    print(f"network.json: {len(stations)} stations, {len(edges)} edges, {len(grids)} grids")


def arc_between(geom, ca, cb):
    def nearest_arc(pt):
        best, acc, ba = 1e18, 0.0, 0.0
        for i in range(len(geom) - 1):
            seg = dist_m(geom[i], geom[i + 1])
            d = dist_m(geom[i], pt)
            if d < best:
                best, ba = d, acc
            acc += seg
        d = dist_m(geom[-1], pt)
        if d < best:
            ba = acc
        return ba
    return abs(nearest_arc(cb) - nearest_arc(ca)) or dist_m(ca, cb)


if __name__ == "__main__":
    main()
