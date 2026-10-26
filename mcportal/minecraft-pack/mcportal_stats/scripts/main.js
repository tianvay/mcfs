// Minecraft Family Portal - player statistics (behavior pack, changes M5/M6)
//
// Collects per player and writes the deltas since the last line to the server
// log every FLUSH_TICKS, as ONE line:
//   [mcportal-stats] {"v":2,"players":{"Steve":{"placed":{"minecraft:stone":3},"time":20,...}}}
// The portal adds the deltas up (docs/03-block-statistik.md). Counters per player:
//   placed / broken   blocks by type
//   deaths            by cause ("minecraft:creeper" if an entity was involved, else the damage cause)
//   kills             mobs killed by the player, by type
//   food              food items eaten, by type
//   bred              baby animals the player bred, by type (see breeding note below)
//   dist              blocks travelled by mode: walk, swim, boat, minecart, horse, ride, elytra, fly
//   xp                experience points collected (only gains, spending XP doesn't subtract)
//   time              seconds online
// Uses only the stable @minecraft/server API - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning, which
// lets these lines through but keeps info-level content noise out of the log.
import { EntityInitializationCause, Player, system, world } from "@minecraft/server";

const FLUSH_TICKS = 20 * 20; // 20 s
const SAMPLE_TICKS = 20; // position/XP sampling: 1 s
const TAG = "[mcportal-stats]";
const MAX_STEP = 60; // blocks per sample; more is a teleport/respawn, not travel
const BREED_WINDOW_MS = 60_000;
const BREED_RADIUS = 16;

/** name -> counters since the last flush */
let pending = new Map();
/** name -> {x,y,z,dim,xp} from the last sample */
const last = new Map();
/** name -> fractional blocks not yet reported, per mode */
const distRest = new Map();
/** recent feeding interactions, for breeding attribution: {name, type, x, z, dim, at} */
let feeds = [];

function entry(name) {
  let e = pending.get(name);
  if (!e) {
    e = { placed: {}, broken: {}, deaths: {}, kills: {}, food: {}, bred: {}, dist: {}, xp: 0, time: 0 };
    pending.set(name, e);
  }
  return e;
}

function bump(name, kind, key, n = 1) {
  if (!name || !key) return;
  const bucket = entry(name)[kind];
  bucket[key] = (bucket[key] ?? 0) + n;
}

// ---------- blocks ----------

world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  bump(ev.player.name, "placed", ev.block.typeId);
});

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  bump(ev.player.name, "broken", ev.brokenBlockPermutation.type.id);
});

// ---------- deaths and kills ----------

world.afterEvents.entityDie.subscribe((ev) => {
  const dead = ev.deadEntity;
  const src = ev.damageSource;
  const killer = src.damagingEntity;
  if (dead instanceof Player) {
    // killed by a mob/player -> its type, otherwise the damage cause (fall, lava, drowning ...)
    bump(dead.name, "deaths", killer?.isValid ? killer.typeId : `cause:${src.cause}`);
  }
  if (killer instanceof Player) {
    bump(killer.name, "kills", dead.typeId);
  }
});

// ---------- food ----------

world.afterEvents.itemCompleteUse.subscribe((ev) => {
  const item = ev.itemStack;
  if (item && item.getComponent("minecraft:food")) {
    bump(ev.source.name, "food", item.typeId);
  }
});

// ---------- breeding ----------
// The game doesn't say who bred an animal. A baby is credited to the player who
// fed an animal of the same type nearby within the last minute.

world.afterEvents.playerInteractWithEntity.subscribe((ev) => {
  const t = ev.target;
  if (!t || !t.isValid) return;
  const l = t.location;
  feeds.push({ name: ev.player.name, type: t.typeId, x: l.x, z: l.z, dim: t.dimension.id, at: Date.now() });
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
  if (best) bump(best.name, "bred", baby.typeId);
});

// ---------- distance, XP, playtime (sampled) ----------

function mode(p) {
  const riding = p.getComponent("minecraft:riding")?.entityRidingOn;
  if (riding) {
    const t = riding.typeId;
    if (t.includes("boat") || t.includes("raft")) return "boat";
    if (t.includes("minecart")) return "minecart";
    if (t === "minecraft:horse" || t === "minecraft:donkey" || t === "minecraft:mule"
        || t.endsWith("skeleton_horse") || t.endsWith("zombie_horse")) return "horse";
    return "ride";
  }
  if (p.isGliding) return "elytra";
  if (p.isFlying) return "fly";
  if (p.isSwimming || p.isInWater) return "swim";
  return "walk";
}

function sample() {
  for (const p of world.getAllPlayers()) {
    const name = p.name;
    const loc = p.location;
    const dim = p.dimension.id;
    const xp = p.getTotalXp();
    const prev = last.get(name);
    if (prev) {
      if (prev.dim === dim) {
        const step = Math.hypot(loc.x - prev.x, loc.y - prev.y, loc.z - prev.z);
        if (step > 0.05 && step < MAX_STEP) {
          const m = mode(p);
          const rest = distRest.get(name) ?? {};
          rest[m] = (rest[m] ?? 0) + step;
          distRest.set(name, rest);
        }
      }
      if (xp > prev.xp) entry(name).xp += xp - prev.xp;
    }
    entry(name).time += SAMPLE_TICKS / 20;
    last.set(name, { x: loc.x, y: loc.y, z: loc.z, dim, xp });
  }
}

world.afterEvents.playerLeave.subscribe((ev) => {
  last.delete(ev.playerName);
});

// ---------- reporting ----------

function compact(e) {
  // drop empty counters so the log line stays short
  const out = {};
  for (const [k, v] of Object.entries(e)) {
    if (typeof v === "number" ? v > 0 : Object.keys(v).length > 0) out[k] = v;
  }
  return out;
}

function flush() {
  for (const [name, rest] of distRest) {
    for (const [m, blocks] of Object.entries(rest)) {
      const whole = Math.floor(blocks);
      if (whole > 0) {
        bump(name, "dist", m, whole);
        rest[m] = blocks - whole;
      }
    }
  }
  if (pending.size === 0) return;
  const players = {};
  for (const [name, e] of pending) {
    const c = compact(e);
    if (Object.keys(c).length) players[name] = c;
  }
  pending = new Map();
  if (Object.keys(players).length) console.warn(`${TAG} ${JSON.stringify({ v: 2, players })}`);
}

system.runInterval(sample, SAMPLE_TICKS);
system.runInterval(flush, FLUSH_TICKS);

system.run(() => console.warn(`${TAG} {"v":2,"started":true}`));
