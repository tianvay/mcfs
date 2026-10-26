// Minecraft Family Portal - timed events (behavior pack, changes M11, M12)
//
//  * Random events while players are online - the more players, the more often, at most one per hour
//    (core.js). Running events only lose time while somebody is online; everything survives restarts.
//  * Events: Unwetter (storm), Mining Rush (ore drops doubled), Glückstag (XP doubled);
//    night events (wait for the next night, end at dawn, no sleeping meanwhile): Blutmond (wolf packs),
//    Zombie-Invasion (waves at the villages near players, better loot, villagers protected);
//    Kopfgeld (a named boss appears in the wild under a column of light, hints every 5 s, bounty for the hunters,
//    escapes after 20 min).
//  * Mobs spawned by events carry the tag "mcfs_ev" + "mcfs_ev_<type>" and are removed when their event is over.
//  * Build register: every chunk a player placed a block in is remembered; world-changing effects
//    (lightning now, meteors later) stay away from it.
//  * Control (console / portal / operators): /scriptevent mcfs:event start|stop <type> | auto on|off | state
//  * Log lines for the portal: [mcportal-events] {"v":1,"event":"started"|"ended"|"state",...}
//  * Other packs (achievements) get the same news via system.sendScriptEvent("mcfs:event_news", json).
// Uses only the stable @minecraft/server API - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning.
import { EntityDamageCause, ItemStack, Player, ScriptEventSource, system, WeatherType, world } from "@minecraft/server";
import {
  activeMinute, beaconColumn, BOSSES, bossHint, BOUNTY_LOOT, bountyHunters, chooseBoss, healthBoostLevel,
  chooseType, chunkKey, decodeRegister, encodeRegister, estimateNext, formatMinutes, invasionLoot,
  invasionMob, invasionTargets, isBed, isGround, isLeftover, isNaturalTop, isRushOre, lightningOffset, MOB_TAG, mobTag, newActive,
  newSchedule, nightStep, packSize, parseControl, participants, ranSeconds, ringOffset, scheduleMinute, shouldDouble,
  TYPES, waveSize, xpBonus, ZOMBIES,
} from "./core.js";

const TAG = "[mcportal-events]";
const STATE_KEY = "mcfs_ev:state";
const REG_PREFIX = "mcfs_ev_reg:"; // + part number; "mcfs_ev_reg:n" = number of parts
const MINUTE = 20 * 60;
const SAVE_REGISTER_TICKS = 20 * 30;
const STATE_LOG_MINUTES = 10;
const ACTIONBAR_EVERY = 10 * 60; // seconds of event time

let schedule;
/** running events, see core.newActive */
let active = [];
let register;
let registerDirty = false;

function log(payload) {
  console.warn(`${TAG} ${JSON.stringify({ v: 1, ...payload })}`);
}

function news(payload) {
  try {
    system.sendScriptEvent("mcfs:event_news", JSON.stringify(payload));
  } catch { /* nobody listening is fine */ }
}

// ---------- storage ----------

function loadState() {
  schedule = newSchedule();
  active = [];
  try {
    const raw = world.getDynamicProperty(STATE_KEY);
    if (typeof raw === "string") {
      const data = JSON.parse(raw);
      schedule = { ...schedule, ...data.schedule };
      active = (data.active ?? []).filter((a) => a.type in TYPES);
    }
  } catch (e) {
    log({ error: `load state: ${e}` });
  }
}

function saveState() {
  world.setDynamicProperty(STATE_KEY, JSON.stringify({ schedule, active }));
}

function loadRegister() {
  const n = Number(world.getDynamicProperty(REG_PREFIX + "n") ?? 0);
  const parts = [];
  for (let i = 0; i < n; i++) parts.push(String(world.getDynamicProperty(REG_PREFIX + i) ?? ""));
  register = decodeRegister(parts);
}

function saveRegister() {
  if (!registerDirty) return;
  const parts = encodeRegister(register);
  const old = Number(world.getDynamicProperty(REG_PREFIX + "n") ?? 0);
  parts.forEach((p, i) => world.setDynamicProperty(REG_PREFIX + i, p));
  for (let i = parts.length; i < old; i++) world.setDynamicProperty(REG_PREFIX + i, undefined);
  world.setDynamicProperty(REG_PREFIX + "n", parts.length);
  registerDirty = false;
}

world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  if (!register) return;
  const k = chunkKey(ev.block.dimension.id, ev.block.location.x, ev.block.location.z);
  if (register.has(k)) return;
  register.add(k);
  registerDirty = true;
});

const isBuilt = (dim, x, z) => register?.has(chunkKey(dim, x, z));

// ---------- the events ----------

const overworld = () => world.getDimension("overworld");

const isActive = (type) => active.some((a) => a.type === type);

/** per type: start / minute (online minute) / stop */
const HANDLERS = {
  storm: {
    start(a) { keepThunder(a); },
    minute(a) { keepThunder(a); },
    stop() {
      try { overworld().setWeather(WeatherType.Clear, 20 * 60 * 10); } catch { /* ignore */ }
    },
  },
  // the work happens in the event subscriptions below; they check isActive()
  mining_rush: { start() {}, minute() {}, stop() {} },
  lucky_day: {
    start() { xpLast.clear(); }, // first poll sets the baseline - what players have is not doubled
    minute() {},
    stop() { xpLast.clear(); },
  },
  // night events: night(a, resumed) at nightfall, tick(a) every second during the night
  blood_moon: {
    start() {},
    minute() {},
    night(a, resumed) { bloodMoonNight(resumed); },
    tick() { bloodMoonTick(); },
    stop() { bloodMoonEnd(); },
  },
  zombie_invasion: {
    start() {},
    minute() {},
    night() { nextWave = 0; }, // first wave right away
    tick() { invasionTick(); },
    stop() {},
  },
  // the boss is placed by the bounty interval below (also later, if nobody was online at the start)
  bounty: { start() {}, minute() {}, stop() {} },
};
const IMPLEMENTED = Object.keys(HANDLERS);

function keepThunder(a) {
  try {
    overworld().setWeather(WeatherType.Thunder, (a.remaining + 120) * 20);
  } catch (e) {
    log({ error: `weather: ${e}` });
  }
}

// extra lightning during a storm: every 20-60 s near a random player in the overworld
let nextStrike = 0;
system.runInterval(() => {
  if (!isActive("storm") || system.currentTick < nextStrike) return;
  nextStrike = system.currentTick + 20 * (20 + Math.floor(Math.random() * 41));
  const players = world.getAllPlayers().filter((p) => p.dimension.id === "minecraft:overworld");
  if (!players.length) return;
  const p = players[Math.floor(Math.random() * players.length)];
  for (let attempt = 0; attempt < 5; attempt++) {
    const t = lightningOffset(p.location.x, p.location.z, Math.random);
    if (strike(t.x, t.z)) return;
  }
}, 20);

/**
 * Top block at (x, z) if the place is "wild": chunk not in the build register and a 7 x 7 area of natural
 * ground - no roofs, paths, fields, lanterns ... (also protects builds from before the register).
 */
function wildTop(dim, x, z) {
  if (isBuilt(dim.id, x, z)) return null;
  try {
    const top = dim.getTopmostBlock({ x, z });
    if (!top) return null;
    for (let dx = -3; dx <= 3; dx++) {
      for (let dz = -3; dz <= 3; dz++) {
        if (isBuilt(dim.id, x + dx, z + dz)) return null;
        const b = dim.getTopmostBlock({ x: x + dx, z: z + dz });
        if (!b || !isNaturalTop(b.typeId)) return null;
      }
    }
    return top;
  } catch {
    return null; // not loaded
  }
}

/** lightning at (x, z) if the ground there looks untouched; true if it struck */
function strike(x, z) {
  const dim = overworld();
  const top = wildTop(dim, x, z);
  if (!top) return false;
  try {
    dim.spawnEntity("minecraft:lightning_bolt", { x: x + 0.5, y: top.location.y + 1, z: z + 0.5 });
    return true;
  } catch {
    return false;
  }
}

// ---------- night events: phases, no sleeping, event mobs ----------

const isNightEventActive = () => active.some((a) => a.night);

// every second: nightfall / dawn, and the per-second work of running night events
system.runInterval(() => {
  if (!schedule) return;
  const tod = world.getTimeOfDay();
  for (const a of [...active]) {
    if (!a.night) continue;
    const step = nightStep(a, tod);
    if (step === "night") {
      announceNight(a);
      try { HANDLERS[a.type].night(a, false); } catch (e) { log({ error: `night ${a.type}: ${e}` }); }
      saveState();
      logState();
    } else if (step === "dawn") {
      stop(a, "dawn");
    } else if (a.phase === "running") {
      try { HANDLERS[a.type].tick?.(a); } catch (e) { log({ error: `tick ${a.type}: ${e}` }); }
    }
  }
}, 20);

function announceNight(a) {
  const t = TYPES[a.type];
  for (const p of world.getAllPlayers()) {
    try {
      p.onScreenDisplay.setTitle(t.nightTitle, { subtitle: t.nightSubtitle, fadeInDuration: 10, stayDuration: 80, fadeOutDuration: 20 });
    } catch { /* left */ }
  }
  world.sendMessage(`§6[Event] ${t.nightTitle}§f ${t.nightSubtitle}`);
}

// no sleeping through a night event
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || !isNightEventActive() || !isBed(ev.block.typeId)) return;
  ev.cancel = true;
  const p = ev.player;
  system.run(() => p.sendMessage("§cHeute Nacht schläft niemand!"));
});

/** spawn a mob for an event, marked for tidying up */
function spawnEventMob(dim, typeId, type, at) {
  const e = dim.spawnEntity(typeId, at);
  e.addTag(MOB_TAG);
  e.addTag(mobTag(type));
  return e;
}

/** remove event mobs whose event is over - also those in chunks that were unloaded at the end */
function tidyUp() {
  const running = active.map((a) => a.type);
  let removed = 0;
  for (const id of ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]) {
    let mobs = [];
    try { mobs = world.getDimension(id).getEntities({ tags: [MOB_TAG] }); } catch { /* ignore */ }
    for (const m of mobs) {
      try {
        if (isLeftover(m.getTags(), running)) { m.remove(); removed++; }
      } catch { /* gone */ }
    }
  }
  return removed;
}
system.runInterval(tidyUp, MINUTE);

// ---------- Blutmond ----------

const BLOOD_FOG = "mcfs_blood";
const PACK_EVERY = 90 * 20;
const MAX_WOLVES_PER_PLAYER = 12;
const lastPack = new Map(); // player name -> tick of the last wolf pack
const fogged = new Set();   // player names with the blood fog

function bloodMoonNight(resumed) {
  lastPack.clear();
  fogged.clear();
  if (resumed) return; // after a restart: fog comes back with the next tick, no second flash
  for (const p of world.getAllPlayers()) {
    try {
      p.camera.fade({ fadeColor: { red: 0.6, green: 0, blue: 0 }, fadeTime: { fadeInTime: 0.5, holdTime: 1.5, fadeOutTime: 2 } });
      p.playSound("mob.wolf.growl");
    } catch { /* left */ }
  }
}

function bloodMoonTick() {
  const now = system.currentTick;
  for (const p of world.getAllPlayers()) {
    if (p.dimension.id !== "minecraft:overworld") continue;
    if (!fogged.has(p.name)) {
      try {
        p.runCommand(`fog @s push minecraft:fog_crimson_forest ${BLOOD_FOG}`);
        fogged.add(p.name);
      } catch (e) {
        fogged.add(p.name); // don't retry every second
        log({ error: `fog: ${e}` });
      }
    }
    if (now - (lastPack.get(p.name) ?? -PACK_EVERY) < PACK_EVERY) continue;
    lastPack.set(p.name, now);
    spawnWolfPack(p.dimension, p.location);
  }
}

/** 3-5 angry wolves 20-32 blocks from `near`, only in the wild; false if no spot or enough wolves around */
function spawnWolfPack(dim, near) {
  try {
    // only at the surface: nobody gets a wolf pack into a cave or a mine
    const top = dim.getTopmostBlock({ x: Math.floor(near.x), z: Math.floor(near.z) });
    if (top && near.y < top.location.y - 6) return false;
    const around = dim.getEntities({ tags: [mobTag("blood_moon")], location: near, maxDistance: 64 }).length;
    if (around >= MAX_WOLVES_PER_PLAYER) return false;
  } catch {
    return false;
  }
  for (let attempt = 0; attempt < 6; attempt++) {
    const spot = ringOffset(near.x, near.z, 20, 32, Math.random);
    const top = wildTop(dim, spot.x, spot.z);
    if (!top || !isGround(top.typeId)) continue;
    const n = packSize(Math.random);
    for (let i = 0; i < n; i++) {
      try {
        const w = spawnEventMob(dim, "minecraft:wolf", "blood_moon",
          { x: spot.x + 0.5 + (i % 2), y: top.location.y + 1, z: spot.z + 0.5 + Math.floor(i / 2) });
        w.triggerEvent("minecraft:become_angry");
      } catch { /* ignore */ }
    }
    return true;
  }
  return false;
}

function bloodMoonEnd() {
  for (const p of world.getAllPlayers()) {
    try { p.runCommand(`fog @s remove ${BLOOD_FOG}`); } catch { /* had none */ }
  }
  fogged.clear();
  lastPack.clear();
}

// ---------- Zombie-Invasion ----------

const WAVE_EVERY = 60 * 20;
const VILLAGE_RADIUS = 96;
let nextWave = 0;

function invasionTick() {
  if (system.currentTick < nextWave) return;
  nextWave = system.currentTick + WAVE_EVERY;
  const dim = overworld();
  const players = world.getAllPlayers().filter((p) => p.dimension.id === "minecraft:overworld");
  invasionWave(dim, players.map((p) => p.location));
}

/** one wave for every place the players are at: their village, or themselves if no village is near */
function invasionWave(dim, positions) {
  const near = positions.map((l) => {
    let villagers = [];
    try {
      villagers = dim.getEntities({ type: "minecraft:villager_v2", location: l, maxDistance: VILLAGE_RADIUS })
        .map((v) => v.location);
    } catch { /* unloaded */ }
    return { x: l.x, z: l.z, villagers };
  });
  const result = [];
  for (const t of invasionTargets(near)) {
    const center = { x: t.x, y: 64, z: t.z };
    if (t.village) protectVillagers(dim, center);
    let alive = 0;
    try {
      alive = dim.getEntities({ tags: [mobTag("zombie_invasion")], location: center, maxDistance: VILLAGE_RADIUS }).length;
    } catch { /* ignore */ }
    let spawned = 0;
    const want = waveSize(t.players, alive);
    for (let attempt = 0; spawned < want && attempt < want * 4; attempt++) {
      const spot = ringOffset(t.x, t.z, 24, 40, Math.random);
      const at = zombieSpot(dim, spot.x, spot.z);
      if (!at) continue;
      try {
        spawnEventMob(dim, invasionMob(Math.random), "zombie_invasion", at);
        spawned++;
      } catch { /* ignore */ }
    }
    result.push({ village: t.village, spawned, alive });
  }
  return result;
}

/** ground for a zombie: outside built chunks, on natural ground, not in water (they would turn into drowned) */
function zombieSpot(dim, x, z) {
  if (isBuilt(dim.id, x, z)) return null;
  try {
    const top = dim.getTopmostBlock({ x, z });
    if (!top || !isGround(top.typeId)) return null;
    return { x: x + 0.5, y: top.location.y + 1, z: z + 0.5 };
  } catch {
    return null;
  }
}

/** villagers of the attacked village can't be hurt during the invasion (on easy, zombies kill them) */
function protectVillagers(dim, center) {
  try {
    for (const v of dim.getEntities({ type: "minecraft:villager_v2", location: center, maxDistance: VILLAGE_RADIUS })) {
      v.addEffect("resistance", WAVE_EVERY + 200, { amplifier: 4, showParticles: false });
      v.addEffect("fire_resistance", WAVE_EVERY + 200, { showParticles: false });
    }
  } catch { /* ignore */ }
}

// ---------- Kopfgeld-Boss ----------

const HINT_EVERY = 5 * 20;
const HUNTER_RADIUS = 32;
const BEACON_PARTICLE = "minecraft:endrod";
let nextHint = 0;

system.runInterval(() => {
  const a = active.find((x) => x.type === "bounty");
  if (!a) return;
  const dim = overworld();
  if (!a.boss) {
    // place the boss near a random player in the overworld (tried every second until somebody is there)
    const players = world.getAllPlayers().filter((p) => p.dimension.id === "minecraft:overworld");
    if (!players.length) return;
    const p = players[Math.floor(Math.random() * players.length)];
    if (spawnBoss(a, dim, p.location)) {
      const b = a.boss;
      world.sendMessage(`§6[Kopfgeld] §e${b.name}§f wurde bei §eX ${Math.round(b.x)} · Y ${Math.round(b.y)} · `
        + `Z ${Math.round(b.z)}§f gesehen – folgt der Lichtsäule! Wer ihn besiegt, bekommt das Kopfgeld.`);
      saveState();
      logState();
    }
    return;
  }
  // follow the boss while its chunk is loaded (the last known place stays otherwise) and mark it with a
  // column of light that can be seen from far away
  try {
    const e = dim.getEntities({ tags: [mobTag("bounty")] })[0];
    if (e) {
      Object.assign(a.boss, { x: e.location.x, y: e.location.y, z: e.location.z, missing: 0 });
      const hp = e.getComponent("minecraft:health")?.currentValue;
      if (hp > 0) a.boss.hp = hp;
      for (const p of beaconColumn(e.location)) dim.spawnParticle(BEACON_PARTICLE, p);
    } else if (bossAreaWatched(dim, a.boss) && (a.boss.missing = (a.boss.missing ?? 0) + 1) >= 3) {
      // Minecraft despawned it (hostile mobs further than 32 blocks from players vanish at random, a name set
      // by script doesn't protect them): bring it back where it was, with the health it had
      const def = BOSSES.find((b) => b.id === a.boss.id) ?? BOSSES[0];
      createBoss(dim, def, a.boss, a.boss.hp);
      a.boss.missing = 0;
      a.boss.respawns = (a.boss.respawns ?? 0) + 1;
      log({ event: "boss_back", boss: a.boss.name, respawns: a.boss.respawns });
    }
  } catch (err) { log({ error: `boss follow: ${err}` }); }
  if (system.currentTick < nextHint) return;
  nextHint = system.currentTick + HINT_EVERY;
  for (const p of world.getAllPlayers()) {
    if (p.dimension.id !== "minecraft:overworld") continue;
    try { p.onScreenDisplay.setActionBar(`§6${bossHint(a.boss.name, p.location, a.boss)}`); } catch { /* left */ }
  }
}, 20);

let testWatcher = null; // test server only: stands in for a player (there are none there)

/** a player is close enough to the boss's last place that its chunk is loaded - then it should be there */
function bossAreaWatched(dim, b) {
  const watchers = world.getAllPlayers().filter((p) => p.dimension.id === dim.id).map((p) => p.location);
  if (testWatcher) watchers.push(testWatcher);
  const near = watchers.some((l) => Math.hypot(l.x - b.x, l.z - b.z) < 48);
  if (!near) return false;
  try {
    return !!dim.getBlock({ x: Math.floor(b.x), y: Math.floor(b.y ?? 64), z: Math.floor(b.z) });
  } catch {
    return false; // not loaded
  }
}

/** the boss mob itself: name, effects, equipment, full (or the given) health */
function createBoss(dim, def, at, hp) {
  const e = spawnEventMob(dim, def.mob, "bounty", { x: at.x, y: at.y, z: at.z });
  e.nameTag = def.name;
  const long = 20 * 60 * 60;
  e.addEffect("health_boost", long, { amplifier: healthBoostLevel(def.base, def.health), showParticles: false });
  for (const [effect, level] of def.effects) e.addEffect(effect, long, { amplifier: level, showParticles: false });
  // mobs can only be dressed by command (the script equipment API is for players)
  if (def.helmet) e.runCommand(`replaceitem entity @s slot.armor.head 0 ${def.helmet}`);
  if (def.weapon) e.runCommand(`replaceitem entity @s slot.weapon.mainhand 0 ${def.weapon}`);
  // the boost raises the maximum - fill it up one tick later
  system.runTimeout(() => {
    try {
      const h = e.getComponent("minecraft:health");
      h.setCurrentValue(hp > 0 ? Math.min(hp, h.effectiveMax) : h.effectiveMax);
    } catch { /* gone */ }
  }, 2);
  return e;
}

/** the boss 30-60 blocks from `near`, in the wild; false if there is no spot (yet) */
function spawnBoss(a, dim, near) {
  const boss = chooseBoss(Math.random);
  for (let attempt = 0; attempt < 16; attempt++) {
    const spot = ringOffset(near.x, near.z, 30, 60, Math.random);
    const top = wildTop(dim, spot.x, spot.z);
    if (!top || !isGround(top.typeId)) continue; // not on tree tops, not in water
    const at = { x: spot.x + 0.5, y: top.location.y + 1, z: spot.z + 0.5 };
    try {
      createBoss(dim, boss, at);
      a.boss = { id: boss.id, name: boss.name, ...at, missing: 0 };
      nextHint = 0;
      return true;
    } catch (err) {
      log({ error: `boss: ${err}` });
      return false;
    }
  }
  return false;
}

/** boss died: the bounty for the hunters, or nothing if it fell into lava by itself */
function bossDied(dead, killer) {
  const a = active.find((x) => x.type === "bounty");
  const name = a?.boss?.name ?? dead.nameTag ?? "Der Boss";
  if (!(killer instanceof Player)) {
    if (a) stop(a, "died", `${name} ist verunglückt – das Kopfgeld verfällt.`);
    return;
  }
  for (const [id, n] of BOUNTY_LOOT) {
    try { dead.dimension.spawnItem(new ItemStack(id, n), dead.location); } catch { /* ignore */ }
  }
  let nearby = [];
  try {
    nearby = dead.dimension.getPlayers({ location: dead.location, maxDistance: HUNTER_RADIUS }).map((p) => p.name);
  } catch { /* ignore */ }
  const hunters = bountyHunters(killer.name, nearby);
  log({ event: "bounty", boss: name, killer: killer.name, hunters });
  news({ event: "bounty", boss: name, hunters });
  for (const p of world.getAllPlayers()) {
    try { p.onScreenDisplay.setTitle("§6Kopfgeld!", { subtitle: `§e${killer.name}§7 hat §e${name}§7 besiegt`, fadeInDuration: 10, stayDuration: 70, fadeOutDuration: 20 }); } catch { /* left */ }
  }
  if (a) stop(a, "killed", `${killer.name} hat ${name} besiegt und das Kopfgeld kassiert!`);
}

// event mobs: loot and news for the achievements
world.afterEvents.entityDie.subscribe((ev) => {
  const dead = ev.deadEntity;
  const killer = ev.damageSource.damagingEntity;
  // every zombie a player defeats during the invasion night drops more - also the ones that came by themselves
  if (killer instanceof Player && ZOMBIES.has(dead.typeId)
      && active.some((a) => a.type === "zombie_invasion" && a.phase === "running")) {
    for (const [id, n] of invasionLoot(Math.random)) {
      try { dead.dimension.spawnItem(new ItemStack(id, n), dead.location); } catch { /* ignore */ }
    }
    news({ event: "kill", kind: "invasion_zombie", player: killer.name });
  }
  let tags;
  try { tags = dead.getTags(); } catch { return; }
  if (!tags.includes(MOB_TAG)) return;
  if (tags.includes(mobTag("bounty"))) return bossDied(dead, killer);
  if (tags.includes(mobTag("blood_moon"))) {
    try {
      dead.dimension.spawnItem(new ItemStack("minecraft:bone", 1 + Math.floor(Math.random() * 2)), dead.location);
    } catch { /* ignore */ }
    if (killer instanceof Player) news({ event: "kill", kind: "blood_wolf", player: killer.name });
  }
});

// Mining Rush: one tick after an ore was mined, the items that dropped at its place come once more.
// Fortune is included (the real drop is copied); silk touch drops (the ore block itself) are not doubled.
const doubled = new Set(); // item entity ids already handled (also our own copies)
const itemSpawnTick = new Map(); // item entity id -> tick it appeared (only during a Mining Rush)

world.afterEvents.entitySpawn.subscribe((ev) => {
  if (!isActive("mining_rush")) return;
  try {
    if (ev.entity.typeId === "minecraft:item") itemSpawnTick.set(ev.entity.id, system.currentTick);
  } catch { /* gone again */ }
});

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  if (!isActive("mining_rush")) return;
  const oreId = ev.brokenBlockPermutation.type.id;
  if (!isRushOre(oreId)) return;
  const dim = ev.block.dimension;
  const l = ev.block.location;
  const tick = system.currentTick;
  system.runTimeout(() => doubleDrops(dim, { x: l.x + 0.5, y: l.y + 0.5, z: l.z + 0.5 }, oreId, tick), 1);
});

/** copy the drops of the ore mined in `tick`: only items that appeared right then and match the ore */
function doubleDrops(dim, center, oreId, tick) {
  let items;
  try {
    items = dim.getEntities({ type: "minecraft:item", location: center, maxDistance: 1.5 });
  } catch {
    return; // chunk unloaded
  }
  let n = 0;
  for (const item of items) {
    if (doubled.has(item.id)) continue;
    const born = itemSpawnTick.get(item.id);
    if (born === undefined || born < tick || born > tick + 1) continue; // lay there before
    doubled.add(item.id);
    const stack = item.getComponent("minecraft:item")?.itemStack;
    if (!stack || !shouldDouble(stack.typeId, oreId)) continue;
    try {
      const copy = dim.spawnItem(stack, item.location);
      doubled.add(copy.id);
      n++;
    } catch { /* ignore */ }
  }
  if (n) {
    try { dim.spawnParticle("minecraft:villager_happy", center); } catch { /* cosmetic */ }
  }
  if (doubled.size > 2000) doubled.clear();
  for (const [id, t] of itemSpawnTick) if (t < system.currentTick - 40) itemSpawnTick.delete(id);
  return n;
}

// Glückstag: every 5 ticks each player's XP gain since the last look is given once more
const xpLast = new Map(); // name -> total xp including our bonus
system.runInterval(() => {
  if (!isActive("lucky_day")) return;
  const online = new Set();
  for (const p of world.getAllPlayers()) {
    online.add(p.name);
    try {
      const { bonus, last } = xpBonus(xpLast.get(p.name), p.getTotalXp());
      if (bonus > 0) p.addExperience(bonus);
      xpLast.set(p.name, last);
    } catch { /* left */ }
  }
  for (const n of xpLast.keys()) if (!online.has(n)) xpLast.delete(n); // rejoining starts a new baseline
}, 5);

// "Geistesblitz": hit by lightning during a storm and survived
const recentlyStruck = new Map();
world.afterEvents.entityHurt.subscribe((ev) => {
  const p = ev.hurtEntity;
  if (!(p instanceof Player) || ev.damageSource.cause !== EntityDamageCause.lightning) return;
  if (!isActive("storm")) return;
  const now = system.currentTick;
  if ((recentlyStruck.get(p.name) ?? -1e9) > now - 100) return;
  recentlyStruck.set(p.name, now);
  system.runTimeout(() => {
    try {
      if (!p.isValid || (p.getComponent("minecraft:health")?.currentValue ?? 0) <= 0) return;
      log({ event: "lightning_survived", player: p.name });
      news({ event: "lightning_survived", player: p.name });
    } catch { /* left */ }
  }, 10);
});

// ---------- start / stop ----------

const SOUNDS = { storm: "ambient.weather.thunder", mining_rush: "random.anvil_land", lucky_day: "random.levelup",
  blood_moon: "mob.wolf.growl", zombie_invasion: "mob.zombie.say", bounty: "mob.wither.spawn" };

function start(type, by) {
  if (!HANDLERS[type] || active.some((a) => a.type === type)) return false;
  const a = newActive(type, by);
  active.push(a);
  if (by === "auto") schedule.last = type;
  HANDLERS[type].start(a);
  const t = TYPES[type];
  // a night event started at night begins at once - then the night title follows right away
  const now = a.night ? nightStep(a, world.getTimeOfDay()) : null;
  for (const p of world.getAllPlayers()) {
    try {
      p.onScreenDisplay.setTitle(`${t.color}${t.name}!`, { subtitle: t.subtitle, fadeInDuration: 10, stayDuration: 80, fadeOutDuration: 20 });
      p.playSound(SOUNDS[type]);
    } catch { /* left */ }
  }
  world.sendMessage(`§6[Event] ${t.color}${t.name}§f – ${t.subtitle}`);
  log({ event: "started", type, by, duration: a.total, phase: a.phase });
  news({ event: "started", type });
  if (now === "night") {
    system.runTimeout(() => {
      if (!active.includes(a)) return;
      announceNight(a);
      try { HANDLERS[type].night(a, false); } catch (e) { log({ error: `night ${type}: ${e}` }); }
    }, 60);
  }
  saveState();
  logState();
  return true;
}

function stop(a, by, endMessage) {
  active = active.filter((x) => x !== a);
  try { HANDLERS[a.type]?.stop(a); } catch (e) { log({ error: `stop ${a.type}: ${e}` }); }
  const t = TYPES[a.type];
  world.sendMessage(`§6[Event] §7${endMessage ?? t.end}`);
  const who = participants(a);
  log({ event: "ended", type: a.type, by, ran: ranSeconds(a), participants: who });
  news({ event: "ended", type: a.type, participants: who });
  tidyUp();
  saveState();
  logState();
}

// ---------- the online minute ----------

let minutesSinceStateLog = 0;

function logState() {
  minutesSinceStateLog = 0;
  const online = world.getAllPlayers().length;
  log({
    event: "state", auto: schedule.auto, online,
    active: active.map((a) => ({ type: a.type, remaining: a.remaining, total: a.total, by: a.by, phase: a.phase,
      boss: a.boss ? { name: a.boss.name, x: Math.round(a.boss.x), y: Math.round(a.boss.y ?? 0), z: Math.round(a.boss.z) }
        : undefined })),
    next_in: estimateNext(schedule, online), last: schedule.last, register: register?.size ?? 0,
    types: IMPLEMENTED,
  });
  news({ event: "state", active: active.map((a) => a.type) });
}

function minute() {
  const players = world.getAllPlayers();
  const names = players.map((p) => p.name);
  for (const a of activeMinute(active, names)) stop(a, "time");
  for (const a of active) {
    if (!names.length) continue;
    try { HANDLERS[a.type].minute(a); } catch (e) { log({ error: `minute ${a.type}: ${e}` }); }
    if (a.night) continue; // a night is short - the title at nightfall is enough
    const ran = ranSeconds(a);
    if (ran > 0 && ran % ACTIONBAR_EVERY === 0) {
      const t = TYPES[a.type];
      for (const p of players) {
        try { p.onScreenDisplay.setActionBar(`${t.color}${t.name}§7: noch ${formatMinutes(a.remaining)}`); } catch { /* left */ }
      }
    }
  }
  if (scheduleMinute(schedule, players.length, Math.random)) {
    const type = chooseType(IMPLEMENTED, active, schedule.last, Math.random);
    if (type) start(type, "auto");
  }
  saveState();
  if (names.length && ++minutesSinceStateLog >= STATE_LOG_MINUTES) logState();
}

// ---------- control: /scriptevent mcfs:event <command> ----------

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id !== "mcfs:event" || !schedule) return;
  const fromConsole = ev.sourceType === ScriptEventSource.Server;
  const test = /^test (strike|minute|rush|pack|tidy|wave|villagers|boss|despawn)\b/.exec(ev.message);
  if (test && fromConsole) return runTest(ev.message);
  const cmd = parseControl(ev.message);
  const reply = (msg) => {
    if (ev.sourceEntity instanceof Player) ev.sourceEntity.sendMessage(msg);
    else log({ event: "control", message: msg });
  };
  if (!cmd) return reply(`Aufruf: start|stop <${IMPLEMENTED.join("|")}>, auto on|off, state`);
  const by = fromConsole ? "console" : `player:${ev.sourceEntity?.name ?? "?"}`;
  if (cmd.verb === "start") {
    if (!HANDLERS[cmd.type]) return reply(`${cmd.type} gibt es noch nicht.`);
    return reply(start(cmd.type, by) ? `${cmd.type} gestartet.` : `${cmd.type} läuft schon.`);
  }
  if (cmd.verb === "stop") {
    const a = active.find((x) => x.type === cmd.type);
    if (!a) return reply(`${cmd.type} läuft nicht.`);
    stop(a, by);
    return reply(`${cmd.type} beendet.`);
  }
  if (cmd.verb === "auto") {
    schedule.auto = cmd.on;
    saveState();
    logState();
    return reply(`Automatische Events ${cmd.on ? "an" : "aus"}.`);
  }
  logState();
});

/** console-only test hooks for the throwaway test server (no players there) */
function runTest(message) {
  const [, kind, a, b] = message.split(/\s+/);
  if (kind === "rush") {
    // simulated drops at (a, top, b) while a Mining Rush runs; only raw_iron may be doubled
    const dim = overworld();
    const top = dim.getTopmostBlock({ x: Number(a), z: Number(b) });
    const at = { x: Number(a) + 0.5, y: top.location.y + 1.5, z: Number(b) + 0.5 };
    // ore drop, silk touch drop, a diamond thrown there - and an older item lying there already
    dim.spawnItem(new ItemStack("minecraft:emerald", 1), at);
    system.runTimeout(() => {
      const tick = system.currentTick;
      for (const id of ["raw_iron", "iron_ore", "diamond"]) dim.spawnItem(new ItemStack(`minecraft:${id}`, 2), at);
      system.runTimeout(() => {
        const n = doubleDrops(dim, at, "minecraft:iron_ore", tick);
        const again = doubleDrops(dim, at, "minecraft:iron_ore", tick);
        const lying = dim.getEntities({ type: "minecraft:item", location: at, maxDistance: 1.5 })
          .map((e) => `${e.getComponent("minecraft:item").itemStack.typeId.slice(10)}x${e.getComponent("minecraft:item").itemStack.amount}`).sort();
        log({ event: "test", rush: n, again, lying });
      }, 1);
    }, 5);
    return;
  } else if (kind === "pack") {
    // a wolf pack as if a player stood at (a, top, b)
    const dim = overworld();
    const top = dim.getTopmostBlock({ x: Number(a), z: Number(b) });
    const ok = spawnWolfPack(dim, { x: Number(a) + 0.5, y: top.location.y + 1, z: Number(b) + 0.5 });
    // angry wolves lose "tameable" (become_angry swaps the wild component group, effective next tick)
    system.runTimeout(() => {
      const wolves = dim.getEntities({ tags: [mobTag("blood_moon")] });
      const tame = wolves.filter((w) => w.getComponent("minecraft:tameable")).length;
      log({ event: "test", pack: ok, wolves: wolves.length, still_tameable: tame });
    }, 5);
  } else if (kind === "boss") {
    // place the boss of a running bounty as if a player stood at (a, b)
    const bounty = active.find((x) => x.type === "bounty");
    const dim = overworld();
    const at = { x: Number(a) + 0.5, y: 0, z: Number(b) + 0.5 };
    const ok = bounty && !bounty.boss && spawnBoss(bounty, dim, at);
    system.runTimeout(() => {
      const e = dim.getEntities({ tags: [mobTag("bounty")] })[0];
      const h = e?.getComponent("minecraft:health");
      log({ event: "test", boss: ok, name: e?.nameTag, type: e?.typeId, health: h ? `${h.currentValue}/${h.effectiveMax}` : null,
        effects: e ? e.getEffects().map((x) => `${x.typeId}${x.amplifier}`) : [],
        hint: bounty?.boss ? bossHint(bounty.boss.name, { ...at, y: 60 }, bounty.boss) : null, y: bounty?.boss?.y,
        standsOn: e ? dim.getBlock({ x: Math.floor(e.location.x), y: Math.floor(e.location.y) - 1, z: Math.floor(e.location.z) })?.typeId : null });
      if (e) {
        try { dim.spawnParticle(BEACON_PARTICLE, e.location); log({ event: "test", particle: "ok" }); }
        catch (err) { log({ event: "test", particle: String(err) }); }
      }
    }, 10);
  } else if (kind === "despawn") {
    // remove the boss silently like Minecraft's despawning; a "player" stands at its place
    const e = overworld().getEntities({ tags: [mobTag("bounty")] })[0];
    const bounty = active.find((x) => x.type === "bounty");
    if (e) {
      e.getComponent("minecraft:health").setCurrentValue(33);
      system.runTimeout(() => {
        bounty.boss.hp = 33;
        testWatcher = { x: e.location.x, z: e.location.z };
        e.remove();
        system.runTimeout(() => {
          const back = overworld().getEntities({ tags: [mobTag("bounty")] });
          const h = back[0]?.getComponent("minecraft:health");
          log({ event: "test", despawned: true, back: back.length, name: back[0]?.nameTag,
            health: h ? `${h.currentValue}/${h.effectiveMax}` : null, respawns: bounty.boss.respawns });
          testWatcher = null;
        }, 20 * 6);
      }, 25);
    }
  } else if (kind === "villagers") {
    // a small "village": 4 villagers on the ground at (a, b)
    const dim = overworld();
    for (let i = 0; i < 4; i++) {
      const x = Number(a) + i * 2, z = Number(b);
      dim.spawnEntity("minecraft:villager_v2", { x: x + 0.5, y: dim.getTopmostBlock({ x, z }).location.y + 1, z: z + 0.5 });
    }
    log({ event: "test", villagers: dim.getEntities({ type: "minecraft:villager_v2" }).length });
  } else if (kind === "wave") {
    // one invasion wave as if players stood at "x,z;x,z" (a = list)
    const dim = overworld();
    const positions = a.split(";").map((p) => {
      const [x, z] = p.split(",").map(Number);
      return { x: x + 0.5, y: dim.getTopmostBlock({ x, z }).location.y + 1, z: z + 0.5 };
    });
    const res = invasionWave(dim, positions);
    system.runTimeout(() => {
      const villagers = dim.getEntities({ type: "minecraft:villager_v2" });
      log({ event: "test", wave: res, zombies: dim.getEntities({ tags: [mobTag("zombie_invasion")] }).length,
        villagers: villagers.length, protected: villagers.filter((v) => v.getEffect("resistance")).length });
    }, 2);
  } else if (kind === "tidy") {
    log({ event: "test", removed: tidyUp(), left: overworld().getEntities({ tags: [MOB_TAG] }).length });
  } else if (kind === "strike") {
    log({ event: "test", strike: strike(Number(a), Number(b)), built: isBuilt("minecraft:overworld", Number(a), Number(b)) });
  } else if (kind === "minute") {
    // simulate n online minutes with fake player names
    const names = Array.from({ length: Number(b) || 1 }, (_, i) => `Test${i + 1}`);
    for (let i = 0; i < Number(a); i++) {
      for (const x of activeMinute(active, names)) stop(x, "time");
      if (scheduleMinute(schedule, names.length, Math.random)) {
        const type = chooseType(IMPLEMENTED, active, schedule.last, Math.random);
        if (type) start(type, "auto");
      }
    }
    saveState();
    logState();
  }
}

// ---------- startup ----------

system.run(() => {
  loadState();
  loadRegister();
  console.warn(`${TAG} {"v":1,"started":true}`);
  for (const a of active) {
    try {
      HANDLERS[a.type]?.start(a);
      if (a.night && a.phase === "running") HANDLERS[a.type].night(a, true);
    } catch (e) { log({ error: `resume ${a.type}: ${e}` }); }
  }
  logState();
  system.runInterval(minute, MINUTE);
  system.runInterval(saveRegister, SAVE_REGISTER_TICKS);
});
