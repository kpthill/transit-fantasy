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

### Placement heuristics (PROPOSED — pending Kevin's reaction)

Guiding test: politics and cost ignored, but the result should be something
that in the most ideal world might actually get built. No station within a
5-minute walk of every suburban home.

- **Tier 1**: gated by density within each Census urbanized area.
  - ≥ ~4,000 people+jobs/km² sustained: full 1-km grid.
  - ~2,000–4,000/km²: coarser 2-km grid or arterial corridor lines.
  - Below: no tier 1 — access by taxi/bus/bike to nearest station.
  - Urbanized area < ~50k population: no tier 1 (tier-2 station only);
    ~50–150k: single spine line; larger: grid scaled to dense footprint.
  - Grid geometry deforms to follow arterials/terrain; ~1 km spacing is the
    invariant, not geometric purity.
- **Tier 2**: serves urbanized areas ≥ ~15–20k on or near a defensible
  corridor. Stop spacing 10–15 km in metro regions, wider across rural
  gaps. Every tier-2 station in a gridded city is also a tier-1 node.
- **Tier 3**: metro areas ≥ ~400–500k; city-center stations; typical
  spacing ≥ 50 km; always co-located with a tier-2 hub.
- **Frequencies**: T1 90–120 s; T2 10 min on metro trunks, 15–30 min on
  branches; T3 15–30 min per corridor. Timed transfers wherever the
  connecting service runs less often than ~every 10 min.

### Open questions

1. Tier-1 floor & the 2-km coarse-grid compromise: in-spirit, or prefer
   "1-km grid or nothing" with a smaller footprint?
2. Confirm deformed-grid geometry (follow arterials, keep spacing) is fine.
