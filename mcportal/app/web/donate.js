"use strict";
// Tab "Spenden": choose a player (or everybody online), an item and an amount, then give it.
// The item pictures are Mojang's own (downloaded once by the portal); until then a coloured letter stands in.
// Loaded before app.js; uses its helpers ($, el, api, toast, state) only inside functions.

const gift = { data: null, player: null, item: "diamond", count: 16, cat: "popular", query: "", sending: false };
const GIFT_ALL = "@a";

const giftItem = (id) => gift.data && gift.data.items.find((i) => i.id === id);
const giftVisible = () => document.body.classList.contains("admin") && !$("#tab-donate").hidden;

async function loadDonate() {
  try {
    gift.data = await api("GET", "/api/donate");
  } catch (e) { $("#gift-note").textContent = e.message; $("#gift-note").hidden = false; return; }
  renderDonate();
}

/** live player list: re-read when somebody joins or leaves while the tab is open */
let giftPlayersKey = null;
function donateOnState(s) {
  const key = s.players.map((p) => p.name).join("|") + `|${s.status}`;
  if (key !== giftPlayersKey && giftPlayersKey !== null && giftVisible()) loadDonate();
  giftPlayersKey = key;
}

// soft hyphen after the material, so "Diamantspitzhacke" breaks as "Diamant-/spitzhacke" in the small tiles
const GIFT_PREFIX = /^(Diamant|Netherit|Eisen|Gold|Kupfer|Smaragd|Eichen|Schildkröten|Erfahrungs|Feuerwerks|Melonen|Honig|Namens|Knochen|Amethyst|Bücher|Stein|Ziegel|Kürbis|Lapis|Nether|Süß|Ofen)(?=\p{Ll}{3})/u;
const giftTileName = (name) => name.replace(GIFT_PREFIX, "$1­");

function giftIcon(item, cls = "gift-icon") {
  if (item.icon) {
    const img = el("img", { className: cls, src: `/api/donate/icons/${item.id}.png`, alt: "", loading: "lazy", decoding: "async" });
    img.addEventListener("error", () => img.replaceWith(giftIcon({ ...item, icon: false }, cls)), { once: true });
    return img;
  }
  // placeholder until the portal has the picture: first letter on a colour derived from the id
  let h = 0;
  for (const c of item.id) h = (h * 31 + c.charCodeAt(0)) % 360;
  const ph = el("span", { className: `${cls} gift-ph`, textContent: item.name.charAt(0) });
  ph.style.background = `hsl(${h} 45% 45%)`;
  return ph;
}

function stackText(item, n) {
  if (item.stack === 1) return "nicht stapelbar";
  const full = Math.floor(n / item.stack), rest = n % item.stack;
  if (!full) return `von ${item.stack} pro Stapel`;
  return `${full} Stapel${rest ? ` + ${rest}` : ""}`;
}

function quickAmounts(item) {
  if (item.stack === 1) return [1, 2, 3, 5].filter((n) => n <= item.max);
  if (item.stack === 16) return [1, 4, 8, 16, 32];
  return [1, 8, 16, 32, 64, 128];
}

function renderDonate() {
  const d = gift.data;
  if (!d) return;
  const note = $("#gift-note");
  note.hidden = d.console;
  note.textContent = d.console ? "" : "Der Server läuft gerade nicht – Geschenke gehen nur, wenn er online ist.";

  // the chosen player may have left; "Alle online" makes no sense with nobody there
  const online = d.online;
  if (gift.player === GIFT_ALL ? !online.length : !online.includes(gift.player)) gift.player = online.length === 1 ? online[0] : null;

  renderGiftPlayers();
  renderGiftCats();
  renderGiftItems();
  renderGiftAmount();
  renderGiftSummary();
  renderGiftRecent();
}

function renderGiftPlayers() {
  const d = gift.data;
  const chip = (value, label, extra) => {
    const b = el("button", { type: "button", className: `gift-chip${gift.player === value ? " sel" : ""}` }, ...extra, label);
    b.setAttribute("aria-pressed", gift.player === value);
    b.addEventListener("click", () => { gift.player = value; renderGiftPlayers(); renderGiftSummary(); });
    return b;
  };
  const chips = d.online.map((n) => chip(n, n, [el("span", { className: "dot on" })]));
  if (d.online.length > 1) chips.push(chip(GIFT_ALL, `Alle online (${d.online.length})`, ["👥 "]));
  const off = d.offline.map((n) => el("span", { className: "gift-chip off", title: "Nur Spieler im Spiel können etwas bekommen" },
    el("span", { className: "dot" }), `${n}`));
  const box = $("#gift-players");
  box.replaceChildren(...chips, ...off);
  if (!chips.length) box.prepend(el("p", { className: "note small gift-none", textContent: "Gerade ist niemand online." }));
}

function renderGiftCats() {
  $("#gift-cats").replaceChildren(...gift.data.categories.map((c) => {
    const b = el("button", { type: "button", className: `gift-cat${!gift.query && gift.cat === c.id ? " sel" : ""}`, textContent: c.name });
    b.addEventListener("click", () => {
      gift.cat = c.id; gift.query = ""; $("#gift-search").value = "";
      renderGiftCats(); renderGiftItems();
    });
    return b;
  }));
}

const giftNorm = (s) => s.toLowerCase().replace(/ä/g, "a").replace(/ö/g, "o").replace(/ü/g, "u").replace(/ß/g, "ss");

function renderGiftItems() {
  const q = giftNorm(gift.query.trim());
  const items = gift.data.items.filter((i) => (q
    ? giftNorm(i.name).includes(q) || i.id.includes(q.replace(/ /g, "_"))
    : gift.cat === "popular" ? i.popular : i.cat === gift.cat));
  const grid = $("#gift-items");
  if (!items.length) { grid.replaceChildren(el("p", { className: "empty", textContent: "Kein Item gefunden." })); return; }
  grid.replaceChildren(...items.map((i) => {
    const b = el("button", { type: "button", className: `gift-item${gift.item === i.id ? " sel" : ""}`, title: i.name },
      giftIcon(i), el("span", { textContent: giftTileName(i.name) }));
    b.setAttribute("aria-pressed", gift.item === i.id);
    b.addEventListener("click", () => selectGiftItem(i.id));
    return b;
  }));
}

function selectGiftItem(id) {
  const prev = giftItem(gift.item), item = giftItem(id);
  gift.item = id;
  // from 16 diamonds to a sword: start again at 1 instead of 16 swords
  if (item.stack !== (prev && prev.stack)) gift.count = Math.min(gift.count, item.stack === 1 ? 1 : item.stack);
  gift.count = Math.min(gift.count, item.max);
  renderGiftItems(); renderGiftAmount(); renderGiftSummary();
}

function setGiftCount(n) {
  const item = giftItem(gift.item);
  gift.count = Math.max(1, Math.min(item ? item.max : 1, Math.round(Number(n) || 1)));
  renderGiftAmount(); renderGiftSummary();
}

function renderGiftAmount() {
  const item = giftItem(gift.item);
  if (!item) return;
  const inp = $("#gift-count");
  if (document.activeElement !== inp) inp.value = gift.count;
  inp.max = item.max;
  $("#gift-stack").textContent = stackText(item, gift.count);
  $("#gift-quick").replaceChildren(...quickAmounts(item).map((n) => {
    const label = n === 2 * item.stack && item.stack > 1 ? "2 Stapel" : String(n);
    const b = el("button", { type: "button", className: `gift-q${gift.count === n ? " sel" : ""}`, textContent: label });
    b.addEventListener("click", () => setGiftCount(n));
    return b;
  }));
}

function giftWho() {
  if (gift.player === GIFT_ALL) return "alle, die online sind";
  return gift.player;
}

function renderGiftSummary() {
  const item = giftItem(gift.item);
  const box = $("#gift-summary");
  const text = $("#gift-summary-text");
  box.querySelector(".gift-sum-icon").replaceChildren(item ? giftIcon(item, "gift-icon big") : "");
  if (!item) { text.textContent = "Wähle ein Item."; return; }
  const what = `${gift.count}× ${item.name}`;
  text.replaceChildren(
    el("strong", { textContent: gift.player ? `${what} an ${giftWho()}` : what }),
    el("small", { textContent: gift.player
      ? (gift.player === GIFT_ALL ? "Jeder bekommt eine Chat-Nachricht im Spiel." : `${gift.player} bekommt eine Chat-Nachricht im Spiel.`)
      : "Oben noch einen Spieler wählen." }));
  $("#gift-send").disabled = gift.sending;
}

function renderGiftRecent() {
  const ul = $("#gift-recent");
  const recent = gift.data.recent;
  if (!recent.length) { ul.replaceChildren(el("li", { className: "empty", textContent: "Noch nichts gespendet." })); return; }
  ul.replaceChildren(...recent.map((r) => {
    const item = giftItem(r.item);
    const again = el("button", { type: "button", className: "btn small", textContent: "Nochmal" });
    again.addEventListener("click", () => {
      if (item) { gift.item = item.id; gift.count = Math.min(r.count, item.max); }
      if (r.player === "alle online") gift.player = gift.data.online.length ? GIFT_ALL : null;
      else if (gift.data.online.includes(r.player)) gift.player = r.player;
      else toast(`${r.player} ist gerade nicht online.`, true);
      renderDonate();
      $("#gift-summary").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    return el("li", {}, item ? giftIcon(item) : "",
      el("span", { className: "gift-rec-text" }, `${r.count}× ${item ? item.name : r.item} → ${r.player}`,
        el("small", { textContent: r.time.slice(0, 16) })), again);
  }));
}

async function sendGift() {
  const item = giftItem(gift.item);
  if (!gift.player) { toast("Wähle zuerst, wer das Geschenk bekommt.", true); return; }
  if (!item) { toast("Wähle zuerst ein Item.", true); return; }
  gift.sending = true; renderGiftSummary();
  try {
    const r = await api("POST", "/api/donate", { player: gift.player, item: item.id, count: gift.count });
    toast(`🎁 ${r.count}× ${r.name} an ${r.player === "alle online" ? "alle" : r.player} geschickt`);
  } catch (e) { toast(e.message, true); }
  gift.sending = false;
  await loadDonate();
}

// after app.js has run (it defines $)
document.addEventListener("DOMContentLoaded", () => {
  $("#gift-search").addEventListener("input", (e) => { gift.query = e.target.value; renderGiftCats(); renderGiftItems(); });
  $("#gift-minus").addEventListener("click", () => setGiftCount(gift.count - 1));
  $("#gift-plus").addEventListener("click", () => setGiftCount(gift.count + 1));
  $("#gift-count").addEventListener("change", (e) => setGiftCount(e.target.value));
  $("#gift-count").addEventListener("blur", (e) => { e.target.value = gift.count; });
  $("#gift-send").addEventListener("click", sendGift);
});
