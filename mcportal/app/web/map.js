"use strict";
// World map tab: tiles from /api/map/tiles, pan (drag/touch), zoom (wheel, pinch, buttons).
// Loaded before app.js; uses its helpers ($, el, api, toast, fmtDate) only inside functions.

const MAP_DIMS = { overworld: "Oberwelt", the_end: "Ende" };
const MAP_MIN_SCALE = 1 / 256, MAP_MAX_SCALE = 8;
const mapView = { index: null, dim: "overworld", cx: 0, cz: 0, scale: 0.5, images: new Map(), placed: false };
let mapBuild = null;

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
  } catch (e) { toast(e.message, true); }
}

function mapOnState(s) {
  if (!s.map) return;
  renderMapState(s.map);
  if (s.map.build !== mapBuild && !$("#tab-map").hidden) loadMap();
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
    b.addEventListener("click", () => { mapView.dim = d; mapView.images.clear(); mapHome(); renderDimButtons(); mapDraw(); });
    return b;
  }));
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
  if (!dim) return;
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
  if (mapView.dim === "overworld" && idx.spawn) {
    const px = (idx.spawn[0] - left) * s, pz = (idx.spawn[1] - top) * s;
    g.font = `${16 * dpr}px system-ui`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("⭐", px, pz);
  }
  $("#map-scale").textContent = mapView.scale >= 1 ? `${mapView.scale} px je Block` : `1 px = ${Math.round(1 / mapView.scale)} Blöcke`;
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
  let pinch = null;
  const local = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  c.addEventListener("pointerdown", (e) => { c.setPointerCapture(e.pointerId); pointers.set(e.pointerId, local(e)); pinch = null; });
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
  c.addEventListener("pointerup", up);
  c.addEventListener("pointercancel", up);
  c.addEventListener("wheel", (e) => { e.preventDefault(); const p = local(e); mapZoom(e.deltaY < 0 ? 1.25 : 0.8, p[0], p[1]); }, { passive: false });
  document.getElementById("map-zoom-in").addEventListener("click", () => mapZoom(2));
  document.getElementById("map-zoom-out").addEventListener("click", () => mapZoom(0.5));
  document.getElementById("map-home").addEventListener("click", () => { mapHome(); mapDraw(); });
  document.getElementById("map-render").addEventListener("click", async () => {
    try { await api("POST", "/api/map/render"); toast("Karte wird neu gezeichnet"); } catch (e) { toast(e.message, true); }
  });
  window.addEventListener("resize", () => { if (!document.getElementById("tab-map").hidden) mapDraw(); });
}
mapSetupInput();
