// Waypoints - pure logic without Minecraft imports (tested with node --test tests/core.test.mjs).
//
// A waypoint is stored as one world dynamic property "mcfs_wp:<key>" (key = lower-case name):
//   {v:1, name, x, y, z, dim, owner, created, physical, public}
// Private (public missing/false): only the owner (and operators) can use it. Public: everybody.
// For a physical waypoint x/y/z is the diamond block in the middle of the floor.

export const ITEM_ID = "mcfs:waypoint";
export const PROP_PREFIX = "mcfs_wp:";
export const NAME_MAX = 24;
export const RESERVED = new Set(["set", "list", "delete", "rename", "help", "hilfe", "liste",
  "public", "private", "öffentlich", "privat"]);

const NAME_RE = /^[A-Za-z0-9ÄÖÜäöüß][A-Za-z0-9ÄÖÜäöüß _\-']*$/;

export function keyOf(name) {
  return name.trim().toLowerCase();
}

/** @returns {string|null} error message (German) or null if the name is fine */
export function validateName(name, existingKeys, ownKey = null) {
  const n = (name ?? "").trim();
  if (!n) return "Bitte einen Namen eingeben.";
  if (n.length > NAME_MAX) return `Der Name darf höchstens ${NAME_MAX} Zeichen lang sein.`;
  if (!NAME_RE.test(n)) return "Erlaubt sind Buchstaben, Ziffern, Leerzeichen, - und _.";
  if (n.includes("  ")) return "Bitte keine doppelten Leerzeichen.";
  if (RESERVED.has(keyOf(n))) return `„${n}“ ist ein Befehlswort und kann kein Name sein.`;
  const k = keyOf(n);
  if (k !== ownKey && existingKeys.has(k)) return `Einen Wegpunkt „${n}“ gibt es schon.`;
  return null;
}

/**
 * /warp [a] [b] [c]
 *   (none) | help        -> help
 *   list                 -> list
 *   set <name>           -> set (operators: virtual waypoint at the current position)
 *   delete <name>        -> delete
 *   rename <alt> <neu>   -> rename
 *   public <name>        -> make public (owner, operators)
 *   private <name>       -> make private (owner, operators)
 *   <name>               -> teleport
 */
export function parseCommand(a, b, c) {
  const first = (a ?? "").trim();
  const verb = first.toLowerCase();
  if (!first || verb === "help" || verb === "hilfe") return { action: "help" };
  if (verb === "list" || verb === "liste") return { action: "list" };
  if (verb === "set") return b ? { action: "set", name: b.trim() } : { action: "error", message: "Aufruf: /warp set <Name>" };
  if (verb === "delete") return b ? { action: "delete", name: b.trim() } : { action: "error", message: "Aufruf: /warp delete <Name>" };
  if (verb === "public" || verb === "öffentlich" || verb === "private" || verb === "privat") {
    const pub = verb === "public" || verb === "öffentlich";
    return b ? { action: "visibility", name: b.trim(), public: pub }
      : { action: "error", message: `Aufruf: /warp ${pub ? "public" : "private"} <Name>` };
  }
  if (verb === "rename") {
    return b && c ? { action: "rename", name: b.trim(), newName: c.trim() }
      : { action: "error", message: "Aufruf: /warp rename <alter Name> <neuer Name>" };
  }
  if (b) return { action: "error", message: "Namen mit Leerzeichen in Anführungszeichen setzen: /warp \"Mein Haus\"" };
  return { action: "teleport", name: first };
}

export const HELP = [
  "§6Wegpunkte§r",
  "§e/warp <Name>§r – zum Wegpunkt reisen",
  "§e/warp list§r – Wegpunkte anzeigen, die du benutzen darfst",
  "§e/warp delete <Name>§r – eigenen Wegpunkt löschen",
  "§e/warp rename <alt> <neu>§r – eigenen Wegpunkt umbenennen",
  "§e/warp public <Name>§r / §e/warp private <Name>§r – für alle freigeben / nur für dich",
  "Neue Wegpunkte: Wegpunkt-Item craften (Laternen, Steinziegelmauern, Diamantblock) und auf den Boden setzen.",
];

// ---- the structure (relative to the diamond block in the middle of the floor)

const CORNERS = [[-1, -1], [-1, 1], [1, -1], [1, 1]];

/** @returns {{dx:number, dy:number, dz:number, block:string, states?:object}[]} */
export function layout() {
  const cells = [];
  for (let dx = -1; dx <= 1; dx++) {
    for (let dz = -1; dz <= 1; dz++) {
      const center = dx === 0 && dz === 0;
      cells.push({ dx, dy: 0, dz, block: center ? "minecraft:diamond_block" : "minecraft:stone_bricks" });
    }
  }
  for (const [dx, dz] of CORNERS) {
    cells.push({ dx, dy: 1, dz, block: "minecraft:stone_brick_wall", states: { wall_post_bit: true } });
    cells.push({ dx, dy: 2, dz, block: "minecraft:stone_brick_wall", states: { wall_post_bit: true } });
    cells.push({ dx, dy: 3, dz, block: "minecraft:lantern", states: { hanging: false } });
  }
  return cells;
}

/**
 * What stays of a removed waypoint (a "ruin"): the lanterns become copper lanterns (they oxidize over
 * time) and - when deleted by command - the diamond block becomes a coal block. Only blocks that are
 * still the original ones are replaced.
 */
export function ruinCells(withCenter) {
  const cells = CORNERS.map(([dx, dz]) => ({
    dx, dy: 3, dz, from: "minecraft:lantern", to: "minecraft:copper_lantern", states: { hanging: false },
  }));
  if (withCenter) cells.unshift({ dx: 0, dy: 0, dz: 0, from: "minecraft:diamond_block", to: "minecraft:coal_block" });
  return cells;
}

/** all positions that have to be free before building: 3 x 3 x 4 */
export function clearanceCells() {
  const out = [];
  for (let dx = -1; dx <= 1; dx++) for (let dy = 0; dy <= 3; dy++) for (let dz = -1; dz <= 1; dz++) out.push({ dx, dy, dz });
  return out;
}

// plants and snow that may be replaced when placing a waypoint
export const REPLACEABLE = new Set(["minecraft:air", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
  "minecraft:large_fern", "minecraft:snow_layer", "minecraft:dead_bush", "minecraft:dandelion", "minecraft:poppy",
  "minecraft:cave_vines", "minecraft:glow_lichen", "minecraft:deadbush", "minecraft:grass"]);

export function cellKey(dim, x, y, z) {
  return `${dim}|${x}|${y}|${z}`;
}

/** keys of all blocks that belong to a physical waypoint (for explosion protection) */
export function structureKeys(wp) {
  return layout().map((c) => cellKey(wp.dim, wp.x + c.dx, wp.y + c.dy, wp.z + c.dz));
}

/** where a player arrives: on top of the diamond (physical) or exactly where it was set (virtual) */
export function arrival(wp) {
  return wp.physical ? { x: wp.x + 0.5, y: wp.y + 1, z: wp.z + 0.5 } : { x: wp.x, y: wp.y, z: wp.z };
}

export const DIMENSIONS = {
  "minecraft:overworld": "Oberwelt",
  "minecraft:nether": "Nether",
  "minecraft:the_end": "Ende",
};

/** may this player travel to / see the waypoint? */
export function canUse(wp, playerName, isOperator) {
  return wp.owner === playerName || wp.public === true || isOperator;
}

/** the list a player gets: only usable waypoints, marked public/private */
export function formatList(wps, playerName, isOperator) {
  const visible = wps.filter((w) => canUse(w, playerName, isOperator));
  if (!visible.length) return ["§6Wegpunkte:§r noch keine. Crafte ein Wegpunkt-Item und setze es auf den Boden."];
  const sorted = [...visible].sort((a, b) => a.name.localeCompare(b.name, "de"));
  return [`§6Wegpunkte (${visible.length}):§r`, ...sorted.map((w) => {
    const tags = [w.owner, w.public ? "öffentlich" : "privat", w.physical ? null : "ohne Bauwerk"].filter(Boolean);
    return `§e${w.name}§r – ${DIMENSIONS[w.dim] ?? w.dim} ${Math.floor(w.x)} / ${Math.floor(w.y)} / ${Math.floor(w.z)} §7(${tags.join(", ")})`;
  })];
}

/** next free automatic name "Wegpunkt 1", "Wegpunkt 2", ... */
export function provisionalName(existingKeys) {
  for (let i = 1; ; i++) {
    const n = `Wegpunkt ${i}`;
    if (!existingKeys.has(keyOf(n))) return n;
  }
}
