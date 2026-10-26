"use strict";
// Card "Events" on the overview: running timed events, automatic on/off, start/stop buttons, history.
// Loaded before app.js; uses its helpers ($, el, api, toast, dialog, fmtDate) only inside functions.

const EVENT_NAMES = { storm: "🌧️ Unwetter", mining_rush: "💎 Mining Rush", lucky_day: "🍀 Glückstag" };
const EVENT_BY = { auto: "automatisch", console: "Portal/Konsole", time: "Zeit abgelaufen" };
let eventsKey = null;

const eventName = (t) => EVENT_NAMES[t] || t;
const evMinutes = (sec) => {
  const m = Math.max(1, Math.round(sec / 60));
  return m >= 60 ? `${Math.floor(m / 60)} Std.${m % 60 ? ` ${m % 60} Min.` : ""}` : `${m} Min.`;
};
const evBy = (by) => (by && by.startsWith("player:") ? by.slice(7) : EVENT_BY[by] || by || "–");

async function loadEvents() {
  try {
    renderEvents(await api("GET", "/api/gameevents"));
  } catch (e) { /* card stays as it is */ }
}

function eventsOnState(s) {
  const key = String(s.events && s.events.updated);
  if (eventsKey !== null && key !== eventsKey && !$("#tab-home").hidden) loadEvents();
  eventsKey = key;
}

async function eventCommand(action, type, question) {
  if (question && !(await dialog(question))) return;
  try {
    await api("POST", `/api/gameevents/${action}`, { type });
    toast("Befehl gesendet");
    setTimeout(loadEvents, 1500);
  } catch (e) { toast(e.message, true); }
}

function renderEvents(d) {
  const card = $("#events-card");
  card.hidden = false;
  $("#events-missing").hidden = d.installed;
  $("#events-body").hidden = !d.installed;
  if (!d.installed) return;

  const auto = $("#events-auto");
  auto.textContent = d.auto ? "Automatik: an" : "Automatik: aus";
  auto.className = "btn small" + (d.auto ? " on" : "");
  auto.onclick = () => eventCommand(d.auto ? "auto_off" : "auto_on", null,
    d.auto ? "Automatische Events ausschalten? Laufende Events laufen zu Ende." : null);

  const running = $("#events-running");
  if (d.active.length) {
    running.replaceChildren(...d.active.map((a) => {
      const stop = el("button", { className: "btn small danger", textContent: "Beenden", type: "button" });
      stop.onclick = () => eventCommand("stop", a.type, `${eventName(a.type)} jetzt beenden?`);
      return el("li", {},
        el("span", {}, el("strong", { textContent: eventName(a.type) }),
          el("small", { textContent: ` noch ca. ${evMinutes(a.remaining)} Spielzeit · ${evBy(a.by)}` })),
        stop);
    }));
  } else {
    const next = d.auto === false ? "Automatik ist aus."
      : d.next_in != null ? `Nächstes Event in ca. ${evMinutes(d.next_in * 60)} gemeinsamer Spielzeit.` : "";
    running.replaceChildren(el("li", { className: "empty", textContent: `Gerade läuft kein Event. ${next}` }));
  }

  const runningTypes = new Set(d.active.map((a) => a.type));
  $("#events-start").replaceChildren(...d.types.filter((t) => !runningTypes.has(t)).map((t) => {
    const b = el("button", { className: "btn small", textContent: `${eventName(t)} starten`, type: "button" });
    b.onclick = () => eventCommand("start", t, `${eventName(t)} jetzt starten? Alle Spieler sehen die Ankündigung.`);
    return b;
  }));

  const hist = $("#events-history");
  hist.replaceChildren(...(d.history.length ? d.history.slice(0, 5).map((h) => el("li", {},
    el("span", { textContent: `${eventName(h.type)} · ${fmtDate(h.started || h.ended)}${h.ran ? ` · ${evMinutes(h.ran)}` : ""}` }),
    el("small", { textContent: h.participants.length ? `dabei: ${h.participants.join(", ")}` : "niemand lange genug dabei" })))
    : [el("li", { className: "empty", textContent: "Noch keine Events." })]));
}
