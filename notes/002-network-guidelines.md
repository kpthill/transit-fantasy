# 002 — Fantasy network design guidelines

Status: in progress — being developed interactively. Decisions below are
final unless amended; interpretation notes are Claude's readings of the
decisions, flagged for correction.

## Premise

"What could California have if it had invested in public transit for 50
years" — NOT "what if California pioneered new technology". Politics and
budget are ignored; engineering conservatism is not.

## Decided

### Technology envelope (2026-08-05)

**Well-proven current technology only.** Maglev is excluded (only one
operational deployment — just shy of well-proven). The ceiling is
peak-European-levels of HSR, with lower top speeds over hills and through
curves.

*Interpretation (Claude, to be corrected if wrong):*
- New dedicated HSR track: 300–320 km/h design speed (LGV / LAV class).
- Upgraded or shared conventional corridors: 160–250 km/h depending on
  geometry.
- Mountain crossings: long tunnels are fine (well-proven — Gotthard class),
  but where geometry forces surface alignment, speeds drop realistically.
- Urban approaches (amended 2026-08-05): **no blanket urban slow running.**
  Today's crawl into cities is a consequence of underinvestment (legacy shared
  curvy tracks, noise limits, grade crossings) — all bought away by premise via
  dedicated grade-separated approaches, walls, and deep urban tunnels
  (200–250+ km/h in-tunnel is well-proven). What remains is physics only:
  stopping trains follow a realistic braking/acceleration curve (~6–8 km to
  brake from 300 km/h), and the final ~2 km terminal throat runs at
  ~60–100 km/h through switches — a 1–2 minute cost per stop, not a crawl.
  Through-trains keep line speed past metros they don't serve.
- Standard well-proven kit is all allowed: full electrification, tilting
  trains, high-frequency signaling (ETCS-class), timed cross-platform
  transfers.

### Alignment realism (2026-08-05)

**Realistic where cheap.** Do it the way a transit agency would when that's
low-effort; otherwise approximations are fine (e.g. following the
straightest road that goes the right way). Where terrain would genuinely
require geological investigation to settle feasibility, don't investigate —
declare a **"magic tunnel"** and document it as such. Keep a list of magic
tunnels in the network notes so the hand-waving is explicit.

### Network structure: three cooperating tiers (2026-08-05)

Not three alternative scenarios — one network with three integrated tiers.
Map overlays toggle tiers for display; directions always route over the
combined network (single fantasy-network travel-time matrix).

- **Tier 1 — Urban grid metro.** Simple grid of driverless subway/elevated
  lines covering urban areas at ~1 km station spacing. Small/medium cars,
  maximum frequency (autonomy means demand is met with train length, not
  reduced frequency). Headways 90 s peak / 120 s off-peak — verified
  well-proven (Paris M14 ~85 s, Vancouver SkyTrain ~75–110 s, Copenhagen).
  Mean wait ≤ 1 min ⇒ transfers into tier 1 are untimed by design.
- **Tier 2 — Regional express (~200 km/h).** Intercity service stopping
  every 10–15 km; connects urban areas along corridors and doubles as the
  express overlay within large metros (e.g. SF→San Jose ~25 min). Timed
  transfers with tier 3 and, where infrequent, with other tier-2 services.
- **Tier 3 — True HSR (300–320 km/h).** City-center stations in the most
  populous metros only; timed pulse transfers to tier 2 at every station.

Modeling decision (Claude): tier-1 grids are drawn as real lines on the map
(following arterials), but travel times are computed analytically —
Manhattan distance over the grid, closed-form stop penalty, ≤ 1 transfer —
rather than by routing over the drawn geometry.

### Placement heuristics (DECIDED 2026-08-05)

Guiding test: politics and cost ignored, but the result should be something
that in the most ideal world might actually get built. No station within a
5-minute walk of every suburban home. Density (people + jobs, via Census +
LODES) is the primary gate but is only a proxy for **transit desirability**:
"how many people would want to take a train to within walking distance of
this place?" Visitor-heavy, job-light destinations are handled explicitly
(see highlights).

- **Tier 1, dense core — the grid**: full grid where sustained density
  ≥ ~4,000 people+jobs/km² within a Census urbanized area.
  - 1-km station spacing is a *guideline*, not a rule. The principle is
    "densely connected, not hub-and-spoke." Geometry deforms to follow
    arterials and terrain; stations slide off the lattice to land on
    squares, shopping centers, parks, campuses, and transfer points.
  - Urbanized area < ~50k population: no tier 1 (tier-2 station only);
    ~50–150k: single spine line; larger: grid scaled to dense footprint.
- **Tier 1, medium density — corridors + highlights** (replaces the earlier
  2-km-grid proposal, rejected: at 2-km spacing worst-case walks exceed
  comfortable distance, mesh topology only pays off under dense isotropic
  demand, and a mesh through single-family sprawl fails the
  might-actually-get-built test):
  - In ~2,000–4,000/km² fabric: **arterial corridor lines**, stations every
    ~1.5–2 km, whose jobs are to (a) connect dense-core grids to each
    other, (b) reach designated highlights, (c) leave no substantial
    medium-density blob without a line through its middle.
  - **Highlights**: an explicit destination list for visitor-heavy,
    job-light places the jobs data misses — theme parks, stadiums,
    university campuses, beaches/major parks, fairgrounds, convention
    centers. Each gets a station on a corridor line or a short spur to the
    nearest grid / tier-2 hub. (Employment centers — office campuses,
    malls, warehouse districts — are already captured by the jobs term in
    the density gate.)
  - **Park-and-rides** at edge-of-network stations near freeway junctions.
    (Stretch: exposes a drive-to-transit hybrid mode in the directions
    engine nearly for free.)
  - Below ~2,000/km² and away from highlights: no rail. Local bus service
    is assumed to exist but is not modeled; directions-engine access legs
    remain walk/taxi.
- **Tier 2**: serves urbanized areas ≥ ~15–20k on or near a defensible
  corridor. Stop spacing 10–15 km in metro regions, wider across rural
  gaps. Every tier-2 station in a gridded city is also a tier-1 node.
- **Gateway rule** (added 2026-08-05): major out-of-city attractions —
  national/state parks, resort regions, wine country — get a tier-2 branch
  to a **gateway station** when (a) annual visitation ≥ ~1M and (b) a
  terrain-feasible corridor exists (historical rail precedent counts as
  proof). Rail stops at the gateway/edge; circulation beyond it is by
  park shuttle (assumed, unmodeled — like local buses; engine access legs
  from gateway remain walk/taxi). No rail into fragile interiors or over
  passes that would demand geological study — that's magic-tunnel
  territory and gateways don't rate magic. Seasonal demand is fine:
  autonomous short trains keep frequency decent off-season (same argument
  as tier-1 capacity scaling). Gateway destinations are included in the
  geocoder and anchor set so directions to e.g. "Yosemite Valley" work.
- **Tier 3**: metro areas ≥ ~400–500k; city-center stations; typical
  spacing ≥ 50 km; always co-located with a tier-2 hub.
- **Frequencies**: T1 90–120 s; T2 10 min on metro trunks, 15–30 min on
  branches; T3 15–30 min per corridor. Timed transfers wherever the
  connecting service runs less often than ~every 10 min.
