// CA Fantasy Transit — map shell.
// Zero-build vanilla JS: maplibre-gl is loaded globally from vendor/.

const CA_BOUNDS = [[-125.5, 32.0], [-113.4, 42.5]];
const BASEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';

// Fallback style keeps the network visible even if the basemap host is
// unreachable (also used for local dev in sandboxes without tile access).
const BLANK_STYLE = {
  version: 8,
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#e8ecef' } }],
};

async function resolveStyle() {
  if (new URLSearchParams(location.search).get('basemap') === 'none') return BLANK_STYLE;
  try {
    const r = await fetch(BASEMAP_STYLE, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (err) {
    console.warn('Basemap style unavailable, using blank background:', err);
    return BLANK_STYLE;
  }
}

const map = new maplibregl.Map({
  container: 'map',
  style: await resolveStyle(),
  bounds: CA_BOUNDS,
  fitBoundsOptions: { padding: 20 },
  maxBounds: [[-130.0, 30.0], [-109.0, 44.5]],
  attributionControl: { compact: false },
});
map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

// Zoom thresholds keep tier-1 city grids from cluttering the state view.
const TIER_STYLE = {
  1: { lineWidth: 1.6, lineMinzoom: 9, stationRadius: 3, stationMinzoom: 11, labelMinzoom: 13 },
  2: { lineWidth: 2.4, lineMinzoom: 0, stationRadius: 4.5, stationMinzoom: 7, labelMinzoom: 9 },
  3: { lineWidth: 3.5, lineMinzoom: 0, stationRadius: 6, stationMinzoom: 0, labelMinzoom: 6 },
};

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function mergeCollections(collections) {
  const features = collections.flatMap((c) => c.features);
  for (const f of features) {
    if (Array.isArray(f.properties.lines)) {
      f.properties.n_lines = f.properties.lines.length;
    }
  }
  return { type: 'FeatureCollection', features };
}

function addGroup(group, data) {
  const s = TIER_STYLE[group.tier];
  const src = `net-${group.id}`;
  map.addSource(src, { type: 'geojson', data });

  map.addLayer({
    id: `${src}-lines-casing`,
    type: 'line',
    source: src,
    minzoom: s.lineMinzoom,
    filter: ['==', ['geometry-type'], 'LineString'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#ffffff',
      'line-width': s.lineWidth + 2,
      'line-opacity': 0.6,
    },
  });
  map.addLayer({
    id: `${src}-lines`,
    type: 'line',
    source: src,
    minzoom: s.lineMinzoom,
    filter: ['==', ['geometry-type'], 'LineString'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': group.color, 'line-width': s.lineWidth },
  });
  // Interchanges (3+ lines) render larger with a darker ring.
  const isInterchange = ['>=', ['coalesce', ['get', 'n_lines'], 0], 3];
  map.addLayer({
    id: `${src}-stations`,
    type: 'circle',
    source: src,
    minzoom: s.stationMinzoom,
    filter: ['==', ['geometry-type'], 'Point'],
    paint: {
      'circle-radius': ['case', isInterchange, s.stationRadius + 2, s.stationRadius],
      'circle-color': '#ffffff',
      'circle-stroke-color': ['case', isInterchange, '#333333', group.color],
      'circle-stroke-width': ['case', isInterchange, 2.5, 2],
    },
  });
  map.addLayer({
    id: `${src}-labels`,
    type: 'symbol',
    source: src,
    minzoom: s.labelMinzoom,
    filter: ['==', ['geometry-type'], 'Point'],
    layout: {
      'text-field': ['get', 'name'],
      'text-font': ['Noto Sans Regular'],
      'text-size': 11,
      'text-offset': [0, 0.9],
      'text-anchor': 'top',
      'text-optional': true,
    },
    paint: {
      'text-color': '#222',
      'text-halo-color': '#fff',
      'text-halo-width': 1.5,
    },
  });

  map.on('click', `${src}-stations`, (e) => {
    const p = e.features[0].properties;
    const lines = typeof p.lines === 'string' ? JSON.parse(p.lines) : (p.lines || []);
    const html = `
      <h3>${p.name}</h3>
      <div class="meta">${group.name}</div>
      ${lines.length ? `<div>${lines.join('<br>')}</div>` : ''}
      ${p.headway ? `<div class="meta">every ${p.headway}</div>` : ''}`;
    new maplibregl.Popup({ closeButton: false })
      .setLngLat(e.features[0].geometry.coordinates)
      .setHTML(html)
      .addTo(map);
  });
  map.on('mouseenter', `${src}-stations`, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', `${src}-stations`, () => { map.getCanvas().style.cursor = ''; });

  return [`${src}-lines-casing`, `${src}-lines`, `${src}-stations`, `${src}-labels`];
}

function addToggle(group, layerIds) {
  const container = document.getElementById('layer-toggles');
  const label = document.createElement('label');
  const box = document.createElement('input');
  box.type = 'checkbox';
  box.checked = true;
  box.addEventListener('change', () => {
    for (const id of layerIds) {
      map.setLayoutProperty(id, 'visibility', box.checked ? 'visible' : 'none');
    }
  });
  const swatch = document.createElement('span');
  swatch.className = 'swatch';
  swatch.style.background = group.color;
  label.append(box, swatch, document.createTextNode(group.name));
  container.append(label);
}

// --- directions UI ---------------------------------------------------
import('./directions.js').then(({ directions }) => {
  const pts = { origin: null, dest: null };
  let arming = null;
  const markers = {};
  const fmt = (m) => m >= 90 ? `${Math.floor(m / 60)} h ${Math.round(m % 60)} min` : `${Math.round(m)} min`;

  function arm(which, btn) {
    arming = which;
    document.querySelectorAll('.dir-row button').forEach((b) => b.classList.remove('armed'));
    btn.classList.add('armed');
  }
  document.getElementById('set-origin').addEventListener('click', (e) => arm('origin', e.target));
  document.getElementById('set-dest').addEventListener('click', (e) => arm('dest', e.target));

  map.on('click', (e) => {
    if (!arming) return;
    pts[arming] = { lon: e.lngLat.lng, lat: e.lngLat.lat };
    document.getElementById(arming === 'origin' ? 'origin-label' : 'dest-label').textContent =
      `${e.lngLat.lat.toFixed(3)}, ${e.lngLat.lng.toFixed(3)}`;
    if (markers[arming]) markers[arming].remove();
    markers[arming] = new maplibregl.Marker({ color: arming === 'origin' ? '#009E73' : '#D55E00' })
      .setLngLat(e.lngLat).addTo(map);
    document.querySelectorAll('.dir-row button').forEach((b) => b.classList.remove('armed'));
    arming = null;
    document.getElementById('go').disabled = !(pts.origin && pts.dest);
  });

  document.getElementById('go').addEventListener('click', async () => {
    const el = document.getElementById('results');
    el.innerHTML = 'computing…';
    try {
      const res = await directions(pts.origin, pts.dest);
      el.innerHTML = '';
      for (const r of res) {
        const div = document.createElement('div');
        div.className = 'result' + (r.highlight ? ' highlight' : '');
        div.innerHTML = `<span>${r.mode}</span><span>${fmt(r.minutes)}</span>`;
        el.append(div);
        if (r.note) {
          const n = document.createElement('div');
          n.className = 'note';
          n.textContent = r.note;
          el.append(n);
        }
        if (r.legs) {
          const ul = document.createElement('ul');
          ul.className = 'legs';
          for (const l of r.legs) {
            const li = document.createElement('li');
            const dest = l.to === 'destination' ? 'destination' : (l.to.split(':')[1] || l.to);
            li.textContent = l.type === 'ride'
              ? `${l.line} → ${dest} (${fmt(l.min)}${l.stops ? `, ${l.stops} stops` : ''})`
              : `${l.type} → ${dest} (${fmt(l.min)})`;
            ul.append(li);
          }
          el.append(ul);
        }
      }
    } catch (err) {
      el.textContent = `error: ${err.message}`;
      console.error(err);
    }
  });
});

map.on('load', async () => {
  const index = await fetchJson('data/network/index.json');
  for (const group of index.groups) {
    try {
      const collections = await Promise.all(group.files.map((f) => fetchJson(`data/network/${f}`)));
      const layerIds = addGroup(group, mergeCollections(collections));
      addToggle(group, layerIds);
    } catch (err) {
      console.error(`Failed to load layer group ${group.id}:`, err);
    }
  }
});
