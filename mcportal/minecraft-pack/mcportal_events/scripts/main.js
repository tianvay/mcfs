// Minecraft Family Portal - timed events (behavior pack, change M11)
//
//  * Random events while players are online - the more players, the more often, at most one per hour
//    (core.js). Running events only lose time while somebody is online; everything survives restarts.
//  * Events: Unwetter (storm), Mining Rush (ore drops doubled), Glückstag (XP doubled).
//  * Build register: every chunk a player placed a block in is remembered; world-changing effects
//    (lightning now, meteors later) stay away from it.
//  * Control (console / portal / operators): /scriptevent mcfs:event start|stop <type> | auto on|off | state
//  * Log lines for the portal: [mcportal-events] {"v":1,"event":"started"|"ended"|"state",...}
//  * Other packs (achievements) get the same news via system.sendScriptEvent("mcfs:event_news", json).
// Uses only the stable @minecraft/server API - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning.
import { EntityDamageCause, ItemStack, Player, ScriptEventSource, system, WeatherType, world } from "@minecraft/server";
import {
  activeMinute, chooseType, chunkKey, decodeRegister, encodeRegister, estimateNext, formatMinutes, isNaturalTop,
  isRushOre, lightningOffset, newActive, newSchedule, parseControl, participants, scheduleMinute, shouldDouble, TYPES,
  xpBonus,
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

/** lightning at (x, z) if the ground there looks untouched; true if it struck */
function strike(x, z) {
  const dim = overworld();
  if (isBuilt(dim.id, x, z)) return false;
  let top;
  try {
    top = dim.getTopmostBlock({ x, z });
    if (!top) return false;
    // a 7 x 7 area of natural ground: no roofs, paths, fields, lanterns ... (also protects older builds)
    for (let dx = -3; dx <= 3; dx++) {
      for (let dz = -3; dz <= 3; dz++) {
        if (isBuilt(dim.id, x + dx, z + dz)) return false;
        const b = dim.getTopmostBlock({ x: x + dx, z: z + dz });
        if (!b || !isNaturalTop(b.typeId)) return false;
      }
    }
    dim.spawnEntity("minecraft:lightning_bolt", { x: x + 0.5, y: top.location.y + 1, z: z + 0.5 });
    return true;
  } catch {
    return false; // not loaded
  }
}

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

function start(type, by) {
  if (!HANDLERS[type] || active.some((a) => a.type === type)) return false;
  const a = newActive(type, by);
  active.push(a);
  if (by === "auto") schedule.last = type;
  HANDLERS[type].start(a);
  const t = TYPES[type];
  for (const p of world.getAllPlayers()) {
    try {
      p.onScreenDisplay.setTitle(`${t.color}${t.name}!`, { subtitle: t.subtitle, fadeInDuration: 10, stayDuration: 80, fadeOutDuration: 20 });
      p.playSound({ storm: "ambient.weather.thunder", mining_rush: "random.anvil_land", lucky_day: "random.levelup" }[type]);
    } catch { /* left */ }
  }
  world.sendMessage(`§6[Event] ${t.color}${t.name}§f – ${t.subtitle}`);
  log({ event: "started", type, by, duration: a.total });
  news({ event: "started", type });
  saveState();
  logState();
  return true;
}

function stop(a, by) {
  active = active.filter((x) => x !== a);
  try { HANDLERS[a.type]?.stop(a); } catch (e) { log({ error: `stop ${a.type}: ${e}` }); }
  const t = TYPES[a.type];
  world.sendMessage(`§6[Event] §7${t.end}`);
  const who = participants(a);
  log({ event: "ended", type: a.type, by, ran: a.total - Math.max(0, a.remaining), participants: who });
  news({ event: "ended", type: a.type, participants: who });
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
    active: active.map((a) => ({ type: a.type, remaining: a.remaining, total: a.total, by: a.by })),
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
    const ran = a.total - a.remaining;
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
  const test = /^test (strike|minute|rush) /.exec(ev.message);
  if (test && fromConsole) return runTest(ev.message);
  const cmd = parseControl(ev.message);
  const reply = (msg) => {
    if (ev.sourceEntity instanceof Player) ev.sourceEntity.sendMessage(msg);
    else log({ event: "control", message: msg });
  };
  if (!cmd) return reply("Aufruf: start|stop <storm|mining_rush|lucky_day>, auto on|off, state");
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
    try { HANDLERS[a.type]?.start(a); } catch (e) { log({ error: `resume ${a.type}: ${e}` }); }
  }
  logState();
  system.runInterval(minute, MINUTE);
  system.runInterval(saveRegister, SAVE_REGISTER_TICKS);
});
