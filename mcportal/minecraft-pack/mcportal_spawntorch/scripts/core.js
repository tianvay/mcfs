// Spawn torch - rules without @minecraft/server, tested with node --test (tests/core.test.mjs).
//
// A block gets the red veil when a hostile mob could spawn ON it at night (Bedrock rules, minecraft wiki "Spawn"):
//   1. the block itself has a full, solid top (no glass, leaves, bottom slab, upright stairs, carpet ...),
//   2. the block above is free for the mob's feet (air, grass, flowers, thin snow ...) - one block is enough,
//      spiders fit; no rail or redstone part in the block above that either,
//   3. no block light reaches the space above (Bedrock: block light 0 and sky light below 7 - at night the
//      sky light in the open is 4, so only block light decides),
//   4. not in a biome without monsters (mushroom fields, deep dark).
// The rules lean towards red: a block we don't know counts as "mobs can spawn here".

export const ITEM_ID = "mcfs:spawn_torch";
export const PARTICLE_ID = "mcfs:spawn_veil";
export const RADIUS = 16; // ~1 chunk around the player
export const BELOW = 10; // blocks below the feet that are still scanned
export const ABOVE = 6; // blocks above the feet

const id = (typeId) => typeId.replace(/^minecraft:/, "");

// floor blocks mobs can't stand on (no full solid top, transparent or special)
const NO_FLOOR = new RegExp(
  "^(air|water|flowing_water|lava|flowing_lava|barrier|structure_void|light_block.*|invisible_bedrock|" +
    "mob_spawner|trial_spawner|vault|beacon|conduit|cobweb|web|ladder|vine|scaffolding|iron_bars|chain|" +
    "end_rod|lightning_rod|hopper|cauldron|brewing_stand|enchanting_table|lectern|daylight_detector.*|" +
    "unpowered_repeater|powered_repeater|unpowered_comparator|powered_comparator|redstone_wire|lever|" +
    "tripwire|tripwire_hook|bell|campfire|soul_campfire|grindstone|stonecutter_block|composter|" +
    "magma|dragon_egg|cactus|bamboo|kelp|seagrass|sea_pickle|pointed_dripstone|amethyst_cluster|" +
    "chorus_plant|chorus_flower|snow_layer|cake|flower_pot|decorated_pot|bed|mangrove_roots)$|" +
    "glass|_leaves$|^leaves2?$|carpet$|pressure_plate$|button$|rail$|fence|_wall$|door$|" +
    "sign$|banner$|torch$|lantern$|chest$|candle|head$|skull|anvil$|_bud$|coral(?!_block)|_pane$|grate$",
);

// blocks a mob's feet can be in (the block above the floor)
const OPEN = new RegExp(
  "^(air|short_grass|tall_grass|fern|large_fern|deadbush|dead_bush|short_dry_grass|tall_dry_grass|" +
    "bush|firefly_bush|snow_layer|vine|red_mushroom|brown_mushroom|sweet_berry_bush|pink_petals|wildflowers|" +
    "leaf_litter|cactus_flower|crimson_roots|warped_roots|nether_sprouts|structure_void|" +
    "dandelion|poppy|blue_orchid|allium|azure_bluet|oxeye_daisy|cornflower|lily_of_the_valley|wither_rose|" +
    "torchflower|sunflower|lilac|rose_bush|peony|.*_tulip|.*_flower|.*_sapling|.*_propagule)$",
);

/** typeId of the floor + its block states -> can a mob stand on its top? */
export function isSpawnFloor(typeId, states = {}) {
  const name = id(typeId);
  if (NO_FLOOR.test(name)) return false;
  if (name.endsWith("_stairs")) return states.upside_down_bit === true; // upside-down stairs have a full top
  if (name.endsWith("_slab") || /^stone_block_slab\d$/.test(name)) {
    if (name.includes("double")) return true; // oak_double_slab, double_stone_block_slab
    // only the upper half of a slab has its top at the block's top
    return states["minecraft:vertical_half"] === "top" || states.top_slot_bit === true;
  }
  return true;
}

// rails and redstone parts stop spawning in the feet block and in the block above it
const NO_HEAD = /rail$|redstone|repeater|comparator|^lever$|button$|pressure_plate$|tripwire|observer|daylight_detector|^target$|sculk_sensor/;

/** typeId of a block above the floor -> room for a mob's feet? */
export function isOpen(typeId) {
  return OPEN.test(id(typeId));
}

/** light a block gives off (0 = none); unknown blocks give none */
export function lightEmission(typeId, states = {}) {
  const name = id(typeId);
  const m = /^light_block_(\d+)$/.exec(name);
  if (m) return Number(m[1]);
  if (/campfire$/.test(name)) return states.extinguished ? 0 : name.startsWith("soul") ? 10 : 15;
  if (/^(soul_torch|soul_lantern|soul_fire|crying_obsidian)$/.test(name)) return 10;
  if (/^(unlit_redstone_torch|redstone_torch)$/.test(name)) return name.startsWith("unlit") ? 0 : 7;
  if (/torch$/.test(name)) return 14; // torch, copper torch
  if (/lantern$/.test(name)) return 15; // lantern, copper lanterns
  if (/froglight$/.test(name)) return 15;
  if (/^(lava|flowing_lava|fire|glowstone|sea_lantern|shroomlight|lit_pumpkin|beacon|conduit|lit_redstone_lamp|end_gateway|end_portal)$/.test(name)) return 15;
  if (/^(end_rod|cave_vines_body_with_berries|cave_vines_head_with_berries)$/.test(name)) return 14;
  if (/^lit_(furnace|blast_furnace|smoker)$/.test(name)) return 13;
  if (name === "portal") return 11;
  if (/^lit_(deepslate_)?redstone_ore$/.test(name)) return 9;
  if (/^(glow_lichen|enchanting_table|ender_chest)$/.test(name)) return 7;
  if (name === "sculk_catalyst") return 6;
  if (name === "amethyst_cluster") return 5;
  if (name === "large_amethyst_bud") return 4;
  if (name === "magma") return 3;
  return 0;
}

/** strongest block light that reaches pos from the given sources ({x,y,z,level}), ignoring walls */
export function estimateBlockLight(pos, sources) {
  let best = 0;
  for (const s of sources) {
    const l = s.level - Math.abs(s.x - pos.x) - Math.abs(s.y - pos.y) - Math.abs(s.z - pos.z);
    if (l > best) best = l;
  }
  return best;
}

/**
 * Is there no block light at the space above a floor?
 * The server only reports total = max(block light, sky light at the current time) and the sky light.
 *   total > sky  -> block light = total > 0, lit
 *   total == 0   -> dark
 *   else (block light hidden behind the sky, e.g. by day in the open) -> estimate() from nearby light sources
 */
export function isDark(total, sky, estimate) {
  if (total > sky) return false;
  if (total === 0) return true;
  return estimate() <= 0;
}

/** biomes without hostile mobs */
export function isPeacefulBiome(biomeId) {
  return /mushroom|deep_dark/.test(biomeId ?? "");
}

/** text for the action bar while the torch is held */
export function statusText(dark, scanning) {
  if (scanning) return "§7Spawnfackel sucht dunkle Stellen ...";
  if (dark === 0) return "§aAlles hell genug - hier spawnen keine Monster";
  return `§c${dark} §fdunkle Stelle${dark === 1 ? "" : "n"} - dort fehlt Licht`;
}

/**
 * One column of blocks, top to bottom ([{typeId, states}], index 0 = highest block) ->
 * indexes of the free blocks a mob could spawn in (floor below is solid, the block is open, no rail/redstone above).
 */
export function spotsInColumn(column) {
  const spots = [];
  for (let i = 1; i < column.length - 1; i++) {
    const floor = column[i + 1];
    if (isOpen(column[i].typeId) && !NO_HEAD.test(id(column[i - 1].typeId)) && isSpawnFloor(floor.typeId, floor.states)) {
      spots.push(i);
    }
  }
  return spots;
}
