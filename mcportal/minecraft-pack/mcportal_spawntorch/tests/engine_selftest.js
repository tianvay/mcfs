// Engine check for the test server only (world-pack.sh leaves tests/ out):
// copy this file into scripts/ of a COPY of the pack and make it the manifest entry. It loads main.js, builds two
// scenes in chunk 0 of a fresh world and logs the scan result as a 16x16 grid ('#' = red veil, '.' = none):
//   cave  (y -42): closed cavity on deepslate; strips z=2 glass, z=4 carpet, z=6 bottom slab, z=8 top slab,
//                  torch at x=12 z=12 -> expected red everywhere except z=2/4/6 and within 13 blocks of the torch;
//                  z=0: upside-down stairs x 0-4 (red), upright stairs x 5-9 (none);
//                  z=1: ceiling right above the feet at x 0-4 (still red: one block is enough)
//   sky   (y 200): stone platform in the open at noon, torch at x=4 z=4 -> red only >= 14 blocks from the torch
import { system, world } from "@minecraft/server";
import "./main.js";
import { scanArea } from "./scan.js";

const out = (o) => console.warn("[mcportal-spawntorch] " + JSON.stringify(o));

function grid(dark, y) {
  const rows = [];
  for (let z = 0; z < 16; z++) {
    let row = "";
    for (let x = 0; x < 16; x++) row += dark.some((p) => p.x === x && p.y === y && p.z === z) ? "#" : ".";
    rows.push(row);
  }
  return rows;
}

function scan(dim, center, y, tag, next) {
  const result = {};
  system.runJob((function* () {
    yield* scanArea(dim, center, result);
    out({ selftest: tag, stats: result.stats, grid: grid(result.dark, y) });
    next?.();
  })());
}

system.run(() => {
  const dim = world.getDimension("overworld");
  dim.runCommand("tickingarea add 0 -64 0 15 255 15 selftest");
  let tries = 0;
  const h = system.runInterval(() => {
    if (!dim.isChunkLoaded({ x: 8, y: 0, z: 8 }) && ++tries < 30) return;
    system.clearRun(h);
    const set = (x, y, z, t) => dim.setBlockType({ x, y, z }, t);
    // cave: deepslate box, air inside (y -42..-39), floor y -43
    for (let x = 0; x < 16; x++) for (let z = 0; z < 16; z++) {
      for (let y = -44; y <= -37; y++) set(x, y, z, y >= -42 && y <= -39 ? "minecraft:air" : "minecraft:deepslate");
      if (z === 2) set(x, -43, z, "minecraft:glass");
      if (z === 4) set(x, -42, z, "minecraft:white_carpet");
    }
    for (let x = 0; x < 16; x++) {
      set(x, -43, 6, "minecraft:oak_slab"); // default: bottom half
      set(x, -43, 8, "minecraft:oak_slab");
      const b = dim.getBlock({ x, y: -43, z: 8 });
      b.setPermutation(b.permutation.withState("minecraft:vertical_half", "top"));
    }
    for (let x = 0; x < 10; x++) {
      set(x, -43, 0, "minecraft:oak_stairs");
      const b = dim.getBlock({ x, y: -43, z: 0 });
      b.setPermutation(b.permutation.withState("upside_down_bit", x < 5));
    }
    for (let x = 0; x < 5; x++) set(x, -41, 1, "minecraft:deepslate");
    set(12, -42, 12, "minecraft:torch");
    // sky: platform at y 199, torch on it
    for (let x = 0; x < 16; x++) for (let z = 0; z < 16; z++) set(x, 199, z, "minecraft:stone");
    set(4, 200, 4, "minecraft:torch");
    dim.runCommand("time set noon");
    system.runTimeout(() => {
      scan(dim, { x: 8, y: -42, z: 8 }, -42, "cave", () => scan(dim, { x: 8, y: 200, z: 8 }, 200, "sky_noon"));
    }, 60);
  }, 10);
});
