"use strict";
// Tab "Server" → card "Funktionen": switch the packs of the world on and off (M17). Uses helpers from app.js.

const PACK_STATE = {
  on: ["✓ an", "on"],
  off: ["aus", "off"],
  pending_on: ["⏳ an nach Neustart", "pending"],
  pending_off: ["⏳ aus nach Neustart", "pending"],
  failed: ["✗ nicht gestartet", "failed"],
};
let packsKey = null;

function packsVisible() { return admin && !$("#tab-server").hidden; }

async function loadPacks() {
  try {
    renderPacks(await api("GET", "/api/packs"));
  } catch (e) {
    const err = $("#packs-error");
    err.hidden = false;
    err.textContent = e.message;
  }
}

function renderPacks(data) {
  const err = $("#packs-error");
  err.hidden = data.writable;
  err.textContent = data.writable ? "" : "Das Portal darf die Pack-Listen der Welt nicht ändern. Einmal auf dem "
    + "Server ausführen: sudo bash ~/mcfs/mcportal/deploy/install.sh";
  $("#packs-restart").hidden = !data.restart_needed;
  const ul = $("#packs-list");
  if (!data.features.length) {
    ul.replaceChildren(el("li", { className: "empty", textContent: "Keine Packs in der Welt." }));
    return;
  }
  ul.replaceChildren(...data.features.map((f) => {
    const [text, cls] = PACK_STATE[f.state] || [f.state, ""];
    const versions = f.packs.map((p) => `${p.kind === "resource" ? "Grafik " : ""}${p.version}`).join(" · ");
    const btn = el("button", {
      className: `btn small${f.enabled ? "" : " primary"}`, type: "button",
      textContent: f.enabled ? "Ausschalten" : "Einschalten", disabled: !data.writable,
    });
    btn.addEventListener("click", () => switchPack(f, !f.enabled));
    const warn = [];
    if (f.items) warn.push("eigene Gegenstände");
    if (f.entities) warn.push("eigene Kreaturen");
    return el("li", { className: "pack" },
      el("div", { className: "pack-main" },
        el("div", { className: "pack-title" },
          el("strong", { textContent: f.name }),
          el("span", { className: `pack-state ${cls}`, textContent: text })),
        el("small", { textContent: f.description }),
        el("small", { className: "pack-meta", textContent: `Version ${versions}${warn.length ? ` · ${warn.join(", ")}` : ""}` })),
      btn);
  }));
}

function packWarning(f) {
  const lines = [`„${f.name}“ ausschalten?`];
  if (f.items) {
    lines.push(`⚠ Alle Gegenstände von „${f.name}“ – in Inventaren, Truhen und auf dem Boden – werden von Minecraft `
      + "gelöscht, sobald sie geladen werden. Sie kommen auch beim Wiedereinschalten nicht zurück.");
  }
  if (f.entities) lines.push("Laufende Events enden, Bosse und andere eigene Kreaturen verschwinden.");
  lines.push("Was das Pack in der Welt gespeichert hat, bleibt erhalten. Wirksam nach dem nächsten Neustart.");
  return lines.join("\n\n");
}

async function switchPack(f, enabled) {
  if (!enabled && !(await dialog(packWarning(f)))) return;
  try {
    renderPacks(await api("PUT", `/api/packs/${encodeURIComponent(f.id)}`, { enabled }));
    toast(`${f.name}: ${enabled ? "eingeschaltet" : "ausgeschaltet"} – wirksam nach dem Neustart`);
    loadAudit();
  } catch (e) { toast(e.message, true); }
}

// loaded before app.js (no "$" yet at this point)
document.getElementById("packs-restart-btn")
  .addEventListener("click", () => document.querySelector('[data-action="restart"]').click());

// called from render() in app.js with every status update
function packsOnState(s) {
  const p = s.packs || { off: [], restart_needed: false };
  const eventsOff = p.off.includes("mcportal_events");
  $(".events-card").classList.toggle("pack-off", eventsOff);
  $("#events-off").hidden = !eventsOff;
  // undoing meteor craters etc. goes through the events pack as well (weather/time are plain commands)
  const undo = $("#events-undo");
  undo.hidden = eventsOff;
  undo.previousElementSibling.hidden = eventsOff;
  document.querySelector('.tabs button[data-tab="events"]').classList.toggle("off", eventsOff);
  const key = `${p.off.join(",")}|${p.restart_needed}|${s.status}|${s.busy}`;
  if (packsKey !== key && packsKey !== null && packsVisible()) loadPacks();
  packsKey = key;
}
