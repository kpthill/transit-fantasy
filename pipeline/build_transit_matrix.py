#!/usr/bin/env python3
"""Current-transit travel-time matrices via the frequency-based model
(notes/007 amendment): graph over Cal-ITP stops with route ride edges
(speed by route x period), boarding waits from stop arrival frequency,
short walk transfers, and walk access from anchors.

Usage: python3 build_transit_matrix.py {offpeak|peak} [start [end]]
Writes pipeline/cache/matrix_transit_{period}.bin (uint16 minutes,
row-major over anchor indices; 65535 = unreachable).
"""
import heapq
import json
import math
import sys
import time
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"

WALK_MPS = 4.8 / 3.6 / 1.3      # walking speed over detour factor
ACCESS_MAX_M = 2000.0
TRANSFER_MAX_M = 300.0
DWELL_MIN = 0.4                  # minutes per intermediate stop
WAIT_CAP_MIN = 30.0
DEFAULT_MPH = {0: 15, 1: 25, 2: 30, 3: 11, 4: 12, 5: 8}  # by GTFS route_type


def dist_m(ax, ay, bx, by):
    c = math.cos(math.radians((ay + by) / 2))
    return math.hypot((ax - bx) * 111320 * c, (ay - by) * 110540)


def build(period):
    stops = json.loads((CACHE / "calitp_stops.json").read_text())
    routes = json.loads((CACHE / "calitp_routes.json").read_text())
    speeds = json.loads((CACHE / "calitp_speeds.json").read_text())

    sp = {}
    for r in speeds:
        if (r["period"] or "").lower().startswith(period[:4]) and r["mph"]:
            key = (r["agency"], r["route_id"])
            sp.setdefault(key, []).append(r["mph"])
    sp = {k: sum(v) / len(v) for k, v in sp.items()}

    # stop membership by (agency, route_id)
    members = {}
    for i, s in enumerate(stops):
        for rid in s["routes"]:
            rid = rid.strip()
            if rid:
                members.setdefault((s["agency"], rid), []).append(i)

    # wait (min) charged when boarding at a stop
    wait = []
    for s in stops:
        if s["n_arrivals"] and s["n_hours"]:
            headway = 60.0 * s["n_hours"] / s["n_arrivals"]
        else:
            headway = 60.0
        wait.append(min(headway / 2, WAIT_CAP_MIN))

    adj = [[] for _ in range(len(stops))]
    n_edges = 0
    for r in routes:
        key = (r["agency"], r["route_id"])
        idxs = members.get(key)
        if not idxs or len(idxs) < 2:
            continue
        shape = r["shape"]
        # arc positions along shape
        arc = [0.0]
        for a, b in zip(shape, shape[1:]):
            arc.append(arc[-1] + dist_m(a[0], a[1], b[0], b[1]))
        def arcpos(x, y):
            best, bi = 1e18, 0
            for k in range(len(shape)):
                d = dist_m(x, y, shape[k][0], shape[k][1])
                if d < best:
                    best, bi = d, k
            return arc[bi], best
        seq = []
        for i in idxs:
            s = stops[i]
            pos, off = arcpos(s["lon"], s["lat"])
            if off < 500:
                seq.append((pos, i))
        seq.sort()
        mph = sp.get(key) or DEFAULT_MPH.get(r["route_type"], 12)
        mpm = mph * 1609.34 / 60
        for (pa, ia), (pb, ib) in zip(seq, seq[1:]):
            ride = (pb - pa) / mpm + DWELL_MIN
            if ride <= 0:
                continue
            adj[ia].append((ib, ride))
            adj[ib].append((ia, ride))
            n_edges += 2

    # walk transfer edges via grid hash
    CELL = 0.004
    grid = {}
    for i, s in enumerate(stops):
        grid.setdefault((int(s["lon"] / CELL), int(s["lat"] / CELL)), []).append(i)
    n_tr = 0
    for i, s in enumerate(stops):
        cx, cy = int(s["lon"] / CELL), int(s["lat"] / CELL)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    d = dist_m(s["lon"], s["lat"], stops[j]["lon"], stops[j]["lat"])
                    if d <= TRANSFER_MAX_M:
                        walk = d / WALK_MPS / 60
                        adj[i].append((j, walk + wait[j]))
                        adj[j].append((i, walk + wait[i]))
                        n_tr += 2
    print(f"{period}: {len(stops)} stops, {n_edges} ride edges, {n_tr} transfer edges", flush=True)
    return stops, adj, wait, grid, CELL


def main():
    period = sys.argv[1]
    anchors = json.loads((ROOT / "site" / "data" / "anchors.json").read_text())["anchors"]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else len(anchors)
    stops, adj, wait, grid, CELL = build(period)

    # anchor -> nearby stops access lists
    def access(a):
        out = []
        cx, cy = int(a["lon"] / CELL), int(a["lat"] / CELL)
        r = int(ACCESS_MAX_M / 111320 / CELL * 1.6) + 1
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    d = dist_m(a["lon"], a["lat"], stops[j]["lon"], stops[j]["lat"])
                    if d <= ACCESS_MAX_M:
                        out.append((j, d / WALK_MPS / 60))
        return out

    acc = [access(a) for a in anchors]
    n = len(anchors)
    out_path = CACHE / f"matrix_transit_{period}.bin"
    mat = array("H", [65535]) * 0
    if out_path.exists() and lo > 0:
        mat = array("H")
        mat.frombytes(out_path.read_bytes())
    if len(mat) != n * n:
        mat = array("H", [65535] * (n * n))

    t0 = time.time()
    for si in range(lo, hi):
        dist = {}
        pq = []
        for j, wmin in acc[si]:
            v = wmin + wait[j]
            if v < dist.get(j, 1e18):
                dist[j] = v
                heapq.heappush(pq, (v, j))
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18) and nd < 600:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        # egress: stop -> anchor
        row = si * n
        for ti in range(n):
            best = 1e18
            for j, wmin in acc[ti]:
                dj = dist.get(j)
                if dj is not None and dj + wmin < best:
                    best = dj + wmin
            if best < 1e17:
                mat[row + ti] = min(65534, int(best + 0.5))
        if (si - lo) % 50 == 0:
            print(f"{si}/{hi} [{time.time()-t0:.0f}s]", flush=True)
    out_path.write_bytes(mat.tobytes())
    print(f"wrote {out_path.name}", flush=True)


if __name__ == "__main__":
    main()
