"""Road router: loads the extracted graph, builds time-weighted adjacency
for a speed profile, runs Dijkstra one-to-all.

Speed model (km/h). Off-peak defaults are calibrated against
calibration_pairs.json (spec 3.4, ±15% median gate). Peak applies
congestion multipliers to edges inside metro congestion bboxes —
modeled, not measured (spec 3.3).
"""
import gzip
import heapq
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "pipeline" / "cache" / "road_graph.json.gz"

SPEEDS = {
    "motorway": 105, "motorway_link": 60,
    "trunk": 88, "trunk_link": 55,
    "primary": 62, "primary_link": 45,
    "secondary": 48, "secondary_link": 40,
    "tertiary": 38,
}
MAXSPEED_CAP = 115
# Congestion zones (s, w, n, e) and peak multipliers by class group
CONGESTION_BBOXES = [
    (33.60, -118.60, 34.35, -117.20),   # LA basin + IE + OC
    (37.20, -122.55, 38.10, -121.80),   # Bay Area
    (32.55, -117.30, 33.10, -116.90),   # San Diego
    (38.40, -121.60, 38.75, -121.25),   # Sacramento
]
PEAK_MULT_FWY = 1.65
PEAK_MULT_ARTERIAL = 1.30
PEAK_MULT_ELSEWHERE = 1.05


def load_graph():
    with gzip.open(GRAPH, "rt") as fh:
        g = json.load(fh)
    return g["coords"], g["edges"]


def in_congestion(lon, lat):
    for s, w, n, e in CONGESTION_BBOXES:
        if s <= lat <= n and w <= lon <= e:
            return True
    return False


def build_adjacency(coords, edges, peak=False):
    n = len(coords)
    adj = [[] for _ in range(n)]
    for u, v, meters, hw, oneway, kmh in edges:
        speed = min(kmh, MAXSPEED_CAP) if kmh else SPEEDS.get(hw, 45)
        if peak:
            lon, lat = coords[u]
            if in_congestion(lon, lat):
                speed /= PEAK_MULT_FWY if hw.startswith(("motorway", "trunk")) else PEAK_MULT_ARTERIAL
            else:
                speed /= PEAK_MULT_ELSEWHERE
        secs = meters / (speed / 3.6)
        adj[u].append((v, secs))
        if not oneway:
            adj[v].append((u, secs))
    return adj


def dijkstra(adj, source):
    n = len(adj)
    dist = [float("inf")] * n
    dist[source] = 0.0
    pq = [(0.0, source)]
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
    return dist


def nearest_node(coords, lon, lat):
    best, bi = float("inf"), -1
    c = math.cos(math.radians(lat))
    for i, (x, y) in enumerate(coords):
        d = abs(x - lon) * c + abs(y - lat)  # cheap L1 prefilter
        if d < best:
            best, bi = d, i
    return bi
