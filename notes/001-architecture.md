# 001 — Architecture (proposed, under discussion)

Status: draft — captures the plan as proposed by Kevin plus Claude's refinements.
This directory (`notes/`) is the source of truth for decisions. Each note is
numbered; superseded decisions get amended in place with a dated strikethrough
or a follow-up note.

## Goal

Statically-hosted website (GitHub Pages) exhibiting a fantasy transit network
for California — technologically possible today, ignoring politics and budget.
Google-Maps-like interface: zoomable searchable map, toggleable overlays for
the fantasy network's three tiers (amended 2026-08-05: originally "~3 variant
networks", now one network of three cooperating tiers — see note 002), and
point-to-point directions comparing:

- walking
- current transit
- driving (peak / off-peak)
- flying + taxi
- the fantasy network (with taxi/walk access legs)

## Hard constraints

- **No backend, ever.** GitHub Pages static hosting only.
- All routing precomputed offline; browser does only cheap local math.
- Total shipped assets should stay well under GitHub Pages' 1 GB site limit;
  no single file near the 100 MB limit. Target: < 500 MB total, ideally < 300 MB.

## Core routing architecture: anchor matrices

- ~2–3k **anchor points**: incorporated places (weighted by population), major
  unincorporated communities, transit hubs, commercial airports, fantasy-network
  stations.
- Offline, run real routers to produce anchor×anchor travel-time matrices per
  mode. Encode as uint16 minutes (or deciminutes), shard by origin row.
  - 2,500 anchors → ~5 KB/row, ~12.5 MB/mode raw; ~7 matrices ≈ < 100 MB. Fine.
- Browser: snap origin/destination to nearby anchors (try several, not just
  nearest), fetch origin rows, add live-computed access/egress legs.
- Both endpoints close together → fully local computation (haversine ×
  road-detour factor, or a small local graph) instead of matrix lookup.
- Accepted fidelity tradeoffs: snapping error, no live traffic, modeled flight
  times, sampled transit departure times.

## Per-mode plan

| Mode | Method |
|---|---|
| Driving off-peak | Valhalla (or OSRM) offline over OSM California extract, free-flow speeds |
| Driving peak | Same router with peak speed model: per-road-class multipliers inside metro congestion polygons, calibrated to published congestion indices. Documented as modeled, not measured. |
| Current transit | Purpose-built RAPTOR over Cal-ITP statewide GTFS aggregation. Sample several departure times (e.g. Wed 8:00 / 12:00 / 17:30) and report a representative time; include first-mile access to stops. Not OTP2 (memory, and we only need anchor-to-anchor). |
| Flying | Modeled: great-circle + cruise speed + climb/descent penalty + fixed overheads (arrive-early, security, taxi-out/in, deplane). Restricted to airport pairs with plausible commercial service; + taxi legs to/from airports. |
| Walking | No matrix needed at state scale: distance × walking speed × road detour factor; only relevant for short trips (live local computation path). |
| Fantasy network | Timetable-free frequency model: in-vehicle time from alignment geometry + integrated speed profile (accel/braking curves, dwell, throat penalty), wait = headway/2 (or timed-transfer offset), transfer penalties. ONE matrix over the combined three-tier network (amended 2026-08-05 — tiers cooperate, they are not variants). Tier-1 grid legs computed analytically (Manhattan distance, closed form), not routed over drawn geometry. |

## Frontend

- MapLibre GL JS.
- Basemap: **DECIDED (2026-08-05) — OpenFreeMap** (free hosted OSM vector
  tiles, no API key, no usage caps, MapLibre-native). Fallback: MapTiler/Stadia
  free tier with domain-restricted key. Self-hosted PMTiles rejected (Pages
  100 MB/file limit, flaky range-request support).
- Network overlays: GeoJSON (or small PMTiles) generated from network
  definition files; toggle per variant.

## Search / geocoding

- Tier 1 (core): client-side index of places + POIs + stations built from OSM
  California extract. A few MB, loaded eagerly or on first search keystroke.
- Tier 2 (stretch): street addresses. Feasible on a static site via sharding:
  parse the address client-side, fetch a per-city/per-geohash shard on demand.
  Candidate sources: OpenAddresses CA statewide + OSM `addr:*` points; or
  street-geometry interpolation (smaller). Budget ~50–150 MB of sharded assets.
  Decision deferred until Tier 1 works.

## Fantasy network design

To be developed interactively — see `002-network-guidelines.md` (forthcoming).
Open questions logged there.

## Open questions (architecture)

1. ~~Basemap provider~~ — DECIDED: OpenFreeMap (see above).
2. Anchor set definition: exact criteria + count (drives all matrix sizes).
3. Transit representative time: median of sampled departures vs. best-case —
   pick one and document.
4. Peak-driving congestion model calibration source.
5. ~~Data assets in-repo vs. CI-built~~ — DECIDED (2026-08-05): generated
   assets live in-repo. Simpler deploys; revisit only if repo size becomes a
   problem.
