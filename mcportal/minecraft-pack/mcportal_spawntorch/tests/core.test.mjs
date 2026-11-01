// node --test mcportal/minecraft-pack/mcportal_spawntorch/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  estimateBlockLight, isDark, isOpen, isPeacefulBiome, isSpawnFloor, lightEmission, spotsInColumn, statusText,
} from "../scripts/core.js";

test("floors mobs can stand on", () => {
  for (const b of ["stone", "grass_block", "dirt", "deepslate", "oak_planks", "sand", "netherrack", "farmland",
    "brain_coral_block", "dead_tube_coral_block", "oak_double_slab", "double_stone_block_slab", "packed_ice"]) {
    assert.equal(isSpawnFloor("minecraft:" + b), true, b);
  }
});

test("spawn-proof floors", () => {
  for (const b of ["air", "water", "lava", "glass", "white_stained_glass", "glass_pane", "tinted_glass",
    "oak_leaves", "azalea_leaves", "oak_stairs", "white_carpet", "moss_carpet", "stone_pressure_plate",
    "oak_button", "rail", "golden_rail", "oak_fence", "oak_fence_gate", "cobblestone_wall", "oak_trapdoor",
    "iron_door", "torch", "lantern", "chest", "ender_chest", "bed", "magma", "hopper", "barrier", "brain_coral",
    "oak_hanging_sign", "candle_cake", "mob_spawner", "snow_layer", "scaffolding"]) {
    assert.equal(isSpawnFloor("minecraft:" + b), false, b);
  }
});

test("slabs: only the upper half is a floor", () => {
  assert.equal(isSpawnFloor("minecraft:oak_slab", { "minecraft:vertical_half": "bottom" }), false);
  assert.equal(isSpawnFloor("minecraft:oak_slab", { "minecraft:vertical_half": "top" }), true);
  assert.equal(isSpawnFloor("minecraft:stone_block_slab2", { top_slot_bit: true }), true);
  assert.equal(isSpawnFloor("minecraft:stone_block_slab2", { top_slot_bit: false }), false);
  assert.equal(isSpawnFloor("minecraft:oak_slab"), false, "unknown half -> bottom");
});

test("open space", () => {
  for (const b of ["air", "short_grass", "tall_grass", "fern", "poppy", "red_tulip", "oak_sapling", "snow_layer",
    "dead_bush", "sweet_berry_bush", "torchflower"]) assert.equal(isOpen("minecraft:" + b), true, b);
  for (const b of ["stone", "grass_block", "grass", "water", "torch", "white_carpet", "rail", "stone_pressure_plate",
    "oak_button", "redstone_wire", "seagrass", "cobweb", "glass"]) assert.equal(isOpen("minecraft:" + b), false, b);
});

test("light emission", () => {
  assert.equal(lightEmission("minecraft:torch"), 14);
  assert.equal(lightEmission("minecraft:copper_torch"), 14);
  assert.equal(lightEmission("minecraft:soul_torch"), 10);
  assert.equal(lightEmission("minecraft:redstone_torch"), 7);
  assert.equal(lightEmission("minecraft:unlit_redstone_torch"), 0);
  assert.equal(lightEmission("minecraft:lantern"), 15);
  assert.equal(lightEmission("minecraft:soul_lantern"), 10);
  assert.equal(lightEmission("minecraft:sea_lantern"), 15);
  assert.equal(lightEmission("minecraft:glowstone"), 15);
  assert.equal(lightEmission("minecraft:campfire"), 15);
  assert.equal(lightEmission("minecraft:campfire", { extinguished: true }), 0);
  assert.equal(lightEmission("minecraft:light_block_9"), 9);
  assert.equal(lightEmission("minecraft:stone"), 0);
  assert.equal(lightEmission("minecraft:torchflower"), 0);
});

test("block light estimate: falls off by 1 per block (taxicab)", () => {
  const torch = [{ x: 0, y: 64, z: 0, level: 14 }];
  assert.equal(estimateBlockLight({ x: 0, y: 64, z: 0 }, torch), 14);
  assert.equal(estimateBlockLight({ x: 4, y: 64, z: 4 }, torch), 6, "same as measured on the test server");
  assert.equal(estimateBlockLight({ x: 7, y: 64, z: 7 }, torch), 0);
  assert.equal(estimateBlockLight({ x: 20, y: 64, z: 0 }, torch), 0);
  assert.equal(estimateBlockLight({ x: 0, y: 0, z: 0 }, []), 0);
});

test("dark or lit, from total and sky light (values from the test server)", () => {
  const never = () => assert.fail("no estimate needed");
  assert.equal(isDark(0, 0, never), true, "closed cave");
  assert.equal(isDark(6, 0, never), false, "cave with a torch");
  assert.equal(isDark(12, 4, never), false, "midnight, next to a torch");
  assert.equal(isDark(15, 15, () => 0), true, "noon in the open, no light source near");
  assert.equal(isDark(15, 15, () => 3), false, "noon in the open, torch near");
  assert.equal(isDark(4, 4, () => 0), true, "midnight in the open");
});

test("column: spots need a solid floor and two open blocks", () => {
  const col = (...ids) => ids.map((b) => (typeof b === "string" ? { typeId: "minecraft:" + b, states: {} } : b));
  // index:        0      1      2        3       4      5      6
  assert.deepEqual(spotsInColumn(col("air", "air", "stone", "air", "air", "glass", "air")), [1]);
  assert.deepEqual(spotsInColumn(col("air", "short_grass", "grass_block")), [1]);
  assert.deepEqual(spotsInColumn(col("stone", "air", "stone")), [], "only one block high");
  assert.deepEqual(spotsInColumn(col("air", "white_carpet", "stone")), [], "carpet on the floor");
  assert.deepEqual(spotsInColumn(col("air", "torch", "stone")), []);
  assert.deepEqual(spotsInColumn(col("air", "air", { typeId: "minecraft:oak_slab", states: { "minecraft:vertical_half": "top" } })), [1]);
});

test("biomes and status text", () => {
  assert.equal(isPeacefulBiome("minecraft:mushroom_island"), true);
  assert.equal(isPeacefulBiome("minecraft:plains"), false);
  assert.equal(isPeacefulBiome(undefined), false);
  assert.match(statusText(0, false), /hell genug/);
  assert.match(statusText(1, false), /1 §fdunkle Stelle -/);
  assert.match(statusText(5, false), /dunkle Stellen/);
  assert.match(statusText(0, true), /sucht/);
});
