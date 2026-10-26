"use strict";
// World map tab: tiles from /api/map/tiles, pan (drag/touch), zoom (wheel, pinch, buttons),
// markers for the world spawn and all waypoints (admin view: private ones too).
// Loaded before app.js; uses its helpers ($, el, api, toast, fmtDate, DIM_NAMES) only inside functions.

const MAP_DIMS = { overworld: "Oberwelt", the_end: "Ende" };
const MAP_WP_DIM = { "minecraft:overworld": "overworld", "minecraft:the_end": "the_end", "minecraft:nether": "nether" };
const MAP_MIN_SCALE = 1 / 256, MAP_MAX_SCALE = 8;
const MAP_HIT = 14; // css px around a marker that count as a click on it
const mapView = { index: null, dim: "overworld", cx: 0, cz: 0, scale: 0.5, images: new Map(), placed: false,
                  waypoints: [], showWaypoints: true, selected: null };
let mapBuild = null;
let mapWaypointsKey = null;

async function loadMap() {
  try {
    const m = await api("GET", "/api/map");
    renderMapState(m);
    $("#map-seed").textContent = m.seed || "–";
    if (m.index && m.index.build !== (mapView.index && mapView.index.build)) {
      mapView.index = m.index;
      mapView.images.clear();
      if (!m.index.dims[mapView.dim]) mapView.dim = Object.keys(m.index.dims)[0] || "overworld";
      if (!mapView.placed) mapHome();
      renderDimButtons();
    }
    mapBuild = m.build;
    $("#map-empty").hidden = !!m.index;
    mapDraw();
    loadMapWaypoints();
  } catch (e) { toast(e.message, true); }
}

async function loadMapWaypoints() {
  try {
    const w = await api("GET", "/api/waypoints");
    mapView.waypoints = Object.values(w.players).flat().sort((a, b) => a.name.localeCompare(b.name, "de"));
    if (mapView.selected && mapView.selected.kind === "wp") {
      const again = mapView.waypoints.find((x) => x.name === mapView.selected.item.name);
      mapView.selected = again ? { kind: "wp", item: again } : null;
    }
    renderWaypointList();
    mapDraw();
  } catch (e) { /* the map works without them */ }
}

function mapOnState(s) {
  if (!s.map) return;
  renderMapState(s.map);
  const visible = !$("#tab-map").hidden;
  if (s.map.build !== mapBuild && visible) loadMap();
  const wpKey = String(s.waypoints && s.waypoints.updated);
  if (mapWaypointsKey !== null && wpKey !== mapWaypointsKey && visible) loadMapWaypoints();
  mapWaypointsKey = wpKey;
}

function renderMapState(m) {
  const btn = $("#map-render");
  btn.disabled = !!m.running;
  btn.textContent = m.running === "snapshot" ? "⏳ Welt wird kopiert …"
    : m.running === "render" ? `⏳ Karte wird gezeichnet …${m.progress ? ` (${m.progress} Chunks)` : ""}`
    : "🔄 Jetzt neu zeichnen";
  $("#map-stand").textContent = m.rendered_at ? fmtDate(m.rendered_at) : "noch nie";
  $("#map-next").textContent = m.next_run ? fmtDate(m.next_run) : "–";
  const err = $("#map-error");
  err.hidden = !m.error;
  err.textContent = m.error || "";
}

function renderDimButtons() {
  const box = $("#map-dims");
  box.replaceChildren(...Object.keys(mapView.index.dims).map((d) => {
    const b = el("button", { className: "btn small" + (d === mapView.dim ? " on" : ""), textContent: MAP_DIMS[d] || d, type: "button" });
    b.addEventListener("click", () => {
      mapView.dim = d; mapView.images.clear(); mapView.selected = null; mapHome(); renderDimButtons(); mapDraw();
    });
    return b;
  }));
}

function renderWaypointList() {
  const ul = $("#map-wp-list");
  $("#map-wp-count").textContent = mapView.waypoints.length ? `(${mapView.waypoints.length})` : "";
  if (!mapView.waypoints.length) {
    ul.replaceChildren(el("li", { className: "empty", textContent: "Noch keine Wegpunkte gesetzt." }));
    return;
  }
  ul.replaceChildren(...mapView.waypoints.map((w) => {
    const onMap = !!(mapView.index && mapView.index.dims[MAP_WP_DIM[w.dim]]);
    const where = `${DIM_NAMES[w.dim] || w.dim} ${Math.floor(w.x)} / ${Math.floor(w.z)}`;
    const b = el("button", { type: "button", className: "map-wp" + (w.public ? " public" : ""), disabled: !onMap,
      title: onMap ? "Auf der Karte zeigen" : "Diese Dimension wird nicht gezeichnet" },
      el("span", { className: "wp-dot" }),
      el("span", { className: "name", textContent: w.name }),
      el("small", { textContent: `${w.owner} · ${w.public ? "öffentlich" : "privat"} · ${where}` }));
    b.addEventListener("click", () => mapFocus(w));
    return el("li", {}, b);
  }));
}

function mapFocus(w) {
  const dim = MAP_WP_DIM[w.dim];
  if (dim !== mapView.dim) { mapView.dim = dim; mapView.images.clear(); renderDimButtons(); }
  mapView.cx = w.x; mapView.cz = w.z;
  mapView.scale = Math.max(mapView.scale, 1);
  mapView.selected = { kind: "wp", item: w };
  $("#map-canvas").scrollIntoView({ behavior: "smooth", block: "nearest" });
  mapDraw();
}

function mapHome() {
  const idx = mapView.index;
  const dim = idx && idx.dims[mapView.dim];
  if (!dim) return;
  const [x0, z0, x1, z1] = dim.bounds;
  const sp = mapView.dim === "overworld" && idx.spawn;
  const inside = sp && sp[0] >= x0 && sp[0] <= x1 && sp[1] >= z0 && sp[1] <= z1;
  mapView.cx = inside ? sp[0] : (x0 + x1) / 2;
  mapView.cz = inside ? sp[1] : (z0 + z1) / 2;
  mapView.scale = 0.5;
  mapView.placed = true;
}

function mapCanvas() {
  const c = $("#map-canvas");
  const dpr = window.devicePixelRatio || 1;
  const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return { c, dpr, w, h };
}

function mapTile(level, tx, tz) {
  const key = `${mapView.dim}/${level}/${tx}_${tz}`;
  let img = mapView.images.get(key);
  if (!img) {
    img = new Image();
    img.onload = () => mapDraw();
    img.src = `/api/map/tiles/${mapView.index.build}/${key}.png`;
    mapView.images.set(key, img);
  }
  return img.complete && img.naturalWidth ? img : null;
}

function mapMarkers() {
  return mapView.showWaypoints ? mapView.waypoints.filter((w) => MAP_WP_DIM[w.dim] === mapView.dim) : [];
}

let mapPending = false;
function mapDraw() {
  if (mapPending) return;
  mapPending = true;
  requestAnimationFrame(() => { mapPending = false; mapDrawNow(); });
}

function mapDrawNow() {
  const { c, dpr, w, h } = mapCanvas();
  const g = c.getContext("2d");
  g.imageSmoothingEnabled = false;
  g.fillStyle = "#11140f";
  g.fillRect(0, 0, w, h);
  const idx = mapView.index;
  const dim = idx && idx.dims[mapView.dim];
  if (!dim) { $("#map-popup").hidden = true; return; }
  const levels = Object.keys(dim.tiles).map(Number);
  const maxLevel = Math.max(...levels);
  const level = Math.max(0, Math.min(maxLevel, Math.floor(Math.log2(1 / mapView.scale))));
  const s = mapView.scale * dpr;                       // screen pixels per block
  const span = 256 * 2 ** level;                        // blocks per tile
  const left = mapView.cx - w / 2 / s, top = mapView.cz - h / 2 / s;
  const have = new Set(dim.tiles[level].map(([x, z]) => `${x}_${z}`));
  for (let tz = Math.floor(top / span); tz * span < top + h / s; tz++) {
    for (let tx = Math.floor(left / span); tx * span < left + w / s; tx++) {
      if (!have.has(`${tx}_${tz}`)) continue;
      const sx = (tx * span - left) * s, sz = (tz * span - top) * s, size = span * s;
      const img = mapTile(level, tx, tz);
      if (img) { g.drawImage(img, sx, sz, size + 0.5, size + 0.5); continue; }
      // still loading: show the coarser parent tile meanwhile
      for (let up = 1; level + up <= maxLevel; up++) {
        const f = 2 ** up, ptx = Math.floor(tx / f), ptz = Math.floor(tz / f);
        const key = `${mapView.dim}/${level + up}/${ptx}_${ptz}`;
        const p = mapView.images.get(key);
        if (p && p.complete && p.naturalWidth) {
          const part = 256 / f;
          g.drawImage(p, (tx - ptx * f) * part, (tz - ptz * f) * part, part, part, sx, sz, size + 0.5, size + 0.5);
          break;
        }
      }
    }
  }
  const toScreen = (x, z) => [(x - left) * s, (z - top) * s];
  if (mapView.dim === "overworld" && idx.spawn) {
    const [px, pz] = toScreen(idx.spawn[0] + 0.5, idx.spawn[1] + 0.5);
    g.font = `${16 * dpr}px system-ui`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("⭐", px, pz);
  }
  const labels = mapView.scale >= 1 / 4;
  for (const wp of mapMarkers()) {
    const [px, pz] = toScreen(wp.x, wp.z);
    if (px < -200 * dpr || pz < -50 * dpr || px > w + 50 * dpr || pz > h + 50 * dpr) continue;
    const sel = mapView.selected && mapView.selected.item === wp;
    g.beginPath();
    g.arc(px, pz, (sel ? 8 : 6) * dpr, 0, Math.PI * 2);
    g.fillStyle = wp.public ? "#f3c760" : "#7fb2ff";
    g.fill();
    g.lineWidth = 2 * dpr;
    g.strokeStyle = sel ? "#ffffff" : "#1b1f1a";
    g.stroke();
    if (labels || sel) {
      g.font = `600 ${12 * dpr}px system-ui`;
      g.textAlign = "left";
      g.textBaseline = "middle";
      g.lineWidth = 3 * dpr;
      g.strokeStyle = "rgba(0,0,0,.75)";
      g.strokeText(wp.name, px + 10 * dpr, pz);
      g.fillStyle = "#ffffff";
      g.fillText(wp.name, px + 10 * dpr, pz);
    }
  }
  mapPopup(toScreen, dpr);
  $("#map-scale").textContent = mapView.scale >= 1 ? `${mapView.scale} px je Block` : `1 px = ${Math.round(1 / mapView.scale)} Blöcke`;
}

function mapPopup(toScreen, dpr) {
  const box = $("#map-popup");
  const sel = mapView.selected;
  if (!sel) { box.hidden = true; return; }
  let title, lines;
  if (sel.kind === "spawn") {
    title = "⭐ Weltspawn";
    lines = [`X ${sel.item.x} · Z ${sel.item.z}`];
  } else {
    const w = sel.item;
    const travel = w.travels ? `${w.travels}× bereist${w.last_travel ? `, zuletzt ${fmtDate(w.last_travel)}` : ""}` : "noch nicht bereist";
    title = `📍 ${w.name}`;
    lines = [`${w.owner} · ${w.public ? "öffentlich" : "privat"}${w.physical ? "" : " · ohne Bauwerk"}`,
             `X ${Math.floor(w.x)} · Y ${Math.floor(w.y)} · Z ${Math.floor(w.z)}`, travel];
  }
  box.replaceChildren(el("strong", { textContent: title }), ...lines.map((t) => el("div", { textContent: t })));
  const [px, pz] = toScreen(sel.kind === "spawn" ? sel.item.x + 0.5 : sel.item.x, sel.kind === "spawn" ? sel.item.z + 0.5 : sel.item.z);
  box.style.left = `${px / dpr}px`;
  box.style.top = `${pz / dpr}px`;
  box.hidden = false;
}

function mapHitTest(sx, sz) {
  const r = $("#map-canvas").getBoundingClientRect();
  const at = (x, z) => [(x - mapView.cx) * mapView.scale + r.width / 2, (z - mapView.cz) * mapView.scale + r.height / 2];
  let best = null, bestD = MAP_HIT;
  for (const w of mapMarkers()) {
    const [px, pz] = at(w.x, w.z);
    const d = Math.hypot(px - sx, pz - sz);
    if (d <= bestD) { best = { kind: "wp", item: w }; bestD = d; }
  }
  const sp = mapView.dim === "overworld" && mapView.index && mapView.index.spawn;
  if (!best && sp) {
    const [px, pz] = at(sp[0] + 0.5, sp[1] + 0.5);
    if (Math.hypot(px - sx, pz - sz) <= MAP_HIT) best = { kind: "spawn", item: { x: sp[0], z: sp[1] } };
  }
  return best;
}

function mapZoom(factor, sx, sz) {
  const { c } = mapCanvas();
  const r = c.getBoundingClientRect();
  sx = sx ?? r.width / 2; sz = sz ?? r.height / 2;
  const bx = mapView.cx + (sx - r.width / 2) / mapView.scale, bz = mapView.cz + (sz - r.height / 2) / mapView.scale;
  const ns = Math.min(MAP_MAX_SCALE, Math.max(MAP_MIN_SCALE, mapView.scale * factor));
  mapView.cx = bx - (sx - r.width / 2) / ns;
  mapView.cz = bz - (sz - r.height / 2) / ns;
  mapView.scale = ns;
  mapDraw();
}

function mapSetupInput() {
  const c = document.getElementById("map-canvas");
  const pointers = new Map();
  let pinch = null, clickStart = null, moved = 0;
  const local = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  c.addEventListener("pointerdown", (e) => {
    c.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, local(e));
    pinch = null;
    clickStart = pointers.size === 1 ? local(e) : null;
    moved = 0;
  });
  c.addEventListener("pointermove", (e) => {
    const p = local(e);
    if (mapView.index) {
      const r = c.getBoundingClientRect();
      const bx = Math.floor(mapView.cx + (p[0] - r.width / 2) / mapView.scale);
      const bz = Math.floor(mapView.cz + (p[1] - r.height / 2) / mapView.scale);
      document.getElementById("map-coords").textContent = `X ${bx} · Z ${bz}`;
    }
    const prev = pointers.get(e.pointerId);
    if (!prev) return;
    pointers.set(e.pointerId, p);
    moved += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
    if (pointers.size === 1) {
      mapView.cx -= (p[0] - prev[0]) / mapView.scale;
      mapView.cz -= (p[1] - prev[1]) / mapView.scale;
      mapDraw();
    } else if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch) mapZoom(d / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      pinch = d;
    }
  });
  const up = (e) => { pointers.delete(e.pointerId); pinch = null; };
  c.addEventListener("pointerup", (e) => {
    const click = clickStart && pointers.size === 1 && moved < 6;
    up(e);
    clickStart = null;
    if (!click || !mapView.index) return;
    mapView.selected = mapHitTest(...local(e));  // a click next to all markers closes the popup
    mapDraw();
  });
  c.addEventListener("pointercancel", up);
  c.addEventListener("wheel", (e) => { e.preventDefault(); const p = local(e); mapZoom(e.deltaY < 0 ? 1.25 : 0.8, p[0], p[1]); }, { passive: false });
  document.getElementById("map-zoom-in").addEventListener("click", () => mapZoom(2));
  document.getElementById("map-zoom-out").addEventListener("click", () => mapZoom(0.5));
  document.getElementById("map-home").addEventListener("click", () => { mapHome(); mapDraw(); });
  document.getElementById("map-wp-toggle").addEventListener("change", (e) => {
    mapView.showWaypoints = e.target.checked;
    if (!mapView.showWaypoints && mapView.selected && mapView.selected.kind === "wp") mapView.selected = null;
    mapDraw();
  });
  document.getElementById("map-render").addEventListener("click", async () => {
    try { await api("POST", "/api/map/render"); toast("Karte wird neu gezeichnet"); } catch (e) { toast(e.message, true); }
  });
  window.addEventListener("resize", () => { if (!document.getElementById("tab-map").hidden) mapDraw(); });
}
mapSetupInput();
