// Spawn torch - scanning the area around a player for dark spawn spots (runs in the engine).
import { BlockTypes, BlockVolume } from "@minecraft/server";
import { ABOVE, BELOW, estimateBlockLight, isDark, isPeacefulBiome, lightEmission, RADIUS, spotsInColumn } from "./core.js";

const SOURCE_REACH = 14; // a torch outside the scanned area still lights its edge
const MAX_SOURCES = 4000; // lava lakes

let sourceTypes;

/** ids of all block types that give off light (computed once) */
function lightTypes() {
  if (!sourceTypes) sourceTypes = BlockTypes.getAll().map((t) => t.id).filter((tid) => lightEmission(tid, {}) > 0);
  return sourceTypes;
}

/** light sources around the scanned box: [{x, y, z, level}]; [] if the engine refuses (then everything stays red) */
function collectSources(dim, min, max, stats) {
  const sources = [];
  try {
    const volume = new BlockVolume(
      { x: min.x - SOURCE_REACH, y: Math.max(min.y - SOURCE_REACH, dim.heightRange.min), z: min.z - SOURCE_REACH },
      { x: max.x + SOURCE_REACH, y: Math.min(max.y + SOURCE_REACH, dim.heightRange.max - 1), z: max.z + SOURCE_REACH },
    );
    const found = dim.getBlocks(volume, { includeTypes: lightTypes() }, true);
    for (const loc of found.getBlockLocationIterator()) {
      const b = dim.getBlock(loc);
      if (!b) continue;
      const level = lightEmission(b.typeId, b.permutation.getAllStates());
      if (level > 0) sources.push({ x: loc.x, y: loc.y, z: loc.z, level });
      if (sources.length >= MAX_SOURCES) break;
    }
  } catch (e) {
    stats.sourceError = String(e);
  }
  return sources;
}

/**
 * Generator for system.runJob: scans RADIUS around center and fills result.dark with the free blocks
 * ({x, y, z}) where a mob could spawn at night. Yields after every column.
 */
export function* scanArea(dim, center, result) {
  const started = Date.now();
  const cx = Math.floor(center.x), cy = Math.floor(center.y), cz = Math.floor(center.z);
  const top = Math.min(cy + ABOVE + 1, dim.heightRange.max - 1);
  const bottom = Math.max(cy - BELOW - 1, dim.heightRange.min);
  const stats = { columns: 0, skipped: 0, spots: 0, estimated: 0 };
  let sources;
  const nearbySources = () => {
    sources ??= collectSources(dim, { x: cx - RADIUS, y: bottom, z: cz - RADIUS }, { x: cx + RADIUS, y: top, z: cz + RADIUS }, stats);
    return sources;
  };
  const dark = [];
  for (let dx = -RADIUS; dx <= RADIUS; dx++) {
    for (let dz = -RADIUS; dz <= RADIUS; dz++) {
      const x = cx + dx, z = cz + dz;
      let column = [];
      try {
        for (let y = top; y >= bottom; y--) {
          const b = dim.getBlock({ x, y, z });
          if (!b) { column = []; break; }
          column.push({ typeId: b.typeId, states: /slab|stairs/.test(b.typeId) ? b.permutation.getAllStates() : undefined });
        }
      } catch {
        column = []; // chunk not loaded
      }
      if (column.length === 0) { stats.skipped++; yield; continue; }
      stats.columns++;
      const spots = spotsInColumn(column);
      if (spots.length > 0) {
        let peaceful = false;
        try { peaceful = isPeacefulBiome(dim.getBiome({ x, y: cy, z })?.id); } catch { /* no biome -> not peaceful */ }
        if (!peaceful) {
          for (const i of spots) {
            const pos = { x, y: top - i, z };
            stats.spots++;
            const lit = !isDark(dim.getLightLevel(pos), dim.getSkyLightLevel(pos), () => {
              stats.estimated++;
              return estimateBlockLight(pos, nearbySources());
            });
            if (!lit) dark.push(pos);
          }
        }
      }
      yield;
    }
  }
  stats.sources = sources?.length;
  stats.ms = Date.now() - started;
  result.dark = dark;
  result.stats = stats;
  result.done = true;
}
