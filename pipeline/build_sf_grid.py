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
NETWORK_DIR = ROOT / "network"
OUT = ROOT / "site" / "data" / "network" / "tier1-sf.geojson"

BBOX = (37.703, -122.525, 37.815, -122.350)  # south, west, north, east
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {"User-Agent": "ca-fantasy-transit/0.1 (github.com/kpthill/transit-fantasy)"}

# Corridors are chains of parts, joined in order; gaps between consecutive
# parts are drawn as straight connectors (= tunnels under hills/parks — per
# Kevin 2026-08-05: paint the line wherever the tunnel goes, lines must
# cross Twin Peaks etc., not die at the hills). A part is a list of OSM
# street names, optionally with a bbox (s, w, n, e) to disambiguate.
def P(names, bbox=None):
    return {"names": names if isinstance(names, list) else [names], "bbox": bbox}


def PTS(points):
    """Literal coordinate part (e.g. an extension to a hub off any street)."""
    return {"points": points}

CORRIDORS = [
    # East–west, full width of the city where terrain-sensible
    ("Geary",      "ew", [P("Point Lobos Avenue"), P("Geary Boulevard"), P("Geary Street"),
                          PTS([[-122.3927, 37.7897]])]),  # extend to Transbay hub
    ("Fulton",     "ew", [P("Fulton Street")]),
    ("Judah",      "ew", [P("Judah Street"), P("Duboce Avenue")]),          # Sunset Tunnel
    ("Taraval",    "ew", [P("Taraval Street"), P("West Portal Avenue"),
                          P("Castro Street", (37.760, -122.437, 37.7627, -122.433))]),  # Twin Peaks Tunnel to Castro/Market
    ("Vicente–24th", "ew", [P("Vicente Street"), P("24th Street")]),  # Mt Davidson tunnel
    ("Ocean",      "ew", [P("Ocean Avenue"), P("Geneva Avenue")]),
    ("California", "ew", [P("California Street")]),
    ("Union",      "ew", [P("Union Street")]),
    ("Market",     "ew", [P("Portola Drive"), P("Market Street")]),
    ("16th St",    "ew", [P("Parnassus Avenue"), P("16th Street")]),        # Corona Heights tunnel
    # North–south
    ("Sunset",     "ns", [P("Sunset Boulevard"), P("36th Avenue", (37.771, -122.51, 37.79, -122.49))]),
    ("9th Ave",    "ns", [P("9th Avenue")]),
    ("19th Ave",   "ns", [P("Junipero Serra Boulevard", (37.703, -122.48, 37.735, -122.46)),
                          P("19th Avenue"), P("Park Presidio Boulevard")]),
    ("Masonic",    "ns", [P("Clayton Street"), P("Masonic Avenue"), P("Presidio Avenue")]),
    ("Divisadero", "ns", [P("San Jose Avenue", (37.703, -122.46, 37.742, -122.42)),
                          P("Castro Street", (37.741, -122.44, 37.769, -122.43)),
                          P("Divisadero Street")]),
    ("Fillmore",   "ns", [P("Church Street"), P("Fillmore Street")]),
    ("Van Ness",   "ns", [P("South Van Ness Avenue"), P("Van Ness Avenue")]),
    ("Polk",       "ns", [P("Polk Street")]),
    ("Mission",    "ns", [P("Mission Street")]),
    ("Stockton",   "ns", [P("4th Street", (37.768, -122.41, 37.79, -122.39)), P("Stockton Street")]),
    ("Columbus",   "ns", [P("3rd Street"), P("Kearny Street"), P("Columbus Avenue")]),
    ("Potrero",    "ns", [P("Bayshore Boulevard", (37.703, -122.42, 37.75, -122.39)),
                          P("Potrero Avenue"), P("10th Street", (37.768, -122.42, 37.78, -122.40))]),
    ("Embarcadero", "ns", [P("The Embarcadero")]),
]

BUCKET_M = 60.0  # centerline resolution along the principal axis


def all_names() -> list[str]:
    return sorted({n for _, _, parts in CORRIDORS for p in parts for n in p.get("names", [])})


def fetch_streets() -> dict:
    import hashlib
    names = all_names()
    key = hashlib.md5("|".join(names).encode()).hexdigest()[:12]
    cache = CACHE.with_name(f"sf_streets_{key}.json")
    if cache.exists():
        return json.loads(cache.read_text())
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
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
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
        # Concatenate part centerlines IN SPEC ORDER, flipping each to
        # minimize the junction gap. Gaps become straight connectors —
        # that's how tunnels under hills/parks get painted.
        chain = list(parts[0])
        for q in parts[1:]:
            best = None
            for flip_chain in (False, True):
                for flip_q in (False, True):
                    c = chain[::-1] if flip_chain else chain
                    p = q[::-1] if flip_q else q
                    d = math.dist(mercator(*c[-1]), mercator(*p[0]))
                    if best is None or d < best[0]:
                        best = (d, flip_chain, flip_q)
            _, fc, fq = best
            if fc:
                chain = chain[::-1]
            chain = chain + (list(q[::-1]) if fq else list(q))
        return chain

    def in_bbox(lon, lat, bbox):
        s, w, n, e = bbox
        return s <= lat <= n and w <= lon <= e

    def rdp(pts_m, eps):
        # Douglas–Peucker in meters: kills centerline wobble/kinks while
        # keeping the alignment on the street.
        if len(pts_m) < 3:
            return pts_m
        def dseg(p, a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            l2 = dx * dx + dy * dy
            t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
        keep = [False] * len(pts_m)
        keep[0] = keep[-1] = True
        stack = [(0, len(pts_m) - 1)]
        while stack:
            i, j = stack.pop()
            if j <= i + 1:
                continue
            k, dm = max(((k, dseg(pts_m[k], pts_m[i], pts_m[j])) for k in range(i + 1, j)),
                        key=lambda kv: kv[1])
            if dm > eps:
                keep[k] = True
                stack += [(i, k), (k, j)]
        return [p for p, f in zip(pts_m, keep) if f]

    lines = {}
    for label, orient, part_specs in CORRIDORS:
        parts = []
        for spec in part_specs:
            if "points" in spec:
                parts.append(spec["points"])
                continue
            ways = [w for n in spec["names"] for w in by_name.get(n, [])]
            if spec["bbox"]:
                ways = [[pt for pt in way if in_bbox(pt[0], pt[1], spec["bbox"])] for way in ways]
                ways = [w for w in ways if len(w) >= 2]
            if ways:
                parts.append(smooth(centerline(ways)))
            else:
                print(f"WARNING: corridor {label}: no ways for part {spec['names']}")
        if not parts:
            print(f"WARNING: no OSM ways found for corridor {label}")
            continue
        chain = join_parts(parts)
        chain_m = rdp([mercator(*p) for p in chain], 25.0)
        lines[label] = (orient, smooth([inv_mercator(x, y) for x, y in chain_m], passes=2))

    # Bend corridors into nearby tier-2/3 hub stations so the urban grid
    # physically meets the intercity network (e.g. Transbay).
    hubs = {}
    for fn in ("tier3.json", "tier2-bay.json"):
        spec = json.loads((NETWORK_DIR / fn).read_text())
        for meta in spec["stations"].values():
            lon, lat = meta["coord"]
            if BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]:
                hubs[meta["name"]] = (lon, lat)
    def seg_dist_t(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        l2 = dx * dx + dy * dy
        t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
        return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)), t

    hub_marks = []  # (corridor label, hub name, lon, lat)
    for label, (orient, line) in list(lines.items()):
        for name, (hlon, hlat) in hubs.items():
            hx, hy = mercator(hlon, hlat)
            lm = [mercator(*p) for p in line]
            best = None  # (dist, segment index)
            for i in range(len(lm) - 1):
                d, _ = seg_dist_t((hx, hy), lm[i], lm[i + 1])
                if best is None or d < best[0]:
                    best = (d, i)
            if best[0] > 350:
                continue
            i = best[1]
            # drop vertices within 200 m of the hub, insert hub after seg start
            newline = []
            for k, p in enumerate(line):
                if math.hypot(lm[k][0] - hx, lm[k][1] - hy) <= 200:
                    continue
                newline.append(p)
                if k == i:
                    newline.append((hlon, hlat))
            if (hlon, hlat) not in newline:
                newline.insert(min(i + 1, len(newline)), (hlon, hlat))
            lines[label] = (orient, newline)
            line = newline
            hub_marks.append((label, name, hlon, hlat))

    features = []

    seen = []
    per_corridor: dict[str, list[tuple[float, str]]] = {lb: [] for lb in lines}

    def arc_pos(line_m: list[tuple[float, float]], px: float, py: float) -> float:
        # arc-length of the exact closest point on the polyline
        best, acc, best_acc = float("inf"), 0.0, 0.0
        for i in range(len(line_m) - 1):
            ax, ay = line_m[i]
            bx, by = line_m[i + 1]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = 0 if l2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / l2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(px - qx, py - qy)
            seg = math.sqrt(l2)
            if d < best:
                best, best_acc = d, acc + t * seg
            acc += seg
        return best_acc

    lines_m = {lb: [mercator(*p) for p in ln] for lb, (_, ln) in lines.items()}

    def add_station(lon: float, lat: float, name: str, serving: list[str]) -> None:
        x, y = mercator(lon, lat)
        for sx, sy, feat in seen:
            if math.hypot(x - sx, y - sy) < 250:
                # merge into the existing station instead of duplicating
                for lb in serving:
                    ln = f"{lb} Line"
                    if ln not in feat["properties"]["lines"]:
                        feat["properties"]["lines"].append(ln)
                    per_corridor[lb].append((arc_pos(lines_m[lb], sx, sy), feat["properties"]["name"]))
                return
        feat = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {"ftype": "station", "name": name, "tier": 1,
                           "lines": [f"{lb} Line" for lb in serving], "headway": "90 s"},
        }
        seen.append((x, y, feat))
        for lb in serving:
            per_corridor[lb].append((arc_pos(lines_m[lb], x, y), name))
        features.append(feat)

    # Hub stations first so they own their position (crossings merge in).
    for label, name, hlon, hlat in hub_marks:
        add_station(hlon, hlat, name, [label])

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

    # Every line must end at a station — a consumer travel map has no
    # business drawing track nobody can get off at. Any end whose nearest
    # on-line station is > DANGLE away gets a terminal station at the end
    # (this is what puts stops at Ocean Beach etc.).
    DANGLE = 250.0
    for lb, (orient, line) in lines.items():
        lm = lines_m[lb]
        total = sum(math.hypot(lm[i + 1][0] - lm[i][0], lm[i + 1][1] - lm[i][1]) for i in range(len(lm) - 1))
        marks = sorted(t for t, _ in per_corridor[lb])
        ends = []
        if not marks or marks[0] > DANGLE:
            ends.append(line[0])
        if not marks or total - marks[-1] > DANGLE:
            ends.append(line[-1])
        for lon, lat in ends:
            if orient == "ew":
                side = "West" if lon == min(line[0][0], line[-1][0]) else "East"
            else:
                side = "South" if lat == min(line[0][1], line[-1][1]) else "North"
            add_station(lon, lat, f"{lb} {side} Terminal", [lb])

    # Sanity: report any remaining dangling ends
    stations_m = [mercator(*s.get("geometry", {}).get("coordinates"))
                  for s in features if s["properties"]["ftype"] == "station"]
    for lb, (_, line) in lines.items():
        for end in (line[0], line[-1]):
            ex, ey = mercator(*end)
            d = min(math.hypot(ex - sx, ey - sy) for sx, sy in stations_m)
            if d > 300:
                print(f"WARNING: {lb} line end still {d:.0f} m from nearest station")

    for label, (orient, line) in lines.items():
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in line]},
            "properties": {"ftype": "line", "id": f"sf-{label}", "name": f"{label} Line", "tier": 1,
                           "headway": "90 s"},
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n")
    n_lines = sum(1 for f in features if f["properties"]["ftype"] == "line")
    n_sta = len(features) - n_lines
    print(f"tier1-sf.geojson: {n_lines} lines, {n_sta} stations")


if __name__ == "__main__":
    main()
