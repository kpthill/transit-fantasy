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

## Pending (Kevin to spell out a different approach)

- What the ~3 network variants represent.
- Intercity only vs. urban transit too.
- Service model (headways vs. timetables; wait/transfer treatment).
