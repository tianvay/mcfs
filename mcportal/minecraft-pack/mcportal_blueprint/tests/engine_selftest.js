// Engine check for the test server only (world-pack.sh leaves tests/ out):
// copy this file into scripts/ of a COPY of the pack and make it the manifest entry. It loads main.js, builds an
// asymmetric 4 x 3 x 2 test piece in chunk 0 of a fresh world (every block different, plus a chest and a hopper
// with items, a diamond block and ores), saves it with saveArea as if the player looked north, then places it
// for all four facings and compares every block with what core.placement/placedCell/blockRule predict.
// Also: checkFree must refuse an occupied spot, and the hopper must arrive empty.
// "containers": every block that can hold items, filled, saved by the real rules and placed again - reports
// which ones have a script inventory, that a raw structure WOULD copy their contents (rawItems), and that none
// arrives with anything in it after saveArea (savedItems 0, or air for the ones without script inventory).
import { BlockPermutation, ItemStack, StructureSaveMode, system, world } from "@minecraft/server";
import "./main.js";
import { blockRule, placedCell, placement } from "./core.js";
import { checkFree, clearContainers, place, saveArea } from "./volume.js";

const out = (o) => console.warn("[mcportal-blueprint] " + JSON.stringify(o));

const PIECE = [ // [x, y, z, block]
  [0, 0, 0, "cobblestone"], [1, 0, 0, "stone_bricks"], [2, 0, 0, "oak_planks"], [3, 0, 0, "sandstone"],
  [0, 0, 1, "brick_block"], [1, 0, 1, "hopper"], [2, 0, 1, "diamond_block"], [3, 0, 1, "iron_ore"],
  [0, 1, 0, "oak_stairs"], [1, 1, 0, "chest"], [2, 1, 0, "deepslate_gold_ore"], [3, 1, 0, "glass"],
  [0, 1, 1, "redstone_block"], [1, 1, 1, "obsidian"], [2, 1, 1, "copper_block"], [3, 1, 1, "oak_log"],
  [0, 2, 0, "white_wool"], [3, 2, 1, "red_wool"],
];
const SIZE = { x: 4, y: 3, z: 2 };
const ORIGIN = { x: 2, y: 100, z: 2 };

function job(gen, then) {
  system.runJob((function* () {
    yield* gen;
    then();
  })());
}

system.run(() => {
  const dim = world.getDimension("overworld");
  dim.runCommand("tickingarea add 0 -64 0 15 255 15 selftest");
  let tries = 0;
  const h = system.runInterval(() => {
    if (!dim.isChunkLoaded({ x: 8, y: 0, z: 8 }) && ++tries < 30) return;
    system.clearRun(h);
    for (const [x, y, z, b] of PIECE) dim.setBlockType({ x: ORIGIN.x + x, y: ORIGIN.y + y, z: ORIGIN.z + z }, `minecraft:${b}`);
    const inv = (x, y, z) => dim.getBlock({ x: ORIGIN.x + x, y: ORIGIN.y + y, z: ORIGIN.z + z })
      .getComponent("minecraft:inventory").container;
    inv(1, 1, 0).setItem(0, new ItemStack("minecraft:diamond", 5));
    inv(1, 0, 1).setItem(0, new ItemStack("minecraft:iron_ingot", 3));
    const saved = {};
    job(saveArea(dim, ORIGIN, SIZE, "mcfs:bp_selftest", saved), () => {
      out({ selftest: "saved", ok: saved.ok === true, excluded: saved.excluded });
      const results = [];
      const target = { x: 8, y: 120, z: 8 };
      for (let f = 0; f < 4; f++) {
        const p = placement(SIZE, 0, f, { ...target, y: target.y + f * 5 });
        place(dim, "mcfs:bp_selftest", p.min, p.rotation);
        const wrong = [];
        for (const [x, y, z, b] of PIECE) {
          const r = blockRule(`minecraft:${b}`);
          const want = r.action === "replace" ? r.to : `minecraft:${b}`;
          const at = placedCell(SIZE, f, p.min, { x, y, z });
          const got = dim.getBlock(at)?.typeId;
          if (got !== want) wrong.push(`${b}@${x},${y},${z}->${at.x},${at.y},${at.z}: ${got}`);
        }
        const hopper = placedCell(SIZE, f, p.min, { x: 1, y: 0, z: 1 });
        const hopperItem = dim.getBlock(hopper)?.getComponent("minecraft:inventory")?.container?.getItem(0)?.typeId ?? null;
        const stairs = dim.getBlock(placedCell(SIZE, f, p.min, { x: 0, y: 1, z: 0 }))?.permutation.getAllStates();
        results.push({ facing: f, rotation: p.rotation, min: p.min, wrong, hopperItem, stairs });
      }
      out({ selftest: "placed", results });
      const free = {};
      job(checkFree(dim, ORIGIN, SIZE, free), () => {
        const empty = {};
        job(checkFree(dim, { x: 0, y: 200, z: 0 }, { x: 16, y: 32, z: 16 }, empty), () => {
          out({ selftest: "checkFree", occupied: free.problem, emptySky: empty.problem });
          const t0 = Date.now();
          const big = {};
          job(saveArea(dim, { x: 0, y: 90, z: 0 }, { x: 16, y: 32, z: 16 }, "mcfs:bp_big", big), () => {
            out({ selftest: "save16x32x16", ok: big.ok === true, ms: Date.now() - t0 });
            containers(dim);
          });
        });
      });
    });
  }, 10);
});

const HOLDERS = ["hopper", "dropper", "dispenser", "crafter", "furnace", "blast_furnace", "smoker", "brewing_stand",
  "chiseled_bookshelf", "lectern", "jukebox", "decorated_pot", "frame", "glow_frame", "campfire", "soul_campfire",
  "oak_shelf", "chest", "barrel"];

function containers(dim) {
  const at = (i) => ({ x: i % 16, y: 160 + Math.floor(i / 16) * 2, z: 12 });
  const report = {};
  HOLDERS.forEach((b, i) => {
    try {
      dim.setBlockType(at(i), `minecraft:${b}`);
    } catch (e) {
      report[b] = `unknown block: ${e}`;
      return;
    }
    const c = dim.getBlock(at(i)).getComponent("minecraft:inventory")?.container;
    if (!c) {
      report[b] = { inventory: false };
      return;
    }
    let filled = 0;
    for (const item of ["minecraft:diamond", "minecraft:blaze_powder", "minecraft:book", "minecraft:cobblestone"]) {
      for (let slot = 0; slot < c.size && !filled; slot++) {
        try { c.setItem(slot, new ItemStack(item, 1)); filled = c.getItem(slot) ? 1 : 0; } catch { /* not allowed */ }
      }
    }
    report[b] = { inventory: true, size: c.size, filled: filled === 1 };
  });
  // 1) raw structure WITHOUT emptying - does the engine copy contents at all? 2) the real saveArea
  const min = { x: 0, y: 160, z: 12 };
  const size = { x: 16, y: 3, z: 1 };
  const raw = world.structureManager.createFromWorld("mcfs:bp_raw", dim, min,
    { x: 15, y: 162, z: 12 }, { includeEntities: false, saveMode: StructureSaveMode.World });
  void raw; void BlockPermutation;
  const saved = {};
  job(saveArea(dim, min, size, "mcfs:bp_holders", saved), () => {
    const check = (sid, y0, key) => {
      place(dim, sid, { x: 0, y: y0, z: 14 }, "None");
      HOLDERS.forEach((b, i) => {
        const p = at(i);
        const blk = dim.getBlock({ x: p.x, y: y0 + (p.y - 160), z: 14 });
        const c = blk?.getComponent("minecraft:inventory")?.container;
        let items = 0;
        if (c) for (let s = 0; s < c.size; s++) if (c.getItem(s)) items++;
        if (typeof report[b] === "object") report[b][key] = c ? items : `${blk?.typeId} (no inv)`;
      });
    };
    check("mcfs:bp_raw", 180, "rawItems");
    check("mcfs:bp_holders", 190, "savedItems");
    const left = clearContainers(dim, saved.emptied.map(([x, y, z]) => ({ x, y: 190 + y, z: 14 + z })));
    out({ selftest: "containers", emptied: saved.emptied.length, leftAfterPlace: left, excluded: saved.excluded, report });
  });
}
