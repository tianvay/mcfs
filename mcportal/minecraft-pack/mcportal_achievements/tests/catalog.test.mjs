// node --test mcportal/minecraft-pack/mcportal_achievements/tests/catalog.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  armorCounters, CATALOG, deathCounters, evaluate, EVENT_WAVES, eventCounters, flatCatalog, invasionKill, isDiamondOre, isOre,
  isSapling,
  killCounters,
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

test("events: 5/20/50 taken part, every wave-1 event once, the special ones", () => {
  let c = {};
  const take = (type) => { c = { ...c, ...eventCounters(c, type) }; };
  for (let i = 0; i < 4; i++) take("storm");
  assert.equal(c.events, 4);
  assert.equal(c.seen_wave1, 1, "the same event four times is still one kind");
  take("mining_rush");
  assert.deepEqual(evaluate(c, {}).map((a) => a.name), ["Mittendrin statt nur dabei"]);
  take("lucky_day");
  assert.equal(c.seen_wave1, 3);
  assert.ok(evaluate(c, {}).map((a) => a.name).includes("Hab ich alles schon gesehen"));
  for (let i = 0; i < 44; i++) take("storm");
  assert.ok(evaluate(c, {}).map((a) => a.name).includes("Partylöwe"));
  assert.deepEqual(eventCounters({}, "meteor"), { events: 1, ev_meteor: 1 }, "types of later waves don't touch wave 1");
  const first = (counters) => evaluate(counters, {}).map((a) => a.name);
  assert.deepEqual(first({ rush_ores: 100 }), ["Goldrausch"]);
  assert.deepEqual(first({ lucky_xp: 1000 }), ["Glückspilz"]);
  assert.deepEqual(first({ lightning_survived: 1 }), ["Geistesblitz"]);
  assert.equal(CATALOG.find((a) => a.id === "seen_wave1").tiers[0].at, EVENT_WAVES[1].length);
});

test("wave 2, night dangers and together", () => {
  let c = {};
  const take = (type, n = 1) => { c = { ...c, ...eventCounters(c, type, n) }; };
  take("storm");
  take("blood_moon");
  take("zombie_invasion");
  assert.equal(c.seen_wave1, 1);
  assert.equal(c.seen_wave2, 2);
  take("bounty", 3);
  assert.equal(c.seen_wave2, 3);
  const names = evaluate(c, {}).map((a) => a.name);
  assert.ok(names.includes("Hab ich alles schon gesehen II"));
  assert.ok(names.includes("Gemeinsam stark"), "the bounty had 3 hunters");
  assert.ok(!names.includes("Hab ich alles schon gesehen"), "wave 1 is not complete");
  assert.equal(CATALOG.find((a) => a.id === "seen_wave2").tiers[0].at, EVENT_WAVES[2].length);
  // invasion: the best single night counts, not the sum
  let k = {};
  for (let i = 0; i < 15; i++) k = { ...k, ...invasionKill(k) };
  k.inv_now = 0; // next night
  for (let i = 0; i < 12; i++) k = { ...k, ...invasionKill(k) };
  assert.deepEqual([k.inv_now, k.invasion_best], [12, 15]);
  assert.deepEqual(evaluate(k, {}), []);
  for (let i = 0; i < 8; i++) k = { ...k, ...invasionKill(k) };
  assert.deepEqual(evaluate(k, {}).map((a) => a.name), ["Hirn-Rissig"]);
  const first = (counters) => evaluate(counters, {}).map((a) => a.name);
  assert.deepEqual(first({ blood_wolves: 10 }), ["Wer hat Angst vorm bösen Wolf?"]);
  assert.deepEqual(first({ bounties: 1 }), ["Kopfgeldjäger"]);
});
