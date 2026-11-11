// node --test mcportal/minecraft-pack/mcportal_shop/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  book, canAfford, cubeOffsets, emptyAccount, fieldOffsets, isCubeBlock, isLeaves, isLog, isRipe, ITEMS, parseControl,
  readAccount, REWARDS, rewardsFor, treeLogs, wear,
} from "../scripts/core.js";

test("taking part in an event is worth 5, and nothing costs more than four of them", () => {
  assert.equal(REWARDS.participation, 5);
  for (const item of ITEMS) {
    assert.ok(item.price >= 1 && item.price <= 4 * REWARDS.participation, item.name);
    assert.match(item.id, /^mcfs:[a-z]+$/);
  }
});

test("news of the events pack become bookings", () => {
  assert.deepEqual(rewardsFor({ event: "ended", type: "storm", participants: ["Steve", "Alex"] }), [
    { player: "Steve", amount: 5, reason: "participation", detail: "storm" },
    { player: "Alex", amount: 5, reason: "participation", detail: "storm" },
  ]);
  assert.deepEqual(rewardsFor({ event: "bounty", boss: "Bernd", hunters: ["Steve", "Steve", 7] }),
    [{ player: "Steve", amount: 5, reason: "bounty", detail: "Bernd" }]);
  assert.deepEqual(rewardsFor({ event: "star", player: "Sunny" }),
    [{ player: "Sunny", amount: 1, reason: "star", detail: undefined }]);
  assert.equal(rewardsFor({ event: "meteor_hit", players: ["Steve", "Alex"] }).length, 2);
  assert.deepEqual(rewardsFor({ event: "treasure_found", player: "Alex" })[0].amount, 5);
});

test("news that are worth nothing", () => {
  for (const n of [null, "x", {}, { event: "started", type: "storm" }, { event: "state", active: [] },
    { event: "kill", kind: "blood_wolf", player: "Steve" }, { event: "ended", type: "storm" },
    { event: "star" }, { event: "ended", participants: "Steve" }]) {
    assert.deepEqual(rewardsFor(n), [], JSON.stringify(n));
  }
});

test("accounts: earning, spending, never below zero", () => {
  let a = emptyAccount();
  ({ account: a } = book(a, 5, "participation"));
  ({ account: a } = book(a, 20, "seed"));
  assert.deepEqual(a, { b: 25, e: 25, s: 1 });
  assert.ok(canAfford(a, { price: 25 }));
  assert.ok(!canAfford(a, { price: 26 }));
  const bought = book(a, -20, "buy");
  assert.deepEqual(bought, { account: { b: 5, e: 25, s: 1 }, delta: -20 });
  const taken = book(bought.account, -50, "admin");
  assert.deepEqual(taken, { account: { b: 0, e: 25, s: 1 }, delta: -5 }, "only what is there can be taken");
  const gift = book(taken.account, 10, "admin");
  assert.deepEqual(gift.account, { b: 10, e: 25, s: 1 }, "a gift from the admin is not earned");
});

test("stored accounts: broken or old entries start again", () => {
  assert.deepEqual(readAccount('{"b":12,"e":40,"s":1}'), { b: 12, e: 40, s: 1 });
  assert.deepEqual(readAccount('{"b":3.9,"e":4}'), { b: 3, e: 4 });
  for (const raw of [undefined, "", "{", '{"b":"x","e":1}', "null", 5]) assert.deepEqual(readAccount(raw), { b: 0, e: 0 });
});

test("console commands", () => {
  assert.deepEqual(parseControl("grant 15 Steve"), { action: "grant", amount: 15, name: "Steve" });
  assert.deepEqual(parseControl("grant -5 Sunny Day#12"), { action: "grant", amount: -5, name: "Sunny Day#12" });
  assert.deepEqual(parseControl("seed 40 Alex"), { action: "seed", amount: 40, name: "Alex" });
  assert.deepEqual(parseControl(" balances "), { action: "balances" });
  for (const bad of ["", "grant", "grant x Steve", "grant 0 Steve", "grant 1000 Steve", "seed -5 Steve",
    "grant 5 @a", "grant 5 Steve; op Steve", "grant 5 a  b", "give 5 Steve", "grant 5.5 Steve"]) {
    assert.equal(parseControl(bad).action, "error", bad);
  }
});

test("Bergbrecher: natural rock and ores, nothing people build with", () => {
  for (const t of ["stone", "deepslate", "granite", "tuff", "netherrack", "end_stone", "diamond_ore",
    "deepslate_iron_ore", "lit_redstone_ore", "quartz_ore", "ancient_debris", "hardened_clay", "orange_terracotta",
    "raw_iron_block", "sandstone"]) {
    assert.ok(isCubeBlock(`minecraft:${t}`), t);
  }
  for (const t of ["cobblestone", "stone_bricks", "polished_granite", "furnace", "chest", "hopper", "obsidian",
    "bedrock", "mob_spawner", "budding_amethyst", "glass", "dirt", "gravel", "oak_planks", "iron_block",
    "diamond_block", "smooth_stone", "orange_glazed_terracotta", "ender_chest", "air", "water", "ice",
    "reinforced_deepslate", "undyed_shulker_box"]) {
    assert.ok(!isCubeBlock(`minecraft:${t}`), t);
  }
  const o = cubeOffsets();
  assert.equal(o.length, 26);
  assert.ok(!o.some((p) => !p.x && !p.y && !p.z));
});

test("Holzfäller-Axt: logs and leaves", () => {
  for (const t of ["oak_log", "cherry_log", "mangrove_log", "pale_oak_log", "crimson_stem", "warped_stem"]) {
    assert.ok(isLog(`minecraft:${t}`), t);
  }
  for (const t of ["stripped_oak_log", "oak_planks", "oak_wood", "mushroom_stem", "bamboo_block", "oak_leaves"]) {
    assert.ok(!isLog(`minecraft:${t}`), t);
  }
  for (const t of ["oak_leaves", "azalea_leaves_flowered", "nether_wart_block", "leaves", "leaves2"]) {
    assert.ok(isLeaves(`minecraft:${t}`), t);
  }
  assert.ok(!isLeaves("minecraft:oak_log"));
});

function world(blocks) {
  return (p) => blocks[`${p.x},${p.y},${p.z}`] ?? "other";
}

test("Holzfäller-Axt: the whole tree, but only a tree", () => {
  // trunk 0..4, a branch going off diagonally at the top, leaves around it
  const tree = { "0,1,0": "log", "0,2,0": "log", "0,3,0": "log", "0,4,0": "log", "1,5,1": "log",
    "1,4,0": "leaves", "0,5,0": "leaves", "0,-1,0": "log" };
  const r = treeLogs({ x: 0, y: 0, z: 0 }, world(tree));
  assert.equal(r.leaves, true);
  assert.equal(r.logs.length, 6, "start + 5 logs; the log below the cut stays");
  assert.deepEqual(r.logs[0], { x: 0, y: 0, z: 0 });
  // a wall of logs without leaves is no tree
  const cabin = {};
  for (let x = 0; x < 5; x++) for (let y = 0; y < 3; y++) cabin[`${x},${y},0`] = "log";
  assert.equal(treeLogs({ x: 0, y: 0, z: 0 }, world(cabin)).leaves, false);
  // a giant "tree" stops at the limit
  const huge = { "0,201,0": "leaves" };
  for (let y = 1; y < 200; y++) huge[`0,${y},0`] = "log";
  assert.equal(treeLogs({ x: 0, y: 0, z: 0 }, world(huge), 20).logs.length, 20);
});

test("Ernte-Sichel: only ripe crops", () => {
  assert.ok(isRipe("minecraft:wheat", { growth: 7 }));
  assert.ok(!isRipe("minecraft:wheat", { growth: 6 }));
  assert.ok(isRipe("minecraft:nether_wart", { age: 3 }));
  assert.ok(!isRipe("minecraft:melon_stem", { growth: 7 }));
  assert.ok(!isRipe("minecraft:carrots", undefined));
  assert.equal(fieldOffsets().length, 9);
});

test("wear", () => {
  assert.deepEqual(wear(10, 100, 27), { damage: 37, broken: false });
  assert.deepEqual(wear(90, 100, 10), { damage: 100, broken: true });
  assert.deepEqual(wear(5, 100, -3), { damage: 5, broken: false });
});
