// node --test mcportal/minecraft-pack/mcportal_achievements/tests/catalog.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  armorCounters, CATALOG, deathCounters, evaluate, flatCatalog, isDiamondOre, isOre, isSapling, killCounters,
} from "../scripts/catalog.js";

test("catalog is consistent", () => {
  const ids = new Set();
  for (const a of CATALOG) {
    assert.ok(!ids.has(a.id), `duplicate id ${a.id}`);
    ids.add(a.id);
    assert.ok(a.tiers.length > 0);
    for (let i = 1; i < a.tiers.length; i++) assert.ok(a.tiers[i].at > a.tiers[i - 1].at, `${a.id} tiers ascending`);
    for (const t of a.tiers) assert.ok(t.name && t.desc && !t.name.includes("§"));
  }
  const names = flatCatalog().map((e) => e.name);
  assert.equal(new Set(names).size, names.length, "achievement names are unique");
});

test("tiers unlock one after another, each only once", () => {
  const unlocked = {};
  assert.deepEqual(evaluate({ ores: 99 }, unlocked), []);
  assert.deepEqual(evaluate({ ores: 100 }, unlocked).map((a) => a.name), ["Kumpel"]);
  assert.deepEqual(evaluate({ ores: 500 }, unlocked), []);
  // a big jump unlocks all tiers in between, in order
  assert.deepEqual(evaluate({ ores: 20000 }, unlocked).map((a) => [a.name, a.tier]), [["Bergarbeiter", 2], ["Glück auf!", 3]]);
  assert.deepEqual(evaluate({ ores: 99999 }, unlocked), []);
  assert.equal(unlocked.ores, 3);
});

test("the wished-for achievements exist with the right thresholds", () => {
  const first = (counters) => evaluate(counters, {}).map((a) => a.name);
  assert.ok(first({ ores: 1000 }).includes("Bergarbeiter"));
  assert.deepEqual(first({ diamonds: 1 }), ["Diamant!"]);
  assert.deepEqual(first({ armor_diamond: 1 }), ["Strahlend"]);
  assert.ok(first({ saplings: 100 }).includes("Förster"));
  assert.deepEqual(first({ deaths: 1 }), ["Anfängerfehler"]);
});

test("block classification", () => {
  for (const ore of ["minecraft:coal_ore", "minecraft:deepslate_iron_ore", "minecraft:nether_quartz_ore",
    "minecraft:lit_redstone_ore", "minecraft:ancient_debris"]) assert.ok(isOre(ore), ore);
  assert.ok(!isOre("minecraft:stone") && !isOre("minecraft:diamond_block"));
  assert.ok(isDiamondOre("minecraft:deepslate_diamond_ore") && !isDiamondOre("minecraft:diamond_block"));
  assert.ok(isSapling("minecraft:cherry_sapling") && isSapling("minecraft:mangrove_propagule"));
  assert.ok(!isSapling("minecraft:oak_leaves"));
});

test("kills and deaths map to counters", () => {
  assert.deepEqual(killCounters("minecraft:husk"), ["kills", "kills_zombie"]);
  assert.deepEqual(killCounters("minecraft:creeper"), ["kills", "kills_creeper"]);
  assert.deepEqual(killCounters("minecraft:cow"), [], "animals are not monsters");
  assert.deepEqual(killCounters("minecraft:wither"), ["kills", "kill_wither"]);
  assert.deepEqual(deathCounters("entityExplosion", "minecraft:creeper"), ["deaths", "death_creeper"]);
  assert.deepEqual(deathCounters("lava", undefined), ["deaths", "death_lava"]);
  assert.deepEqual(deathCounters("fall", undefined), ["deaths", "death_fall"]);
});

test("armor sets need all four pieces", () => {
  const dia = ["minecraft:diamond_helmet", "minecraft:diamond_chestplate", "minecraft:diamond_leggings", "minecraft:diamond_boots"];
  assert.deepEqual(armorCounters(dia), ["armor_diamond"]);
  assert.deepEqual(armorCounters([...dia.slice(0, 3), "minecraft:iron_boots"]), []);
  assert.deepEqual(armorCounters([undefined, undefined, undefined, undefined]), []);
  assert.deepEqual(armorCounters(dia.map((id) => id.replace("diamond", "netherite"))), ["armor_netherite"]);
});
