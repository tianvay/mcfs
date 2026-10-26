"use strict";

const $ = (sel) => document.querySelector(sel);
const STATUS_TEXT = {
  online: "🟢 SERVER ONLINE",
  offline: "🔴 SERVER OFFLINE",
  starting: "🟡 Server startet …",
  stopping: "🟡 Server stoppt …",
  failed: "🔴 Server-Fehler",
  unknown: "Status unbekannt",
};
const ACTION_TEXT = { start: "Starten", stop: "Stoppen", restart: "Neustart", update: "Update" };
const AUDIT_TEXT = {
  SERVER_START: "Server gestartet", SERVER_STOP: "Server gestoppt", SERVER_RESTART: "Server neu gestartet",
  WHITELIST_ADD: "Whitelist: hinzugefügt", WHITELIST_REMOVE: "Whitelist: entfernt", LOGIN: "PIN-Anmeldung",
  OPERATOR_GRANT: "Operator-Rechte vergeben", OPERATOR_REVOKE: "Operator-Rechte entzogen",
  UPDATE: "Server-Update",
};

let state = null;
let clockOffset = 0; // server time - client time
let lastAllowCount = null;
let lastStatsUpdate = null;

// ---------- helpers ----------

function el(tag, props = {}, ...children) {
  const e = document.createElement(tag);
  Object.assign(e, props);
  for (const c of children) e.append(c);
  return e;
}

function fmtDate(ts) {
  if (!ts) return "–";
  return new Date(ts * 1000).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

function fmtDuration(sec) {
  sec = Math.max(0, Math.floor(sec));
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${m}m`;
  return `${m}m ${sec % 60}s`;
}

function now() { return Date.now() / 1000 + clockOffset; }

let toastTimer;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), isError ? 6000 : 3000);
}

function dialog(text, { input = false } = {}) {
  const dlg = $("#dlg");
  $("#dlg-text").textContent = text;
  const inp = $("#dlg-input");
  inp.hidden = !input;
  inp.value = "";
  return new Promise((resolve) => {
    dlg.onclose = () => resolve(dlg.returnValue === "ok" ? (input ? inp.value : true) : null);
    dlg.returnValue = "";
    dlg.showModal();
    if (input) inp.focus();
  });
}

async function api(method, path, body) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
    if (res.status === 401 && attempt === 0 && path !== "/api/login") {
      const pin = await dialog("Bitte PIN eingeben:", { input: true });
      if (pin === null) throw new Error("Abgebrochen");
      await api("POST", "/api/login", { pin });
      continue;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.detail || `Fehler ${res.status}`);
    return data;
  }
}

// ---------- tabs ----------

function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${name}`));
  try { sessionStorage.setItem("tab", name); } catch {}
  if (name === "allow") loadAllowlist();
  if (name === "stats") loadStats();
  if (name === "server") loadAudit();
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.goto)));

// ---------- status ----------

function render(s) {
  const prevBusy = state && state.busy;
  state = s;
  clockOffset = s.now - Date.now() / 1000;

  $("#server-name").textContent = "Minecraft Family Server";
  const badge = $("#status-badge");
  badge.className = `badge ${s.status}`;
  badge.textContent = s.busy ? `🟡 ${ACTION_TEXT[s.busy] || s.busy} läuft …` : STATUS_TEXT[s.status] || s.status;

  const n = s.players.length;
  $("#player-count").textContent = s.status === "online"
    ? `${n} ${n === 1 ? "Spieler" : "Spieler"} online${s.max_players ? ` (max. ${s.max_players})` : ""}`
    : "";
  const list = $("#player-list");
  list.replaceChildren(...s.players.map((p) =>
    el("li", {}, el("span", { textContent: p.name }), el("small", { textContent: `seit ${fmtDuration(now() - p.since)}` }))));

  $("#f-version").textContent = s.version || "–";
  $("#f-start").textContent = fmtDate(s.last_start);
  $("#f-update").textContent = fmtDate(s.last_update);
  $("#f-allow").textContent = s.allowlist_count == null ? "–" : `${s.allowlist_count} Spieler`;
  tickUptime();

  // server tab
  $("#srv-state").textContent = STATUS_TEXT[s.status] || s.status;
  const busy = $("#srv-busy");
  busy.hidden = !s.busy;
  busy.textContent = s.busy ? `${ACTION_TEXT[s.busy] || s.busy} läuft – bitte warten …` : "";
  const err = $("#srv-error");
  err.hidden = !s.last_error;
  err.textContent = s.last_error || "";
  const running = ["online", "starting"].includes(s.status);
  document.querySelector('[data-action="start"]').disabled = !!s.busy || running || s.status === "stopping";
  document.querySelector('[data-action="stop"]').disabled = !!s.busy || !running;
  document.querySelector('[data-action="restart"]').disabled = !!s.busy || !running;
  $("#srv-console-note").hidden = s.console_available || !running;

  renderUpdate(s);
  if (s.stats && s.stats.updated !== lastStatsUpdate && !$("#tab-stats").hidden) loadStats();
  lastStatsUpdate = s.stats ? s.stats.updated : null;

  if (prevBusy && !s.busy) loadAudit();
  if (lastAllowCount !== null && lastAllowCount !== s.allowlist_count && !$("#tab-allow").hidden) loadAllowlist();
  lastAllowCount = s.allowlist_count;
}

function tickUptime() {
  if (!state) return;
  $("#f-uptime").textContent = state.started_at ? fmtDuration(now() - state.started_at) : "–";
}
setInterval(tickUptime, 1000);

function connect() {
  const conn = $("#conn");
  const es = new EventSource("/api/events");
  es.onopen = () => { conn.className = "conn live"; conn.title = "Live verbunden"; };
  es.onmessage = (e) => render(JSON.parse(e.data));
  es.onerror = () => { conn.className = "conn down"; conn.title = "Verbindung unterbrochen – verbinde neu …"; };
}

// ---------- server control ----------

document.querySelectorAll("[data-action]").forEach((b) => b.addEventListener("click", async () => {
  const action = b.dataset.action;
  let question = `Server wirklich ${ACTION_TEXT[action].toLowerCase()}?`;
  const n = state ? state.players.length : 0;
  if (action !== "start" && n) question += `\n\n${n} Spieler ${n === 1 ? "ist" : "sind"} gerade online und ${n === 1 ? "wird" : "werden"} getrennt.`;
  if (!(await dialog(question))) return;
  try {
    await api("POST", `/api/server/${action}`);
    toast(`${ACTION_TEXT[action]} gestartet …`);
  } catch (e) { toast(e.message, true); }
}));

// ---------- update ----------

const JOB_TEXT = {
  running: "Update läuft – bitte die Seite offen lassen oder später wiederkommen.",
  success: null, failed: null, rolled_back: null, rollback_failed: null,
};

function renderUpdate(s) {
  const u = s.update;
  if (!u) return;
  const job = u.job;
  const running = job && job.state === "running";

  const hint = $("#home-update");
  hint.hidden = !(u.available || running);
  $("#home-update-text").textContent = running
    ? `⏳ Update auf ${job.to} läuft …`
    : `⬆ Update verfügbar: ${u.latest}`;

  $("#up-current").textContent = u.current || "–";
  $("#up-latest").textContent = u.latest || "–";
  let note = "";
  if (u.check_error) note = u.check_error;
  else if (u.checked_at) note = (u.available ? "Neue Version verfügbar. " : "Der Server ist aktuell. ")
    + `Zuletzt geprüft: ${fmtDate(u.checked_at)}`;
  $("#up-note").textContent = note;
  $("#up-start").hidden = !u.available || running;
  $("#up-start").disabled = !!s.busy;
  $("#up-check").disabled = running;

  $("#up-job").hidden = !job;
  if (job) {
    const msg = $("#up-job-msg");
    msg.textContent = job.state === "running" ? JOB_TEXT.running : (job.message || "");
    msg.className = "note" + (job.state === "success" ? " ok" : ["failed", "rollback_failed"].includes(job.state) ? " error" : "");
    $("#up-steps").replaceChildren(...job.steps.map((st) => el("li", { className: st.status, textContent: st.label })));
  }
  const b = u.last_backup;
  $("#up-backup").textContent = b
    ? `Letzte Sicherung vor einem Update: ${b.name.replace("_pre_update", "")}${b.size ? ` (${Math.round(b.size / 2 ** 20)} MB)` : ""}`
    : "";
}

$("#up-check").addEventListener("click", async () => {
  try {
    const u = await api("POST", "/api/update/check");
    toast(u.check_error ? u.check_error : u.available ? `Update verfügbar: ${u.latest}` : "Der Server ist aktuell.", !!u.check_error);
  } catch (e) { toast(e.message, true); }
});

$("#up-start").addEventListener("click", async () => {
  const u = state && state.update;
  if (!u) return;
  const n = state.players.length;
  let q = `Update von ${u.current} auf ${u.latest} installieren?\n\n`
    + "Ablauf: Download und Prüfung, Server stoppen, Backup, Dateien aktualisieren, Server starten. "
    + "Welt, Whitelist, Operatoren und server.properties bleiben erhalten. "
    + "Bei einem Fehler wird automatisch der alte Stand wiederhergestellt.\n\n"
    + "Der Server ist ca. 1–2 Minuten nicht erreichbar.";
  if (n) q += `\n\n${n} Spieler ${n === 1 ? "ist" : "sind"} online und ${n === 1 ? "wird" : "werden"} vorher im Chat gewarnt.`;
  if (!(await dialog(q))) return;
  try {
    await api("POST", "/api/update/start");
    toast("Update gestartet …");
  } catch (e) { toast(e.message, true); }
});

// ---------- statistics ----------

const BLOCK_NAMES = {
  stone: "Stein", cobblestone: "Bruchstein", dirt: "Erde", grass_block: "Grasblock", sand: "Sand",
  gravel: "Kies", glass: "Glas", torch: "Fackel", oak_planks: "Eichenholzbretter", spruce_planks: "Fichtenholzbretter",
  birch_planks: "Birkenholzbretter", oak_log: "Eichenstamm", spruce_log: "Fichtenstamm", birch_log: "Birkenstamm",
  stone_bricks: "Steinziegel", bricks: "Ziegelsteine", deepslate: "Tiefenschiefer", cobbled_deepslate: "Bruchtiefenschiefer",
  netherrack: "Netherrack", obsidian: "Obsidian", diamond_ore: "Diamanterz", deepslate_diamond_ore: "Tiefenschiefer-Diamanterz",
  iron_ore: "Eisenerz", deepslate_iron_ore: "Tiefenschiefer-Eisenerz", coal_ore: "Steinkohle", copper_ore: "Kupfererz",
  gold_ore: "Golderz", crafting_table: "Werkbank", furnace: "Ofen", chest: "Truhe", tnt: "TNT", water: "Wasser",
  lava: "Lava", oak_leaves: "Eichenlaub", andesite: "Andesit", diorite: "Diorit", granite: "Granit", tuff: "Tuffstein",
  white_wool: "Weiße Wolle", ladder: "Leiter", oak_door: "Eichenholztür", glass_pane: "Glasscheibe",
  farmland: "Ackerboden", wheat: "Weizen", sandstone: "Sandstein", snow_layer: "Schnee", ice: "Eis", clay: "Ton",
};

function blockName(id) {
  const key = id.replace(/^minecraft:/, "");
  if (BLOCK_NAMES[key]) return BLOCK_NAMES[key];
  return key.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

const fmtNum = (n) => n.toLocaleString("de-DE");

function bars(items, cls) {
  const max = items.length ? items[0][1] : 1;
  return el("ul", { className: `bars ${cls}` }, ...items.map(([id, n]) => {
    const bar = el("span", { className: "bar" });
    bar.style.width = `${Math.max(4, (100 * n) / max)}%`;
    return el("li", {}, bar, el("span", { textContent: blockName(id) }), el("span", { textContent: fmtNum(n) }));
  }));
}

async function loadStats() {
  let data;
  try { data = await api("GET", "/api/stats"); } catch (e) { toast(e.message, true); return; }
  const note = $("#stats-note");
  if (!data.pack_seen && !data.since) {
    note.textContent = "Die Statistik ist noch nicht aktiv: Das Statistik-Paket ist noch nicht in der Welt installiert.";
  } else {
    note.textContent = `Gezählt seit ${fmtDate(data.since)} · zuletzt aktualisiert ${fmtDate(data.updated)}. `
      + "Neue Blöcke erscheinen mit bis zu 20 Sekunden Verzögerung.";
  }
  const list = $("#stats-list");
  if (!data.players.length) {
    list.replaceChildren(el("p", { className: "empty", textContent: "Noch keine Blöcke gezählt." }));
    return;
  }
  list.replaceChildren(...data.players.map((p) => el("div", { className: "stat-player" },
    el("h3", {}, el("span", { textContent: p.name }),
      el("small", { textContent: p.last_active ? `zuletzt ${fmtDate(p.last_active)}` : "" })),
    el("div", { className: "stat-totals" },
      el("span", { className: "placed", textContent: `▲ ${fmtNum(p.placed)} gesetzt` }),
      el("span", { className: "broken", textContent: `▼ ${fmtNum(p.broken)} abgebaut` })),
    el("div", { className: "stat-cols" },
      el("div", {}, el("h4", { textContent: "Am meisten gesetzt" }), bars(p.top_placed, "placed")),
      el("div", {}, el("h4", { textContent: "Am meisten abgebaut" }), bars(p.top_broken, "broken"))))));
}

// ---------- allowlist ----------

async function loadAllowlist() {
  try {
    renderAllowlist(await api("GET", "/api/allowlist"));
  } catch (e) { toast(e.message, true); }
}

function renderAllowlist(data) {
  const note = $("#allow-note");
  note.hidden = data.mode !== "blocked";
  note.textContent = data.reason || "";
  const blocked = data.mode === "blocked";
  $("#allow-form").querySelectorAll("input, button").forEach((x) => (x.disabled = blocked));

  const ul = $("#allow-list");
  if (!data.entries.length) {
    ul.replaceChildren(el("li", { className: "empty", textContent: "Noch keine Spieler auf der Whitelist." }));
    return;
  }
  ul.replaceChildren(...data.entries.map((e) => {
    const tags = [e.online ? "online" : null, e.xuid ? null : "noch nie verbunden"]
      .filter(Boolean).join(" · ");
    const opBlocked = data.op_mode === "blocked" || !e.xuid;
    const op = el("button", {
      className: `btn small${e.operator ? " on" : ""}`,
      textContent: e.operator ? "★ Operator" : "☆ Operator",
      disabled: opBlocked,
      title: !e.xuid ? "Erst möglich, nachdem der Spieler einmal auf dem Server war"
        : data.op_mode === "blocked" ? (data.op_reason || "")
        : e.operator ? "Operator-Rechte entziehen" : "Zum Operator machen",
    });
    op.addEventListener("click", async () => {
      const q = e.operator
        ? `${e.name} die Operator-Rechte entziehen?`
        : `${e.name} zum Operator machen?\n\nOperatoren dürfen Befehle nutzen, z. B. Spielmodus ändern, teleportieren oder andere Spieler kicken.`;
      if (!(await dialog(q))) return;
      try {
        renderAllowlist(await api("PUT", `/api/allowlist/${encodeURIComponent(e.name)}/operator`, { operator: !e.operator }));
        toast(e.operator ? `${e.name} ist kein Operator mehr` : `${e.name} ist jetzt Operator`);
      } catch (err) { toast(err.message, true); }
    });
    const rm = el("button", { className: "btn small danger", textContent: "Entfernen", disabled: blocked });
    rm.addEventListener("click", async () => {
      if (!(await dialog(`${e.name} von der Whitelist entfernen?`))) return;
      try {
        renderAllowlist(await api("DELETE", `/api/allowlist/${encodeURIComponent(e.name)}`));
        toast(`${e.name} entfernt`);
      } catch (err) { toast(err.message, true); }
    });
    return el("li", {},
      el("span", { className: `dot ${e.online ? "on" : ""}`, title: e.online ? "online" : "offline" }),
      el("span", { className: "name", textContent: `✓ ${e.name}` }, el("span", { className: "tags", textContent: tags })),
      el("span", { className: "actions" }, op, rm));
  }));
}

$("#allow-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const input = $("#allow-name");
  const name = input.value.trim();
  if (!name) return;
  const btn = ev.target.querySelector("button");
  btn.disabled = true;
  try {
    renderAllowlist(await api("POST", "/api/allowlist", { name }));
    input.value = "";
    toast(`${name} hinzugefügt`);
  } catch (e) { toast(e.message, true); }
  finally { btn.disabled = false; }
});

// ---------- audit ----------

async function loadAudit() {
  try {
    const items = await api("GET", "/api/audit?limit=20");
    const ul = $("#audit-list");
    if (!items.length) { ul.replaceChildren(el("li", { className: "empty", textContent: "Noch keine Aktionen." })); return; }
    ul.replaceChildren(...items.map((a) => el("li", {},
      el("div", {}, `${AUDIT_TEXT[a.action] || a.action}${a.player ? `: ${a.player}` : ""}${a.from ? `: ${a.from} → ${a.to}` : ""} `,
        el("span", { className: a.result, textContent: a.result === "SUCCESS" ? "✓" : "✗ fehlgeschlagen" })),
      el("div", { className: "meta", textContent: `${a.time} · ${a.user}${a.error ? ` · ${a.error}` : ""}` }))));
  } catch (e) { /* not critical */ }
}

// ---------- start ----------

let initial = "home";
try { initial = sessionStorage.getItem("tab") || "home"; } catch {}
showTab(initial);
connect();
