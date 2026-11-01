// Minecraft Family Portal - spawn torch (behavior pack, change M14)
//
//  * Crafting: 9 torches (the whole crafting grid) -> item "mcfs:spawn_torch" (Spawnfackel)
//  * While a player holds it in the main hand, every block around them (~1 chunk) on which a hostile mob could
//    spawn at night gets a red veil - only that player sees it. The action bar counts the dark spots.
//  * Rules (floor, free space, block light) in core.js, scanning in scan.js; only in the overworld.
//  * Log: only the startup line [mcportal-spawntorch] {"v":1,"started":true} - the portal gets nothing else.
// Uses only stable APIs (@minecraft/server) - no experiments in the world.
import { EquipmentSlot, system, world } from "@minecraft/server";
import { ITEM_ID, PARTICLE_ID, statusText } from "./core.js";
import { scanArea } from "./scan.js";

const TAG = "[mcportal-spawntorch]";
const CHECK_TICKS = 10; // who holds the torch, start scans
const DRAW_TICKS = 20; // the veil particle lives 1.1 s (resource pack)
const MIN_SCAN_TICKS = 40; // a new scan of the same player at most every 2 s
const MAX_PARTICLES = 1500; // per player and draw, so a huge dark cave doesn't choke a tablet

/** player id -> { dark: [{x,y,z}], scanning, lastScan, dim } */
const holders = new Map();

function holdsTorch(player) {
  try {
    return player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand)?.typeId === ITEM_ID;
  } catch {
    return false;
  }
}

function check() {
  const now = system.currentTick;
  const seen = new Set();
  for (const player of world.getPlayers()) {
    if (!player.isValid || !holdsTorch(player)) continue;
    seen.add(player.id);
    let h = holders.get(player.id);
    if (!h || h.dim !== player.dimension.id) {
      h = { dark: [], scanning: false, lastScan: -MIN_SCAN_TICKS, dim: player.dimension.id, first: true };
      holders.set(player.id, h);
    }
    if (h.dim !== "minecraft:overworld" || h.scanning || now - h.lastScan < MIN_SCAN_TICKS) continue;
    h.scanning = true;
    h.lastScan = now;
    const result = {};
    const job = scanArea(player.dimension, player.location, result);
    system.runJob((function* () {
      yield* job;
      h.dark = result.dark;
      h.scanning = false;
      h.first = false;
    })());
  }
  for (const id of holders.keys()) if (!seen.has(id)) holders.delete(id);
}

function draw() {
  for (const player of world.getPlayers()) {
    const h = holders.get(player.id);
    if (!h || !player.isValid) continue;
    if (h.dim !== "minecraft:overworld") {
      player.onScreenDisplay.setActionBar("§7Die Spawnfackel wirkt nur in der Oberwelt");
      continue;
    }
    player.onScreenDisplay.setActionBar(statusText(h.dark.length, h.first));
    const n = Math.min(h.dark.length, MAX_PARTICLES);
    for (let i = 0; i < n; i++) {
      const p = h.dark[i];
      try {
        player.spawnParticle(PARTICLE_ID, { x: p.x + 0.5, y: p.y + 0.02, z: p.z + 0.5 });
      } catch {
        break; // player left / area unloaded - next draw tries again
      }
    }
  }
}

system.runInterval(check, CHECK_TICKS);
system.runInterval(draw, DRAW_TICKS);
system.run(() => console.warn(`${TAG} {"v":1,"started":true}`));
