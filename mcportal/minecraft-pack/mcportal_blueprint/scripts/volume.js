// Blueprint in the world: save an area, check free space, place. Generators for system.runJob, so a
// 32 x 32 x 32 area never blocks a tick. Separate from main.js so the test server can run it without a player.
import { BlockPermutation, StructureSaveMode, world } from "@minecraft/server";
import { blockRule, REPLACEABLE } from "./core.js";

const STEP = 256; // blocks per job step

/**
 * Save the box as structure `sid` without the blocks core.blockRule excludes.
 * result.excluded = {typeId: count}; result.emptied = [[x,y,z]] (box coordinates); result.error = text if it failed.
 */
export function* saveArea(dim, min, size, sid, result) {
  result.excluded = {};
  result.emptied = []; // box coordinates of the emptied containers
  const max = { x: min.x + size.x - 1, y: min.y + size.y - 1, z: min.z + size.z - 1 };
  let s;
  try {
    s = world.structureManager.createFromWorld(sid, dim, min, max,
      { includeEntities: false, includeBlocks: true, saveMode: StructureSaveMode.Memory });
  } catch (e) {
    result.error = String(e);
    return;
  }
  const cache = new Map(); // "to" -> permutation
  let n = 0;
  for (let x = 0; x < size.x; x++) {
    for (let y = 0; y < size.y; y++) {
      for (let z = 0; z < size.z; z++) {
        if (++n % STEP === 0) yield;
        const p = { x, y, z };
        const perm = s.getBlockPermutation(p);
        if (!perm) continue;
        let r = blockRule(perm.type.id);
        // safety net for item holders the list doesn't know yet (new Minecraft versions)
        if (r.action === "keep" && hasInventory(dim, { x: min.x + x, y: min.y + y, z: min.z + z })) r = { action: "empty" };
        if (r.action === "keep") continue;
        if (r.action === "empty") {
          // setting the same permutation again drops the block's contents (measured on the test server)
          s.setBlockPermutation(p, BlockPermutation.resolve("minecraft:air"));
          s.setBlockPermutation(p, perm);
          result.emptied.push([x, y, z]);
          continue;
        }
        result.excluded[perm.type.id] = (result.excluded[perm.type.id] ?? 0) + 1;
        if (!cache.has(r.to)) cache.set(r.to, BlockPermutation.resolve(r.to));
        s.setBlockPermutation(p, cache.get(r.to));
      }
    }
  }
  s.saveToWorld();
  result.ok = true;
}

/** result.problem = text if something is in the way (or not loaded), else null */
export function* checkFree(dim, min, size, result) {
  result.problem = null;
  let n = 0;
  for (let y = 0; y < size.y; y++) {
    for (let x = 0; x < size.x; x++) {
      for (let z = 0; z < size.z; z++) {
        if (++n % STEP === 0) yield;
        const at = { x: min.x + x, y: min.y + y, z: min.z + z };
        let b;
        try {
          b = dim.getBlock(at);
        } catch {
          b = undefined; // outside the world height
        }
        if (!b) {
          result.problem = "Der Bereich ist nicht geladen oder liegt außerhalb der Welt.";
          return;
        }
        if (!REPLACEABLE.has(b.typeId)) {
          result.problem = `Nicht genug Platz: ${b.typeId.replace(/^minecraft:/, "").replace(/_/g, " ")} bei `
            + `${at.x} ${at.y} ${at.z} ist im Weg.`;
          result.blocker = at;
          return;
        }
      }
    }
  }
}

function hasInventory(dim, at) {
  try {
    return !!dim.getBlock(at)?.getComponent("minecraft:inventory");
  } catch {
    return false;
  }
}

export function place(dim, sid, min, rotation) {
  world.structureManager.place(sid, dim, min, { rotation, includeEntities: false });
}

/**
 * Second safety net after placing: empty every placed container again (world coordinates).
 * @returns {number} items that were still there (should always be 0)
 */
export function clearContainers(dim, cells) {
  let found = 0;
  for (const at of cells) {
    try {
      const c = dim.getBlock(at)?.getComponent("minecraft:inventory")?.container;
      if (!c) continue;
      for (let i = 0; i < c.size; i++) if (c.getItem(i)) found++;
      c.clearAll();
    } catch { /* unloaded */ }
  }
  return found;
}
