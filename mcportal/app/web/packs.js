"use strict";
// Tab "Funktionen" (M17): everyone sees the features that run, with the recipes of their own items;
// the admin also sees the switched-off ones and switches them. Uses helpers from app.js.

const PACK_STATE = {
  on: ["✓ an", "on"],
  off: ["aus", "off"],
  pending_on: ["⏳ an nach Neustart", "pending"],
  pending_off: ["⏳ aus nach Neustart", "pending"],
  failed: ["✗ nicht gestartet", "failed"],
};
let packsKey = null;

function packsVisible() { return !$("#tab-features").hidden; }

async function loadPacks() {
  const err = $("#packs-error");
  try {
    if (admin) renderPacks(await api("GET", "/api/packs"));
    else renderPacks({ ...(await api("GET", "/api/features")), writable: true, restart_needed: false, public: true });
  } catch (e) {
    err.hidden = false;
    err.textContent = e.message;
  }
}

function itemPicture(item, cls) {
  const box = el("div", { className: cls, title: item.name });
  if (item.icon) {
    const img = el("img", { src: item.icon, alt: item.name, loading: "lazy" });
    // no picture (offline, unknown texture): the name instead
    img.addEventListener("error", () => img.replaceWith(el("span", { className: "ph", textContent: item.name })));
    box.append(img);
  } else {
    box.append(el("span", { className: "ph", textContent: item.name }));
  }
  return box;
}

function recipeView(r) {
  const cells = [];
  const counts = new Map();
  for (let y = 0; y < 3; y++) {
    for (let x = 0; x < 3; x++) {
      const it = (r.grid[y] || [])[x] || null;
      cells.push(it ? itemPicture(it, "recipe-cell") : el("div", { className: "recipe-cell" }));
      if (it) counts.set(it.name, (counts.get(it.name) || 0) + 1);
    }
  }
  const result = itemPicture(r.result, "recipe-result");
  if (r.result.count > 1) result.append(el("span", { className: "recipe-count", textContent: r.result.count }));
  const legend = [...counts].map(([name, n]) => `${n}× ${name}`).join(", ");
  return el("div", { className: "recipe" },
    el("div", { className: "recipe-grid", role: "img", ariaLabel: `Rezept für ${r.result.name}` }, ...cells),
    el("span", { className: "recipe-arrow", textContent: "→" }),
    result,
    el("p", { className: "recipe-legend" },
      el("strong", { textContent: `${r.result.count > 1 ? `${r.result.count}× ` : ""}${r.result.name}` }),
      `${r.shapeless ? " (Anordnung egal)" : ""}: ${legend}`));
}

function renderPacks(data) {
  const err = $("#packs-error");
  err.hidden = data.writable;
  err.textContent = data.writable ? "" : "Das Portal darf die Pack-Listen der Welt nicht ändern. Einmal auf dem "
    + "Server ausführen: sudo bash ~/mcfs/mcportal/deploy/install.sh";
  $("#packs-restart").hidden = !data.restart_needed;
  const ul = $("#packs-list");
  if (!data.features.length) {
    ul.replaceChildren(el("li", { className: "empty", textContent: data.public
      ? "Gerade läuft reines Minecraft, ohne Erweiterungen." : "Keine Packs in der Welt." }));
    return;
  }
  ul.replaceChildren(...data.features.map((f) => {
    const title = el("div", { className: "pack-title" }, el("strong", { textContent: f.name }));
    const main = el("div", { className: "pack-main" }, title, el("small", { textContent: f.description }));
    const li = el("li", { className: "pack" }, main);
    if (!data.public) {
      const [text, cls] = PACK_STATE[f.state] || [f.state, ""];
      title.append(el("span", { className: `pack-state ${cls}`, textContent: text }));
      const versions = f.packs.map((p) => `${p.kind === "resource" ? "Grafik " : ""}${p.version}`).join(" · ");
      const warn = [];
      if (f.items) warn.push("eigene Gegenstände");
      if (f.entities) warn.push("eigene Kreaturen");
      main.append(el("small", { className: "pack-meta", textContent: `Version ${versions}${warn.length ? ` · ${warn.join(", ")}` : ""}` }));
      const btn = el("button", {
        className: `btn small${f.enabled ? "" : " primary"}`, type: "button",
        textContent: f.enabled ? "Ausschalten" : "Einschalten", disabled: !data.writable,
      });
      btn.addEventListener("click", () => switchPack(f, !f.enabled));
      title.append(btn);   // in the title row, so a recipe keeps the full width
    }
    if (f.recipes && f.recipes.length) main.append(el("div", { className: "recipes" }, ...f.recipes.map(recipeView)));
    return li;
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
  } catch (e) { toast(e.message, true); }
}

// loaded before app.js (no "$" yet at this point)
document.getElementById("packs-restart-btn").addEventListener("click", async () => {
  const n = state ? state.players.length : 0;
  let question = "Server jetzt neu starten?";
  if (n) question += `\n\n${n} Spieler ${n === 1 ? "ist" : "sind"} gerade online und ${n === 1 ? "wird" : "werden"} getrennt.`;
  if (!(await dialog(question))) return;
  try {
    await api("POST", "/api/server/restart");
    toast("Neustart gestartet …");
  } catch (e) { toast(e.message, true); }
});

// called from render() in app.js with every status update
function packsOnState(s) {
  const p = s.packs || { off: [], restart_needed: false };
  // no events pack running: the whole tab disappears
  const eventsTab = document.querySelector('.tabs button[data-tab="events"]');
  eventsTab.classList.toggle("pack-hidden", p.off.includes("mcportal_events"));
  if (eventsTab.classList.contains("pack-hidden") && !$("#tab-events").hidden) showTab("home");
  const key = `${p.off.join(",")}|${p.restart_needed}|${s.status}|${s.busy}`;
  if (packsKey !== key && packsKey !== null && packsVisible()) loadPacks();
  packsKey = key;
}
