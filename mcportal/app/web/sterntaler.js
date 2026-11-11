"use strict";
// Tab "Sterntaler" (M19): balances of all players, the shop's offer and how to earn - for everyone;
// the admin also sees the ledger and can give or take Sterntaler. Bought is in the game only (/shop).
// Loaded before app.js; uses its helpers ($, el, api, toast, dialog, fmtDate, state) only inside functions.

const SHOP_PACK = "mcportal_shop";
const TALER_REASONS = {
  participation: "Event mitgemacht", bounty: "Kopfgeld-Boss besiegt", treasure_found: "Schatz gefunden",
  coven_defeated: "Hexenzirkel gesprengt", curse_broken: "Fluch gebrochen", meteor_hit: "Meteoriteneinschlag miterlebt",
  lightning_survived: "Blitz im Unwetter überlebt", star: "Sternstück gefunden", buy: "Gekauft",
  seed: "Startguthaben für frühere Events", admin: "Vom Admin",
};
const TALER_REWARD_ORDER = ["participation", "bounty", "treasure_found", "coven_defeated", "curse_broken",
  "meteor_hit", "lightning_survived", "star"];
let talerKey = null;
let talerData = null;

const talerVisible = () => !$("#tab-taler").hidden;
const talerOff = (s) => !!(s && s.packs && s.packs.off.includes(SHOP_PACK));

async function loadTaler() {
  try {
    renderTaler(await api("GET", "/api/sterntaler"));
  } catch (e) { toast(e.message, true); }
}

function talerReason(b, data) {
  const base = TALER_REASONS[b.reason] || b.reason;
  if (!b.detail) return base;
  if (b.reason === "participation") return `${base}: ${eventName(b.detail)}`;
  if (b.reason === "buy") return `${base}: ${(data.items.find((i) => i.id === b.detail) || { name: b.detail }).name}`;
  return `${base}: ${b.detail}`;
}

function shopOffer(items, currency) {
  return el("ul", { className: "taler-shop" }, ...items.map((i) => el("li", {},
    itemPicture({ name: i.name, icon: i.icon }, "recipe-result"),
    el("div", { className: "taler-item" },
      el("div", { className: "taler-item-head" },
        el("strong", { textContent: i.name }),
        el("span", { className: "taler-price", textContent: `⭐ ${i.price} ${currency}` })),
      el("small", { textContent: i.desc })))));
}

function renderTaler(data) {
  talerData = data;
  const cur = data.currency;
  $("#taler-missing").hidden = data.installed;
  $("#taler-body").hidden = !data.installed;
  if (!data.installed) return;

  const rank = $("#taler-rank");
  rank.replaceChildren(...(data.players.length ? data.players.map((p, i) => {
    const bought = Object.entries(p.bought || {})
      .map(([id, n]) => `${n > 1 ? `${n}× ` : ""}${(data.items.find((x) => x.id === id) || { name: id }).name}`).join(", ");
    return el("li", {},
      el("span", { className: "taler-place", textContent: `${i + 1}.` }),
      el("span", { className: "taler-name" }, el("strong", { textContent: p.name }),
        el("small", { textContent: `verdient ${p.earned}${p.spent ? ` · ausgegeben ${p.spent}` : ""}`
          + `${bought ? ` · gekauft: ${bought}` : ""}` })),
      el("span", { className: "taler-balance", textContent: `⭐ ${p.balance}` }));
  }) : [el("li", { className: "empty", textContent: `Noch hat niemand ${cur} – das nächste Event kommt bestimmt.` })]));

  $("#taler-shop").replaceChildren(shopOffer(data.items, cur));
  $("#taler-rewards").replaceChildren(...TALER_REWARD_ORDER.filter((k) => data.rewards[k]).map((k) => el("li", {},
    el("span", { textContent: TALER_REASONS[k] }),
    el("span", { className: "taler-price", textContent: `${k === "participation" ? "" : "+"}${data.rewards[k]}` }))));

  if (!data.ledger) return;  // not the admin
  const names = new Set([...data.players.map((p) => p.name), ...((state && state.players) || []).map((p) => p.name)]);
  $("#taler-names").replaceChildren(...[...names].sort().map((n) => el("option", { value: n })));
  const seed = data.seed || { planned: {}, pending: [] };
  const planned = Object.entries(seed.planned);
  $("#taler-seed").textContent = planned.length
    ? `Startguthaben für frühere Events: ${planned.map(([n, a]) => `${n} ${a}`).join(", ")}`
      + (seed.pending.length ? ` – noch nicht gebucht: ${seed.pending.join(", ")} (kommt, sobald der Server läuft).` : " – gebucht.")
    : "";
  $("#taler-ledger").replaceChildren(...(data.ledger.length ? data.ledger.map((b) => el("li", {},
    el("span", {}, el("strong", { textContent: b.player }), ` ${talerReason(b, data)}`),
    el("span", { className: `taler-delta ${b.delta < 0 ? "minus" : "plus"}`,
      textContent: `${b.delta > 0 ? "+" : ""}${b.delta}` }),
    el("small", { textContent: `${fmtDate(b.at)} · Kontostand ${b.balance}` })))
    : [el("li", { className: "empty", textContent: "Noch keine Buchungen." })]));
}

// loaded before app.js (no "$" yet at this point)
document.getElementById("taler-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const player = $("#taler-player").value.trim();
  const amount = Number($("#taler-amount").value);
  if (!player || !Number.isInteger(amount) || amount === 0) { toast("Spieler und Betrag angeben (Minus zieht ab).", true); return; }
  const cur = talerData ? talerData.currency : "Sterntaler";
  const q = amount > 0 ? `${player} ${amount} ${cur} gutschreiben?` : `${player} ${-amount} ${cur} abziehen?`;
  if (!(await dialog(q))) return;
  try {
    await api("POST", "/api/sterntaler/grant", { player, amount });
    toast(amount > 0 ? `${amount} ${cur} für ${player}` : `${-amount} ${cur} von ${player} abgezogen`);
    $("#taler-amount").value = "";
  } catch (e) { toast(e.message, true); }
});

// called from render() in app.js with every status update
function talerOnState(s) {
  // shop pack switched off (tab Funktionen): no tab, no tiles
  const tab = document.querySelector('.tabs button[data-tab="taler"]');
  tab.classList.toggle("pack-hidden", talerOff(s));
  if (talerOff(s) && talerVisible()) showTab("home");
  const key = `${s.sterntaler && s.sterntaler.updated}`;
  if (talerKey !== key && talerKey !== null && talerVisible()) loadTaler();
  talerKey = key;
}
