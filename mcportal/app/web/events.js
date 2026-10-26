"use strict";
// Tab "Events": running timed events with a live countdown (night events: "beginnt in …" until nightfall),
// automatic on/off, start/stop buttons, history, weather and time of day.
// The overview only gets a one-line hint while an event runs.
// Loaded before app.js; uses its helpers ($, el, api, toast, dialog, fmtDate, now, state) only inside functions.

const EVENT_NAMES = {
  storm: "🌧️ Unwetter", mining_rush: "💎 Mining Rush", lucky_day: "🍀 Glückstag",
  blood_moon: "🌕 Blutmond", zombie_invasion: "🧟 Zombie-Invasion", bounty: "👑 Kopfgeld",
  meteor: "☄️ Meteorit", shooting_stars: "🌠 Sternschnuppen", treasure: "🗺️ Schatzsuche", haunted: "👻 Spukort",
};
const UNDO_NAMES = { meteor: "☄️ Meteoritenkrater", treasure: "🗺️ Schatztruhe" };
const EVENT_BY = { auto: "automatisch", console: "Portal/Konsole", time: "Zeit abgelaufen", dawn: "Sonnenaufgang",
  killed: "besiegt", died: "verunglückt", found: "gefunden", broken: "Fluch gebrochen", fizzled: "verglüht" };
const EVENTS_RESYNC_MS = 60_000; // while an event runs: fresh remaining times from the pack every minute
const WEATHER_TEXT = { clear: "Klar", rain: "Regen", thunder: "Gewitter" };
const TIME_TEXT = { morning: "Morgen", noon: "Mittag", evening: "Abend", night: "Nacht", midnight: "Mitternacht" };
let eventsKey = null;
let eventsData = null;
let eventsLoadedAt = 0;

const eventName = (t) => EVENT_NAMES[t] || t;
const evMinutes = (sec) => {
  const m = Math.max(1, Math.round(sec / 60));
  return m >= 60 ? `${Math.floor(m / 60)} Std.${m % 60 ? ` ${m % 60} Min.` : ""}` : `${m} Min.`;
};
const evBy = (by) => (by && by.startsWith("player:") ? by.slice(7) : EVENT_BY[by] || by || "–");
const eventsVisible = () => !$("#tab-events").hidden || !$("#tab-home").hidden;

async function loadEvents() {
  eventsLoadedAt = Date.now();
  try {
    renderEvents(await api("GET", "/api/gameevents"));
  } catch (e) { /* stays as it is */ }
}

// Event time only runs while somebody is online (the pack counts online minutes; Minecraft time stands
// still without players). Between two reports of the pack the countdown runs here and is corrected later.
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

/** what the pack tells about the world-changing events */
function eventDetail(a) {
  if (a.meteor) {
    return a.meteor.impacted ? `eingeschlagen bei X ${a.meteor.x} · Y ${a.meteor.y} · Z ${a.meteor.z}`
      : `Einschlag gleich bei X ${a.meteor.x} · Y ${a.meteor.y} · Z ${a.meteor.z}`;
  }
  if (a.type === "meteor") return "sucht einen Einschlagort";
  if (a.treasure) return a.treasure.found ? "gefunden" : a.treasure.buried ? "vergraben" : "wird vergraben, sobald jemand in die Nähe kommt";
  if (a.haunt) return `${a.haunt.village ? "im Dorf" : "bei"} X ${a.haunt.x} · Z ${a.haunt.z} · Fluch ${a.haunt.kills} / 15`;
  return null;
}

/** timer text, note and progress (0..1) of a running event */
function evProgress(a) {
  const left = evRemaining(a);
  const paused = !somebodyOnline();
  const boss = a.boss ? `${a.boss.name} · zuletzt bei X ${a.boss.x}${a.boss.y ? ` · Y ${a.boss.y}` : ""} · Z ${a.boss.z}` : null;
  const extra = [boss, eventDetail(a)].filter(Boolean).join(" · ") || null;
  if (a.phase === "waiting") {
    return { timer: paused ? "⏸ pausiert" : `in ${evClock(left)}`, done: 0,
      note: `wartet auf die Nacht · beginnt in ca. ${evMinutes(left)} · ${evBy(a.by)}` };
  }
  return {
    timer: paused ? "⏸ pausiert" : left > 0 ? evClock(left) : "endet gleich …",
    done: Math.min(1, 1 - left / (a.total || 1)),
    note: paused ? `noch ${evClock(left)} · läuft weiter, sobald jemand online ist`
      : [extra, a.phase === "running" ? "bis Sonnenaufgang" : `von ${evMinutes(a.total)}`, evBy(a.by)].filter(Boolean).join(" · "),
  };
}

function tickEvents() {
  if (!eventsData || !eventsVisible()) return;
  for (const a of eventsData.active) {
    const row = document.querySelector(`#events-running [data-event="${a.type}"]`);
    if (!row) continue;
    const p = evProgress(a);
    row.querySelector(".ev-timer").textContent = p.timer;
    row.querySelector(".ev-note").textContent = p.note;
    row.querySelector(".ev-bar > span").style.width = `${100 * p.done}%`;
  }
  renderHomeHint();
  if (eventsData.active.length && Date.now() - eventsLoadedAt > EVENTS_RESYNC_MS) loadEvents();
}
setInterval(tickEvents, 1000);

/** overview: one line per running event, link to the Events tab */
function renderHomeHint() {
  const card = $("#home-event");
  const list = eventsData ? eventsData.active : [];
  card.hidden = !list.length;
  if (!list.length) return;
  $("#home-event-text").textContent = list.map((a) => `${eventName(a.type)} ${evProgress(a).timer}`).join(" · ");
}

function eventsOnState(s) {
  const key = String(s.events && s.events.updated);
  if (eventsKey !== key && eventsVisible()) loadEvents();
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

async function worldCommand(kind, value, question) {
  if (!(await dialog(question))) return;
  try {
    await api("POST", `/api/world/${kind}`, { value });
    toast(kind === "weather" ? `Wetter: ${WEATHER_TEXT[value]}` : `Tageszeit: ${TIME_TEXT[value]}`);
  } catch (e) { toast(e.message, true); }
}

function renderEvents(d) {
  eventsData = d;
  $("#events-missing").hidden = d.installed;
  $("#events-body").hidden = !d.installed;
  renderHomeHint();
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
    const b = el("button", { className: "btn small", textContent: eventName(t), type: "button", title: `${eventName(t)} starten` });
    b.onclick = () => eventCommand("start", t, `${eventName(t)} jetzt starten? Alle Spieler sehen die Ankündigung.`);
    return b;
  }));

  const hist = $("#events-history");
  hist.replaceChildren(...(d.history.length ? d.history.slice(0, 8).map((h) => el("li", {},
    el("span", { textContent: `${eventName(h.type)} · ${fmtDate(h.started || h.ended)}${h.ran ? ` · ${evMinutes(h.ran)}` : ""}`
      + (h.stopped_by && h.stopped_by !== "time" ? ` · ${evBy(h.stopped_by)}` : "") }),
    el("small", { textContent: h.participants.length ? `dabei: ${h.participants.join(", ")}` : "niemand lange genug dabei" })))
    : [el("li", { className: "empty", textContent: "Noch keine Events." })]));

  $("#events-register").textContent = d.register != null
    ? `🛡️ Geschützt: ${d.register.toLocaleString("de-DE")} Chunks mit Bauten – dort verändern Events keine Blöcke `
      + "(alles, was Spieler gesetzt haben, und was die Karte als bebaut erkennt)." : "";
  const undoList = $("#events-undo");
  undoList.replaceChildren(...(d.undo.length ? d.undo.map((id) => {
    const [kind, n] = id.split("-");
    const b = el("button", { className: "btn small danger", textContent: "Rückgängig", type: "button" });
    b.onclick = async () => {
      if (!(await dialog(`${UNDO_NAMES[kind] || kind} #${n} rückgängig machen? Alle Blöcke, die noch so sind, wie `
        + "das Event sie hinterlassen hat, werden wie vorher. Jemand muss in der Nähe sein, damit der Bereich geladen ist."))) return;
      try {
        await api("POST", "/api/gameevents/undo", { value: id });
        toast("Befehl gesendet");
        setTimeout(loadEvents, 1500);
      } catch (e) { toast(e.message, true); }
    };
    return el("li", {}, el("span", { textContent: `${UNDO_NAMES[kind] || kind} #${n}` }), b);
  }) : [el("li", { className: "empty", textContent: "Keine Blockänderungen durch Events." })]));
  const people = Object.entries(d.participations || {});
  $("#events-people").textContent = people.length
    ? people.map(([n, c]) => `${n} ${c}×`).join(" · ") : "Noch niemand.";
}

function setupWorldButtons() {
  const weather = document.getElementById("world-weather");
  for (const [value, label] of [["clear", "☀️ Klar"], ["rain", "🌧️ Regen"], ["thunder", "⛈️ Gewitter"]]) {
    const b = document.createElement("button");
    Object.assign(b, { className: "btn small", type: "button", textContent: label });
    b.onclick = () => worldCommand("weather", value, `Wetter auf „${WEATHER_TEXT[value]}“ stellen?`);
    weather.append(b);
  }
  const time = document.getElementById("world-time");
  for (const [value, label] of [["morning", "🌅 Morgen"], ["noon", "☀️ Mittag"], ["evening", "🌇 Abend"],
    ["night", "🌙 Nacht"], ["midnight", "🌌 Mitternacht"]]) {
    const b = document.createElement("button");
    Object.assign(b, { className: "btn small", type: "button", textContent: label });
    b.onclick = () => worldCommand("time", value, `Tageszeit auf „${TIME_TEXT[value]}“ stellen? Alle Spieler sehen es sofort.`);
    time.append(b);
  }
}
setupWorldButtons();
