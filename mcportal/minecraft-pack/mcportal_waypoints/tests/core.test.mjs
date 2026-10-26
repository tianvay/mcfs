// node --test mcportal/minecraft-pack/mcportal_waypoints/tests/core.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  arrival, canUse, clearanceCells, formatList, keyOf, layout, parseCommand, provisionalName, ruinCells, structureKeys,
  validateName,
} from "../scripts/core.js";

test("names: valid, invalid, duplicate (case-insensitive), reserved", () => {
  const existing = new Set(["zuhause"]);
  assert.equal(validateName("Mine 2", existing), null);
  assert.equal(validateName("Bäckerei", existing), null);
  assert.match(validateName("ZUHAUSE", existing), /gibt es schon/);
  assert.equal(validateName("Zuhause", existing, "zuhause"), null, "renaming to itself with other case is ok");
  assert.match(validateName("", existing), /Namen/);
  assert.match(validateName("x".repeat(25), existing), /höchstens/);
  assert.match(validateName("a;b", existing), /Erlaubt/);
  assert.match(validateName('"@a', existing), /Erlaubt/);
  assert.match(validateName("list", existing), /Befehlswort/);
  assert.match(validateName("a  b", existing), /doppelten/);
});

test("command parsing", () => {
  assert.deepEqual(parseCommand(), { action: "help" });
  assert.deepEqual(parseCommand("list"), { action: "list" });
  assert.deepEqual(parseCommand("Zuhause"), { action: "teleport", name: "Zuhause" });
  assert.deepEqual(parseCommand("set", "Zuhause"), { action: "set", name: "Zuhause" });
  assert.deepEqual(parseCommand("delete", "Zuhause"), { action: "delete", name: "Zuhause" });
  assert.deepEqual(parseCommand("rename", "Wegpunkt 1", "Mine"), { action: "rename", name: "Wegpunkt 1", newName: "Mine" });
  assert.equal(parseCommand("set").action, "error");
  assert.equal(parseCommand("Mein", "Haus").action, "error", "unquoted name with space");
  assert.deepEqual(parseCommand("SET", "X"), { action: "set", name: "X" }, "verbs are case-insensitive");
  assert.deepEqual(parseCommand("public", "Dorf"), { action: "visibility", name: "Dorf", public: true });
  assert.deepEqual(parseCommand("private", "Dorf"), { action: "visibility", name: "Dorf", public: false });
  assert.equal(parseCommand("public").action, "error");
});

test("structure as wished: 3x3 stone bricks, diamond in the middle, 2-high walls + lantern on the corners", () => {
  const cells = layout();
  const at = (dx, dy, dz) => cells.find((c) => c.dx === dx && c.dy === dy && c.dz === dz)?.block;
  assert.equal(at(0, 0, 0), "minecraft:diamond_block");
  for (const [dx, dz] of [[0, 1], [1, 0], [0, -1], [-1, 0], [1, 1]]) assert.equal(at(dx, 0, dz), "minecraft:stone_bricks");
  for (const [dx, dz] of [[-1, -1], [-1, 1], [1, -1], [1, 1]]) {
    assert.equal(at(dx, 1, dz), "minecraft:stone_brick_wall");
    assert.equal(at(dx, 2, dz), "minecraft:stone_brick_wall");
    assert.equal(at(dx, 3, dz), "minecraft:lantern");
  }
  assert.equal(at(0, 1, 1), undefined, "edge middles stay open");
  assert.equal(cells.filter((c) => c.block === "minecraft:diamond_block").length, 1, "exactly one diamond block");
  assert.equal(cells.length, 9 + 12);
  assert.equal(clearanceCells().length, 36);
});

test("ruin: copper lanterns on the corners, coal block in the middle only after delete", () => {
  const del = ruinCells(true);
  assert.deepEqual(del[0], { dx: 0, dy: 0, dz: 0, from: "minecraft:diamond_block", to: "minecraft:coal_block" });
  assert.equal(del.filter((c) => c.to === "minecraft:copper_lantern" && c.dy === 3).length, 4);
  const lanterns = layout().filter((c) => c.block === "minecraft:lantern");
  for (const l of lanterns) assert.ok(del.some((c) => c.dx === l.dx && c.dy === l.dy && c.dz === l.dz), "every lantern is covered");
  const mined = ruinCells(false);
  assert.equal(mined.length, 4);
  assert.ok(!mined.some((c) => c.to === "minecraft:coal_block"), "no coal block when the diamond was mined");
});

test("arrival on top of the diamond; virtual waypoints exactly where set", () => {
  assert.deepEqual(arrival({ physical: true, x: 10, y: 64, z: -5 }), { x: 10.5, y: 65, z: -4.5 });
  assert.deepEqual(arrival({ physical: false, x: 1.2, y: 70, z: 3.4 }), { x: 1.2, y: 70, z: 3.4 });
  assert.equal(new Set(structureKeys({ dim: "minecraft:overworld", x: 0, y: 64, z: 0 })).size, 21);
});

test("private by default: owner, public, operators", () => {
  const priv = { name: "Dorf", owner: "Steve" }; // stored before the public flag existed
  assert.equal(canUse(priv, "Steve", false), true);
  assert.equal(canUse(priv, "Alex", false), false);
  assert.equal(canUse(priv, "Alex", true), true, "operators can use everything");
  assert.equal(canUse({ ...priv, public: true }, "Alex", false), true);
  assert.equal(canUse({ ...priv, public: "yes" }, "Alex", false), false, "only a real true makes it public");
});

test("list and provisional names", () => {
  assert.match(formatList([], "Steve", false)[0], /noch keine/);
  const wps = [
    { name: "Zuhause", dim: "minecraft:nether", x: 1.7, y: 64, z: -3.2, owner: "Steve", physical: true },
    { name: "Markt", dim: "minecraft:overworld", x: 0, y: 70, z: 0, owner: "Alex", physical: true, public: true },
    { name: "Geheim", dim: "minecraft:overworld", x: 0, y: 70, z: 0, owner: "Alex", physical: true },
  ];
  const lines = formatList(wps, "Steve", false);
  assert.equal(lines.length, 3, "Steve sees his own and the public one, not Alex' private one");
  const text = lines.join("|");
  assert.match(text, /Zuhause.*Nether 1 \/ 64 \/ -4.*Steve, privat/);
  assert.match(text, /Markt.*Alex, öffentlich/);
  assert.doesNotMatch(text, /Geheim/);
  assert.equal(formatList(wps, "Mama", true).length, 4, "operators see all");
  assert.equal(provisionalName(new Set(["wegpunkt 1"])), "Wegpunkt 2");
  assert.equal(keyOf("  ZuHause "), "zuhause");
});
