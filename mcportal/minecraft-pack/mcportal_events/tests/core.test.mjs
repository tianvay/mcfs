// node --test mcportal/minecraft-pack/mcportal_events/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  activeMinute, chooseType, chunkKey, decodeRegister, encodeRegister, estimateNext, intervalMinutes, isNaturalTop,
  lightningOffset, MIN_GAP, newActive, newSchedule, parseControl, participants, scheduleMinute, TYPES,
} from "../scripts/core.js";

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
  for (const bad of ["start", "start meteor", "auto maybe", "start storm now", "", "state x", "rm -rf"]) {
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
