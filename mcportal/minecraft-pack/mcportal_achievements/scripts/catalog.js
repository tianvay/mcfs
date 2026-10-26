// Achievement catalog and evaluation - pure JavaScript, no Minecraft imports,
// so it can be unit-tested with Node: node --test tests/catalog.test.mjs
//
// Every achievement watches one counter; tiers unlock one after another.
// Counters are filled by main.js (units: blocks, seconds, pieces).

const KM = 1000; // blocks
const HOUR = 3600; // seconds

/** @type {{id: string, group: string, counter: string, tiers: {at: number, name: string, desc: string}[]}[]} */
export const CATALOG = [
  // ---- Bergbau
  { id: "ores", group: "Bergbau", counter: "ores", tiers: [
    { at: 100, name: "Kumpel", desc: "100 Erze abgebaut" },
    { at: 1000, name: "Bergarbeiter", desc: "1.000 Erze abgebaut" },
    { at: 10000, name: "Glück auf!", desc: "10.000 Erze abgebaut" },
  ] },
  { id: "diamonds", group: "Bergbau", counter: "diamonds", tiers: [
    { at: 1, name: "Diamant!", desc: "Den ersten Diamanten gefunden" },
    { at: 50, name: "Diamantenfieber", desc: "50 Diamanten gefunden" },
    { at: 250, name: "Ungeschliffen reich", desc: "250 Diamanten gefunden" },
  ] },
  { id: "debris", group: "Bergbau", counter: "debris", tiers: [
    { at: 1, name: "Schrott vom Feinsten", desc: "Antiken Schrott abgebaut" },
  ] },

  // ---- Ausrüstung
  { id: "armor_diamond", group: "Ausrüstung", counter: "armor_diamond", tiers: [
    { at: 1, name: "Strahlend", desc: "Eine komplette Diamantrüstung angelegt" },
  ] },
  { id: "armor_netherite", group: "Ausrüstung", counter: "armor_netherite", tiers: [
    { at: 1, name: "Unkaputtbar", desc: "Eine komplette Netheriterüstung angelegt" },
  ] },

  // ---- Natur
  { id: "saplings", group: "Natur", counter: "saplings", tiers: [
    { at: 10, name: "Grüner Daumen", desc: "10 Bäume gepflanzt" },
    { at: 100, name: "Förster", desc: "100 Bäume gepflanzt" },
    { at: 1000, name: "Der Wald ruft", desc: "1.000 Bäume gepflanzt" },
  ] },
  { id: "bred", group: "Natur", counter: "bred", tiers: [
    { at: 10, name: "Tierfreund", desc: "10 Tiere gezüchtet" },
    { at: 100, name: "Arche Noah", desc: "100 Tiere gezüchtet" },
  ] },
  { id: "bred_cow", group: "Natur", counter: "bred_cow", tiers: [
    { at: 25, name: "Muh-ltitalent", desc: "25 Kühe gezüchtet" },
  ] },

  // ---- Kampf
  { id: "kills", group: "Kampf", counter: "kills", tiers: [
    { at: 10, name: "Nachtwächter", desc: "10 Monster besiegt" },
    { at: 100, name: "Monsterjäger", desc: "100 Monster besiegt" },
    { at: 1000, name: "Albtraum der Albträume", desc: "1.000 Monster besiegt" },
  ] },
  { id: "kills_zombie", group: "Kampf", counter: "kills_zombie", tiers: [
    { at: 100, name: "Hirn-los glücklich", desc: "100 Zombies besiegt" },
  ] },
  { id: "kills_skeleton", group: "Kampf", counter: "kills_skeleton", tiers: [
    { at: 50, name: "Knochenarbeit", desc: "50 Skelette besiegt" },
  ] },
  { id: "kills_creeper", group: "Kampf", counter: "kills_creeper", tiers: [
    { at: 50, name: "Sssss-chluss jetzt!", desc: "50 Creeper besiegt" },
  ] },
  { id: "kill_dragon", group: "Kampf", counter: "kill_dragon", tiers: [
    { at: 1, name: "Drachentöter", desc: "Den Enderdrachen besiegt" },
  ] },
  { id: "kill_wither", group: "Kampf", counter: "kill_wither", tiers: [
    { at: 1, name: "Wither-sprochen!", desc: "Den Wither besiegt" },
  ] },

  // ---- Missgeschicke
  { id: "deaths", group: "Missgeschicke", counter: "deaths", tiers: [
    { at: 1, name: "Anfängerfehler", desc: "Zum ersten Mal gestorben" },
    { at: 10, name: "Wiederholungstäter", desc: "10-mal gestorben" },
    { at: 100, name: "Respawn-Routine", desc: "100-mal gestorben" },
  ] },
  { id: "death_creeper", group: "Missgeschicke", counter: "death_creeper", tiers: [
    { at: 1, name: "Sssssurprise!", desc: "Von einem Creeper erwischt worden" },
  ] },
  { id: "death_lava", group: "Missgeschicke", counter: "death_lava", tiers: [
    { at: 1, name: "Heiße Sache", desc: "In Lava gestorben" },
  ] },
  { id: "death_fall", group: "Missgeschicke", counter: "death_fall", tiers: [
    { at: 1, name: "Die Schwerkraft gewinnt immer", desc: "An Fallschaden gestorben" },
  ] },
  { id: "death_drowning", group: "Missgeschicke", counter: "death_drowning", tiers: [
    { at: 1, name: "Blubb.", desc: "Ertrunken" },
  ] },

  // ---- Reisen
  { id: "nether", group: "Reisen", counter: "nether", tiers: [
    { at: 1, name: "Höllisch heiß", desc: "Den Nether betreten" },
  ] },
  { id: "end", group: "Reisen", counter: "end", tiers: [
    { at: 1, name: "Das Ende vom Lied", desc: "Das Ende betreten" },
  ] },
  { id: "walk", group: "Reisen", counter: "walk", tiers: [
    { at: 10 * KM, name: "Wandervogel", desc: "10 km zu Fuß unterwegs" },
    { at: 100 * KM, name: "Ultramarathon", desc: "100 km zu Fuß unterwegs" },
  ] },
  { id: "elytra", group: "Reisen", counter: "elytra", tiers: [
    { at: 10 * KM, name: "Überflieger", desc: "10 km mit der Elytra geflogen" },
  ] },
  { id: "boat", group: "Reisen", counter: "boat", tiers: [
    { at: 5 * KM, name: "Leinen los!", desc: "5 km mit dem Boot gefahren" },
  ] },

  // ---- Essen
  { id: "food", group: "Essen", counter: "food", tiers: [
    { at: 50, name: "Snackpause", desc: "50-mal gegessen" },
    { at: 500, name: "Vielfraß", desc: "500-mal gegessen" },
  ] },
  { id: "golden_apple", group: "Essen", counter: "eat_golden_apple", tiers: [
    { at: 1, name: "Goldener Biss", desc: "Einen Goldenen Apfel gegessen" },
  ] },
  { id: "rotten_flesh", group: "Essen", counter: "eat_rotten_flesh", tiers: [
    { at: 10, name: "Zombie-Diät", desc: "10-mal Verrottetes Fleisch gegessen" },
  ] },

  // ---- Bauen
  { id: "placed", group: "Bauen", counter: "placed", tiers: [
    { at: 1000, name: "Häuslebauer", desc: "1.000 Blöcke gesetzt" },
    { at: 10000, name: "Stein auf Stein", desc: "10.000 Blöcke gesetzt" },
  ] },
  { id: "dirt", group: "Bauen", counter: "dirt_placed", tiers: [
    { at: 500, name: "Erdverbunden", desc: "500 Erdblöcke verbaut" },
  ] },

  // ---- Dabeisein
  { id: "time", group: "Dabeisein", counter: "time", tiers: [
    { at: 10 * HOUR, name: "Stammgast", desc: "10 Stunden gespielt" },
    { at: 100 * HOUR, name: "Hier wohn ich jetzt", desc: "100 Stunden gespielt" },
  ] },
  { id: "xp", group: "Dabeisein", counter: "xp", tiers: [
    { at: 5000, name: "Erfahrungsschatz", desc: "5.000 Erfahrungspunkte gesammelt" },
  ] },

  // ---- Events (news from the events pack, mcportal_events)
  { id: "events", group: "Events", counter: "events", tiers: [
    { at: 5, name: "Mittendrin statt nur dabei", desc: "5 Events mitgemacht" },
    { at: 20, name: "Eventhopper", desc: "20 Events mitgemacht" },
    { at: 50, name: "Partylöwe", desc: "50 Events mitgemacht" },
  ] },
  // one achievement per wave of events, so a reached one never changes when new events come
  { id: "seen_wave1", group: "Events", counter: "seen_wave1", tiers: [
    { at: 3, name: "Hab ich alles schon gesehen", desc: "Unwetter, Mining Rush und Glückstag mitgemacht" },
  ] },
  { id: "rush_ores", group: "Events", counter: "rush_ores", tiers: [
    { at: 100, name: "Goldrausch", desc: "100 Erze während eines Mining Rush abgebaut" },
  ] },
  { id: "lucky_xp", group: "Events", counter: "lucky_xp", tiers: [
    { at: 1000, name: "Glückspilz", desc: "1.000 Erfahrungspunkte an Glückstagen gesammelt" },
  ] },
  { id: "lightning", group: "Events", counter: "lightning_survived", tiers: [
    { at: 1, name: "Geistesblitz", desc: "Bei einem Unwetter vom Blitz getroffen – und überlebt" },
  ] },
  // wave 2: the night dangers (events pack 1.1.0)
  { id: "seen_wave2", group: "Events", counter: "seen_wave2", tiers: [
    { at: 3, name: "Hab ich alles schon gesehen II", desc: "Zombie-Invasion, Blutmond und Kopfgeld-Jagd mitgemacht" },
  ] },
  { id: "invasion", group: "Events", counter: "invasion_best", tiers: [
    { at: 20, name: "Hirn-Rissig", desc: "20 Zombies in einer einzigen Invasionsnacht besiegt" },
  ] },
  { id: "blood_wolves", group: "Events", counter: "blood_wolves", tiers: [
    { at: 10, name: "Wer hat Angst vorm bösen Wolf?", desc: "10 Blutmond-Wölfe besiegt" },
  ] },
  { id: "bounty", group: "Events", counter: "bounties", tiers: [
    { at: 1, name: "Kopfgeldjäger", desc: "Bei der Jagd auf einen Kopfgeld-Boss dabei gewesen, als er fiel" },
  ] },
  // community: the first meta achievement (the others come with the third event package)
  { id: "together", group: "Events", counter: "together", tiers: [
    { at: 1, name: "Gemeinsam stark", desc: "Ein Event mit mindestens 3 Mitspielern gemeinsam erlebt" },
    { at: 10, name: "Unzertrennlich", desc: "10 Events mit mindestens 3 Mitspielern gemeinsam erlebt" },
  ] },
  // wave 3: the world changes (events pack 1.3.0)
  { id: "seen_wave3", group: "Events", counter: "seen_wave3", tiers: [
    { at: 4, name: "Hab ich alles schon gesehen III", desc: "Meteorit, Sternschnuppen-Nacht, Schatzsuche und Spukort mitgemacht" },
  ] },
  { id: "meteor_hit", group: "Events", counter: "meteor_hit", tiers: [
    { at: 1, name: "Volltreffer", desc: "Beim Einschlag eines Meteoriten ganz in der Nähe gewesen" },
  ] },
  { id: "stars", group: "Events", counter: "stars", tiers: [
    { at: 10, name: "Sterntaler", desc: "10 Sternenstücke aufgesammelt" },
  ] },
  { id: "treasure", group: "Events", counter: "treasures", tiers: [
    { at: 1, name: "Schatzsucher", desc: "Als Erste/r einen vergrabenen Schatz gefunden" },
  ] },
  { id: "curse", group: "Events", counter: "curses", tiers: [
    { at: 1, name: "Geisterjäger", desc: "Dabei gewesen, als ein Fluch gebrochen wurde" },
  ] },
  // meta: every event of a category taken part in at least once
  { id: "cat_welt", group: "Events", counter: "cat_welt", tiers: [
    { at: 3, name: "Wetterfest und Weltenbummler", desc: "Unwetter, Meteorit und Sternschnuppen-Nacht mitgemacht" },
  ] },
  { id: "cat_ressourcen", group: "Events", counter: "cat_ressourcen", tiers: [
    { at: 3, name: "Schatzkammer", desc: "Mining Rush, Glückstag und Schatzsuche mitgemacht" },
  ] },
  { id: "cat_mobs", group: "Events", counter: "cat_mobs", tiers: [
    { at: 4, name: "Nachtwache", desc: "Blutmond, Zombie-Invasion, Kopfgeld und Spukort mitgemacht" },
  ] },
];

/**
 * Event types per wave (= event package). "Hab ich alles schon gesehen" counts the distinct types of a wave
 * a player took part in; a new wave gets its own achievement (seen_wave2 ...).
 */
export const EVENT_WAVES = {
  1: ["storm", "mining_rush", "lucky_day"],
  2: ["blood_moon", "zombie_invasion", "bounty"],
  3: ["meteor", "shooting_stars", "treasure", "haunted"],
};

/** event categories for the meta achievements (same as the events pack's TYPES[...].category) */
export const EVENT_CATEGORIES = {
  welt: ["storm", "meteor", "shooting_stars"],
  ressourcen: ["mining_rush", "lucky_day", "treasure"],
  mobs: ["blood_moon", "zombie_invasion", "bounty", "haunted"],
};

export const TOGETHER = 3; // players taking part in one event for "Gemeinsam stark"

/**
 * Counter changes when a player took part in an event of `type` that had `participants` participants in all.
 * @returns {Record<string, number>} counter -> new absolute value
 */
export function eventCounters(counters, type, participants = 1) {
  const out = { events: (counters.events ?? 0) + 1, [`ev_${type}`]: (counters[`ev_${type}`] ?? 0) + 1 };
  if (participants >= TOGETHER) out.together = (counters.together ?? 0) + 1;
  const after = { ...counters, ...out };
  for (const [wave, types] of Object.entries(EVENT_WAVES)) {
    if (types.includes(type)) out[`seen_wave${wave}`] = types.filter((t) => after[`ev_${t}`] > 0).length;
  }
  for (const [cat, types] of Object.entries(EVENT_CATEGORIES)) {
    if (types.includes(type)) out[`cat_${cat}`] = types.filter((t) => after[`ev_${t}`] > 0).length;
  }
  return out;
}

/**
 * Zombies defeated in the current invasion night (inv_now, reset at its start) and the best night so far.
 * @returns {Record<string, number>}
 */
export function invasionKill(counters) {
  const now = (counters.inv_now ?? 0) + 1;
  return { inv_now: now, invasion_best: Math.max(counters.invasion_best ?? 0, now) };
}

/**
 * Check counters against the catalog.
 * @param {Record<string, number>} counters
 * @param {Record<string, number>} unlocked  id -> number of tiers already unlocked (mutated)
 * @returns {{id: string, tier: number, name: string, desc: string}[]} newly unlocked, in catalog order
 */
export function evaluate(counters, unlocked) {
  const fresh = [];
  for (const a of CATALOG) {
    const value = counters[a.counter] ?? 0;
    let done = unlocked[a.id] ?? 0;
    while (done < a.tiers.length && value >= a.tiers[done].at) {
      const t = a.tiers[done];
      fresh.push({ id: a.id, tier: done + 1, name: t.name, desc: t.desc });
      done += 1;
    }
    if (done) unlocked[a.id] = done;
  }
  return fresh;
}

/** Flat list for the portal: one entry per tier. */
export function flatCatalog() {
  return CATALOG.flatMap((a) => a.tiers.map((t, i) => ({
    id: a.id, tier: i + 1, tiers: a.tiers.length, group: a.group, name: t.name, desc: t.desc,
  })));
}

// ---- classification of game ids into counters (pure, also tested)

const ZOMBIES = new Set(["minecraft:zombie", "minecraft:husk", "minecraft:drowned",
  "minecraft:zombie_villager", "minecraft:zombie_villager_v2"]);
const SKELETONS = new Set(["minecraft:skeleton", "minecraft:stray", "minecraft:bogged"]);
// mobs that count as "monsters" for the kill achievements (passive animals don't)
const MONSTERS = new Set([...ZOMBIES, ...SKELETONS, "minecraft:creeper", "minecraft:spider",
  "minecraft:cave_spider", "minecraft:enderman", "minecraft:endermite", "minecraft:witch", "minecraft:slime",
  "minecraft:magma_cube", "minecraft:phantom", "minecraft:silverfish", "minecraft:pillager",
  "minecraft:vindicator", "minecraft:evocation_illager", "minecraft:ravager", "minecraft:vex",
  "minecraft:blaze", "minecraft:ghast", "minecraft:piglin_brute", "minecraft:hoglin", "minecraft:zoglin",
  "minecraft:guardian", "minecraft:elder_guardian", "minecraft:shulker", "minecraft:warden",
  "minecraft:breeze", "minecraft:wither_skeleton", "minecraft:zombie_pigman", "minecraft:ender_dragon",
  "minecraft:wither"]);

export function isOre(blockId) {
  return blockId.endsWith("_ore") || blockId === "minecraft:ancient_debris";
}

export function isDiamondOre(blockId) {
  return blockId === "minecraft:diamond_ore" || blockId === "minecraft:deepslate_diamond_ore";
}

export function isSapling(blockId) {
  return blockId.endsWith("_sapling") || blockId === "minecraft:mangrove_propagule"
    || blockId === "minecraft:azalea" || blockId === "minecraft:flowering_azalea";
}

/** counter names to increase for a killed entity */
export function killCounters(typeId) {
  const out = [];
  if (MONSTERS.has(typeId)) out.push("kills");
  if (ZOMBIES.has(typeId)) out.push("kills_zombie");
  if (SKELETONS.has(typeId)) out.push("kills_skeleton");
  if (typeId === "minecraft:creeper") out.push("kills_creeper");
  if (typeId === "minecraft:ender_dragon") out.push("kill_dragon");
  if (typeId === "minecraft:wither") out.push("kill_wither");
  return out;
}

/** counter names to increase for a player death */
export function deathCounters(cause, killerTypeId) {
  const out = ["deaths"];
  if (killerTypeId === "minecraft:creeper") out.push("death_creeper");
  if (cause === "lava") out.push("death_lava");
  if (cause === "fall") out.push("death_fall");
  if (cause === "drowning") out.push("death_drowning");
  return out;
}

const DIAMOND_SET = ["minecraft:diamond_helmet", "minecraft:diamond_chestplate",
  "minecraft:diamond_leggings", "minecraft:diamond_boots"];
const NETHERITE_SET = ["minecraft:netherite_helmet", "minecraft:netherite_chestplate",
  "minecraft:netherite_leggings", "minecraft:netherite_boots"];

/** @param {(string|undefined)[]} worn  type ids in head, chest, legs, feet */
export function armorCounters(worn) {
  const out = [];
  if (DIAMOND_SET.every((id, i) => worn[i] === id)) out.push("armor_diamond");
  if (NETHERITE_SET.every((id, i) => worn[i] === id)) out.push("armor_netherite");
  return out;
}
