// What the shop's tools do to the world - no players needed, so the test server can check it
// (tests/engine_selftest.js).
import { cubeOffsets, fieldOffsets, isCubeBlock, isLeaves, isLog, isRipe, treeLogs } from "./core.js";

/** break a block the way the game does it, with its drops; true if something was broken */
export function breakBlock(dim, pos) {
  try {
    return dim.runCommand(`setblock ${pos.x} ${pos.y} ${pos.z} air destroy`).successCount > 0;
  } catch {
    return false; // not loaded
  }
}

/** Bergbrecher: natural rock and ores around `center` (already mined); returns the number of blocks broken */
export function breakCube(dim, center) {
  let n = 0;
  for (const o of cubeOffsets()) {
    const pos = { x: center.x + o.x, y: center.y + o.y, z: center.z + o.z };
    let id;
    try { id = dim.getBlock(pos)?.typeId; } catch { continue; }
    if (id && isCubeBlock(id) && breakBlock(dim, pos)) n++;
  }
  return n;
}

/**
 * Holzfäller-Axt: the rest of the tree whose log at `start` was just cut. Only real trees (logs with leaves);
 * returns the number of logs felled.
 */
export function fellTree(dim, start) {
  const at = (pos) => {
    let id;
    try { id = dim.getBlock(pos)?.typeId; } catch { return "other"; }
    if (!id) return "other";
    return isLog(id) ? "log" : isLeaves(id) ? "leaves" : "other";
  };
  const { logs, leaves } = treeLogs(start, at);
  if (!leaves) return 0;
  let n = 0;
  for (const pos of logs.slice(1)) if (breakBlock(dim, pos)) n++; // logs[0] is the block the player cut
  return n;
}

/** Ernte-Sichel: ripe crops in the 3 x 3 around `center` are harvested and planted again; returns how many */
export function harvest(dim, center) {
  let n = 0;
  for (const o of fieldOffsets()) {
    const pos = { x: center.x + o.x, y: center.y, z: center.z + o.z };
    let block;
    try { block = dim.getBlock(pos); } catch { continue; }
    if (!block) continue;
    const typeId = block.typeId;
    if (!isRipe(typeId, block.permutation.getAllStates())) continue;
    if (!breakBlock(dim, pos)) continue;
    try { dim.setBlockType(pos, typeId); } catch { /* the ground is gone - then it stays harvested */ }
    n++;
  }
  return n;
}
