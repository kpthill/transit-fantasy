// Directions engine: compares walk / drive (peak+off) / current transit
// (peak+off) / fly+taxi / fantasy network for an origin-destination pair.
// Baseline modes read precomputed anchor matrices (row shards); the
// fantasy network is routed live (line-aware Dijkstra with headway waits
// and timed transfers); tier-1 grids use the analytic model (spec §3.5).

const WALK_KMH = 4.8, DETOUR = 1.3;
const TAXI_HAIL_MIN = 4, LOCAL_DRIVE_KMH = 42;
const LOCAL_ONLY_KM = 15;
const K_SNAP = 3;
const FLY = { cruiseKmh: 780, fixedMin: 30 + 75 + 20, minKm: 150 };
const UNREACH = 65535;

const state = { anchors: null, network: null, airports: null, grids: {}, rowCache: new Map() };

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function ensureData() {
  if (!state.anchors) {
    const [a, n, ap] = await Promise.all([
      getJson('data/anchors.json'), getJson('data/network.json'), getJson('data/airports.json')]);
    state.anchors = a.anchors;
    state.network = n;
    state.airports = ap.airports;
  }
}

function km(a, b) {
  const c = Math.cos(((a.lat + b.lat) / 2) * Math.PI / 180);
  return Math.hypot((a.lon - b.lon) * 111.32 * c, (a.lat - b.lat) * 110.54);
}
const walkMin = (d) => d * DETOUR / WALK_KMH * 60;
const taxiMin = (d) => TAXI_HAIL_MIN + d * DETOUR / LOCAL_DRIVE_KMH * 60;

function nearestAnchors(p, k, filter) {
  const scored = [];
  for (let i = 0; i < state.anchors.length; i++) {
    const a = state.anchors[i];
    if (filter && !filter(a)) continue;
    scored.push([km(p, a), i]);
  }
  scored.sort((x, y) => x[0] - y[0]);
  return scored.slice(0, k);
}

async function getRows(i) {
  if (!state.rowCache.has(i)) {
    const n = state.anchors.length;
    const buf = await (await fetch(`data/rows/${i}.bin`)).arrayBuffer();
    const u = new Uint16Array(buf); // 4 rows: driveOff, drivePeak, transitOff, transitPeak
    state.rowCache.set(i, {
      driveOff: u.subarray(0, n), drivePeak: u.subarray(n, 2 * n),
      transitOff: u.subarray(2 * n, 3 * n), transitPeak: u.subarray(3 * n, 4 * n),
    });
  }
  return state.rowCache.get(i);
}

// ---- baseline modes -------------------------------------------------

async function matrixMode(o, d, rowName, accessFn) {
  const near = km(o, d) < LOCAL_ONLY_KM;
  if (near && rowName.startsWith('drive')) {
    return { minutes: taxiMin(km(o, d)) - TAXI_HAIL_MIN + 3, note: 'local estimate' };
  }
  const oa = nearestAnchors(o, K_SNAP);
  const da = nearestAnchors(d, K_SNAP);
  let best = Infinity, via = null;
  for (const [do_, i] of oa) {
    const rows = await getRows(i).catch(() => null);
    if (!rows) continue;
    for (const [dd, j] of da) {
      const m = rows[rowName][j];
      if (m >= UNREACH) continue;
      const total = accessFn(do_) + m + accessFn(dd);
      if (total < best) { best = total; via = [i, j]; }
    }
  }
  if (!isFinite(best)) return null;
  const names = via ? `via ${state.anchors[via[0]].name} → ${state.anchors[via[1]].name}` : '';
  return { minutes: best, note: names };
}

// ---- fly ------------------------------------------------------------

async function flyMode(o, d) {
  const majors = state.airports;
  let best = Infinity, pair = null;
  for (const A of majors) {
    for (const B of majors) {
      if (A === B) continue;
      const gc = km(A, B);
      if (gc < FLY.minKm) continue;
      if (A.tier === 'regional' && B.tier === 'regional' && gc < 400) continue;
      const t = await taxiToAirport(o, A) + FLY.fixedMin +
        (gc / FLY.cruiseKmh) * 60 + await taxiToAirport(d, B);
      if (t < best) { best = t; pair = [A, B]; }
    }
  }
  if (!pair) return null;
  return { minutes: best, note: `${pair[0].code} → ${pair[1].code}` };
}

async function taxiToAirport(p, airport) {
  const d = km(p, airport);
  if (d < LOCAL_ONLY_KM) return taxiMin(d);
  const res = await matrixMode(p, airport, 'driveOff', (acc) => taxiMin(acc));
  return res ? res.minutes : taxiMin(d);
}

// ---- fantasy network -----------------------------------------------

function gridFor(p) {
  for (const g of state.network.grids) {
    const [w, s, e, n] = g.bbox;
    if (p.lon >= w - 0.01 && p.lon <= e + 0.01 && p.lat >= s - 0.01 && p.lat <= n + 0.01) return g;
  }
  return null;
}

function tier1Time(p, q) {
  // analytic grid leg p->q (both should be near/in the same grid)
  const t1 = state.network.tier1;
  const c = Math.cos(((p.lat + q.lat) / 2) * Math.PI / 180);
  const dx = Math.abs(p.lon - q.lon) * 111.32 * c;
  const dy = Math.abs(p.lat - q.lat) * 110.54;
  const walk = 0.4 * DETOUR / WALK_KMH * 60 * 2; // ~400 m to/from stations
  const ride = (dx + dy) / t1.effective_kmh * 60;
  const transfer = (dx > 0.7 && dy > 0.7) ? t1.transfer_min : 0;
  return walk + t1.headway_min + ride + transfer;
}

function accessLeg(p, st) {
  // best access from point to a tier2/3 station: walk, taxi, or tier-1 ride
  const d = km(p, st);
  const opts = [];
  if (d <= 2.0) opts.push({ min: walkMin(d), how: 'walk' });
  opts.push({ min: taxiMin(d), how: 'taxi' });
  const g = gridFor(p);
  if (g && gridFor(st)) opts.push({ min: tier1Time(p, st), how: 'metro' });
  opts.sort((a, b) => a.min - b.min);
  return opts[0];
}

function fantasyRoute(o, d) {
  const net = state.network;
  const ids = Object.keys(net.stations);
  const idx = new Map(ids.map((id, i) => [id, i]));
  // adjacency: [to, minutes, line]
  const adj = ids.map(() => []);
  for (const e of net.edges) {
    const a = idx.get(e.a), b = idx.get(e.b);
    if (a === undefined || b === undefined) continue;
    adj[a].push([b, e.min, e.line]);
    adj[b].push([a, e.min, e.line]);
  }
  // entry/exit candidates: nearest stations by direct distance
  const stArr = ids.map((id) => net.stations[id]);
  const cand = (p) => stArr.map((s, i) => [km(p, s), i]).sort((x, y) => x[0] - y[0]).slice(0, 5);

  // Dijkstra over (station, line) states; boarding waits per line headway,
  // timed transfers cap the wait at 4 min between tier-2/3 lines.
  const H = (line) => net.lines[line] ? net.lines[line].headway : 15;
  const key = (i, line) => `${i}|${line}`;
  const dist = new Map(), prev = new Map();
  const pq = [];
  const push = (k, v, p) => {
    if (v < (dist.get(k) ?? Infinity)) {
      dist.set(k, v); prev.set(k, p);
      pq.push([v, k]); pq.sort((a, b) => a[0] - b[0]); // small graph: ok
    }
  };
  const entry = cand(o), exit = cand(d);
  for (const [dk, i] of entry) {
    const acc = accessLeg(o, stArr[i]);
    push(key(i, ''), acc.min, { leg: { type: acc.how, to: ids[i], min: acc.min } });
  }
  let bestEnd = null, bestVal = Infinity;
  const exitSet = new Map(exit.map(([dk, i]) => [i, null]));
  while (pq.length) {
    const [v, k] = pq.shift();
    if (v > (dist.get(k) ?? Infinity)) continue;
    const [siStr, line] = k.split('|');
    const si = +siStr;
    if (exitSet.has(si)) {
      const eg = accessLeg(d, stArr[si]);
      const total = v + eg.min;
      if (total < bestVal) { bestVal = total; bestEnd = { k, eg }; }
    }
    for (const [to, min, eline] of adj[si]) {
      let w = min;
      if (eline !== line) {
        const wait = line === '' ? H(eline) / 2 : Math.min(H(eline) / 2, 4);
        w += wait + (line === '' ? 0 : 2);
      }
      push(key(to, eline), v + w, { from: k, leg: { type: 'ride', line: eline, to: ids[to], min } });
    }
  }
  if (!bestEnd) return null;
  // reconstruct
  const legs = [];
  let cur = bestEnd.k;
  while (cur) {
    const p = prev.get(cur);
    if (!p) break;
    legs.push(p.leg);
    cur = p.from;
  }
  legs.reverse();
  legs.push({ type: bestEnd.eg.how, to: 'destination', min: bestEnd.eg.min });
  // compress consecutive same-line rides
  const out = [];
  for (const l of legs) {
    const last = out[out.length - 1];
    if (l.type === 'ride' && last && last.type === 'ride' && last.line === l.line) {
      last.min += l.min; last.to = l.to; last.stops = (last.stops || 1) + 1;
    } else out.push({ ...l });
  }
  for (const l of out) {
    if (net.stations[l.to]) l.to = net.stations[l.to].name;
  }
  return { minutes: bestVal, legs: out };
}

// ---- top-level ------------------------------------------------------

export async function directions(o, d) {
  await ensureData();
  const straight = km(o, d);
  const results = [];
  results.push({ mode: 'Walk', minutes: walkMin(straight), note: straight > 30 ? 'not recommended' : '' });
  const [dOff, dPeak, tOff, tPeak] = await Promise.all([
    matrixMode(o, d, 'driveOff', taxiMin.bind(null)),
    matrixMode(o, d, 'drivePeak', taxiMin.bind(null)),
    matrixMode(o, d, 'transitOff', (acc) => walkMin(acc)),
    matrixMode(o, d, 'transitPeak', (acc) => walkMin(acc)),
  ]);
  if (dOff) results.push({ mode: 'Drive (off-peak)', ...dOff });
  if (dPeak) results.push({ mode: 'Drive (peak)', ...dPeak });
  if (tOff) results.push({ mode: 'Transit today (off-peak)', ...tOff });
  else results.push({ mode: 'Transit today', minutes: NaN, note: 'no practical route (10 h+)' });
  if (tPeak) results.push({ mode: 'Transit today (peak)', ...tPeak });
  if (straight > 100) {
    const f = await flyMode(o, d);
    if (f) results.push({ mode: 'Fly + taxi', ...f });
  }
  const fr = fantasyRoute(o, d);
  if (fr) results.push({ mode: 'Fantasy network', minutes: fr.minutes, legs: fr.legs, highlight: true });
  return results;
}
