#!/usr/bin/env python3
"""Extract a routing graph (and place nodes) from the OSM California PBF.

Pass 1 (ways): keep highways in CLASSES statewide, plus tertiary inside
the tier-1 city bboxes. Collect referenced node ids.
Pass 2 (nodes): coordinates for referenced nodes; also collect
place=city|town|village nodes with population tags (for anchors).

Output (pipeline/cache/):
  road_graph.json.gz  {nodes: {id: [lon,lat]} as parallel arrays,
                       edges: [u_idx, v_idx, meters, class, oneway]}
  places.json         [{name, lon, lat, place, population}]

Degree-2 chain contraction keeps the graph small (~hundreds of k edges).
"""
import gzip
import json
import math
import sys
import time
from array import array
from bisect import bisect_left
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osm_pbf import iter_groups  # noqa: E402
from cities import CITIES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PBF = ROOT / "pipeline" / "cache" / "california-latest.osm.pbf"
OUT_GRAPH = ROOT / "pipeline" / "cache" / "road_graph.json.gz"
OUT_PLACES = ROOT / "pipeline" / "cache" / "places.json"

CLASSES = {"motorway", "motorway_link", "trunk", "trunk_link",
           "primary", "primary_link", "secondary", "secondary_link"}
TERTIARY_BBOXES = [cfg["bbox"] for cfg in CITIES.values()]


def in_tertiary_bbox(lat, lon):
    for s, w, n, e in TERTIARY_BBOXES:
        if s <= lat <= n and w <= lon <= e:
            return True
    return False


def main() -> None:
    t0 = time.time()
    kept_ways = []  # (refs, class, oneway, maxspeed_kmh)
    need = set()
    nways = 0
    for kind, payload in iter_groups(PBF, want_dense=False, want_ways=True):
        for wid, tags, refs in payload:
            hw = tags.get("highway")
            if hw is None or len(refs) < 2:
                continue
            nways += 1
            if hw not in CLASSES and hw != "tertiary":
                continue
            ms = tags.get("maxspeed", "")
            kmh = 0
            if ms[:2].isdigit():
                v = int("".join(ch for ch in ms.split(";")[0] if ch.isdigit()) or 0)
                kmh = round(v * 1.609) if "mph" in ms else v
            oneway = 1 if tags.get("oneway") in ("yes", "1", "true") or hw == "motorway" else 0
            if tags.get("oneway") == "-1":
                refs = refs[::-1]
                oneway = 1
            kept_ways.append((refs, hw, oneway, kmh))
            need.update(refs)
    print(f"pass1: {nways} highway ways scanned, {len(kept_ways)} kept, "
          f"{len(need)} node refs [{time.time()-t0:.0f}s]", flush=True)

    need_sorted = array("q", sorted(need))
    need.clear()
    n = len(need_sorted)
    lons = array("d", bytes(8 * n))
    lats = array("d", bytes(8 * n))
    have = bytearray(n)
    places = []

    t1 = time.time()
    for kind, payload in iter_groups(PBF, want_dense=True, want_ways=False):
        ids, plats, plons, keyvals, strings = payload
        # coordinate lookup for graph nodes
        j = bisect_left(need_sorted, ids[0])
        for k in range(len(ids)):
            nid = ids[k]
            while j < n and need_sorted[j] < nid:
                j += 1
            if j < n and need_sorted[j] == nid:
                lons[j] = plons[k]
                lats[j] = plats[k]
                have[j] = 1
        # place nodes from keyvals (tags only exist where keyvals has runs)
        if keyvals:
            idx = 0
            node_i = 0
            tags = {}
            while idx < len(keyvals):
                if keyvals[idx] == 0:
                    if tags.get("place") in ("city", "town", "village"):
                        places.append({
                            "name": tags.get("name", ""),
                            "lon": round(plons[node_i], 5),
                            "lat": round(plats[node_i], 5),
                            "place": tags["place"],
                            "population": tags.get("population", ""),
                        })
                    tags = {}
                    node_i += 1
                    idx += 1
                else:
                    k_ = strings[keyvals[idx]]
                    v_ = strings[keyvals[idx + 1]]
                    if k_ in ("place", "name", "population"):
                        tags[k_] = v_
                    idx += 2
    missing = n - sum(have)
    print(f"pass2: coords for {n - missing}/{n} nodes ({missing} missing), "
          f"{len(places)} places [{time.time()-t1:.0f}s]", flush=True)

    idx_of = {nid: i for i, nid in enumerate(need_sorted)}

    # usage count for chain contraction
    usage = bytearray(n)
    for refs, _, _, _ in kept_ways:
        for r in refs:
            i = idx_of[r]
            if usage[i] < 250:
                usage[i] += 1

    def dist(i, jj):
        c = math.cos(math.radians((lats[i] + lats[jj]) / 2))
        return math.hypot((lons[i] - lons[jj]) * 111320 * c, (lats[i] - lats[jj]) * 110540)

    # contract: emit edges between "keep" nodes (endpoints, junctions)
    node_used = {}
    edges = []
    for refs, hw, oneway, kmh in kept_ways:
        idxs = [idx_of[r] for r in refs if have[idx_of[r]]]
        if len(idxs) < 2:
            continue
        if hw == "tertiary" and not in_tertiary_bbox(lats[idxs[0]], lons[idxs[0]]):
            continue
        chain_start = 0
        acc = 0.0
        for k in range(1, len(idxs)):
            acc += dist(idxs[k - 1], idxs[k])
            if k == len(idxs) - 1 or usage[idxs[k]] > 1:
                u, v = idxs[chain_start], idxs[k]
                if u != v and acc > 0:
                    for node in (u, v):
                        if node not in node_used:
                            node_used[node] = len(node_used)
                    edges.append((node_used[u], node_used[v], round(acc), hw, oneway, kmh))
                chain_start = k
                acc = 0.0

    coords = [None] * len(node_used)
    for orig_i, new_i in node_used.items():
        coords[new_i] = (round(lons[orig_i], 5), round(lats[orig_i], 5))

    with gzip.open(OUT_GRAPH, "wt") as fh:
        json.dump({"coords": coords, "edges": edges}, fh)
    OUT_PLACES.write_text(json.dumps(places))
    print(f"graph: {len(coords)} nodes, {len(edges)} edges -> {OUT_GRAPH.name} "
          f"[total {time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
