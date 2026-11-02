// Blueprint - pure logic without Minecraft imports (tested with node --test tests/core.test.mjs).
//
// Items:
//   mcfs:blueprint          empty blueprint (crafted: 4 diamonds in the corners, 4 emeralds on the edges, paper)
//   mcfs:blueprint_marking  corner 1 is set (dynamic properties c1x/c1y/c1z/c1dim)
//   mcfs:blueprint_filled   a saved area (dynamic property "sid" = structure id), placed once, then used up
//   mcfs:blueprint_copy     crafting result of filled blueprint + 4 diamonds + 4 emeralds (2 pieces); the script
//                           turns it into two filled blueprints of the consumed one
// A saved area is a world structure "mcfs:bp_<n>" plus a world dynamic property "mcfs_bp:<n>":
//   {v:1, sid, name, owner, size:{x,y,z}, facing, created, excluded:{typeId:count}, refs}
// refs = filled blueprints that exist; at 0 the structure is deleted.

export const BLANK_ID = "mcfs:blueprint";
export const MARKING_ID = "mcfs:blueprint_marking";
export const FILLED_ID = "mcfs:blueprint_filled";
export const COPY_ID = "mcfs:blueprint_copy";
export const PARTICLE_ID = "mcfs:blueprint_dot";
export const PROP_PREFIX = "mcfs_bp:";
export const COUNTER_PROP = "mcfs_bp_counter";
export const MAX_SIZE = 32;
export const NAME_MAX = 24;

const id = (typeId) => typeId.replace(/^minecraft:/, "");

// ---------- blocks that are not copied ----------

// ores keep the wall closed: they turn into the stone they sit in
const ORE_HOST = [
  [/^deepslate_.*_ore$|^lit_deepslate_redstone_ore$/, "minecraft:deepslate"],
  [/^(nether_gold_ore|quartz_ore)$/, "minecraft:netherrack"],
  [/^gilded_blackstone$/, "minecraft:blackstone"],
  [/^(coal|iron|copper|gold|redstone|lit_redstone|lapis|diamond|emerald)_ore$/, "minecraft:stone"],
];

// valuable, not obtainable, technical, or containers - become air
const DENY = new RegExp("^(" + [
  // valuable
  "netherite_block|ancient_debris|diamond_block|emerald_block|gold_block|iron_block|lapis_block",
  "raw_gold_block|raw_iron_block|raw_copper_block|coal_block|amethyst_block|budding_amethyst",
  "obsidian|crying_obsidian|sponge|wet_sponge|sea_lantern|glowstone",
  "beacon|conduit|lodestone|heavy_core|enchanting_table|anvil|chipped_anvil|damaged_anvil",
  "wither_skeleton_skull|dragon_head|dragon_egg",
  // copper as a full block (slabs, stairs, grates, bulbs, doors, trapdoors stay)
  "(waxed_)?((exposed|weathered|oxidized)_)?(copper|cut_copper|chiseled_copper)(_block)?",
  // not obtainable / technical
  "bedrock|reinforced_deepslate|end_portal_frame|end_portal|portal|end_gateway",
  "mob_spawner|trial_spawner|vault|suspicious_sand|suspicious_gravel",
  "command_block|repeating_command_block|chain_command_block|structure_block|structure_void|jigsaw",
  "barrier|light_block(_\\d+)?|allow|deny|border_block|invisible_bedrock",
  // storage containers (their contents would be copied)
  "chest|trapped_chest|ender_chest|barrel|.*shulker_box|.*copper_chest",
  // hold items, but a script can't see their contents - so it can't be checked that they arrive empty
  "crafter|chiseled_bookshelf|decorated_pot|frame|glow_frame|campfire|soul_campfire|.*_shelf",
].join("|") + ")$");

// containers that redstone builds need: copied, but always empty. Only blocks with a script inventory, so the
// engine test can prove it (a structure copies contents otherwise - measured). volume.saveArea also empties any
// other block that turns out to have an inventory.
const EMPTIED = new RegExp("^(hopper|dropper|dispenser|furnace|lit_furnace|blast_furnace|lit_blast_furnace|" +
  "smoker|lit_smoker|brewing_stand|lectern|jukebox)$");

/**
 * What happens to a block when it is saved.
 * @returns {{action:"keep"}|{action:"empty"}|{action:"replace", to:string}}
 *   replace: the block is not copied, "to" takes its place (air or the stone around an ore)
 */
export function blockRule(typeId) {
  if (typeId.startsWith("mcfs:")) return { action: "replace", to: "minecraft:air" }; // our own blocks
  if (!typeId.startsWith("minecraft:")) return { action: "keep" };
  const n = id(typeId);
  for (const [re, host] of ORE_HOST) if (re.test(n)) return { action: "replace", to: host };
  if (DENY.test(n)) return { action: "replace", to: "minecraft:air" };
  if (EMPTIED.test(n)) return { action: "empty" };
  return { action: "keep" };
}

// blocks a placed blueprint may overwrite (like the waypoint)
export const REPLACEABLE = new Set([
  "minecraft:air", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern",
  "minecraft:snow_layer", "minecraft:deadbush", "minecraft:dandelion", "minecraft:poppy", "minecraft:blue_orchid",
  "minecraft:allium", "minecraft:azure_bluet", "minecraft:red_tulip", "minecraft:orange_tulip",
  "minecraft:white_tulip", "minecraft:pink_tulip", "minecraft:oxeye_daisy", "minecraft:cornflower",
  "minecraft:lily_of_the_valley", "minecraft:short_dry_grass", "minecraft:tall_dry_grass", "minecraft:bush",
  "minecraft:leaf_litter", "minecraft:wildflowers", "minecraft:pink_petals", "minecraft:vine",
  "minecraft:glow_lichen", "minecraft:brown_mushroom", "minecraft:red_mushroom", "minecraft:water",
  "minecraft:flowing_water",
]);

// ---------- geometry ----------
// Facing index clockwise seen from above: 0 north (-z), 1 east (+x), 2 south (+z), 3 west (-x).
// The engine's Rotate90 turns clockwise: (x, z) in a box of size (sx, sz) -> (sz-1-z, x) (measured on the
// test server, see docs/14-blaupause.md).

export const DIRS = [{ x: 0, z: -1 }, { x: 1, z: 0 }, { x: 0, z: 1 }, { x: -1, z: 0 }];
export const ROTATIONS = ["None", "Rotate90", "Rotate180", "Rotate270"];
const FACING_NAMES = ["Norden", "Osten", "Süden", "Westen"];

/** player yaw (0 = south, 90 = west, ±180 = north, -90 = east) -> facing index */
export function facingOf(yaw) {
  const q = ((Math.round(yaw / 90) % 4) + 4) % 4; // 0 S, 1 W, 2 N, 3 E
  return (q + 2) % 4;
}

export const facingName = (f) => FACING_NAMES[f];

/** box between two corners (inclusive) */
export function boxOf(a, b) {
  const min = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), z: Math.min(a.z, b.z) };
  const size = { x: Math.abs(a.x - b.x) + 1, y: Math.abs(a.y - b.y) + 1, z: Math.abs(a.z - b.z) + 1 };
  return { min, size };
}

/** @returns {string|null} why this area can't be saved */
export function sizeProblem(size) {
  if (size.x > MAX_SIZE || size.y > MAX_SIZE || size.z > MAX_SIZE) {
    return `Zu groß: ${sizeText(size)} – höchstens ${MAX_SIZE} × ${MAX_SIZE} × ${MAX_SIZE} Blöcke.`;
  }
  return null;
}

export const sizeText = (s) => `${s.x} × ${s.y} × ${s.z}`;

/** one clockwise quarter turn of a point inside a box of the given size */
function turn(p, size) {
  return { p: { x: size.z - 1 - p.z, y: p.y, z: p.x }, size: { x: size.z, y: size.y, z: size.x } };
}

/**
 * The corner the player sees "near, left, bottom" when looking in direction `facing` - in box coordinates.
 * That corner is the anchor: it lands on the block the player clicks when placing.
 */
export function anchorOf(size, facing) {
  const d = DIRS[facing];
  const left = { x: d.z, z: -d.x };
  const pick = (dir, s) => (dir > 0 ? s - 1 : 0);
  return {
    x: d.x !== 0 ? (d.x > 0 ? 0 : size.x - 1) : pick(left.x, size.x),
    y: 0,
    z: d.z !== 0 ? (d.z > 0 ? 0 : size.z - 1) : pick(left.z, size.z),
  };
}

/**
 * Where a saved area goes when placed.
 * @param size    saved size
 * @param saved   facing when it was saved
 * @param facing  facing of the player now
 * @param target  block the anchor lands on
 * @returns {{rotation:string, min:{x,y,z}, size:{x,y,z}}} rotation for structureManager.place, box in the world
 */
export function placement(size, saved, facing, target) {
  const k = (((facing - saved) % 4) + 4) % 4;
  let p = anchorOf(size, saved);
  let s = size;
  for (let i = 0; i < k; i++) ({ p, size: s } = turn(p, s));
  return { rotation: ROTATIONS[k], min: { x: target.x - p.x, y: target.y, z: target.z - p.z }, size: s };
}

/** where a block of the saved area (box coordinates) ends up in the world after placement() */
export function placedCell(size, k, min, cell) {
  let p = cell;
  let s = size;
  for (let i = 0; i < k; i++) ({ p, size: s } = turn(p, s));
  return { x: min.x + p.x, y: min.y + p.y, z: min.z + p.z };
}

/** the 12 edges of a box as points, for the outline particles (block corners, not block centres) */
export function outline(min, size, step = 1) {
  const pts = [];
  const max = { x: min.x + size.x, y: min.y + size.y, z: min.z + size.z };
  const along = (from, axis, len) => {
    for (let t = 0; t <= len; t += step) pts.push({ ...from, [axis]: from[axis] + t });
  };
  for (const y of [min.y, max.y]) for (const z of [min.z, max.z]) along({ x: min.x, y, z }, "x", size.x);
  for (const y of [min.y, max.y]) for (const x of [min.x, max.x]) along({ x, y, z: min.z }, "z", size.z);
  for (const x of [min.x, max.x]) for (const z of [min.z, max.z]) along({ x, y: min.y, z }, "y", size.y);
  return pts;
}

export const inBox = (p, min, size) => p.x >= min.x && p.x < min.x + size.x && p.y >= min.y
  && p.y < min.y + size.y && p.z >= min.z && p.z < min.z + size.z;

// ---------- names and texts ----------

export function cleanName(name, fallback) {
  const n = String(name ?? "").replace(/§./g, "").replace(/\s+/g, " ").trim().slice(0, NAME_MAX);
  return n || fallback;
}

/** "4 × Diamantblock, 2 × Eisenerz" - ids without namespace, most first */
export function excludedText(excluded) {
  const parts = Object.entries(excluded).sort((a, b) => b[1] - a[1])
    .map(([t, n]) => `${n} × ${id(t).replace(/_/g, " ")}`);
  if (parts.length > 6) return parts.slice(0, 6).join(", ") + ` und ${parts.length - 6} weitere`;
  return parts.join(", ");
}

export function lore(rec) {
  return [`§7${sizeText(rec.size)} Blöcke`, `§7von ${rec.owner}`, "§7Einmal einsetzbar"];
}

// ---------- copies: which consumed blueprint did the crafting use? ----------

/**
 * Bookkeeping per player: counts of filled blueprints (by structure id) between two inventory scans.
 * A blueprint that disappears goes onto the "gone" list (crafting grid, dropped, ...); one that comes back
 * is taken off again. A copy item takes the newest gone entry.
 */
export function updateGone(gone, before, now, tick) {
  for (const [sid, n] of before) {
    for (let i = now.get(sid) ?? 0; i < n; i++) gone.push({ sid, tick });
  }
  for (const [sid, n] of now) {
    for (let i = before.get(sid) ?? 0; i < n; i++) {
      const at = gone.findLastIndex((g) => g.sid === sid);
      if (at >= 0) gone.splice(at, 1);
    }
  }
}

export function pruneGone(gone, tick, maxAge) {
  while (gone.length && tick - gone[0].tick > maxAge) gone.shift();
}
