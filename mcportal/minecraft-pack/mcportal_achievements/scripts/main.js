// Minecraft Family Portal - achievements (behavior pack, change M7)
//
// Counts per player what the catalog (catalog.js) needs, keeps the progress in a
// world dynamic property per player (survives restarts), and announces unlocks:
// title + level-up sound for the player, chat message for everyone, and one log line
//   [mcportal-ach] {"v":1,"unlocked":[{"player":"Steve","id":"diamonds","tier":1,"name":"Diamant!"}]}
// for the portal. At startup the catalog is written once: [mcportal-ach] {"v":1,"catalog":[...]}.
// Event achievements (1.1.0, 1.2.0) come from the events pack via system.sendScriptEvent("mcfs:event_news", json):
// started / ended (with participants) / state (running types) / lightning_survived / kill / bounty.
// Uses only the stable @minecraft/server API - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning.
import { EntityInitializationCause, EquipmentSlot, Player, ScriptEventSource, system, world } from "@minecraft/server";
import {
  armorCounters, deathCounters, evaluate, eventCounters, flatCatalog, invasionKill, isDiamondOre, isOre, isSapling,
  killCounters,
} from "./catalog.js";

const TAG = "[mcportal-ach]";
const KEY = "mcfs_ach:"; // + player name -> JSON {c: counters, u: unlocked tiers}
const SAMPLE_TICKS = 20; // 1 s
const SAVE_TICKS = 20 * 10; // 10 s
const MAX_STEP = 60;
const BREED_WINDOW_MS = 60_000;
const BREED_RADIUS = 16;

/** name -> {c, u, dirty} */
const state = new Map();
/** name -> {x,y,z,dim,xp} */
const last = new Map();
/** name -> {walk, elytra, boat} fractional blocks */
const distRest = new Map();
let feeds = [];
/** event types running right now (from the events pack) */
let eventsRunning = new Set();
/** id of the current invasion night - zombie kills are counted per night */
let invasionNight = null;

// ---------- progress storage ----------

function load(name) {
  let s = state.get(name);
  if (!s) {
    let data = { c: {}, u: {} };
    try {
      const raw = world.getDynamicProperty(KEY + name);
      if (typeof raw === "string") data = JSON.parse(raw);
    } catch (e) {
      console.warn(`${TAG} {"v":1,"error":${JSON.stringify(`load ${name}: ${e}`)}}`);
    }
    s = { c: data.c ?? {}, u: data.u ?? {}, dirty: false };
    state.set(name, s);
  }
  return s;
}

function save(name, s) {
  world.setDynamicProperty(KEY + name, JSON.stringify({ c: s.c, u: s.u }));
  s.dirty = false;
}

function saveDirty() {
  for (const [name, s] of state) {
    if (s.dirty) save(name, s);
  }
}

// ---------- counting ----------

function add(player, counter, n = 1) {
  const s = load(player.name);
  s.c[counter] = (s.c[counter] ?? 0) + n;
  s.dirty = true;
  check(player, s);
}

function flag(player, counter) {
  const s = load(player.name);
  if (s.c[counter]) return;
  s.c[counter] = 1;
  s.dirty = true;
  check(player, s);
}

/** counters for a player who may be offline: stored now, announced when online (else at the next check) */
function setByName(name, values) {
  const s = load(name);
  Object.assign(s.c, values);
  s.dirty = true;
  const player = world.getAllPlayers().find((p) => p.name === name);
  if (player) check(player, s);
  else save(name, s);
}

function check(player, s) {
  const fresh = evaluate(s.c, s.u);
  if (!fresh.length) return;
  save(player.name, s);
  for (const a of fresh) announce(player, a);
  const unlocked = fresh.map((a) => ({ player: player.name, id: a.id, tier: a.tier, name: a.name }));
  console.warn(`${TAG} ${JSON.stringify({ v: 1, unlocked })}`);
}

function announce(player, a) {
  try {
    player.onScreenDisplay.setTitle("§6Erfolg!", {
      subtitle: `§e${a.name}`, fadeInDuration: 10, stayDuration: 70, fadeOutDuration: 20,
    });
  } catch { /* player may have left */ }
  try {
    player.playSound("random.levelup");
  } catch { /* ignore */ }
  world.sendMessage(`§6[Erfolg] §f${player.name} hat §e»${a.name}«§f erreicht §7– ${a.desc}`);
}

// ---------- events ----------

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  const id = ev.brokenBlockPermutation.type.id;
  if (isOre(id)) add(ev.player, "ores");
  if (isOre(id) && eventsRunning.has("mining_rush")) add(ev.player, "rush_ores");
  if (isDiamondOre(id)) add(ev.player, "diamonds");
  if (id === "minecraft:ancient_debris") add(ev.player, "debris");
});

world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  const id = ev.block.typeId;
  add(ev.player, "placed");
  if (isSapling(id)) add(ev.player, "saplings");
  if (id === "minecraft:dirt") add(ev.player, "dirt_placed");
});

world.afterEvents.entityDie.subscribe((ev) => {
  const dead = ev.deadEntity;
  const src = ev.damageSource;
  const killer = src.damagingEntity?.isValid ? src.damagingEntity : undefined;
  if (dead instanceof Player) {
    for (const c of deathCounters(src.cause, killer?.typeId)) add(dead, c);
  }
  if (killer instanceof Player) {
    for (const c of killCounters(dead.typeId)) add(killer, c);
  } else if (dead.typeId === "minecraft:ender_dragon") {
    // the final blow often comes from an end crystal or arrow without an owner:
    // everybody who fought in the End gets it
    for (const p of world.getAllPlayers()) {
      if (p.dimension.id === "minecraft:the_end") add(p, "kill_dragon");
    }
  }
});

world.afterEvents.itemCompleteUse.subscribe((ev) => {
  const item = ev.itemStack;
  if (!item || !item.getComponent("minecraft:food")) return;
  add(ev.source, "food");
  if (item.typeId === "minecraft:golden_apple" || item.typeId === "minecraft:enchanted_golden_apple") {
    add(ev.source, "eat_golden_apple");
  }
  if (item.typeId === "minecraft:rotten_flesh") add(ev.source, "eat_rotten_flesh");
});

world.afterEvents.playerDimensionChange.subscribe((ev) => {
  if (ev.toDimension.id === "minecraft:nether") flag(ev.player, "nether");
  if (ev.toDimension.id === "minecraft:the_end") flag(ev.player, "end");
});

// breeding: credited to the player who fed an animal of the same type nearby (the game names no breeder)
world.afterEvents.playerInteractWithEntity.subscribe((ev) => {
  const t = ev.target;
  if (!t || !t.isValid) return;
  const l = t.location;
  feeds.push({ player: ev.player, type: t.typeId, x: l.x, z: l.z, dim: t.dimension.id, at: Date.now() });
  if (feeds.length > 200) feeds = feeds.slice(-100);
});

world.afterEvents.entitySpawn.subscribe((ev) => {
  if (ev.cause !== EntityInitializationCause.Born) return;
  const baby = ev.entity;
  if (!baby || !baby.isValid) return;
  const now = Date.now();
  const l = baby.location;
  let best;
  let bestD = BREED_RADIUS * BREED_RADIUS;
  for (const f of feeds) {
    if (f.type !== baby.typeId || f.dim !== baby.dimension.id || now - f.at > BREED_WINDOW_MS) continue;
    const d = (f.x - l.x) ** 2 + (f.z - l.z) ** 2;
    if (d <= bestD) { best = f; bestD = d; }
  }
  if (best && best.player.isValid) {
    add(best.player, "bred");
    if (baby.typeId === "minecraft:cow") add(best.player, "bred_cow");
  }
});

world.afterEvents.playerLeave.subscribe((ev) => {
  last.delete(ev.playerName);
  const s = state.get(ev.playerName);
  if (s?.dirty) save(ev.playerName, s);
});

// ---------- sampled: playtime, XP, distance, armor ----------

function travelMode(p) {
  const riding = p.getComponent("minecraft:riding")?.entityRidingOn;
  if (riding) return riding.typeId.includes("boat") || riding.typeId.includes("raft") ? "boat" : undefined;
  if (p.isGliding) return "elytra";
  if (p.isFlying || p.isSwimming || p.isInWater) return undefined;
  return "walk";
}

function sample() {
  for (const p of world.getAllPlayers()) {
    const name = p.name;
    const loc = p.location;
    const dim = p.dimension.id;
    const xp = p.getTotalXp();
    const prev = last.get(name);
    add(p, "time", SAMPLE_TICKS / 20);
    if (prev) {
      if (xp > prev.xp) add(p, "xp", xp - prev.xp);
      if (xp > prev.xp && eventsRunning.has("lucky_day")) add(p, "lucky_xp", xp - prev.xp);
      if (prev.dim === dim) {
        const step = Math.hypot(loc.x - prev.x, loc.y - prev.y, loc.z - prev.z);
        const m = step > 0.05 && step < MAX_STEP ? travelMode(p) : undefined;
        if (m) {
          const rest = distRest.get(name) ?? {};
          rest[m] = (rest[m] ?? 0) + step;
          const whole = Math.floor(rest[m]);
          if (whole > 0) {
            add(p, m, whole);
            rest[m] -= whole;
          }
          distRest.set(name, rest);
        }
      }
    }
    last.set(name, { x: loc.x, y: loc.y, z: loc.z, dim, xp });

    const eq = p.getComponent("minecraft:equippable");
    if (eq) {
      const worn = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet]
        .map((slot) => eq.getEquipment(slot)?.typeId);
      for (const c of armorCounters(worn)) flag(p, c);
    }
  }
}

// ---------- news from the events pack ----------

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  // only the events pack (script = Server source); /scriptevent by a player can't fake it
  if (ev.sourceType !== ScriptEventSource.Server) return;
  if (ev.id === "mcfs:ach" && ev.message.startsWith("dump ")) {
    // console: show one player's counters and unlocked tiers (troubleshooting)
    const name = ev.message.slice(5).trim();
    const s = load(name);
    console.warn(`${TAG} ${JSON.stringify({ v: 1, dump: { name, c: s.c, u: s.u } })}`);
    return;
  }
  if (ev.id !== "mcfs:event_news") return;
  let n;
  try {
    n = JSON.parse(ev.message);
  } catch {
    return;
  }
  if (n.event === "state" && Array.isArray(n.active)) {
    eventsRunning = new Set(n.active);
    if (eventsRunning.has("zombie_invasion") && !invasionNight) invasionNight = `resumed-${system.currentTick}`;
  } else if (n.event === "started") {
    eventsRunning.add(n.type);
    if (n.type === "zombie_invasion") invasionNight = `night-${system.currentTick}`;
  } else if (n.event === "ended") {
    eventsRunning.delete(n.type);
    const who = (n.participants ?? []).filter((x) => typeof x === "string");
    for (const name of who) setByName(name, eventCounters(load(name).c, n.type, who.length));
  } else if (n.event === "lightning_survived" && typeof n.player === "string") {
    if (!load(n.player).c.lightning_survived) setByName(n.player, { lightning_survived: 1 });
  } else if (n.event === "kill" && typeof n.player === "string") {
    const c = load(n.player).c;
    if (n.kind === "blood_wolf") setByName(n.player, { blood_wolves: (c.blood_wolves ?? 0) + 1 });
    if (n.kind === "invasion_zombie") {
      // count per invasion night: start again at 0 in a new night
      const base = c.inv_id === invasionNight ? c : { ...c, inv_now: 0 };
      setByName(n.player, { ...invasionKill(base), inv_id: invasionNight });
    }
  } else if (n.event === "bounty" && Array.isArray(n.hunters)) {
    for (const name of n.hunters) {
      if (typeof name === "string") setByName(name, { bounties: (load(name).c.bounties ?? 0) + 1 });
    }
  }
});

system.runInterval(sample, SAMPLE_TICKS);
system.runInterval(saveDirty, SAVE_TICKS);

system.run(() => {
  console.warn(`${TAG} ${JSON.stringify({ v: 1, catalog: flatCatalog() })}`);
  console.warn(`${TAG} {"v":1,"started":true}`);
});
