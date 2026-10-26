// Waypoint structure in the world: check the space, build, verify.
// Separate from main.js so it can be exercised on the test server without a player.
import { BlockPermutation } from "@minecraft/server";
import { clearanceCells, layout, REPLACEABLE, ruinCells } from "./core.js";

/** @returns {string|null} why the structure can't be built here, or null */
export function placementProblem(dim, center) {
  for (const c of clearanceCells()) {
    const b = dim.getBlock({ x: center.x + c.dx, y: center.y + c.dy, z: center.z + c.dz });
    if (!b) return "Hier kann kein Wegpunkt stehen (Weltgrenze oder nicht geladen).";
    if (!REPLACEABLE.has(b.typeId)) return "Nicht genug Platz: Ein Wegpunkt braucht 3 × 3 Blöcke und 4 Blöcke Höhe frei.";
  }
  return null;
}

export function build(dim, center) {
  for (const c of layout()) {
    dim.getBlock({ x: center.x + c.dx, y: center.y + c.dy, z: center.z + c.dz })
      ?.setPermutation(BlockPermutation.resolve(c.block, c.states ?? {}));
  }
}

/**
 * Turn a removed waypoint into a ruin (see core.ruinCells).
 * @returns {boolean} false if the area is not loaded - try again later
 */
export function ruin(dim, center, withCenter) {
  const cells = ruinCells(withCenter).map((c) => ({
    c, block: dim.getBlock({ x: center.x + c.dx, y: center.y + c.dy, z: center.z + c.dz }),
  }));
  if (cells.some(({ block }) => !block)) return false;
  for (const { c, block } of cells) {
    if (block.typeId === c.from) block.setPermutation(BlockPermutation.resolve(c.to, c.states ?? {}));
  }
  return true;
}

/** list of differences between the world and the plan (empty = structure complete) */
export function verify(dim, center) {
  const wrong = [];
  for (const c of layout()) {
    const b = dim.getBlock({ x: center.x + c.dx, y: center.y + c.dy, z: center.z + c.dz });
    const states = b?.permutation.getAllStates() ?? {};
    const statesOk = Object.entries(c.states ?? {}).every(([k, v]) => states[k] === v);
    if (b?.typeId !== c.block || !statesOk) wrong.push(`${c.dx}/${c.dy}/${c.dz}: ${b?.typeId} statt ${c.block}`);
  }
  return wrong;
}
