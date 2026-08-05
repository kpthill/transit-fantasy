# 004 — Project spec (v1, for Kevin's review)

Status: APPROVED 2026-08-05 (with amendments below marked "amended"). Once approved, this is the contract
for autonomous building. Notes 001–003 remain the decision history; this
spec consolidates them and pins the remaining technical calls. Conflicts
resolve in favor of this spec; future deviations get documented here or in
new numbered notes.

## 1. Product

A statically-hosted website (GitHub Pages, no backend ever) presenting a
fantasy transit network for California — well-proven current technology,
politics and budget ignored, guided by "in the most ideal world, this might
get built." Working title: **CA Fantasy Transit** (final name Kevin's call;
trivial to change).

### 1.1 User-facing features

- **Map**: MapLibre GL JS, OpenFreeMap basemap, bounded to California +
  margin. Toggleable overlays: Tier 1 (urban metro grids), Tier 2
  (regional express), Tier 3 (HSR), stations, park-and-rides, gateway
  branches (styled per tier; colors chosen for basemap contrast and
  color-blind safety). Clicking a station shows name, tier(s), lines,
  headways.
- **Search**: autocomplete over places, POIs/landmarks, and fantasy
  stations (client-side index). Origin/destination boxes plus
  click-on-map / drag-pin to set either endpoint.
- **Directions**: for an origin/destination pair, a comparison panel:
  | Mode | Time | Notes |
  - Walking
  - Current transit (statewide GTFS, precomputed)
  - Driving, off-peak
  - Driving, peak
  - Flying + taxi (via named airports)
  - **Fantasy network** (with taxi/walk access legs) — plus a full
    itinerary breakdown: legs, lines, transfer points, waits.
  Baseline modes show times (fly/drive show brief context, e.g. airports
  used); only the fantasy mode gets a detailed itinerary (see 3.5).
- **Methodology page**: static page documenting the premise, the modeling
  (including all fidelity tradeoffs and the magic-tunnel registry), and
  data sources/licenses.
- **URL state**: origin/destination/layer toggles encoded in the URL hash
  for shareable links.
- Desktop-first, usable on mobile. No accounts, no analytics, no cookies.

### 1.2 Explicit non-goals

Live traffic/realtime data; turn-by-turn navigation; itinerary details for
baseline modes; routing outside California; timetable simulation; modeling
local buses or park shuttles (assumed to exist, unmodeled).

## 2. The fantasy network (summary of 002/003 — already decided)

Three cooperating tiers, one network. Well-proven tech only (peak-European
HSR ceiling; no maglev). No blanket urban slow running — braking physics
and terminal throats only. Placement per 002 heuristics: density-gated
1-km grids (guideline, not lattice; stations snap to attractions);
corridors + highlights in medium density; tier-2 for 15k+ towns on
defensible corridors; gateway rule for 1M+ visitor attractions; tier-3 HSR
for 400–500k+ metros, city centers, per 003 sketch. Frequencies: T1
90–120 s, T2 10–30 min, T3 15–30 min; timed transfers where headways
> ~10 min. Magic tunnels declared, never studied, and logged in
`network/magic-tunnels.md`.

The 003 sketch is the prior; the data-driven build re-derives coverage
from Census/LODES/OSM and the data wins. Big surprises vs. the sketch get
flagged in notes rather than silently followed.

## 3. Architecture

### 3.1 Repo layout

```
site/       Frontend app (Vite + TypeScript + MapLibre; no heavy framework)
pipeline/   Offline data pipelines (Python; Rust rewrite of hot paths only
            if measured too slow)
network/    Fantasy network definitions: authored line/station files
            (YAML/JSON), generated grid GeoJSON, magic-tunnels.md
data/       Generated static assets served to the browser (committed)
notes/      Decision log (source of truth)
.github/    Actions workflow: build site, assemble data, deploy Pages
```

Raw inputs (OSM pbf, GTFS, Census) are downloaded by pipelines and cached
locally, never committed. Generated `data/` is committed (decided 001).
Budgets: no file ≥ 50 MB, total repo < 500 MB target.

### 3.2 Anchors

~3,000–4,500 anchor points (amended 2026-08-05): all incorporated places,
CDPs ≥ ~1,000 pop, commercial airports (FAA-listed with scheduled
service), all tier-2/3 stations and gateway stations, and — densified so
that intra-metro commute queries work — current-transit rail/BRT/ferry
stops and major bus hubs inside urbanized areas (BART, Muni Metro, LA
Metro, VTA, SacRT, SDMTS, etc.). Without these a city like SF would have
one anchor and intra-city current-transit comparisons would be garbage;
with them, a Sunset→downtown query snaps to nearby Muni stops and reads
the RAPTOR matrix between them. Tier-1 *fantasy* stations are still NOT
anchors (handled analytically). Matrix budget at 4.5k anchors: ~40 MB ×3,
row shards ~27 KB — still within limits. Shipped eagerly as
`data/anchors.json`: id, name, lat/lon, kind, shard ref.

Per-mode local fallback (clarification): for endpoints within ~15 km,
walk/drive are computed locally, but current transit still goes through
hub anchors (a local transit estimate would be fiction), and the fantasy
mode always uses the live network router + analytic grids.

### 3.3 Precomputed matrices (baseline modes only)

Three anchor×anchor matrices, uint16 minutes, sentinel for unreachable:

- **drive-offpeak**: custom Dijkstra road router (see 3.4) at free-flow.
- **drive-peak**: same router with per-road-class multipliers inside metro
  congestion polygons, calibrated to published congestion indices.
- **transit-current**: purpose-built RAPTOR over Cal-ITP statewide GTFS
  aggregate (fallback: merged major-agency feeds). Walk access/egress
  ≤ 2 km at each end; departures sampled Wed 08:00 / 12:00 / 17:30;
  report the median. Times only, no itineraries.

Sharding: **one file per origin anchor containing that origin's row from
all three matrices** (~15–20 KB), so a directions query fetches exactly
two small files (origin + destination shards). ~3k files in `data/rows/`.

The fantasy network gets NO matrix — it is routed live in the browser
(3.5). Flying gets no matrix — composed client-side (3.6).

### 3.4 Road router (judgment call, documented)

Valhalla/OSRM are the gold standard but are impractical to build/run in
this environment. Plan of record: a custom Dijkstra router in Python
(scipy.sparse.csgraph or equivalent C-speed core) over a filtered OSM
graph — motorway/trunk/primary/secondary statewide, + tertiary within
urban areas — with per-class speeds, intersection/turn penalties, and an
access-time constant. **Acceptance test**: ±15% median error against
~30 hand-checked real-world OD drive times (documented in
`pipeline/calibration.md`); recalibrate until met. Access legs and
both-endpoints-near cases don't touch this graph (3.6).

### 3.5 Fantasy network routing (client-side, live)

The tier-2/3 network is a small graph (~500–1,000 stations): shipped as
`data/network.json` with per-segment precomputed run times (from the
speed-profile integrator: line speed by segment, accel/braking curves,
dwell, throat penalty). Browser runs Dijkstra over it with waits =
headway/2 (or timed-transfer offset where defined) — this yields full
itineraries for free.

Tier-1 access is analytic: within a grid polygon, time = walk to nearest
station (from grid spacing) + wait (≤ 1 min) + Manhattan-distance ride at
effective commercial speed (~35–40 km/h, computed once from the profile
integrator) + ≤ 1 transfer + walk. Grids are drawn as real lines on the
map but not routed over.

Access/egress to the network: min(walk, taxi) where taxi time comes from
the drive matrix (stations are anchors) or local estimate; taxi = drive
time + 4 min hail constant. Fantasy door-to-door =
access + network ride + egress, minimized over nearby entry stations /
grid areas.

### 3.6 Client-side composition (all modes)

For endpoints A, B: snap each to the k=3 nearest anchors. Fetch their row
shards. For each mode: time = access(A→anchor) + matrix(anchor, anchor') +
egress(anchor'→B), minimized over anchor pairs. Access legs computed
locally (haversine × road detour factor 1.3, walk 4.8 km/h, drive by
local speed heuristic). If A and B are within ~15 km, skip matrices and
compute fully locally. Walking mode is always computed locally.

**Flying**: composed client-side. fly(A,B) = taxi(A→airport₁) + 75 min
departure overhead + flight time (great-circle at 780 km/h + 30 min
climb/descent/taxi penalty) + 20 min arrival overhead + taxi(airport₂→B),
minimized over commercial airport pairs ≥ 150 km apart. Airports carry an
enplanement-based service tier; tiny-airport pairs excluded.

**Stretch**: park-and-ride hybrid (drive to designated P&R anchor +
fantasy network) — nearly free given the above; build if time allows.

### 3.7 Geocoder

- Tier A (core): client-side index (MiniSearch or equivalent) over OSM
  places, notable POIs, and all fantasy stations. Few MB, lazy-loaded on
  first search focus.
- Tier B (stretch, explicitly deferred): street addresses via sharded
  OpenAddresses/OSM `addr:*` data fetched per-city on demand
  (~50–150 MB budget). Not part of initial milestones.

### 3.8 Network authoring pipeline

- Tier-1 grids: generated per urbanized area from Census block density +
  LODES jobs raster; lines follow OSM arterial graph (deformed grid);
  stations snap to POI attractors. Output GeoJSON, hand-tunable via
  per-city override files.
- Tier-2/3: hand-authored line definitions (ordered station lists +
  corridor hints); geometry auto-traced along OSM roads/rail rights-of-way
  between stations ("straightest road" per 002); manual geometry overrides
  where tracing is ugly. Magic tunnels declared explicitly in the line
  files and aggregated into the registry.

## 4. Data sources

| Data | Source | License note |
|---|---|---|
| Roads, POIs, arterials | OSM California (Geofabrik) | ODbL, attribute |
| Population density | Census 2020 blocks + urban areas | public domain |
| Jobs density | LEHD LODES WAC | public domain |
| Current transit | Cal-ITP statewide GTFS (fallback: agency feeds) | open |
| Airports + enplanements | OurAirports + FAA | public domain |
| Basemap tiles | OpenFreeMap hosted | free, attribute |

All attributions on the methodology page and map attribution control.

## 5. Milestones

Each milestone = pushed commits + updated notes documenting judgment
calls. M1 is a review checkpoint; after that, autonomous through M4.

- **M1 — Skeleton on a map** (review checkpoint): site shell deployed;
  map + layer toggles; SF 1-km grid (flagship, generated); HSR spine
  drawn; Bay Area tier-2 draft; station registry format settled.
- **M2 — Statewide network**: all tiers, all regions, data-driven per
  002; grids for every qualifying area; gateway branches; magic-tunnel
  registry; rendering polish (line colors, station styling, zoom
  behavior).
- **M3 — Directions engine**: anchors; road router + calibration; drive
  matrices; RAPTOR + transit matrix; row shards; client-side fantasy
  router + tier-1 analytic model; fly model; comparison panel with
  fantasy itinerary breakdown.
- **M4 — Product polish**: geocoder, URL sharing, methodology page,
  mobile usability pass, load-time budget (< ~3 s first map paint on
  broadband), attribution.
- **M5 — Stretch** (only after M4): street-address geocoding;
  park-and-ride hybrid mode; transfer-count display for current transit.

## 6. Verification

- Road matrices: calibration acceptance test (3.4).
- Transit matrix: spot-check ~10 OD pairs against Google/agency planners
  (manual, documented).
- Fantasy times: sanity harness asserting e.g. SF–LA center-to-center
  2h00–2h30, SF–Sacramento ≤ 1h, Koreatown→Santa Monica grid trip
  plausibility; documented expected values with tolerance.
- Frontend: Playwright smoke test — load map, toggle layers, run one
  directions query per mode, assert sane outputs.
- CI (GitHub Actions): typecheck, unit tests for composition math,
  Playwright smoke, then Pages deploy.

## 7. Operating agreements

- notes/ stays the decision log; judgment calls made autonomously get a
  dated entry (new note or amendment) — silence is never a decision.
- Data wins over the 003 sketch; surprises get flagged, not buried.
- No PRs unless requested. Work happens on `main` with frequent commits
  (amended 2026-08-05 — Kevin: sole-author repo, main is fine).
- Anything requiring Kevin: enabling GitHub Pages for the repo when M1 is
  ready to deploy (Settings → Pages → deploy from Actions), and the
  site's final name. Everything else proceeds autonomously.
