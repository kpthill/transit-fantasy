#!/usr/bin/env python3
"""Download Cal-ITP statewide transit datasets from the Caltrans ArcGIS
FeatureServer (data.ca.gov is reachable; agency GTFS hosts are not).

Outputs (pipeline/cache/):
  calitp_stops.json   [{stop_id, name, lon, lat, agency, n_arrivals,
                        n_hours, routes:[route_id,...]}]
  calitp_routes.json  [{route_id, agency, route_type, n_trips,
                        shape:[[lon,lat],...]}]
  calitp_speeds.json  [{route_id, agency, period, mph}]
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"
BASE = "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad"
UA = {"User-Agent": "ca-fantasy-transit/0.1 (github.com/kpthill/transit-fantasy)"}


def paged(layer, out_fields, geometry):
    feats = []
    offset = 0
    while True:
        params = {
            "where": "1=1", "outFields": out_fields, "f": "json",
            "returnGeometry": "true" if geometry else "false",
            "resultOffset": offset, "resultRecordCount": 2000,
            "outSR": 4326,
        }
        for attempt in range(5):
            try:
                r = requests.get(f"{BASE}/{layer}/FeatureServer/0/query",
                                 params=params, headers=UA, timeout=180)
                r.raise_for_status()
                d = r.json()
                break
            except Exception as e:  # noqa: BLE001
                print(f"{layer} offset {offset} attempt {attempt+1}: {e}", flush=True)
                time.sleep(8 * (attempt + 1))
        else:
            raise SystemExit(f"{layer}: giving up at offset {offset}")
        batch = d.get("features", [])
        feats.extend(batch)
        print(f"{layer}: {len(feats)} rows", flush=True)
        if not d.get("exceededTransferLimit") and len(batch) < 2000:
            return feats
        offset += len(batch)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)

    if not (CACHE / "calitp_speeds.json").exists():
        rows = paged("Speeds_by_Route_Time_of_Day",
                     "route_id,agency,time_period,speed_mph", geometry=False)
        out = [{"route_id": f["attributes"]["route_id"],
                "agency": f["attributes"]["agency"],
                "period": f["attributes"]["time_period"],
                "mph": f["attributes"]["speed_mph"]} for f in rows]
        (CACHE / "calitp_speeds.json").write_text(json.dumps(out))

    if not (CACHE / "calitp_stops.json").exists():
        rows = paged("CA_Transit_Stops",
                     "stop_id,stop_name,agency,n_arrivals,n_hours_in_service,route_ids_served",
                     geometry=True)
        out = []
        for f in rows:
            g = f.get("geometry") or {}
            if "x" not in g:
                continue
            a = f["attributes"]
            out.append({"name": a.get("stop_name"), "agency": a.get("agency"),
                        "lon": round(g["x"], 5), "lat": round(g["y"], 5),
                        "n_arrivals": a.get("n_arrivals") or 0,
                        "n_hours": a.get("n_hours_in_service") or 0,
                        "routes": (a.get("route_ids_served") or "").split(",")})
        (CACHE / "calitp_stops.json").write_text(json.dumps(out))

    if not (CACHE / "calitp_routes.json").exists():
        rows = paged("CA_Transit_Routes",
                     "route_id,agency,route_type,n_trips", geometry=True)
        out = []
        for f in rows:
            g = f.get("geometry") or {}
            paths = g.get("paths") or []
            if not paths:
                continue
            shape = [[round(x, 5), round(y, 5)] for x, y in max(paths, key=len)]
            a = f["attributes"]
            out.append({"route_id": a.get("route_id"), "agency": a.get("agency"),
                        "route_type": a.get("route_type"),
                        "n_trips": a.get("n_trips") or 0, "shape": shape})
        (CACHE / "calitp_routes.json").write_text(json.dumps(out))
    print("done", flush=True)


if __name__ == "__main__":
    main()
