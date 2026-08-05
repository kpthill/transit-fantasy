#!/usr/bin/env python3
"""Generate the SF tier-1 grid from real street geometry via Overpass.

Corridors are hand-chosen arterial streets forming a deformed grid (see
notes/002). For each corridor we fetch all OSM ways matching its street
names, collapse them to a centerline (project points onto the corridor's
principal axis, bucket, average — robust against dual carriageways and
fragmented ways), and place stations at corridor crossings.

Output: site/data/network/tier1-sf.geojson
Cache: pipeline/cache/sf_streets.json (delete to re-fetch)
"""
import json
import math
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache" / "sf_streets.json"
OUT = ROOT / "site" / "data" / "network" / "tier1-sf.geojson"

BBOX = (37.703, -122.525, 37.815, -122.350)  # south, west, north, east
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {"User-Agent": "ca-fantasy-transit/0.1 (github.com/kpthill/transit-fantasy)"}

# label, orientation (ew/ns), OSM street names to stitch
CORRIDORS = [
    ("Geary",        "ew", ["Geary Boulevard", "Geary Street"]),
    ("Fulton",       "ew", ["Fulton Street"]),
    ("Judah",        "ew", ["Judah Street"]),
    ("Taraval",      "ew", ["Taraval Street"]),
    ("Ocean–Geneva", "ew", ["Ocean Avenue", "Geneva Avenue"]),
    ("California",   "ew", ["California Street"]),
    ("Union",        "ew", ["Union Street"]),
    ("Market",       "ew", ["Market Street"]),
    ("16th St",      "ew", ["16th Street"]),
    ("24th St",      "ew", ["24th Street"]),
    ("Sunset",       "ns", ["Sunset Boulevard"]),
    ("19th Ave",     "ns", ["19th Avenue", "Park Presidio Boulevard"]),
    ("Masonic",      "ns", ["Masonic Avenue"]),
    ("Divisadero",   "ns", ["Divisadero Street", "Castro Street"]),
    ("Fillmore",     "ns", ["Fillmore Street"]),
    ("Van Ness",     "ns", ["Van Ness Avenue", "South Van Ness Avenue"]),
    ("Mission",      "ns", ["Mission Street"]),
    ("3rd St",       "ns", ["3rd Street"]),
    ("Potrero",      "ns", ["Potrero Avenue"]),
    ("Embarcadero",  "ns", ["The Embarcadero"]),
]

BUCKET_M = 60.0  # centerline resolution along the principal axis


def fetch_streets() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    names = sorted({n for _, _, ns in CORRIDORS for n in ns})
    regex = "^(" + "|".join(n.replace(" ", "\\\\ ") for n in names) + ")$"
    # Overpass regex doesn't need space escaping; keep names verbatim.
    regex = "^(" + "|".join(names) + ")$"
    s, w, n, e = BBOX
    query = f"""
[out:json][timeout:120];
way["highway"]["name"~"{regex}"]({s},{w},{n},{e});
out geom;
"""
    import time
    data = None
    last_err = None
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        try:
            r = requests.post(url, data={"data": query}, headers=UA, timeout=180)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:  # noqa: BLE001 - retry any transport/HTTP error
            last_err = e
            print(f"overpass attempt {attempt + 1} via {url} failed: {e}")
            time.sleep(5 * (attempt + 1))
    if data is None:
        raise SystemExit(f"all overpass attempts failed: {last_err}")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data))
    return data


def mercator(lon: float, lat: float) -> tuple[float, float]:
    # local meters approximation around SF
    x = lon * 111320 * math.cos(math.radians(37.76))
    y = lat * 110540
    return x, y


def inv_mercator(x: float, y: float) -> tuple[float, float]:
    lon = x / (111320 * math.cos(math.radians(37.76)))
    lat = y / 110540
    return lon, lat


def principal_axis(points: list[tuple[float, float]]) -> tuple[float, float]:
    # 2D PCA (pure python): dominant eigenvector of the covariance matrix
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points) / n
    syy = sum((p[1] - my) ** 2 for p in points) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points) / n
    # eigenvector for the larger eigenvalue
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    lam = tr / 2 + math.sqrt(max(tr * tr / 4 - det, 0))
    if abs(sxy) > 1e-9:
        vx, vy = lam - syy, sxy
    elif sxx >= syy:
        vx, vy = 1.0, 0.0
    else:
        vx, vy = 0.0, 1.0
    norm = math.hypot(vx, vy)
    return vx / norm, vy / norm


def centerline(ways: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    pts = [mercator(lon, lat) for way in ways for lon, lat in way]
    ax, ay = principal_axis(pts)
    buckets: dict[int, list[tuple[float, float]]] = {}
    for x, y in pts:
        t = x * ax + y * ay
        buckets.setdefault(int(t // BUCKET_M), []).append((x, y))
    line = []
    for key in sorted(buckets):
        bp = buckets[key]
        line.append((sum(p[0] for p in bp) / len(bp), sum(p[1] for p in bp) / len(bp)))
    return [inv_mercator(x, y) for x, y in line]


def seg_intersect(p1, p2, p3, p4):
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < 1e-12:
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / denom
    u = ((p3[0] - p1[0]) * d1[1] - (p3[1] - p1[1]) * d1[0]) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (p1[0] + t * d1[0], p1[1] + t * d1[1])
    return None


def crossings(a: list, b: list):
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            hit = seg_intersect(a[i], a[i + 1], b[j], b[j + 1])
            if hit:
                return hit
    return None


def main() -> None:
    data = fetch_streets()
    by_name: dict[str, list[list[tuple[float, float]]]] = {}
    for el in data["elements"]:
        if el["type"] != "way" or "geometry" not in el:
            continue
        name = el.get("tags", {}).get("name")
        coords = [(g["lon"], g["lat"]) for g in el["geometry"]]
        by_name.setdefault(name, []).append(coords)

    def smooth(line, passes=2):
        for _ in range(passes):
            if len(line) < 3:
                return line
            line = [line[0]] + [
                ((line[i - 1][0] + line[i][0] + line[i + 1][0]) / 3,
                 (line[i - 1][1] + line[i][1] + line[i + 1][1]) / 3)
                for i in range(1, len(line) - 1)
            ] + [line[-1]]
        return line

    def join_parts(parts):
        # Concatenate per-street centerlines end-to-end, choosing orientations
        # that minimize junction gaps (streets in a corridor meet at ends).
        chain = parts[0]
        rest = parts[1:]
        while rest:
            best = None
            for idx, p in enumerate(rest):
                for flip_chain in (False, True):
                    for flip_p in (False, True):
                        c = chain[::-1] if flip_chain else chain
                        q = p[::-1] if flip_p else p
                        d = math.dist(mercator(*c[-1]), mercator(*q[0]))
                        if best is None or d < best[0]:
                            best = (d, idx, flip_chain, flip_p)
            _, idx, fc, fp = best
            if fc:
                chain = chain[::-1]
            q = rest.pop(idx)
            chain = chain + (q[::-1] if fp else q)
        return chain

    lines = {}
    for label, orient, names in CORRIDORS:
        parts = []
        for n in names:
            ways = by_name.get(n, [])
            if ways:
                parts.append(smooth(centerline(ways)))
        if not parts:
            print(f"WARNING: no OSM ways found for corridor {label}")
            continue
        lines[label] = (orient, join_parts(parts))

    features = []
    for label, (orient, line) in lines.items():
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in line]},
            "properties": {"ftype": "line", "id": f"sf-{label}", "name": f"{label} Line", "tier": 1,
                           "headway": "90 s"},
        })

    seen = []
    per_corridor: dict[str, list[tuple[float, str]]] = {lb: [] for lb in lines}

    def arc_pos(line_m: list[tuple[float, float]], px: float, py: float) -> float:
        # arc-length of the closest vertex (adequate at 60 m resolution)
        best, acc, best_acc = float("inf"), 0.0, 0.0
        prev = line_m[0]
        for v in line_m:
            acc += math.hypot(v[0] - prev[0], v[1] - prev[1])
            d = math.hypot(v[0] - px, v[1] - py)
            if d < best:
                best, best_acc = d, acc
            prev = v
        return best_acc

    lines_m = {lb: [mercator(*p) for p in ln] for lb, (_, ln) in lines.items()}

    def add_station(lon: float, lat: float, name: str, serving: list[str]) -> None:
        x, y = mercator(lon, lat)
        for sx, sy, _ in seen:
            if math.hypot(x - sx, y - sy) < 250:
                return
        seen.append((x, y, name))
        for lb in serving:
            per_corridor[lb].append((arc_pos(lines_m[lb], x, y), name))
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {"ftype": "station", "name": name, "tier": 1,
                           "lines": [f"{lb} Line" for lb in serving], "headway": "90 s"},
        })

    for ew_label, (o1, ew_line) in lines.items():
        if o1 != "ew":
            continue
        for ns_label, (o2, ns_line) in lines.items():
            if o2 != "ns":
                continue
            hit = crossings(ew_line, ns_line)
            if hit:
                add_station(hit[0], hit[1], f"{ew_label} & {ns_label}", [ew_label, ns_label])

    # Fill corridor stretches with no crossings (outer neighborhoods, line
    # ends) so spacing stays near the ~1 km guideline. Infill names are
    # placeholders; M2 snaps them to real cross-streets/POIs.
    GAP = 1400.0
    for lb, (_, line) in lines.items():
        lm = lines_m[lb]
        total = sum(math.hypot(lm[i + 1][0] - lm[i][0], lm[i + 1][1] - lm[i][1]) for i in range(len(lm) - 1))
        marks = sorted(t for t, _ in per_corridor[lb])
        anchors = [0.0] + marks + [total]
        targets = []
        for a, b in zip(anchors, anchors[1:]):
            gap = b - a
            if gap > GAP:
                k = int(gap // 1000)
                targets += [a + gap * (i + 1) / (k + 1) for i in range(k)]
        # walk the polyline to place targets
        acc, ti = 0.0, 0
        targets.sort()
        for i in range(len(lm) - 1):
            seg = math.hypot(lm[i + 1][0] - lm[i][0], lm[i + 1][1] - lm[i][1])
            while ti < len(targets) and acc + seg >= targets[ti]:
                f = (targets[ti] - acc) / seg if seg > 0 else 0
                x = lm[i][0] + f * (lm[i + 1][0] - lm[i][0])
                y = lm[i][1] + f * (lm[i + 1][1] - lm[i][1])
                lon, lat = inv_mercator(x, y)
                add_station(lon, lat, f"{lb} {ti + 1}", [lb])
                ti += 1
            acc += seg

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n")
    n_lines = sum(1 for f in features if f["properties"]["ftype"] == "line")
    n_sta = len(features) - n_lines
    print(f"tier1-sf.geojson: {n_lines} lines, {n_sta} stations")


if __name__ == "__main__":
    main()
