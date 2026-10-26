"use strict";
// Card "Events" on the overview: running timed events with a live countdown, automatic on/off,
// start/stop buttons, history.
// Loaded before app.js; uses its helpers ($, el, api, toast, dialog, fmtDate, now, state) only inside functions.

const EVENT_NAMES = { storm: "🌧️ Unwetter", mining_rush: "💎 Mining Rush", lucky_day: "🍀 Glückstag" };
const EVENT_BY = { auto: "automatisch", console: "Portal/Konsole", time: "Zeit abgelaufen" };
const EVENTS_RESYNC_MS = 60_000; // while an event runs: fresh remaining times from the pack every minute
let eventsKey = null;
let eventsData = null;
let eventsLoadedAt = 0;

const eventName = (t) => EVENT_NAMES[t] || t;
const evMinutes = (sec) => {
  const m = Math.max(1, Math.round(sec / 60));
  return m >= 60 ? `${Math.floor(m / 60)} Std.${m % 60 ? ` ${m % 60} Min.` : ""}` : `${m} Min.`;
};
const evBy = (by) => (by && by.startsWith("player:") ? by.slice(7) : EVENT_BY[by] || by || "–");

async function loadEvents() {
  eventsLoadedAt = Date.now();
  try {
    renderEvents(await api("GET", "/api/gameevents"));
  } catch (e) { /* card stays as it is */ }
}

// Event time only runs while somebody is online (the pack counts online minutes).
// Between two reports of the pack the countdown runs here; it is corrected with every new report.
const somebodyOnline = () => !!(state && state.status === "online" && state.players.length);

function evRemaining(a) {
  const since = eventsData && eventsData.state_at ? Math.max(0, now() - eventsData.state_at) : 0;
  return Math.max(0, a.remaining - (somebodyOnline() ? since : 0));
}

function evClock(sec) {
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const two = (n) => String(n).padStart(2, "0");
  return h ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`;
}

function tickEvents() {
  if (!eventsData || !eventsData.active.length || $("#tab-home").hidden) return;
  const paused = !somebodyOnline();
  for (const a of eventsData.active) {
    const row = document.querySelector(`[data-event="${a.type}"]`);
    if (!row) continue;
    const left = evRemaining(a);
    row.querySelector(".ev-timer").textContent = paused ? "⏸ pausiert" : left > 0 ? evClock(left) : "endet gleich …";
    row.querySelector(".ev-note").textContent = paused
      ? `noch ${evClock(left)} · läuft weiter, sobald jemand online ist`
      : `von ${evMinutes(a.total)} · ${evBy(a.by)}`;
    row.querySelector(".ev-bar > span").style.width = `${Math.min(100, 100 * (1 - left / (a.total || 1)))}%`;
  }
  if (Date.now() - eventsLoadedAt > EVENTS_RESYNC_MS) loadEvents();
}
setInterval(tickEvents, 1000);

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
  eventsData = d;
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
      const li = el("li", { className: "ev-running" },
        el("div", { className: "ev-top" },
          el("strong", { textContent: eventName(a.type) }),
          el("span", { className: "ev-timer", title: "Restzeit (läuft nur, solange jemand online ist)" }),
          stop),
        el("div", { className: "ev-bar" }, el("span")),
        el("small", { className: "ev-note" }));
      li.dataset.event = a.type;
      return li;
    }));
  } else {
    const next = d.auto === false ? "Automatik ist aus."
      : d.next_in != null ? `Nächstes Event in ca. ${evMinutes(d.next_in * 60)} gemeinsamer Spielzeit.` : "";
    running.replaceChildren(el("li", { className: "empty", textContent: `Gerade läuft kein Event. ${next}` }));
  }
  tickEvents();

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
