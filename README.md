# CA Fantasy Transit

A statically-hosted map of a fantasy transit network for California — what
the state could have built with 50 years of serious investment, using only
well-proven current technology. Politics and budget ignored; engineering
conservatism kept.

Three cooperating tiers: driverless urban metro grids (~1 km stops, 90 s
headways), regional express rail (~200 km/h, stops every 10–15 km), and
true HSR (300–320 km/h) between major metro centers. Plus a directions
engine comparing the fantasy network against walking, driving, current
transit, and flying — all precomputed or computed client-side; no backend.

## Layout

- `site/` — the website (zero-build vanilla JS + MapLibre; deployed to
  GitHub Pages as-is)
- `network/` — authored network definitions (compiled by pipeline)
- `pipeline/` — offline data pipelines (Python 3.11+, stdlib + requests)
- `notes/` — decision log and spec (start with `notes/004-spec.md`)

## Developing

```sh
python3 pipeline/build_network.py   # compile authored lines to GeoJSON
python3 pipeline/build_sf_grid.py   # regenerate SF grid (Overpass; cached)
cd site && python3 -m http.server   # then open http://localhost:8000
```

Append `?basemap=none` to test without basemap tile access.

## Data & attribution

Street and place data © OpenStreetMap contributors (ODbL). Basemap tiles
by OpenFreeMap. See the in-app methodology page for the full modeling
honesty statement.
