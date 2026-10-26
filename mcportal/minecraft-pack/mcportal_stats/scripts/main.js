// Minecraft Family Portal - block statistics (behavior pack, change M5)
//
// Counts blocks placed and broken per player and block type. Every FLUSH_TICKS
// the collected counts are written to the server log as ONE line:
//   [mcportal-stats] {"v":1,"players":{"Steve":{"placed":{"minecraft:stone":3},"broken":{}}}}
// The portal reads these lines from the journal and keeps the totals.
// Uses only the stable @minecraft/server API - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning, which
// lets these lines through but keeps info-level content noise out of the log.
import { system, world } from "@minecraft/server";

const FLUSH_TICKS = 20 * 20; // 20 s
const TAG = "[mcportal-stats]";

/** @type {Map<string, {placed: Record<string, number>, broken: Record<string, number>}>} */
let pending = new Map();

function bump(player, kind, typeId) {
  if (!player || !typeId) return;
  let entry = pending.get(player.name);
  if (!entry) {
    entry = { placed: {}, broken: {} };
    pending.set(player.name, entry);
  }
  entry[kind][typeId] = (entry[kind][typeId] ?? 0) + 1;
}

world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  bump(ev.player, "placed", ev.block.typeId);
});

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  bump(ev.player, "broken", ev.brokenBlockPermutation.type.id);
});

function flush() {
  if (pending.size === 0) return;
  const players = Object.fromEntries(pending);
  pending = new Map();
  console.warn(`${TAG} ${JSON.stringify({ v: 1, players })}`);
}

system.runInterval(flush, FLUSH_TICKS);

system.run(() => console.warn(`${TAG} {"v":1,"started":true}`));
