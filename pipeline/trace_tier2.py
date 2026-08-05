#!/usr/bin/env python3
"""Trace tier-2 line geometry along real rail (fallback: major roads).

For each authored tier-2 line, station-pair segments are routed over the
OSM railway=rail network fetched per file from Overpass (cached). If no
rail path exists within a sane detour (< 1.8x straight-line), retry on
motorway/trunk/primary roads; else keep the straight segment. Station
coordinates are preserved; traced paths connect to them with short
connectors. Output overwrites site/data/network/tier2-*.geojson (the
compiled straight-line versions from build_network.py).

Tier 3 is deliberately NOT traced: HSR is new dedicated alignment, so
gently-curved hand geometry is the realistic shape.

Usage: python3 pipeline/trace_tier2.py [tier2-bay ...]
"""
import heapq
import json
import math
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
NETWORK_DIR = ROOT / "network"
OUT_DIR = ROOT / "site" / "data" / "network"
CACHE_DIR = ROOT / "pipeline" / "cache"

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "ca-fantasy-transit/0.1 (github.com/kpthill/transit-fantasy)"}
MARGIN = 0.12  # degrees around each segment bbox
SNAP_M = 3000.0  # max distance from station to rail network
DETOUR = 1.8


def dist_m(a, b):
    c = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * c, (a[1] - b[1]) * 110540)


def fetch(stem, pairs, selector):
    tag = "rail" if "railway" in selector else "road"
    cache = CACHE_DIR / f"trace_{stem}_{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    boxes = []
    for a, b in pairs:
        s, n = sorted((a[1], b[1]))
        w, e = sorted((a[0], b[0]))
        boxes.append(f"way{selector}({s - MARGIN:.3f},{w - MARGIN:.3f},{n + MARGIN:.3f},{e + MARGIN:.3f});")
    query = "[out:json][timeout:300];(\n" + "\n".join(boxes) + "\n);out geom;"
    for attempt in range(5):
        try:
            r = requests.post(OVERPASS, data={"data": query}, headers=UA, timeout=320)
            r.raise_for_status()
            data = r.json()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
            return data
        except Exception as e:  # noqa: BLE001
            print(f"  overpass attempt {attempt + 1} failed: {e}")
            time.sleep(10 * (attempt + 1))
    return None


def build_graph(data):
    # nodes keyed by OSM node id -> (lon, lat); adjacency with edge lengths
    coords, adj = {}, {}
    for el in data.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el or "nodes" not in el:
            continue
        ids = el["nodes"]
        geo = [(g["lon"], g["lat"]) for g in el["geometry"]]
        for nid, pt in zip(ids, geo):
            coords[nid] = pt
        for u, v in zip(ids, ids[1:]):
            d = dist_m(coords[u], coords[v])
            adj.setdefault(u, []).append((v, d))
            adj.setdefault(v, []).append((u, d))
    return coords, adj


def nearest_node(coords, pt):
    best, bid = None, None
    for nid, c in coords.items():
        d = dist_m(c, pt)
        if best is None or d < best:
            best, bid = d, nid
    return bid, best


def route(coords, adj, a, b):
    sa, da = nearest_node(coords, a)
    sb, db = nearest_node(coords, b)
    if sa is None or da > SNAP_M or db > SNAP_M:
        return None
    # Dijkstra
    dist = {sa: 0.0}
    prev = {}
    pq = [(0.0, sa)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == sb:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if sb not in dist:
        return None
    straight = dist_m(a, b)
    if dist[sb] > DETOUR * straight + 2000:
        return None
    path = [sb]
    while path[-1] != sa:
        path.append(prev[path[-1]])
    path.reverse()
    return [coords[n] for n in path]


def compile_traced(stem):
    spec = json.loads((NETWORK_DIR / f"{stem}.json").read_text())
    stations = spec["stations"]
    lines_routes = []
    all_pairs = []
    for line in spec["lines"]:
        pts = []
        for step in line["route"]:
            pts.append(tuple(stations[step["station"]]["coord"]) if "station" in step else tuple(step["via"]))
        lines_routes.append((line, pts))
        all_pairs += list(zip(pts, pts[1:]))

    rail = fetch(stem, all_pairs, '["railway"="rail"]')
    road = fetch(stem, all_pairs, '["highway"~"motorway|trunk|primary"]')
    graphs = []
    for data in (rail, road):
        graphs.append(build_graph(data) if data else ({}, {}))

    features = []
    lines_by_station = {}
    stats = {"rail": 0, "road": 0, "straight": 0}
    for line, pts in lines_routes:
        geom = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            seg = None
            for kind, (coords, adj) in zip(("rail", "road"), graphs):
                if coords:
                    seg = route(coords, adj, a, b)
                    if seg:
                        stats[kind] += 1
                        break
            if not seg:
                stats["straight"] += 1
                seg = [a, b]
            geom += seg + [b]
        # thin out dense vertices (rail data is very fine-grained)
        thinned = [geom[0]]
        for p in geom[1:-1]:
            if dist_m(thinned[-1], p) > 120:
                thinned.append(p)
        thinned.append(geom[-1])
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[round(x, 5), round(y, 5)] for x, y in thinned]},
            "properties": {"ftype": "line", "id": line["id"], "name": line["name"],
                           "tier": spec["tier"], "headway": line.get("headway")},
        })
        for step in line["route"]:
            if "station" in step:
                lines_by_station.setdefault(step["station"], []).append(line["name"])

    for sid, meta in stations.items():
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": meta["coord"]},
            "properties": {"ftype": "station", "id": sid, "name": meta["name"],
                           "tier": spec["tier"], "lines": lines_by_station.get(sid, [])},
        })
    out = OUT_DIR / f"{stem}.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n")
    print(f"{stem}: segments rail={stats['rail']} road={stats['road']} straight={stats['straight']}")


if __name__ == "__main__":
    stems = sys.argv[1:] or sorted(p.stem for p in NETWORK_DIR.glob("tier2-*.json"))
    for s in stems:
        compile_traced(s)
