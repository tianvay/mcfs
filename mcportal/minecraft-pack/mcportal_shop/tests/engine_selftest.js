// Engine check for the test server only (world-pack.sh leaves tests/ out):
// copy this file into scripts/ of a COPY of the pack and make it the manifest entry. It loads main.js, builds small
// scenes in chunk 0 of a fresh world and logs what the tools did:
//   items   the four shop items exist, with durability where expected
//   tags    the block tags the item definitions rely on
//   cube    3x3x3 of stone with a diamond ore, a cobblestone and a chest in it -> 24 broken (23 cobblestone, 1 diamond), chest + cobble stay
//   tree    trunk of 5 with leaves -> 4 felled after the cut; logs without leaves -> 0
//   field   3 ripe + 1 young wheat -> 3 harvested, all four are wheat again
//   account bookings through the same script events the events pack and the portal use
import { ItemStack, system, world } from "@minecraft/server";
import "./main.js";
import { ITEMS } from "./core.js";
import { breakCube, fellTree, harvest } from "./work.js";

const out = (o) => console.warn("[mcportal-shop] " + JSON.stringify({ v: 1, event: "test", ...o }));

function drops(dim) {
  const n = {};
  for (const e of dim.getEntities({ type: "minecraft:item" })) {
    const s = e.getComponent("minecraft:item")?.itemStack;
    if (s) n[s.typeId.replace("minecraft:", "")] = (n[s.typeId.replace("minecraft:", "")] ?? 0) + s.amount;
    e.remove();
  }
  return n;
}

system.run(() => {
  const dim = world.getDimension("overworld");
  dim.runCommand("tickingarea add 0 -64 0 15 255 15 selftest");
  let tries = 0;
  const h = system.runInterval(() => {
    if (!dim.isChunkLoaded({ x: 8, y: 0, z: 8 }) && ++tries < 30) return;
    system.clearRun(h);
    const set = (x, y, z, t) => dim.setBlockType({ x, y, z }, t);
    const id = (x, y, z) => dim.getBlock({ x, y, z })?.typeId;

    const items = {};
    for (const it of ITEMS) {
      try {
        const s = new ItemStack(it.id, 1);
        items[it.id] = { max: s.getComponent("minecraft:durability")?.maxDurability ?? null, tags: s.getTags() };
      } catch (e) { items[it.id] = String(e); }
    }
    out({ items });

    for (let x = 0; x < 16; x++) for (let z = 0; z < 16; z++) set(x, 199, z, "minecraft:glass");
    set(1, 200, 1, "minecraft:stone"); set(2, 200, 1, "minecraft:oak_log"); set(3, 200, 1, "minecraft:diamond_ore");
    out({ tags: {
      stone: dim.getBlock({ x: 1, y: 200, z: 1 }).hasTag("minecraft:is_pickaxe_item_destructible"),
      log: dim.getBlock({ x: 2, y: 200, z: 1 }).hasTag("minecraft:is_axe_item_destructible"),
      diamond_ore: dim.getBlock({ x: 3, y: 200, z: 1 }).getTags(),
    } });
    for (const x of [1, 2, 3]) set(x, 200, 1, "minecraft:air");

    // cube
    for (let x = 4; x <= 6; x++) for (let y = 200; y <= 202; y++) for (let z = 4; z <= 6; z++) set(x, y, z, "minecraft:stone");
    set(4, 200, 4, "minecraft:diamond_ore"); set(6, 202, 6, "minecraft:cobblestone"); set(6, 200, 4, "minecraft:chest");
    set(5, 201, 5, "minecraft:air");
    drops(dim);
    const cube = breakCube(dim, { x: 5, y: 201, z: 5 });

    system.runTimeout(() => {
      out({ cube, drops: drops(dim), chest: id(6, 200, 4), cobble: id(6, 202, 6), stone_left: id(4, 201, 4) });

      // tree and "cabin"
      for (let y = 200; y <= 204; y++) set(10, y, 10, "minecraft:oak_log");
      set(11, 204, 10, "minecraft:oak_leaves");
      for (let x = 12; x <= 15; x++) set(x, 200, 12, "minecraft:oak_log");
      set(10, 200, 10, "minecraft:air"); set(12, 200, 12, "minecraft:air");
      const tree = fellTree(dim, { x: 10, y: 200, z: 10 });
      const cabin = fellTree(dim, { x: 12, y: 200, z: 12 });

      // field
      for (let x = 1; x <= 3; x++) for (let z = 8; z <= 10; z++) set(x, 199, z, "minecraft:farmland");
      const wheat = (x, z, growth) => {
        set(x, 200, z, "minecraft:wheat");
        const b = dim.getBlock({ x, y: 200, z });
        b.setPermutation(b.permutation.withState("growth", growth));
      };
      wheat(1, 8, 7); wheat(2, 9, 7); wheat(3, 10, 7); wheat(1, 10, 3);
      system.runTimeout(() => {
        out({ tree, cabin, tree_drops: drops(dim), top: id(10, 204, 10), cabin_left: id(13, 200, 12) });
        const field = harvest(dim, { x: 2, y: 200, z: 9 });
        system.runTimeout(() => {
          const g = (x, z) => `${id(x, 200, z)}:${dim.getBlock({ x, y: 200, z })?.permutation.getState("growth")}`;
          out({ field, field_drops: drops(dim), after: [g(1, 8), g(2, 9), g(3, 10), g(1, 10)] });

          // account: the lines "booking" follow in the log
          system.sendScriptEvent("mcfs:event_news", JSON.stringify({ event: "ended", type: "storm", participants: ["Steve", "Alex"] }));
          system.sendScriptEvent("mcfs:event_news", JSON.stringify({ event: "star", player: "Steve" }));
          system.sendScriptEvent("mcfs:shop", "seed 20 Steve");
          system.sendScriptEvent("mcfs:shop", "seed 20 Steve");
          system.sendScriptEvent("mcfs:shop", "grant -100 Alex");
          system.sendScriptEvent("mcfs:shop", "grant 5 @a");
          dim.runCommand("scriptevent mcfs:shop balances");
        }, 10);
      }, 10);
    }, 10);
  }, 10);
});
