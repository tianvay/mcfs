// node --test mcportal/minecraft-pack/mcportal_blueprint/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  anchorOf, blockRule, boxOf, cleanName, excludedText, facingOf, outline, placedCell, placement, pruneGone,
  sizeProblem, updateGone,
} from "../scripts/core.js";

const rule = (t) => blockRule(`minecraft:${t}`);
const air = { action: "replace", to: "minecraft:air" };

test("valuable and technical blocks become air", () => {
  for (const t of ["netherite_block", "ancient_debris", "diamond_block", "emerald_block", "gold_block", "iron_block",
    "lapis_block", "raw_gold_block", "beacon", "conduit", "lodestone", "heavy_core", "enchanting_table", "anvil",
    "damaged_anvil", "wither_skeleton_skull", "dragon_head", "dragon_egg", "bedrock", "reinforced_deepslate",
    "end_portal_frame", "portal", "mob_spawner", "trial_spawner", "vault", "suspicious_sand", "command_block",
    "chain_command_block", "structure_block", "jigsaw", "barrier", "light_block", "light_block_15", "allow",
    "border_block", "budding_amethyst"]) {
    assert.deepEqual(rule(t), air, t);
  }
});

test("former borderline cases are excluded too, except the redstone block", () => {
  for (const t of ["coal_block", "obsidian", "crying_obsidian", "amethyst_block", "sponge", "wet_sponge",
    "sea_lantern", "glowstone", "copper_block", "exposed_copper", "waxed_oxidized_copper", "cut_copper",
    "waxed_weathered_cut_copper", "chiseled_copper", "ender_chest"]) {
    assert.deepEqual(rule(t), air, t);
  }
  assert.deepEqual(rule("redstone_block"), { action: "keep" });
  for (const t of ["cut_copper_slab", "copper_grate", "copper_bulb", "copper_door", "copper_trapdoor"]) {
    assert.deepEqual(rule(t), { action: "keep" }, t);
  }
});

test("storage containers and item holders without script inventory are not copied", () => {
  for (const t of ["chest", "trapped_chest", "barrel", "ender_chest", "undyed_shulker_box", "red_shulker_box",
    "copper_chest", "waxed_oxidized_copper_chest", "crafter", "chiseled_bookshelf", "decorated_pot", "frame",
    "glow_frame", "campfire", "soul_campfire", "oak_shelf"]) {
    assert.deepEqual(rule(t), air, t);
  }
});

test("containers with a script inventory stay, but empty", () => {
  for (const t of ["hopper", "dropper", "dispenser", "furnace", "lit_furnace", "blast_furnace", "smoker",
    "brewing_stand", "lectern", "jukebox"]) {
    assert.deepEqual(rule(t), { action: "empty" }, t);
  }
});

test("ores turn into the stone around them", () => {
  assert.deepEqual(rule("iron_ore"), { action: "replace", to: "minecraft:stone" });
  assert.deepEqual(rule("lit_redstone_ore"), { action: "replace", to: "minecraft:stone" });
  assert.deepEqual(rule("deepslate_diamond_ore"), { action: "replace", to: "minecraft:deepslate" });
  assert.deepEqual(rule("lit_deepslate_redstone_ore"), { action: "replace", to: "minecraft:deepslate" });
  assert.deepEqual(rule("nether_gold_ore"), { action: "replace", to: "minecraft:netherrack" });
  assert.deepEqual(rule("quartz_ore"), { action: "replace", to: "minecraft:netherrack" });
  assert.deepEqual(rule("gilded_blackstone"), { action: "replace", to: "minecraft:blackstone" });
});

test("normal building blocks and redstone parts are kept", () => {
  for (const t of ["cobblestone", "stone_bricks", "oak_log", "oak_leaves", "redstone_wire", "unpowered_repeater",
    "piston", "sticky_piston", "observer", "redstone_torch", "lever", "glass", "stone", "deepslate", "bookshelf",
    "oak_stairs", "water", "lava", "tnt", "slime", "honey_block", "target"]) {
    assert.deepEqual(rule(t), { action: "keep" }, t);
  }
  assert.deepEqual(blockRule("mcfs:anything"), air, "our own blocks");
});

test("box and size limit 32 x 32 x 32", () => {
  assert.deepEqual(boxOf({ x: 5, y: 70, z: -3 }, { x: 2, y: 64, z: 0 }),
    { min: { x: 2, y: 64, z: -3 }, size: { x: 4, y: 7, z: 4 } });
  assert.equal(sizeProblem({ x: 32, y: 32, z: 32 }), null);
  assert.match(sizeProblem({ x: 33, y: 1, z: 1 }), /höchstens 32/);
});

test("facing from yaw", () => {
  assert.equal(facingOf(0), 2, "south");
  assert.equal(facingOf(90), 3, "west");
  assert.equal(facingOf(180), 0, "north");
  assert.equal(facingOf(-180), 0, "north");
  assert.equal(facingOf(-90), 1, "east");
  assert.equal(facingOf(-100), 1);
  assert.equal(facingOf(44), 2);
  assert.equal(facingOf(271), 1);
});

test("anchor = near, left, bottom corner as the player sees it", () => {
  const size = { x: 4, y: 3, z: 2 };
  // looking north (-z): near is the south side (max z), left is west (min x)
  assert.deepEqual(anchorOf(size, 0), { x: 0, y: 0, z: 1 });
  // looking east (+x): near is west (min x), left is north (min z)
  assert.deepEqual(anchorOf(size, 1), { x: 0, y: 0, z: 0 });
  // looking south: near is north (min z), left is east (max x)
  assert.deepEqual(anchorOf(size, 2), { x: 3, y: 0, z: 0 });
  // looking west: near is east (max x), left is south (max z)
  assert.deepEqual(anchorOf(size, 3), { x: 3, y: 0, z: 1 });
});

test("same facing: the area goes back exactly where the anchor says", () => {
  const size = { x: 4, y: 3, z: 2 };
  for (let f = 0; f < 4; f++) {
    const a = anchorOf(size, f);
    const p = placement(size, f, f, { x: 100, y: 64, z: 100 });
    assert.equal(p.rotation, "None");
    assert.deepEqual(p.size, size);
    assert.deepEqual(p.min, { x: 100 - a.x, y: 64, z: 100 - a.z });
  }
});

test("turned placement: anchor on the target, the area in front of and right of the player", () => {
  // a wall 4 long (x) and 1 deep, saved looking north: runs to the right (east) of the anchor
  const size = { x: 4, y: 3, z: 1 };
  const target = { x: 0, y: 64, z: 0 };
  // now looking east: the wall must run to the right = south (+z), starting at the target
  const east = placement(size, 0, 1, target);
  assert.equal(east.rotation, "Rotate90");
  assert.deepEqual(east.size, { x: 1, y: 3, z: 4 });
  assert.deepEqual(east.min, { x: 0, y: 64, z: 0 });
  // looking south: to the right = west (-x)
  const south = placement(size, 0, 2, target);
  assert.equal(south.rotation, "Rotate180");
  assert.deepEqual(south.min, { x: -3, y: 64, z: 0 });
  // looking west: to the right = north (-z)
  const west = placement(size, 0, 3, target);
  assert.equal(west.rotation, "Rotate270");
  assert.deepEqual(west.min, { x: 0, y: 64, z: -3 });
  // the anchor block itself lands on the target in every case
  for (let f = 0; f < 4; f++) {
    const p = placement(size, 0, f, target);
    assert.deepEqual(placedCell(size, (f - 0 + 4) % 4, p.min, anchorOf(size, 0)), target, `facing ${f}`);
  }
});

test("depth goes away from the player", () => {
  // 1 wide, 3 deep, saved looking south (+z): near = min z
  const size = { x: 1, y: 1, z: 3 };
  const p = placement(size, 2, 0, { x: 0, y: 0, z: 0 }); // now looking north
  assert.deepEqual(p.min, { x: 0, y: 0, z: -2 }, "extends to -z = forward");
});

test("outline: 12 edges", () => {
  const pts = outline({ x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1 });
  assert.equal(pts.length, 24);
  assert.ok(pts.every((p) => [0, 1].includes(p.x) && [0, 1].includes(p.y) && [0, 1].includes(p.z)));
});

test("names and texts", () => {
  assert.equal(cleanName("  §cStadt   mauer ", "Bauplan 1"), "Stadt mauer");
  assert.equal(cleanName("", "Bauplan 1"), "Bauplan 1");
  assert.equal(cleanName("x".repeat(40), "-").length, 24);
  assert.equal(excludedText({ "minecraft:iron_ore": 2, "minecraft:diamond_block": 4 }), "4 × diamond block, 2 × iron ore");
});

test("copies: the blueprint that went into the crafting grid is found", () => {
  const gone = [];
  // two copies of A and one B in the inventory; one A goes into the crafting grid
  updateGone(gone, new Map([["A", 2], ["B", 1]]), new Map([["A", 1], ["B", 1]]), 10);
  assert.deepEqual(gone, [{ sid: "A", tick: 10 }]);
  // B is put into the grid and taken out again -> back off the list
  updateGone(gone, new Map([["A", 1], ["B", 1]]), new Map([["A", 1]]), 12);
  updateGone(gone, new Map([["A", 1]]), new Map([["A", 1], ["B", 1]]), 14);
  assert.deepEqual(gone, [{ sid: "A", tick: 10 }]);
  pruneGone(gone, 10 + 100, 50);
  assert.deepEqual(gone, []);
});
