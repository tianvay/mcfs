// Sterntaler & shop - rules without @minecraft/server, tested with node (tests/core.test.mjs).

export const CURRENCY = "Sterntaler";
export const PROP_PREFIX = "mcfs_shop:"; // + player name -> JSON {b: balance, e: earned in all, s: start credit given}
export const MAX_GRANT = 999;

/** what the shop sells; `id` is the item of this pack (items/*.json) */
export const ITEMS = [
  { id: "mcfs:bergbrecher", name: "Bergbrecher", price: 20,
    desc: "Spitzhacke, die 3 × 3 × 3 Blöcke Gestein und Erz auf einmal abbaut. Schleichen: nur ein Block." },
  { id: "mcfs:holzfaeller", name: "Holzfäller-Axt", price: 15,
    desc: "Fällt einen ganzen Baum mit einem Schlag. Schleichen: nur ein Block." },
  { id: "mcfs:magnet", name: "Magnet-Amulett", price: 20,
    desc: "Zieht herumliegende Gegenstände aus 8 Blöcken an, solange es in der Schnellleiste oder Zweithand liegt. "
      + "Schleichen: Pause." },
  { id: "mcfs:erntesichel", name: "Ernte-Sichel", price: 15,
    desc: "Erntet reife Feldfrüchte in 3 × 3 und pflanzt gleich neu." },
];

/** Sterntaler per occasion; "participation" = took part in an event (rule of the events pack) */
export const REWARDS = {
  participation: 5,
  bounty: 5,
  treasure_found: 5,
  coven_defeated: 3,
  curse_broken: 3,
  meteor_hit: 2,
  lightning_survived: 2,
  star: 1,
};

/** texts for the chat line of a booking */
export const REASON_TEXT = {
  participation: "Event mitgemacht",
  bounty: "Kopfgeld-Boss besiegt",
  treasure_found: "Schatz gefunden",
  coven_defeated: "Hexenzirkel gesprengt",
  curse_broken: "Fluch gebrochen",
  meteor_hit: "Meteoriteneinschlag miterlebt",
  lightning_survived: "Blitz überlebt",
  star: "Sternstück gefunden",
  seed: "Startguthaben für frühere Events",
  admin: "vom Admin",
};

const names = (list) => [...new Set((Array.isArray(list) ? list : []).filter((n) => typeof n === "string" && n))];

/**
 * Bookings for one news message of the events pack (system.sendScriptEvent "mcfs:event_news"):
 * [{player, amount, reason, detail}]
 */
export function rewardsFor(n) {
  if (!n || typeof n !== "object") return [];
  const each = (players, reason, detail) => names(players)
    .map((player) => ({ player, amount: REWARDS[reason], reason, detail }));
  switch (n.event) {
    case "ended": return each(n.participants, "participation", typeof n.type === "string" ? n.type : undefined);
    case "bounty": return each(n.hunters, "bounty", typeof n.boss === "string" ? n.boss : undefined);
    case "coven_defeated":
    case "curse_broken":
    case "meteor_hit": return each(n.players, n.event);
    case "treasure_found":
    case "star":
    case "lightning_survived": return each([n.player], n.event);
    default: return [];
  }
}

export function emptyAccount() {
  return { b: 0, e: 0 };
}

export function readAccount(raw) {
  try {
    const d = typeof raw === "string" ? JSON.parse(raw) : null;
    if (d && Number.isFinite(d.b) && Number.isFinite(d.e)) {
      return { b: Math.max(0, Math.trunc(d.b)), e: Math.max(0, Math.trunc(d.e)), ...(d.s ? { s: 1 } : {}) };
    }
  } catch { /* broken entry: start again */ }
  return emptyAccount();
}

/**
 * Account after a booking of `amount` (negative = spent / taken away), plus what was really booked:
 * the balance never goes below 0. Positive amounts count as earned, except the admin's corrections.
 */
export function book(account, amount, reason) {
  const delta = Math.max(Math.trunc(amount), -account.b);
  const next = { ...account, b: account.b + delta };
  if (delta > 0 && reason !== "admin") next.e = account.e + delta;
  if (reason === "seed") next.s = 1;
  return { account: next, delta };
}

export const canAfford = (account, item) => account.b >= item.price;

const NAME = /^[A-Za-z0-9](?:[A-Za-z0-9 _-]{0,30}[A-Za-z0-9_-])?(?:#\d{1,4})?$/;

/**
 * console / portal: "grant <amount> <name>" (admin: +/-), "seed <amount> <name>" (start credit, once per player),
 * "balances" (complete list into the log)
 */
export function parseControl(message) {
  const text = String(message ?? "").trim();
  if (text === "balances") return { action: "balances" };
  const m = /^(grant|seed) (-?\d{1,4}) (.+)$/.exec(text);
  if (!m) return { action: "error", message: `unbekannt: ${text.slice(0, 40)}` };
  const amount = Number(m[2]);
  const name = m[3].trim();
  if (!NAME.test(name) || name.includes("  ")) return { action: "error", message: "ungültiger Spielername" };
  if (amount === 0 || Math.abs(amount) > MAX_GRANT) return { action: "error", message: "ungültiger Betrag" };
  if (m[1] === "seed" && amount < 0) return { action: "error", message: "ungültiger Betrag" };
  return { action: m[1], amount, name };
}

// ---------- Bergbrecher ----------

/**
 * What the Bergbrecher takes along around the block that was mined: natural rock and ores only. Worked stone
 * (bricks, cobblestone, polished ...), furnaces, chests and everything else people build with stays.
 */
const ROCK = new Set(["stone", "deepslate", "granite", "diorite", "andesite", "tuff", "calcite", "dripstone_block",
  "basalt", "smooth_basalt", "blackstone", "gilded_blackstone", "netherrack", "end_stone", "sandstone",
  "red_sandstone", "hardened_clay", "magma", "amethyst_block", "ancient_debris", "raw_iron_block",
  "raw_copper_block", "raw_gold_block"]);

export function isCubeBlock(typeId) {
  const id = String(typeId).replace(/^minecraft:/, "");
  if (ROCK.has(id)) return true;
  if (/_ore$/.test(id)) return true;                              // all ores, also lit redstone ore, nether ores
  return /_terracotta$/.test(id) && !/glazed/.test(id);           // badlands; glazed terracotta is built
}

/** the 26 blocks around (0, 0, 0) */
export function cubeOffsets() {
  const out = [];
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
    if (dx || dy || dz) out.push({ x: dx, y: dy, z: dz });
  }
  return out;
}

// ---------- Holzfäller-Axt ----------

export const TREE_MAX_LOGS = 96;

export function isLog(typeId) {
  const id = String(typeId).replace(/^minecraft:/, "");
  return !id.startsWith("stripped_") && id !== "mushroom_stem" && /_(log|stem)$/.test(id);
}

export function isLeaves(typeId) {
  const id = String(typeId).replace(/^minecraft:/, "");
  return /_leaves$/.test(id) || /^(leaves2?|azalea_leaves_flowered|nether_wart_block|warped_wart_block|shroomlight)$/.test(id);
}

const key = (p) => `${p.x},${p.y},${p.z}`;

/**
 * The logs of the tree that `start` belongs to: connected logs (also diagonally), never below the start block.
 * `at(pos)` -> "log" | "leaves" | "other". Returns {logs: [pos...], leaves: boolean}; a trunk without leaves next to
 * it is no tree (a log cabin, a fence post) - the caller then leaves it alone. Stops at TREE_MAX_LOGS.
 */
export function treeLogs(start, at, max = TREE_MAX_LOGS) {
  const seen = new Set([key(start)]);
  const queue = [start];
  const logs = [];
  let leaves = false;
  while (queue.length && logs.length < max) {
    const p = queue.shift();
    logs.push(p);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
      if (!dx && !dy && !dz) continue;
      const q = { x: p.x + dx, y: p.y + dy, z: p.z + dz };
      if (q.y < start.y || seen.has(key(q))) continue;
      seen.add(key(q));
      const kind = at(q);
      if (kind === "leaves") leaves = true;
      else if (kind === "log") queue.push(q);
    }
  }
  return { logs, leaves };
}

// ---------- Ernte-Sichel ----------

/** crops the sickle harvests: block id -> [state name, value when ripe] */
export const CROPS = {
  "minecraft:wheat": ["growth", 7],
  "minecraft:carrots": ["growth", 7],
  "minecraft:potatoes": ["growth", 7],
  "minecraft:beetroot": ["growth", 7],
  "minecraft:nether_wart": ["age", 3],
};

export const isCrop = (typeId) => typeId in CROPS;

export function isRipe(typeId, states) {
  const c = CROPS[typeId];
  return !!c && states?.[c[0]] === c[1];
}

/** the 3 x 3 around (0, 0), same height */
export function fieldOffsets() {
  const out = [];
  for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) out.push({ x: dx, y: 0, z: dz });
  return out;
}

// ---------- wear ----------

/** damage after `uses` more uses; {damage, broken} */
export function wear(damage, max, uses) {
  const next = damage + Math.max(0, uses);
  return next >= max ? { damage: max, broken: true } : { damage: next, broken: false };
}

// ---------- Magnet ----------

export const MAGNET_RADIUS = 8;
export const MAGNET_WAIT_TICKS = 40; // an item lies this long before it is pulled (what you throw away stays a moment)
