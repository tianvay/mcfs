// Timed events - pure logic without Minecraft imports (tested with node --test tests/core.test.mjs).
//
// Time is counted in "online minutes": the clock only runs while at least one player is online.
// Every online minute adds 1 / interval(players) to a credit; at 1.0 an event is due (after a random
// delay of 0-10 minutes), but never earlier than MIN_GAP minutes after the last automatic start.

export const MIN_GAP = 60;           // minutes between automatic starts (= at most one per hour)
export const MAX_DELAY = 10;         // random delay after the credit is full
export const PARTICIPATION = 5 * 60; // seconds online during an event to count as "took part"

/**
 * event types; `minutes` = duration in online minutes, `category` for later meta achievements
 * (welt, ressourcen, mobs, community)
 */
export const TYPES = {
  storm: {
    name: "Unwetter", minutes: 40, color: "§9", category: "welt",
    subtitle: "§7Zwei Tage Gewitter – Blitze schlagen ein!", end: "Das Unwetter ist vorbei.",
  },
  mining_rush: {
    name: "Mining Rush", minutes: 120, color: "§b", category: "ressourcen",
    subtitle: "§72 Stunden doppelte Erze!", end: "Der Mining Rush ist vorbei.",
  },
  lucky_day: {
    name: "Glückstag", minutes: 120, color: "§a", category: "ressourcen",
    subtitle: "§72 Stunden doppelte Erfahrung!", end: "Der Glückstag ist vorbei.",
  },
};

// minutes of shared online time per event, by number of players online (index = players)
const INTERVALS = [Infinity, 180, 150, 120, 105, 90, 75, 75, 60, 60, 60];

export function intervalMinutes(players) {
  if (players <= 0) return Infinity;
  return INTERVALS[Math.min(players, INTERVALS.length - 1)];
}

export function newSchedule() {
  return { auto: true, clock: 0, credit: 0, delay: null, lastStart: -MIN_GAP, last: null };
}

/**
 * One online minute. Returns true when an automatic event should start now.
 * @param {object} s schedule (changed in place)
 * @param {number} players online
 * @param {() => number} rand random in [0, 1)
 */
export function scheduleMinute(s, players, rand) {
  if (players <= 0) return false;
  s.clock += 1;
  if (!s.auto) return false;
  if (s.delay === null) {
    s.credit += 1 / intervalMinutes(players);
    if (s.credit >= 1 - 1e-9) { // 180 x (1/180) is slightly below 1 in floating point
      s.credit = 0;
      s.delay = Math.floor(rand() * (MAX_DELAY + 1));
    }
  }
  if (s.delay === null) return false;
  if (s.delay > 0) {
    s.delay -= 1;
    return false;
  }
  if (s.clock - s.lastStart < MIN_GAP) return false; // due, but wait for the gap
  s.delay = null;
  s.lastStart = s.clock;
  return true;
}

/** rough "next event in" for the portal (online minutes), null if automatic events are off */
export function estimateNext(s, players) {
  if (!s.auto) return null;
  const gap = Math.max(0, MIN_GAP - (s.clock - s.lastStart));
  if (s.delay !== null) return Math.max(gap, s.delay);
  const iv = intervalMinutes(Math.max(players, 1));
  return Math.max(gap, Math.ceil((1 - s.credit) * iv));
}

/** random type that is implemented, not running and not the last one */
export function chooseType(available, active, last, rand) {
  const running = new Set(active.map((a) => a.type));
  let pool = available.filter((t) => !running.has(t) && t !== last);
  if (!pool.length) pool = available.filter((t) => !running.has(t));
  if (!pool.length) return null;
  return pool[Math.floor(rand() * pool.length)];
}

export function newActive(type, by) {
  return { type, remaining: TYPES[type].minutes * 60, total: TYPES[type].minutes * 60, seen: {}, by };
}

/**
 * One online minute for running events: count who is online, reduce the remaining time.
 * @returns {object[]} events that ran out
 */
export function activeMinute(active, playerNames) {
  if (!playerNames.length) return [];
  const ended = [];
  for (const a of active) {
    for (const n of playerNames) a.seen[n] = (a.seen[n] ?? 0) + 60;
    a.remaining -= 60;
    if (a.remaining <= 0) ended.push(a);
  }
  return ended;
}

/** players that took part: online at least PARTICIPATION seconds (or the whole time of a shorter run) */
export function participants(a) {
  const ran = a.total - Math.max(0, a.remaining);
  const need = Math.min(PARTICIPATION, Math.max(60, ran));
  return Object.entries(a.seen).filter(([, s]) => s >= need).map(([n]) => n).sort();
}

export function formatMinutes(seconds) {
  const m = Math.max(1, Math.round(seconds / 60));
  return m >= 60 ? `${Math.floor(m / 60)} Std. ${m % 60 ? `${m % 60} Min.` : ""}`.trim() : `${m} Min.`;
}

/** console / portal control: "start <type>" | "stop <type>" | "auto on|off" | "state" */
export function parseControl(message) {
  const [verb, arg, ...rest] = String(message ?? "").trim().split(/\s+/);
  if (rest.length) return null;
  if ((verb === "start" || verb === "stop") && arg in TYPES) return { verb, type: arg };
  if (verb === "auto" && (arg === "on" || arg === "off")) return { verb, on: arg === "on" };
  if (verb === "state" && !arg) return { verb };
  return null;
}

// ---------- Mining Rush ----------

/** ores whose drops are doubled; ancient debris stays rare on purpose */
export function isRushOre(blockId) {
  return blockId.endsWith("_ore") && blockId !== "minecraft:ancient_debris";
}

const ORE_DROPS = {
  coal_ore: "coal", iron_ore: "raw_iron", copper_ore: "raw_copper", gold_ore: "raw_gold", diamond_ore: "diamond",
  emerald_ore: "emerald", lapis_ore: "lapis_lazuli", redstone_ore: "redstone", nether_gold_ore: "gold_nugget",
  quartz_ore: "quartz",
};

/**
 * Only the ore's real drop is doubled: not the ore block itself (silk touch - that would multiply ore blocks)
 * and not items that just happen to lie next to it (thrown there on purpose).
 */
export function shouldDouble(dropId, oreId) {
  const ore = oreId.replace(/^minecraft:/, "").replace(/^(deepslate_|lit_)/, "").replace("deepslate_", "");
  const want = ORE_DROPS[ore];
  return !!want && dropId === `minecraft:${want}`;
}

// ---------- Glückstag ----------

/**
 * XP bonus for one poll: the gain since the last poll is given once more.
 * @returns {{bonus: number, last: number}} bonus to add and the new baseline (including the bonus)
 */
export function xpBonus(last, now) {
  if (last === undefined || now <= last) return { bonus: 0, last: now };
  const bonus = now - last;
  return { bonus, last: now + bonus };
}

// ---------- build register: chunks where players placed blocks ----------

const DIM_SHORT = { "minecraft:overworld": "o", "minecraft:nether": "n", "minecraft:the_end": "e" };

export function chunkKey(dim, x, z) {
  return `${DIM_SHORT[dim] ?? dim}${Math.floor(x / 16)},${Math.floor(z / 16)}`;
}

export const REGISTER_CHUNK_CHARS = 30000; // one dynamic property string stays below the 32 KB limit

/** split the register into strings that each fit into one dynamic property */
export function encodeRegister(keys) {
  const parts = [];
  let cur = "";
  for (const k of [...keys].sort()) {
    if (cur.length + k.length + 1 > REGISTER_CHUNK_CHARS) {
      parts.push(cur);
      cur = "";
    }
    cur += (cur ? ";" : "") + k;
  }
  if (cur) parts.push(cur);
  return parts;
}

export function decodeRegister(parts) {
  const keys = new Set();
  for (const p of parts) if (p) for (const k of p.split(";")) if (k) keys.add(k);
  return keys;
}

// ---------- lightning: only where nothing looks built ----------

const NATURAL = new Set([
  "grass_block", "dirt", "coarse_dirt", "podzol", "mycelium", "rooted_dirt", "sand", "red_sand", "gravel",
  "stone", "andesite", "diorite", "granite", "deepslate", "tuff", "calcite", "clay", "mud", "moss_block",
  "moss_carpet", "snow", "snow_layer", "powder_snow", "ice", "packed_ice", "blue_ice", "water", "flowing_water",
  "short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "deadbush", "sweet_berry_bush", "cactus",
  "sugar_cane", "bamboo", "vine", "kelp", "seagrass", "brown_mushroom", "red_mushroom", "pumpkin", "melon_block",
  "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower", "lily_of_the_valley",
  "sunflower", "lilac", "rose_bush", "peony", "pink_petals", "waterlily", "azalea", "flowering_azalea",
  "big_dripleaf", "small_dripleaf_block", "bush", "firefly_bush", "leaf_litter", "wildflowers", "short_dry_grass",
  "tall_dry_grass", "cactus_flower",
]);

export function isNaturalTop(typeId) {
  const n = String(typeId).replace(/^minecraft:/, "");
  if (NATURAL.has(n)) return true;
  if (n.endsWith("_leaves")) return true;
  if (/_tulip$/.test(n)) return true;
  return false;
}

/** random point 16-64 blocks around (x, z) */
export function lightningOffset(x, z, rand) {
  const angle = rand() * Math.PI * 2;
  const dist = 16 + rand() * 48;
  return { x: Math.floor(x + Math.cos(angle) * dist), z: Math.floor(z + Math.sin(angle) * dist) };
}
