#!/usr/bin/env python3
"""Drive-time matrices over the road graph, one row per anchor.

Usage: python3 build_drive_matrices.py {offpeak|peak} lo hi
Writes pipeline/cache/chunks/drive_{profile}_{lo}_{hi}.bin — uint16
minutes for rows lo..hi (65535 unreachable). Chunks are merged by
build_shards.py. Snap: nearest graph node within 12 km (grid hash).
"""
import heapq
import json
import math
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import load_graph, build_adjacency  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"


def main():
    profile = sys.argv[1]
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    anchors = json.loads((ROOT / "site" / "data" / "anchors.json").read_text())["anchors"]
    hi = min(hi, len(anchors))
    coords, edges = load_graph()
    adj = build_adjacency(coords, edges, peak=(profile == "peak"))
    n = len(anchors)

    CELL = 0.02
    grid = {}
    for i, (x, y) in enumerate(coords):
        grid.setdefault((int(x / CELL), int(y / CELL)), []).append(i)

    def snap(lon, lat):
        cx, cy = int(lon / CELL), int(lat / CELL)
        best, bi = 1e18, -1
        for ring in range(0, 8):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue
                    for j in grid.get((cx + dx, cy + dy), ()):
                        x, y = coords[j]
                        c = math.cos(math.radians(lat))
                        d = math.hypot((x - lon) * 111320 * c, (y - lat) * 110540)
                        if d < best:
                            best, bi = d, j
            if bi >= 0 and ring >= 2:
                break
        return bi if best < 12000 else -1

    snaps = [snap(a["lon"], a["lat"]) for a in anchors]
    nn = len(coords)
    out = array("H", [65535] * ((hi - lo) * n))
    t0 = time.time()
    for k, si in enumerate(range(lo, hi)):
        src = snaps[si]
        if src < 0:
            continue
        dist = [float("inf")] * nn
        dist[src] = 0.0
        pq = [(0.0, src)]
        push, pop = heapq.heappush, heapq.heappop
        while pq:
            d, u = pop(pq)
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    push(pq, (nd, v))
        base = k * n
        for ti in range(n):
            t = snaps[ti]
            if t >= 0 and dist[t] < float("inf"):
                out[base + ti] = min(65534, int(dist[t] / 60 + 0.5))
        if k % 25 == 0:
            print(f"{profile} {si}/{hi} [{time.time()-t0:.0f}s]", flush=True)
    (CACHE / "chunks").mkdir(exist_ok=True)
    (CACHE / "chunks" / f"drive_{profile}_{lo}_{hi}.bin").write_bytes(out.tobytes())
    print(f"wrote drive_{profile}_{lo}_{hi}.bin", flush=True)


if __name__ == "__main__":
    main()
