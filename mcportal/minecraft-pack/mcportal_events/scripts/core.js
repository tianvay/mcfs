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
 * (welt, ressourcen, mobs, community). `night` events wait for the next night and end at dawn instead.
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
  blood_moon: {
    name: "Blutmond", night: true, color: "§4", category: "mobs",
    subtitle: "§7Heute Nacht streifen Wolfsrudel umher!", end: "Die Sonne geht auf – der Blutmond ist vorbei.",
    nightTitle: "§4Blutmond!", nightSubtitle: "§7Die Wölfe sind hungrig …",
  },
  zombie_invasion: {
    name: "Zombie-Invasion", night: true, color: "§2", category: "mobs",
    subtitle: "§7Heute Nacht greifen Zombies die Dörfer an!", end: "Die Sonne geht auf – die Zombies ziehen sich zurück.",
    nightTitle: "§2Zombie-Invasion!", nightSubtitle: "§7Verteidigt die Dörfer!",
  },
  bounty: {
    name: "Kopfgeld", minutes: 20, color: "§6", category: "mobs",
    subtitle: "§7Ein Boss treibt sein Unwesen – findet ihn!", end: "Der Boss ist entkommen.",
  },
  meteor: {
    name: "Meteorit", minutes: 30, color: "§c", category: "welt",
    subtitle: "§7Ein Meteor nähert sich – gleich schlägt er ein!", end: "Der Meteoritenkrater ist abgekühlt.",
  },
  treasure: {
    name: "Schatzsuche", minutes: 30, color: "§6", category: "ressourcen",
    subtitle: "§7Ein Schatz ist vergraben – folgt den Hinweisen!", end: "Der Schatz ist wieder verschwunden.",
  },
  haunted: {
    name: "Spukort", night: true, color: "§5", category: "mobs",
    subtitle: "§7Heute Nacht spukt es in der Nähe!", end: "Die Sonne geht auf – der Spuk ist vorbei.",
    nightTitle: "§5Es spukt!", nightSubtitle: "§7Besiegt die Spukgestalten und brecht den Fluch!",
  },
  creeper_chaos: {
    name: "Creeper-Chaos", night: true, color: "§a", category: "mobs",
    subtitle: "§7Heute Nacht wimmelt es von Creepern!", end: "Die Sonne geht auf – das Creeper-Chaos ist vorbei.",
    nightTitle: "§aCreeper-Chaos!", nightSubtitle: "§7Sssss … und manche sind geladen!",
  },
  witch_coven: {
    name: "Hexenzirkel", night: true, color: "§d", category: "mobs",
    subtitle: "§7Heute Nacht trifft sich ein Hexenzirkel!", end: "Die Sonne geht auf – der Hexenzirkel löst sich auf.",
    nightTitle: "§dHexenzirkel!", nightSubtitle: "§7Folgt den Funken und sprengt den Zirkel!",
  },
  shooting_stars: {
    name: "Sternschnuppen-Nacht", night: true, color: "§e", category: "welt",
    subtitle: "§7Heute Nacht fallen Sterne vom Himmel!", end: "Die Sternschnuppen-Nacht ist vorbei.",
    nightTitle: "§eSternschnuppen!", nightSubtitle: "§7Schaut nach oben – und sammelt die Sternenstücke!",
  },
};

// ---------- Schatzsuche ----------

export const TREASURE_DEPTH = 3;      // blocks below the surface
export const TREASURE_DISTANCE = [150, 400];

/** the treasure: always worth it, a little random. [item, amount][] */
export function treasureLoot(rand) {
  const n = (min, max) => min + Math.floor(rand() * (max - min + 1));
  const loot = [["minecraft:diamond", n(2, 4)], ["minecraft:emerald", n(4, 8)], ["minecraft:gold_ingot", n(3, 6)],
    ["minecraft:experience_bottle", n(4, 8)]];
  const special = ["minecraft:golden_apple", "minecraft:name_tag", "minecraft:saddle", "minecraft:totem_of_undying"];
  const r = rand();
  loot.push([special[r < 0.4 ? 0 : r < 0.7 ? 1 : r < 0.9 ? 2 : 3], 1]);
  return loot;
}

/** how far, roughly - the exact distance would make it too easy */
export function distanceBand(d) {
  if (d < 12) return "direkt hier – grabt nach!";
  if (d < 30) return "ganz nah";
  if (d < 100) return "nah";
  if (d < 200) return "ein Stück entfernt";
  return "noch weit weg";
}

/**
 * hint for one player: compass direction, rough distance and warmer/colder than at the last hint
 * (Minecraft: -z = north, +x = east)
 */
export function treasureHint(from, to, lastDist) {
  const dx = to.x - from.x, dz = to.z - from.z;
  const d = Math.hypot(dx, dz);
  const sector = Math.round(Math.atan2(dz, dx) / (Math.PI / 4));
  const dir = ["Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten", "Norden", "Nordosten"][(sector + 8) % 8];
  let trend = "";
  if (lastDist !== undefined && d >= 12) {
    if (d < lastDist - 2) trend = "§a wärmer§6 · ";
    else if (d > lastDist + 2) trend = "§9 kälter§6 · ";
  }
  return { text: d < 12 ? `Schatz: ${distanceBand(d)}` : `Schatz:${trend} Richtung ${dir}, ${distanceBand(d)}`, dist: d };
}

// ---------- Spukort ----------

export const HAUNT_GOAL = 15;          // haunted mobs to defeat to break the curse
export const HAUNT_RADIUS = 48;        // the haunted area around its centre
export const MAX_HAUNT_MOBS = 20;

/** mostly skeletons and zombies, sometimes a stray */
export function hauntMob(rand) {
  const r = rand();
  if (r < 0.5) return "minecraft:skeleton";
  if (r < 0.9) return "minecraft:zombie";
  return "minecraft:stray";
}

/** haunted mobs per wave: 3 + 1 per player in the area, never above the cap */
export function hauntWaveSize(playersNear, alive) {
  return Math.max(0, Math.min(3 + playersNear, MAX_HAUNT_MOBS - alive));
}

/** the reward when the curse is broken - dropped above the village square. [item, amount][] */
export function hauntLoot(rand) {
  const n = (min, max) => min + Math.floor(rand() * (max - min + 1));
  return [["minecraft:emerald", n(3, 6)], ["minecraft:iron_ingot", n(4, 8)], ["minecraft:experience_bottle", n(4, 8)],
    ["minecraft:golden_apple", 1], [rand() < 0.5 ? "minecraft:amethyst_shard" : "minecraft:echo_shard", n(1, 3)]];
}

// ---------- Creeper-Chaos ----------

export const CHARGED_CHANCE = 0.2;
export const MAX_CHAOS_CREEPERS = 16; // alive around one player

/** creepers per group: 2-4, never more than the cap allows */
export function creeperGroup(rand, alive) {
  return Math.max(0, Math.min(2 + Math.floor(rand() * 3), MAX_CHAOS_CREEPERS - alive));
}

// ---------- Hexenzirkel ----------

/** 3 witches, one more per 2 players, at most 5 */
export function covenSize(players) {
  return Math.min(5, 3 + Math.floor(Math.max(0, players - 1) / 2));
}

/** the reward when the whole coven is defeated - brewing things. [item, amount][] */
export function covenLoot(rand) {
  const n = (min, max) => min + Math.floor(rand() * (max - min + 1));
  return [["minecraft:nether_wart", n(2, 4)], ["minecraft:ender_pearl", n(1, 3)], ["minecraft:glowstone_dust", n(3, 6)],
    ["minecraft:redstone", n(4, 8)], ["minecraft:experience_bottle", n(3, 5)]];
}

// ---------- Sternschnuppen-Nacht ----------

export const STAR_TAG = "mcfs_star";

/** one star piece: glowstone, experience, lapis - rarely a diamond or netherite scrap. [item, amount] */
export function starLoot(rand) {
  const r = rand();
  const n = (min, max) => min + Math.floor(rand() * (max - min + 1));
  if (r < 0.40) return ["minecraft:glowstone_dust", n(2, 4)];
  if (r < 0.70) return ["minecraft:experience_bottle", n(1, 2)];
  if (r < 0.85) return ["minecraft:lapis_lazuli", n(2, 4)];
  if (r < 0.95) return ["minecraft:diamond", 1];
  return ["minecraft:netherite_scrap", 1];
}

/** a shooting star high above (x, y, z): a straight streak of 30-50 blocks, slightly falling */
export function shootingStarPath(x, y, z, rand) {
  const angle = rand() * Math.PI * 2;
  const len = 30 + rand() * 20;
  const from = { x: x + (rand() - 0.5) * 60, y: y + 45 + rand() * 20, z: z + (rand() - 0.5) * 60 };
  return { from, to: { x: from.x + Math.cos(angle) * len, y: from.y - 6 - rand() * 6, z: from.z + Math.sin(angle) * len } };
}

/** points along a line (for particle trails) */
export function linePoints(from, to, steps) {
  const out = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    out.push({ x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t, z: from.z + (to.z - from.z) * t });
  }
  return out;
}

// ---------- Meteorit ----------

export const CRATER_RADIUS = 5;
export const CRATER_DEPTH = 3;
export const IMPACT_COUNTDOWN = 30; // seconds between announcement and impact

/** depth of the bowl at distance d from the centre: 3 in the middle, 0 at the rim */
export function craterDepth(d, radius = CRATER_RADIUS, depth = CRATER_DEPTH) {
  if (d >= radius) return 0;
  return Math.max(0, Math.round(depth * (1 - (d / radius) ** 2)));
}

/**
 * The crater as a plan relative to the impact point: every column within the radius gets a depth (blocks
 * removed) and a floor block; around the rim some netherrack "splashes" on the ground.
 * @returns {{dx:number, dz:number, depth:number, floor:string|null, cluster:boolean}[]}
 */
export function planCrater(rand) {
  const cells = [];
  const R = CRATER_RADIUS;
  for (let dx = -R - 1; dx <= R + 1; dx++) {
    for (let dz = -R - 1; dz <= R + 1; dz++) {
      const d = Math.hypot(dx, dz);
      if (d > R + 1) continue;
      if (d >= R) {
        // rim: splashes of netherrack on the ground
        if (rand() < 0.3) cells.push({ dx, dz, depth: 0, floor: "minecraft:netherrack", cluster: false });
        continue;
      }
      const amethyst = rand() < 0.25;
      cells.push({ dx, dz, depth: craterDepth(d), floor: amethyst ? "minecraft:amethyst_block" : "minecraft:netherrack",
        cluster: amethyst && rand() < 0.5 });
    }
  }
  // 3-5 diamond ores in the deep middle of the floor
  const deep = cells.filter((c) => c.depth >= 2);
  const n = Math.min(deep.length, 3 + Math.floor(rand() * 3));
  for (let i = 0; i < n; i++) {
    const c = deep.splice(Math.floor(rand() * deep.length), 1)[0];
    Object.assign(c, { floor: "minecraft:diamond_ore", cluster: false });
  }
  return cells;
}

/** small plants and snow on top of the ground - the ground itself is the block below */
export function isCover(typeId) {
  const n = String(typeId).replace(/^minecraft:/, "");
  return isNaturalTop(typeId) && !/(grass_block|dirt|podzol|mycelium|sand|gravel|stone|andesite|diorite|granite|deepslate|tuff|calcite|clay|mud|moss_block|snow$|ice|_ore)/.test(n)
    && !n.endsWith("_leaves") && !n.includes("water") && n !== "cactus" && n !== "pumpkin" && n !== "melon_block";
}

/** blocks a meteor may replace: what the world generated by itself near the surface */
export function isMeteorReplaceable(typeId) {
  const n = String(typeId).replace(/^minecraft:/, "");
  return n === "air" || n.endsWith("_ore") || (isNaturalTop(typeId) && !n.includes("water"));
}

/**
 * Is the ground around the impact point suitable: every column a ground block (no trees, no water) and
 * flat enough (surface within 3 blocks of the centre)?
 * @param {{top:number, typeId:string}[]} columns  surface of every column within radius + 1
 */
export function craterGroundOk(columns, centerTop) {
  return columns.every((c) => isGround(c.typeId) && Math.abs(c.top - centerTop) <= 3);
}

// ---------- day and night (Minecraft time of day in ticks, 0-23999) ----------

export const NIGHT_START = 13000;
export const NIGHT_END = 23000;
export const NIGHT_SECONDS = (NIGHT_END - NIGHT_START) / 20;

export function isNight(timeOfDay) {
  return timeOfDay >= NIGHT_START && timeOfDay < NIGHT_END;
}

/** seconds of game time until the next nightfall (0 at night) */
export function secondsUntilNight(timeOfDay) {
  if (isNight(timeOfDay)) return 0;
  return ((NIGHT_START - timeOfDay + 24000) % 24000) / 20;
}

/** seconds of game time until dawn (0 at day) */
export function secondsUntilDawn(timeOfDay) {
  return isNight(timeOfDay) ? (NIGHT_END - timeOfDay) / 20 : 0;
}

/**
 * Phase of a night event for the current time of day. Changes `a` in place.
 * @returns {"night" | "dawn" | null} "night" when it just began, "dawn" when it is over, else null
 */
export function nightStep(a, timeOfDay) {
  if (a.phase === "waiting") {
    if (!isNight(timeOfDay)) {
      a.remaining = secondsUntilNight(timeOfDay);
      return null;
    }
    a.phase = "running";
    a.remaining = secondsUntilDawn(timeOfDay);
    return "night";
  }
  if (!isNight(timeOfDay)) {
    a.remaining = 0;
    return "dawn";
  }
  a.remaining = secondsUntilDawn(timeOfDay);
  return null;
}

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
  if (TYPES[type].night) {
    // phase and remaining are set by the first nightStep (waiting for the night or running at once)
    return { type, night: true, phase: "waiting", remaining: 0, total: NIGHT_SECONDS, ran: 0, seen: {}, by };
  }
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
    if (a.night) {
      // night events end by nightStep at dawn; only the night itself counts as taking part
      if (a.phase !== "running") continue;
      a.ran += 60;
      for (const n of playerNames) a.seen[n] = (a.seen[n] ?? 0) + 60;
      continue;
    }
    for (const n of playerNames) a.seen[n] = (a.seen[n] ?? 0) + 60;
    a.remaining -= 60;
    if (a.remaining <= 0) ended.push(a);
  }
  return ended;
}

/** seconds the event really ran */
export function ranSeconds(a) {
  return a.night ? a.ran : a.total - Math.max(0, a.remaining);
}

/** players that took part: online at least PARTICIPATION seconds (or the whole time of a shorter run) */
export function participants(a) {
  const ran = ranSeconds(a);
  const need = Math.min(PARTICIPATION, Math.max(60, ran));
  return Object.entries(a.seen).filter(([, s]) => s >= need).map(([n]) => n).sort();
}

export function formatMinutes(seconds) {
  const m = Math.max(1, Math.round(seconds / 60));
  return m >= 60 ? `${Math.floor(m / 60)} Std. ${m % 60 ? `${m % 60} Min.` : ""}`.trim() : `${m} Min.`;
}

export const REGISTER_KEY = /^[one]-?\d{1,7},-?\d{1,7}$/;
export const MAX_REGISTER_BATCH = 200;
export const UNDO_ID = /^[a-z_]+-\d{1,10}$/;

/**
 * console / portal control: "start <type>" | "stop <type>" | "auto on|off" | "state"
 *   | "register <key;key;...>" (chunks with builds, from the map reader) | "undo <id>" (block changes of an event)
 */
export function parseControl(message) {
  const [verb, arg, ...rest] = String(message ?? "").trim().split(/\s+/);
  if (rest.length) return null;
  if (verb === "register" && arg) {
    const keys = arg.split(";");
    return keys.length <= MAX_REGISTER_BATCH && keys.every((k) => REGISTER_KEY.test(k)) ? { verb, keys } : null;
  }
  if (verb === "undo" && arg) return UNDO_ID.test(arg) ? { verb, id: arg } : null;
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

// ---------- spots in the wild (lightning, wolf packs, bosses) ----------

/** random point between `min` and `max` blocks around (x, z) */
export function ringOffset(x, z, min, max, rand) {
  const angle = rand() * Math.PI * 2;
  const dist = min + rand() * (max - min);
  return { x: Math.floor(x + Math.cos(angle) * dist), z: Math.floor(z + Math.sin(angle) * dist) };
}

/** wolves per pack: 3-5 */
export function packSize(rand) {
  return 3 + Math.floor(rand() * 3);
}

/** event mobs carry the tag "mcfs_ev" plus "mcfs_ev_<type>"; tidy up those whose event is not running */
export const MOB_TAG = "mcfs_ev";
export const mobTag = (type) => `mcfs_ev_${type}`;

export function isLeftover(tags, activeTypes) {
  if (!tags.includes(MOB_TAG)) return false;
  return !tags.some((t) => t.startsWith("mcfs_ev_") && activeTypes.includes(t.slice(8)));
}

// ---------- Zombie-Invasion ----------

export const ZOMBIES = new Set(["minecraft:zombie", "minecraft:husk", "minecraft:drowned",
  "minecraft:zombie_villager", "minecraft:zombie_villager_v2"]);
export const MAX_INVASION_ZOMBIES = 30; // alive at once around one place

/** zombies per wave and place: 3 + 1 per player nearby, never more than the cap allows */
export function waveSize(playersNear, alive) {
  return Math.max(0, Math.min(3 + playersNear, MAX_INVASION_ZOMBIES - alive));
}

/** mostly zombies, sometimes a husk or a zombie villager */
export function invasionMob(rand) {
  const r = rand();
  if (r < 0.1) return "minecraft:husk";
  if (r < 0.2) return "minecraft:zombie_villager_v2";
  return "minecraft:zombie";
}

/** extra loot for a zombie a player defeated during an invasion: [item id, amount][] */
export function invasionLoot(rand) {
  const out = [];
  const roll = (chance, id, min = 1, max = 1) => {
    if (rand() < chance) out.push([id, min + Math.floor(rand() * (max - min + 1))]);
  };
  roll(0.4, "minecraft:iron_ingot");
  roll(0.25, "minecraft:carrot", 1, 2);
  roll(0.25, "minecraft:potato", 1, 2);
  roll(0.1, "minecraft:emerald");
  roll(0.1, "minecraft:experience_bottle");
  roll(0.02, "minecraft:golden_apple");
  return out;
}

/**
 * Where the zombies go: the villages near the players (centre of the villagers within 96 blocks), else the
 * players themselves. Places closer than 48 blocks are merged.
 * @param {{x:number,z:number,villagers:{x:number,z:number}[]}[]} players  with the villagers near each one
 * @returns {{x:number,z:number,village:boolean,players:number}[]}
 */
export function invasionTargets(players) {
  const out = [];
  for (const p of players) {
    const v = p.villagers.length >= 3;
    const x = v ? p.villagers.reduce((s, a) => s + a.x, 0) / p.villagers.length : p.x;
    const z = v ? p.villagers.reduce((s, a) => s + a.z, 0) / p.villagers.length : p.z;
    const near = out.find((t) => Math.hypot(t.x - x, t.z - z) < 48);
    if (near) {
      near.players += 1;
      if (v && !near.village) Object.assign(near, { x, z, village: true });
    } else {
      out.push({ x, z, village: v, players: 1 });
    }
  }
  return out;
}

// ---------- Kopfgeld-Boss ----------

/** health boost level n gives (n + 1) * 4 extra health */
export function healthBoostLevel(base, target) {
  return Math.max(0, Math.ceil((target - base) / 4) - 1);
}

/**
 * helmets keep zombie and skeleton from burning in the sun; the mobs are the pack's own boss versions of the
 * vanilla ones (entities/boss_*.json: 50 % larger, never despawn; colour shift in mcportal_events_rp).
 * `spawnEvent`: Bernd always comes as a grown-up zombie, never as a baby or chicken jockey.
 */
export const BOSSES = [
  { id: "bernd", name: "Bernd der Zombiekönig", mob: "mcfs:boss_zombie", spawnEvent: "minecraft:as_adult", base: 20, health: 60,
    helmet: "diamond_helmet", weapon: "iron_sword", effects: [["resistance", 1], ["strength", 0]] },
  { id: "sven", name: "Skelett-Sven", mob: "mcfs:boss_skeleton", base: 20, health: 50,
    helmet: "golden_helmet", weapon: null, effects: [["speed", 0], ["resistance", 0]] },
  { id: "susi", name: "Spinnen-Susi", mob: "mcfs:boss_spider", base: 16, health: 50,
    helmet: null, weapon: null, effects: [["strength", 0], ["resistance", 0]] },
];

export function chooseBoss(rand) {
  return BOSSES[Math.floor(rand() * BOSSES.length)];
}

const DIRECTIONS = ["Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten", "Norden", "Nordosten"];

/**
 * hint for the action bar: distance, compass direction (Minecraft: -z = north, +x = east) and, if it
 * matters, the height difference
 */
export function bossHint(name, from, to) {
  const dx = to.x - from.x, dz = to.z - from.z;
  const dist = Math.round(Math.hypot(dx, dz));
  const dy = to.y === undefined || from.y === undefined ? 0 : Math.round(to.y - from.y);
  const height = Math.abs(dy) >= 4 ? `, ${Math.abs(dy)} Blöcke ${dy > 0 ? "höher" : "tiefer"}` : "";
  if (dist < 8) return `${name} ist ganz in der Nähe!${height}`;
  const sector = Math.round(Math.atan2(dz, dx) / (Math.PI / 4));
  return `${name}: ${dist} Blöcke Richtung ${DIRECTIONS[(sector + 8) % 8]}${height}`;
}

/** points of the light column above the boss (every second) */
export function beaconColumn(at, height = 24, step = 2) {
  const out = [];
  for (let dy = 2; dy <= height; dy += step) out.push({ x: at.x, y: at.y + dy, z: at.z });
  return out;
}

/** the bounty: always the same, so it's worth the hunt */
export const BOUNTY_LOOT = [
  ["minecraft:diamond", 3], ["minecraft:emerald", 5], ["minecraft:golden_apple", 1], ["minecraft:experience_bottle", 5],
];

/** who gets the "Kopfgeldjäger" credit: the killer and everybody within 32 blocks */
export function bountyHunters(killer, nearby) {
  return [...new Set([killer, ...nearby].filter(Boolean))].sort();
}

/** beds can't be used while a night event waits or runs */
export function isBed(typeId) {
  return typeId === "minecraft:bed" || String(typeId).endsWith("_bed");
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

/** ground a mob can be put on: natural, but not tree tops (leaves) and not water */
export function isGround(typeId) {
  const n = String(typeId);
  return isNaturalTop(n) && !n.endsWith("_leaves") && !n.includes("water");
}

/** random point 16-64 blocks around (x, z) */
export function lightningOffset(x, z, rand) {
  return ringOffset(x, z, 16, 64, rand);
}
