// node --test mcportal/minecraft-pack/mcportal_events/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  activeMinute, chooseType, chunkKey, decodeRegister, encodeRegister, estimateNext, intervalMinutes, isNaturalTop,
  isBed, isLeftover, isNight, isRushOre, lightningOffset, MIN_GAP, mobTag, newActive, newSchedule, nightStep, packSize,
  parseControl, participants, ranSeconds, ringOffset, scheduleMinute, secondsUntilDawn, secondsUntilNight,
  shouldDouble, TYPES, xpBonus, invasionLoot, invasionMob, invasionTargets, waveSize, ZOMBIES,
  beaconColumn, isGround, BOSSES, CRATER_RADIUS, craterDepth, craterGroundOk, isCover, isMeteorReplaceable, linePoints, planCrater, shootingStarPath, starLoot, distanceBand, treasureHint, treasureLoot, BOUNTY_LOOT, bossHint, bountyHunters, chooseBoss, healthBoostLevel,
} from "../scripts/core.js";

test("night events: wait for the night, run until dawn", () => {
  assert.ok(!isNight(12999) && isNight(13000) && isNight(22999) && !isNight(23000) && !isNight(0));
  assert.equal(secondsUntilNight(12000), 50);
  assert.equal(secondsUntilNight(23500), (24000 - 23500 + 13000) / 20);
  assert.equal(secondsUntilDawn(18000), 250);
  const a = newActive("blood_moon", "auto");
  assert.equal(a.phase, "waiting");
  assert.equal(nightStep(a, 6000), null);
  assert.equal(a.remaining, 350, "7000 ticks until nightfall");
  assert.deepEqual(activeMinute([a], ["Steve"]), [], "night events never end by minutes");
  assert.deepEqual(a.seen, {}, "waiting doesn't count as taking part");
  assert.equal(nightStep(a, 13020), "night");
  assert.equal(a.phase, "running");
  for (let m = 0; m < 6; m++) activeMinute([a], m < 2 ? ["Alex", "Steve"] : ["Steve"]);
  assert.equal(nightStep(a, 20000), null);
  assert.equal(nightStep(a, 23001), "dawn");
  assert.equal(ranSeconds(a), 360);
  assert.deepEqual(participants(a), ["Steve"], "Alex was there 2 of 6 minutes");
  const b = newActive("zombie_invasion", "console");
  assert.equal(nightStep(b, 15000), "night", "started at night: begins at once");
});

test("zombie invasion: waves, mobs, loot, targets", () => {
  assert.equal(waveSize(1, 0), 4);
  assert.equal(waveSize(3, 0), 6);
  assert.equal(waveSize(3, 28), 2, "cap of 30 alive");
  assert.equal(waveSize(3, 35), 0);
  const counts = {};
  let seq = 0;
  const steps = (n) => () => ((seq++ % n) + 0.5) / n;
  const r = steps(10);
  for (let i = 0; i < 10; i++) counts[invasionMob(r)] = (counts[invasionMob(r)] ?? 0) + 1;
  assert.ok(counts["minecraft:zombie"] >= 6);
  assert.deepEqual(invasionLoot(() => 0.99), [], "unlucky: nothing extra");
  const all = invasionLoot(() => 0);
  assert.deepEqual(all.map(([id]) => id), ["minecraft:iron_ingot", "minecraft:carrot", "minecraft:potato",
    "minecraft:emerald", "minecraft:experience_bottle", "minecraft:golden_apple"]);
  assert.ok(ZOMBIES.has("minecraft:husk") && !ZOMBIES.has("minecraft:skeleton"));
  const vill = (x, z) => [{ x, z }, { x: x + 4, z }, { x, z: z + 4 }];
  const t = invasionTargets([
    { x: 0, z: 0, villagers: vill(10, 10) },     // in a village
    { x: 30, z: 0, villagers: vill(10, 10) },    // same village
    { x: 500, z: 500, villagers: [] },           // alone in the wild
  ]);
  assert.equal(t.length, 2);
  assert.deepEqual([t[0].village, t[0].players], [true, 2]);
  assert.ok(Math.abs(t[0].x - 11.33) < 0.1);
  assert.deepEqual([t[1].village, t[1].x, t[1].players], [false, 500, 1]);
  assert.equal(invasionTargets([{ x: 0, z: 0, villagers: vill(0, 0).slice(0, 2) }])[0].village, false, "2 villagers are no village");
});

test("event mobs: tags and tidying up", () => {
  assert.equal(mobTag("blood_moon"), "mcfs_ev_blood_moon");
  assert.ok(isLeftover(["mcfs_ev", "mcfs_ev_blood_moon"], ["storm"]));
  assert.ok(!isLeftover(["mcfs_ev", "mcfs_ev_blood_moon"], ["blood_moon"]));
  assert.ok(!isLeftover(["some_other_tag"], []), "foreign mobs are never touched");
  assert.ok(isBed("minecraft:bed") && isBed("minecraft:red_bed") && !isBed("minecraft:bedrock"));
  for (let i = 0; i < 50; i++) {
    const p = ringOffset(0, 0, 20, 32, Math.random);
    const d = Math.hypot(p.x, p.z);
    assert.ok(d >= 19 && d <= 33, `ring ${d}`);
    const n = packSize(Math.random);
    assert.ok(n >= 3 && n <= 5);
  }
});

const always = (v) => () => v;

function minutesUntilStart(players, limit = 2000) {
  const s = newSchedule();
  s.lastStart = 0; // like right after an event
  for (let m = 1; m <= limit; m++) if (scheduleMinute(s, players, always(0))) return m;
  return null;
}

test("more players, more events; never more than one per hour", () => {
  assert.equal(intervalMinutes(0), Infinity);
  assert.equal(intervalMinutes(1), 180);
  assert.equal(intervalMinutes(3), 120);
  assert.equal(intervalMinutes(10), 60);
  assert.equal(intervalMinutes(25), 60, "more than max-players behaves like full");
  assert.equal(minutesUntilStart(1), 180);
  assert.equal(minutesUntilStart(3), 120);
  assert.equal(minutesUntilStart(10), 60);
  // even with a full credit the gap holds
  const s = newSchedule();
  s.lastStart = 0;
  s.credit = 5;
  let starts = 0;
  for (let m = 0; m < 600; m++) if (scheduleMinute(s, 10, always(0))) starts++;
  assert.ok(starts <= 10, `${starts} starts in 10 hours`);
});

test("the clock stands still without players and when switched off", () => {
  const s = newSchedule();
  for (let m = 0; m < 500; m++) assert.equal(scheduleMinute(s, 0, always(0)), false);
  assert.equal(s.clock, 0);
  s.auto = false;
  for (let m = 0; m < 500; m++) assert.equal(scheduleMinute(s, 10, always(0)), false);
  assert.equal(estimateNext(s, 3), null);
});

test("random delay of up to 10 minutes after the credit is full", () => {
  const s = newSchedule();
  s.lastStart = -1000;
  s.credit = 0.999;
  assert.equal(scheduleMinute(s, 1, always(0.99)), false); // credit full, delay 10 (this minute counts)
  assert.equal(s.delay, 9);
  let m = 0;
  while (!scheduleMinute(s, 1, always(0.99))) m++;
  assert.equal(m, 9);
});

test("choose: not the running one, not the last one, fallback if only the last is left", () => {
  const all = ["storm", "mining_rush", "lucky_day"];
  assert.equal(chooseType(all, [], "storm", always(0)), "mining_rush");
  assert.equal(chooseType(all, [newActive("mining_rush", "auto")], "storm", always(0)), "lucky_day");
  assert.equal(chooseType(["storm"], [], "storm", always(0)), "storm", "only one type implemented");
  assert.equal(chooseType(["storm"], [newActive("storm", "auto")], null, always(0)), null);
});

test("running events: time only passes with players, participation needs 5 minutes", () => {
  const a = newActive("storm", "auto");
  assert.equal(a.remaining, TYPES.storm.minutes * 60);
  assert.deepEqual(activeMinute([a], []), [], "paused without players");
  assert.equal(a.remaining, 2400);
  for (let m = 0; m < 39; m++) activeMinute([a], m < 4 ? ["Alex", "Steve"] : ["Steve"]);
  assert.deepEqual(activeMinute([a], ["Steve"]), [a], "ends after 40 online minutes");
  assert.deepEqual(participants(a), ["Steve"], "Alex was only there 4 minutes");
  // stopped after 2 minutes: everybody who was there the whole time took part
  const b = newActive("storm", "command");
  activeMinute([b], ["Alex"]);
  activeMinute([b], ["Alex", "Steve"]);
  assert.deepEqual(participants(b), ["Alex"]);
});

test("control commands from console and portal", () => {
  assert.deepEqual(parseControl("start storm"), { verb: "start", type: "storm" });
  assert.deepEqual(parseControl(" stop  mining_rush "), { verb: "stop", type: "mining_rush" });
  assert.deepEqual(parseControl("auto off"), { verb: "auto", on: false });
  assert.deepEqual(parseControl("state"), { verb: "state" });
  assert.deepEqual(parseControl("register o1,2;o-3,-4;e10,0"), { verb: "register", keys: ["o1,2", "o-3,-4", "e10,0"] });
  assert.deepEqual(parseControl("undo meteor-17"), { verb: "undo", id: "meteor-17" });
  const many = Array.from({ length: 201 }, (_, i) => `o${i},0`).join(";");
  for (const bad of ["register", "register o1,2;x", "register o1,2;;o3,4", `register ${many}`, "register o1,2 o3,4",
    "undo", "undo ../x", "undo meteor-1;start"]) {
    assert.equal(parseControl(bad), null, bad);
  }
  for (const bad of ["start", "start volcano", "auto maybe", "start storm now", "", "state x", "rm -rf"]) {
    assert.equal(parseControl(bad), null, bad);
  }
});

test("build register: chunk keys and storage in parts", () => {
  assert.equal(chunkKey("minecraft:overworld", 15, 16), "o0,1");
  assert.equal(chunkKey("minecraft:overworld", -1, -17), "o-1,-2");
  assert.equal(chunkKey("minecraft:the_end", 100, 0), "e6,0");
  const keys = new Set();
  for (let i = 0; i < 5000; i++) keys.add(`o${i},${-i}`);
  const parts = encodeRegister(keys);
  assert.ok(parts.length > 1, "split into several properties");
  for (const p of parts) assert.ok(p.length <= 30000);
  assert.deepEqual(decodeRegister(parts), keys);
  assert.deepEqual(decodeRegister([]), new Set());
});

test("lightning only on natural ground", () => {
  for (const ok of ["minecraft:grass_block", "minecraft:oak_leaves", "minecraft:sand", "minecraft:red_tulip", "minecraft:water"]) {
    assert.ok(isNaturalTop(ok), ok);
  }
  for (const no of ["minecraft:oak_planks", "minecraft:glass", "minecraft:lantern", "minecraft:stone_bricks",
    "minecraft:oak_log", "minecraft:chest", "minecraft:white_wool", "minecraft:farmland", "minecraft:torch"]) {
    assert.ok(!isNaturalTop(no), no);
  }
  for (let i = 0; i < 50; i++) {
    const p = lightningOffset(100, -50, Math.random);
    const d = Math.hypot(p.x - 100, p.z + 50);
    assert.ok(d >= 15 && d <= 65, `distance ${d}`);
  }
});

test("Mining Rush: which ores, no doubling of silk touch drops", () => {
  for (const ore of ["minecraft:iron_ore", "minecraft:deepslate_diamond_ore", "minecraft:nether_gold_ore",
    "minecraft:quartz_ore", "minecraft:lit_redstone_ore", "minecraft:copper_ore"]) assert.ok(isRushOre(ore), ore);
  for (const no of ["minecraft:ancient_debris", "minecraft:stone", "minecraft:raw_iron_block", "minecraft:diamond_block"]) {
    assert.ok(!isRushOre(no), no);
  }
  assert.ok(shouldDouble("minecraft:raw_iron", "minecraft:iron_ore"));
  assert.ok(shouldDouble("minecraft:diamond", "minecraft:deepslate_diamond_ore"));
  assert.ok(!shouldDouble("minecraft:iron_ore", "minecraft:iron_ore"), "silk touch");
  assert.ok(!shouldDouble("minecraft:redstone_ore", "minecraft:lit_redstone_ore"), "silk touch on glowing redstone");
  assert.ok(shouldDouble("minecraft:redstone", "minecraft:lit_redstone_ore"));
  assert.ok(shouldDouble("minecraft:redstone", "minecraft:deepslate_redstone_ore"));
  assert.ok(shouldDouble("minecraft:gold_nugget", "minecraft:nether_gold_ore"));
  assert.ok(shouldDouble("minecraft:lapis_lazuli", "minecraft:deepslate_lapis_ore"));
  assert.ok(!shouldDouble("minecraft:diamond", "minecraft:iron_ore"), "diamonds thrown next to an iron ore");
});

test("Glückstag: every gain once more, nothing for losses or the first look", () => {
  assert.deepEqual(xpBonus(undefined, 500), { bonus: 0, last: 500 }, "joining doesn't double what you have");
  assert.deepEqual(xpBonus(500, 507), { bonus: 7, last: 514 });
  assert.deepEqual(xpBonus(514, 514), { bonus: 0, last: 514 }, "our own bonus is not doubled again");
  assert.deepEqual(xpBonus(514, 300), { bonus: 0, last: 300 }, "enchanting / death");
});

test("every event type has a category for later meta achievements", () => {
  for (const [id, t] of Object.entries(TYPES)) assert.ok(["welt", "ressourcen", "mobs", "community"].includes(t.category), id);
});

test("Kopfgeld-Boss: health, hints, loot, hunters", () => {
  assert.equal(healthBoostLevel(20, 60), 9, "10 levels x 4 = +40");
  assert.equal(healthBoostLevel(20, 50), 7, "8 x 4 = +32 -> 52");
  assert.equal(healthBoostLevel(16, 50), 8);
  assert.equal(healthBoostLevel(20, 20), 0);
  for (const b of BOSSES) {
    assert.ok(b.base + (healthBoostLevel(b.base, b.health) + 1) * 4 >= b.health, b.id);
    if (b.id !== "susi") assert.ok(b.helmet, `${b.id} needs a helmet against the sun`);
    assert.ok(b.mob.startsWith("mcfs:boss_"), `${b.id} uses the pack's own big boss mob`);
  }
  assert.equal(chooseBoss(() => 0).id, "bernd");
  assert.equal(chooseBoss(() => 0.99).id, "susi");
  const at = { x: 0, z: 0 };
  assert.equal(bossHint("Bernd", at, { x: 0, z: -54 }), "Bernd: 54 Blöcke Richtung Norden");
  assert.equal(bossHint("Bernd", at, { x: 40, z: 0 }), "Bernd: 40 Blöcke Richtung Osten");
  assert.equal(bossHint("Bernd", at, { x: -30, z: -30 }), "Bernd: 42 Blöcke Richtung Nordwesten");
  assert.equal(bossHint("Bernd", at, { x: 20, z: 20 }), "Bernd: 28 Blöcke Richtung Südosten");
  assert.equal(bossHint("Bernd", at, { x: 3, z: 2 }), "Bernd ist ganz in der Nähe!");
  const me = { x: 0, y: 70, z: 0 };
  assert.equal(bossHint("Bernd", me, { x: 0, y: 76, z: -38 }), "Bernd: 38 Blöcke Richtung Norden, 6 Blöcke höher");
  assert.equal(bossHint("Bernd", me, { x: 0, y: 58, z: -38 }), "Bernd: 38 Blöcke Richtung Norden, 12 Blöcke tiefer");
  assert.equal(bossHint("Bernd", me, { x: 0, y: 72, z: -38 }), "Bernd: 38 Blöcke Richtung Norden", "small steps don't matter");
  const col = beaconColumn({ x: 5, y: 70, z: 5 });
  assert.equal(col.length, 12);
  assert.deepEqual([col[0].y, col.at(-1).y], [72, 94]);
  assert.ok(BOUNTY_LOOT.some(([id, n]) => id === "minecraft:diamond" && n === 3));
  assert.deepEqual(bountyHunters("Steve", ["Alex", "Steve"]), ["Alex", "Steve"]);
  assert.deepEqual(bountyHunters(null, ["Alex"]), ["Alex"]);
});

test("mobs only on real ground: no tree tops, no water", () => {
  assert.ok(isGround("minecraft:grass_block") && isGround("minecraft:sand") && isGround("minecraft:snow_layer"));
  assert.ok(!isGround("minecraft:oak_leaves") && !isGround("minecraft:water") && !isGround("minecraft:oak_planks"));
});

test("meteor crater: bowl shape, materials, 3-5 diamonds, only natural ground", () => {
  assert.equal(craterDepth(0), 3);
  assert.equal(craterDepth(2.5), 2);
  assert.equal(craterDepth(4.5), 1);
  assert.equal(craterDepth(5), 0);
  for (let i = 0; i < 30; i++) {
    const plan = planCrater(Math.random);
    const diamonds = plan.filter((c) => c.floor === "minecraft:diamond_ore");
    assert.ok(diamonds.length >= 3 && diamonds.length <= 5, `diamonds ${diamonds.length}`);
    assert.ok(diamonds.every((c) => c.depth >= 2), "diamonds in the deep middle");
    assert.ok(plan.every((c) => Math.hypot(c.dx, c.dz) <= CRATER_RADIUS + 1));
    assert.ok(plan.every((c) => !c.cluster || c.floor === "minecraft:amethyst_block"), "clusters only on amethyst");
    assert.ok(plan.some((c) => c.floor === "minecraft:netherrack"));
  }
  assert.ok(isMeteorReplaceable("minecraft:grass_block") && isMeteorReplaceable("minecraft:stone")
    && isMeteorReplaceable("minecraft:iron_ore") && isMeteorReplaceable("minecraft:short_grass") && isMeteorReplaceable("minecraft:air"));
  for (const no of ["minecraft:oak_planks", "minecraft:water", "minecraft:chest", "minecraft:torch", "minecraft:farmland"]) {
    assert.ok(!isMeteorReplaceable(no), no);
  }
  const flat = Array.from({ length: 10 }, () => ({ top: 70, typeId: "minecraft:grass_block" }));
  assert.ok(craterGroundOk(flat, 70));
  assert.ok(!craterGroundOk([...flat, { top: 70, typeId: "minecraft:oak_leaves" }], 70), "trees in the way");
  assert.ok(!craterGroundOk([...flat, { top: 75, typeId: "minecraft:stone" }], 70), "too steep");
  assert.ok(!craterGroundOk([...flat, { top: 70, typeId: "minecraft:water" }], 70), "lake");
});

test("cover on the ground: plants and snow layers, not the ground itself", () => {
  for (const c of ["minecraft:short_grass", "minecraft:tall_grass", "minecraft:poppy", "minecraft:snow_layer", "minecraft:fern",
    "minecraft:red_tulip", "minecraft:dead_bush"]) assert.ok(isCover(c), c);
  for (const g of ["minecraft:grass_block", "minecraft:sand", "minecraft:stone", "minecraft:snow", "minecraft:oak_leaves",
    "minecraft:water", "minecraft:packed_ice", "minecraft:iron_ore", "minecraft:cactus"]) assert.ok(!isCover(g), g);
});

test("shooting stars: loot table, streaks in the sky", () => {
  const seen = new Set();
  for (let i = 0; i < 400; i++) {
    const [id, n] = starLoot(Math.random);
    seen.add(id);
    assert.ok(n >= 1 && n <= 4);
  }
  for (const id of ["glowstone_dust", "experience_bottle", "lapis_lazuli", "diamond"]) assert.ok(seen.has(`minecraft:${id}`), id);
  assert.deepEqual(starLoot(() => 0.99), ["minecraft:netherite_scrap", 1], "rare");
  for (let i = 0; i < 20; i++) {
    const { from, to } = shootingStarPath(0, 70, 0, Math.random);
    assert.ok(from.y >= 115 && to.y < from.y, "high up and falling a bit");
    const len = Math.hypot(to.x - from.x, to.z - from.z);
    assert.ok(len >= 29 && len <= 51);
  }
  const pts = linePoints({ x: 0, y: 0, z: 0 }, { x: 10, y: 10, z: 0 }, 5);
  assert.equal(pts.length, 6);
  assert.deepEqual(pts[5], { x: 10, y: 10, z: 0 });
  assert.equal(TYPES.shooting_stars.night, true);
});

test("treasure hunt: loot, rough distance, warmer and colder", () => {
  for (let i = 0; i < 50; i++) {
    const loot = treasureLoot(Math.random);
    assert.equal(loot.length, 5);
    assert.ok(loot.find(([id, n]) => id === "minecraft:diamond" && n >= 2 && n <= 4));
  }
  assert.equal(distanceBand(5), "direkt hier – grabt nach!");
  assert.equal(distanceBand(250), "noch weit weg");
  const t = { x: 0, z: -300 };
  const first = treasureHint({ x: 0, z: 0 }, t);
  assert.equal(first.text, "Schatz: Richtung Norden, noch weit weg");
  const closer = treasureHint({ x: 0, z: -50 }, t, first.dist);
  assert.match(closer.text, /wärmer/);
  assert.match(closer.text, /noch weit weg/);
  const away = treasureHint({ x: 0, z: 20 }, t, closer.dist);
  assert.match(away.text, /kälter/);
  assert.doesNotMatch(treasureHint({ x: 0, z: -1 }, t, first.dist).text, /wärmer|kälter/, "a step doesn't count");
  assert.equal(treasureHint({ x: 3, z: -298 }, t, 20).text, "Schatz: direkt hier – grabt nach!");
  assert.equal(TYPES.treasure.category, "ressourcen");
});
