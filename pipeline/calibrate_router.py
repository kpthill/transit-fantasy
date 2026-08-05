#!/usr/bin/env python3
"""Run the calibration OD pairs through the road router and report error
vs. the documented real-world estimates. Gate: median |error| <= 15%.

An ACCESS_MIN constant is added per trip (city-center local streets and
parking are not in the filtered graph).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import load_graph, build_adjacency, dijkstra, nearest_node  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ACCESS_MIN = 6.0


def main() -> None:
    pairs = json.loads((ROOT / "pipeline" / "calibration_pairs.json").read_text())["pairs"]
    coords, edges = load_graph()
    print(f"graph: {len(coords)} nodes, {len(edges)} edges", flush=True)
    adj = build_adjacency(coords, edges, peak=False)

    # group by source to reuse Dijkstra runs
    by_src = {}
    for p in pairs:
        by_src.setdefault(tuple(p["a"]), []).append(p)

    errors = []
    for src, plist in by_src.items():
        s = nearest_node(coords, *src)
        t0 = time.time()
        dist = dijkstra(adj, s)
        for p in plist:
            t = nearest_node(coords, *p["b"])
            mins = dist[t] / 60 + ACCESS_MIN
            err = (mins - p["minutes"]) / p["minutes"]
            errors.append(abs(err))
            print(f"{p['name']:22s} model {mins:5.0f}  real {p['minutes']:4d}  err {err:+.0%}"
                  f"   [dijkstra {time.time()-t0:.1f}s]", flush=True)
            t0 = time.time()
    errors.sort()
    med = errors[len(errors) // 2]
    print(f"\nmedian |err| = {med:.0%}  ({'PASS' if med <= 0.15 else 'FAIL'} vs 15% gate)")


if __name__ == "__main__":
    main()
