// Minecraft Family Portal - blueprint (behavior pack, change M15)
//
//  * Crafting: 4 diamonds (corners) + 4 emeralds (edges) + 1 paper (middle) -> "mcfs:blueprint" (Blaupause)
//  * Right click on a block: corner 1 (the item becomes "Blaupause – Ecke 2 wählen"), right click on a second block:
//    the area in between (at most 32 x 32 x 32) is saved and the item becomes "Blaupause: <Name>".
//    Sneak + use in the air with corner 1 set: start over.
//  * Holding a filled blueprint shows an outline where it would go (turned to where the player looks);
//    right click places it if the space is free (air, grass, flowers, snow, water) - once, then the item is used up.
//  * Copying: filled blueprint in the middle instead of the paper -> 2 blueprints of the same area. The crafting
//    result is a placeholder (mcfs:blueprint_copy); the script turns it into two filled blueprints of the one that
//    went into the crafting grid (crafting results can't carry data).
//  * Not copied (core.blockRule): valuable blocks, ores (-> stone), technical blocks, chests/barrels/shulker boxes/
//    ender chests, item holders whose contents a script can't see (crafter, frames, pots ...); hoppers, droppers,
//    furnaces ... are copied empty and emptied again after placing. Entities are never copied.
//  * Log: [mcportal-blueprint] {"v":1,"event":"saved|placed|copied",...} and the startup line.
// Uses only stable APIs (@minecraft/server, @minecraft/server-ui) - no experiments in the world.
import { Direction, EquipmentSlot, ItemStack, system, world } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import {
  BLANK_ID, boxOf, cleanName, COPY_ID, COUNTER_PROP, excludedText, facingName, facingOf, FILLED_ID, inBox, lore,
  MARKING_ID, outline, PARTICLE_ID, placedCell, placement, PROP_PREFIX, pruneGone, ROTATIONS, sizeProblem, sizeText,
  updateGone,
} from "./core.js";
import { checkFree, clearContainers, place, saveArea } from "./volume.js";

const TAG = "[mcportal-blueprint]";
const RED_PARTICLE_ID = "mcfs:blueprint_dot_red";
const DRAW_TICKS = 10; // outline particles live 0.6 s (resource pack)
const SCAN_TICKS = 5; // inventory scan for crafted copies
const GONE_MAX_AGE = 20 * 600; // a blueprint in the crafting grid is remembered for 10 minutes
const COPY_GIVE_UP_TICKS = 60; // a copy whose source can't be found turns into empty blueprints
const LOOK_DISTANCE = 12;
const NAME_FORM_RETRIES = 15;
const OFFSETS = {
  [Direction.Up]: { x: 0, y: 1, z: 0 }, [Direction.Down]: { x: 0, y: -1, z: 0 },
  [Direction.North]: { x: 0, y: 0, z: -1 }, [Direction.South]: { x: 0, y: 0, z: 1 },
  [Direction.East]: { x: 1, y: 0, z: 0 }, [Direction.West]: { x: -1, y: 0, z: 0 },
};

const busy = new Set(); // player ids with a running save/check job
/** player id -> { counts: Map sid->n, gone: [{sid,tick}], copySince } */
const scans = new Map();

function report(event, data) {
  console.warn(`${TAG} ${JSON.stringify({ v: 1, event, ...data })}`);
}

// ---------- records ----------

const keyOfSid = (sid) => sid.replace(/^mcfs:bp_/, "");

function getRecord(sid) {
  try {
    const raw = world.getDynamicProperty(PROP_PREFIX + keyOfSid(sid));
    return raw ? JSON.parse(String(raw)) : null;
  } catch {
    return null;
  }
}

function putRecord(rec) {
  world.setDynamicProperty(PROP_PREFIX + keyOfSid(rec.sid), JSON.stringify(rec));
}

/** one filled blueprint less; the last one takes the structure with it */
function release(rec) {
  rec.refs -= 1;
  if (rec.refs > 0) return putRecord(rec);
  world.setDynamicProperty(PROP_PREFIX + keyOfSid(rec.sid), undefined);
  try { world.structureManager.delete(rec.sid); } catch { /* already gone */ }
}

function nextSid() {
  const n = Number(world.getDynamicProperty(COUNTER_PROP) ?? 0) + 1;
  world.setDynamicProperty(COUNTER_PROP, n);
  return { sid: `mcfs:bp_${n}`, n };
}

function filledItem(rec) {
  const item = new ItemStack(FILLED_ID, 1);
  item.setDynamicProperty("sid", rec.sid);
  item.nameTag = `§rBlaupause: ${rec.name}`;
  item.setLore(lore(rec));
  return item;
}

// ---------- inventory helpers ----------

const containerOf = (player) => player.getComponent("minecraft:inventory")?.container;

function held(player) {
  try {
    return player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand);
  } catch {
    return undefined;
  }
}

/** slot index of the first item matching the test, preferring the selected slot */
function findSlot(container, player, test) {
  const sel = player.selectedSlotIndex;
  const first = container.getItem(sel);
  if (first && test(first)) return sel;
  for (let i = 0; i < container.size; i++) {
    const it = container.getItem(i);
    if (it && test(it)) return i;
  }
  return -1;
}

function give(player, container, item) {
  const rest = container.addItem(item);
  if (rest) player.dimension.spawnItem(rest, player.location);
}

/** replace one item of the stack in `slot` by `item` (the rest of the stack moves elsewhere) */
function swapOne(player, container, slot, item) {
  const old = container.getItem(slot);
  container.setItem(slot, item);
  if (old && old.amount > 1) {
    old.amount -= 1;
    give(player, container, old);
  }
}

// ---------- using the items on blocks ----------

const ITEMS = new Set([BLANK_ID, MARKING_ID, FILLED_ID, COPY_ID]);

world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  const type = ev.itemStack?.typeId;
  if (!ITEMS.has(type)) return;
  ev.cancel = true; // no chest opens, nothing is placed
  if (!ev.isFirstEvent) return;
  const { player, block, blockFace } = ev;
  const loc = block.location;
  const dimId = block.dimension.id;
  system.run(() => {
    if (!player.isValid) return;
    if (type === BLANK_ID) return markFirst(player, loc, dimId);
    if (type === MARKING_ID) return markSecond(player, loc, dimId);
    if (type === FILLED_ID) return startPlacing(player, loc, blockFace);
    player.sendMessage("§7Die Kopie wird gerade fertig – einen Moment.");
  });
});

world.beforeEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== MARKING_ID || !ev.source.isSneaking) return;
  const player = ev.source;
  system.run(() => {
    const c = containerOf(player);
    const slot = c ? findSlot(c, player, (it) => it.typeId === MARKING_ID) : -1;
    if (slot < 0) return;
    c.setItem(slot, new ItemStack(BLANK_ID, 1));
    player.sendMessage("§6Ecke 1 verworfen. Rechtsklick auf einen Block setzt sie neu.");
  });
});

function markFirst(player, loc, dimId) {
  const c = containerOf(player);
  const slot = c ? findSlot(c, player, (it) => it.typeId === BLANK_ID) : -1;
  if (slot < 0) return;
  const item = new ItemStack(MARKING_ID, 1);
  item.setDynamicProperties({ c1x: loc.x, c1y: loc.y, c1z: loc.z, c1dim: dimId });
  item.setLore([`§7Ecke 1: ${loc.x} ${loc.y} ${loc.z}`, "§7Schleichen + Benutzen: neu anfangen"]);
  swapOne(player, c, slot, item);
  player.sendMessage(`§6Ecke 1 gesetzt (${loc.x} ${loc.y} ${loc.z}). Jetzt die gegenüberliegende Ecke anklicken`
    + ` – höchstens 32 × 32 × 32 Blöcke.`);
}

function corner1(item) {
  const x = item.getDynamicProperty("c1x");
  if (typeof x !== "number") return null;
  return { x, y: item.getDynamicProperty("c1y"), z: item.getDynamicProperty("c1z"),
    dim: String(item.getDynamicProperty("c1dim")) };
}

function markSecond(player, loc, dimId) {
  const c = containerOf(player);
  const slot = c ? findSlot(c, player, (it) => it.typeId === MARKING_ID) : -1;
  if (slot < 0) return;
  const c1 = corner1(c.getItem(slot));
  if (!c1) {
    c.setItem(slot, new ItemStack(BLANK_ID, 1));
    return player.sendMessage("§cDie Blaupause hatte keine Ecke 1 – bitte neu anfangen.");
  }
  if (c1.dim !== dimId) return player.sendMessage("§cBeide Ecken müssen in derselben Welt liegen.");
  const { min, size } = boxOf(c1, loc);
  const problem = sizeProblem(size);
  if (problem) return player.sendMessage(`§c${problem}`);
  if (busy.has(player.id)) return player.sendMessage("§7Einen Moment, die Blaupause arbeitet noch.");

  busy.add(player.id);
  const facing = facingOf(player.getRotation().y);
  const { sid, n } = nextSid();
  const result = {};
  system.runJob((function* () {
    try {
      yield* saveArea(player.dimension, min, size, sid, result);
    } finally {
      busy.delete(player.id);
    }
    if (!result.ok) {
      console.warn(`${TAG} ${JSON.stringify({ v: 1, event: "error", sid, error: result.error })}`);
      return player.sendMessage("§cDas Speichern hat nicht geklappt. Ist der ganze Bereich geladen?");
    }
    finishSave(player, { sid, n, size, facing, c1, result });
  })());
}

function finishSave(player, { sid, n, size, facing, c1, result }) {
  const c = containerOf(player);
  const same = (it) => {
    const k = it.typeId === MARKING_ID && corner1(it);
    return k && k.x === c1.x && k.y === c1.y && k.z === c1.z;
  };
  const slot = c ? findSlot(c, player, same) : -1;
  if (slot < 0) {
    try { world.structureManager.delete(sid); } catch { /* not saved */ }
    return player.sendMessage("§cDie Blaupause ist nicht mehr im Inventar – nichts gespeichert.");
  }
  const rec = { v: 1, sid, name: `Bauplan ${n}`, owner: player.name, size, facing,
    created: new Date().toISOString(), excluded: result.excluded, emptied: result.emptied, refs: 1 };
  putRecord(rec);
  c.setItem(slot, filledItem(rec));
  const ex = excludedText(rec.excluded);
  player.sendMessage(`§6Blaupause gespeichert: ${sizeText(size)} Blöcke.`
    + (ex ? ` §7Nicht mitkopiert: ${ex}.` : ""));
  try { player.playSound("random.orb"); } catch { /* sound id may vary */ }
  report("saved", { player: player.name, sid, size, excluded: rec.excluded });
  askName(player, sid, 0);
}

function askName(player, sid, attempt) {
  const rec = getRecord(sid);
  if (!rec) return;
  new ModalFormData()
    .title("Blaupause")
    .textField("Wie soll dieser Bauplan heißen?", "z. B. Stadtmauer", { defaultValue: rec.name })
    .show(player).then((res) => {
      if (res.canceled) {
        if (res.cancelationReason === "UserBusy" && attempt < NAME_FORM_RETRIES) {
          system.runTimeout(() => askName(player, sid, attempt + 1), 20);
        }
        return;
      }
      const now = getRecord(sid);
      if (!now) return;
      now.name = cleanName(res.formValues?.[0], now.name);
      putRecord(now);
      const c = containerOf(player);
      if (!c) return;
      for (let i = 0; i < c.size; i++) {
        const it = c.getItem(i);
        if (it?.typeId === FILLED_ID && it.getDynamicProperty("sid") === sid) c.setItem(i, filledItem(now));
      }
      player.sendMessage(`§6Bauplan heißt jetzt §e${now.name}§6.`);
    }).catch(() => { /* player left */ });
}

// ---------- placing ----------

function plan(player, rec, loc, face) {
  const o = OFFSETS[face] ?? OFFSETS[Direction.Up];
  const target = { x: loc.x + o.x, y: loc.y + o.y, z: loc.z + o.z };
  return placement(rec.size, rec.facing, facingOf(player.getRotation().y), target);
}

function startPlacing(player, loc, face) {
  const item = held(player);
  const sid = item?.getDynamicProperty("sid");
  const rec = typeof sid === "string" ? getRecord(sid) : null;
  if (!rec) return player.sendMessage("§cZu dieser Blaupause gibt es keinen gespeicherten Bauplan mehr.");
  if (busy.has(player.id)) return player.sendMessage("§7Einen Moment, die Blaupause arbeitet noch.");
  const p = plan(player, rec, loc, face);
  const dim = player.dimension;
  const inside = dim.getPlayers().find((pl) => inBox({
    x: Math.floor(pl.location.x), y: Math.floor(pl.location.y), z: Math.floor(pl.location.z),
  }, p.min, p.size) || inBox({
    x: Math.floor(pl.location.x), y: Math.floor(pl.location.y) + 1, z: Math.floor(pl.location.z),
  }, p.min, p.size));
  if (inside) return player.sendMessage(`§c${inside.name === player.name ? "Du stehst" : `${inside.name} steht`} im Bauplatz.`);

  busy.add(player.id);
  const result = {};
  system.runJob((function* () {
    try {
      yield* checkFree(dim, p.min, p.size, result);
    } finally {
      busy.delete(player.id);
    }
    if (result.problem) return player.sendMessage(`§c${result.problem}`);
    const c = containerOf(player);
    const slot = c ? findSlot(c, player, (it) => it.typeId === FILLED_ID && it.getDynamicProperty("sid") === rec.sid) : -1;
    if (slot < 0) return player.sendMessage("§cDie Blaupause ist nicht mehr im Inventar.");
    try {
      place(dim, rec.sid, p.min, p.rotation);
    } catch (e) {
      console.warn(`${TAG} ${JSON.stringify({ v: 1, event: "error", sid: rec.sid, error: String(e) })}`);
      return player.sendMessage("§cEinsetzen hat nicht geklappt.");
    }
    const k = ROTATIONS.indexOf(p.rotation);
    const left = clearContainers(dim, (rec.emptied ?? []).map((cell) =>
      placedCell(rec.size, k, p.min, { x: cell[0], y: cell[1], z: cell[2] })));
    if (left) report("error", { sid: rec.sid, error: `${left} items in placed containers, cleared` });
    c.setItem(slot, undefined); // used up
    rememberInventory(player); // not a crafting ingredient - don't count it as gone
    const fresh = getRecord(rec.sid) ?? rec;
    release(fresh);
    try { dim.playSound("block.beacon.activate", p.min); } catch { /* sound id may vary */ }
    player.sendMessage(`§6Bauplan §e${rec.name}§6 eingesetzt.`);
    report("placed", { player: player.name, sid: rec.sid, name: rec.name, dim: dim.id, min: p.min,
      rotation: p.rotation });
  })());
}

// ---------- outline while holding ----------

function look(player) {
  try {
    return player.getBlockFromViewDirection({ maxDistance: LOOK_DISTANCE, includeLiquidBlocks: false,
      includePassableBlocks: false });
  } catch {
    return undefined;
  }
}

function drawBox(player, min, size, particle) {
  const step = Math.max(size.x, size.y, size.z) > 16 ? 1 : 0.5; // denser dots on small areas
  for (const pt of outline(min, size, step)) {
    try {
      player.spawnParticle(particle, pt);
    } catch {
      return; // area unloaded / player left
    }
  }
}

function draw() {
  for (const player of world.getPlayers()) {
    if (!player.isValid) continue;
    const item = held(player);
    const type = item?.typeId;
    if (type === BLANK_ID) {
      player.onScreenDisplay.setActionBar("§6Blaupause: §fRechtsklick auf die erste Ecke");
    } else if (type === MARKING_ID) {
      const c1 = corner1(item);
      if (!c1) continue;
      const hit = look(player);
      if (!hit || c1.dim !== player.dimension.id) {
        drawBox(player, c1, { x: 1, y: 1, z: 1 }, PARTICLE_ID);
        player.onScreenDisplay.setActionBar("§6Ecke 2: §fauf einen Block schauen");
        continue;
      }
      const { min, size } = boxOf(c1, hit.block.location);
      const tooBig = sizeProblem(size);
      drawBox(player, min, size, tooBig ? RED_PARTICLE_ID : PARTICLE_ID);
      player.onScreenDisplay.setActionBar(tooBig ? `§c${sizeText(size)} – zu groß (höchstens 32)`
        : `§6Ecke 2: §f${sizeText(size)} Blöcke §7– Rechtsklick speichert`);
    } else if (type === FILLED_ID) {
      const sid = item.getDynamicProperty("sid");
      const rec = typeof sid === "string" ? getRecord(sid) : null;
      if (!rec) continue;
      const hit = look(player);
      if (!hit) {
        player.onScreenDisplay.setActionBar(`§6${rec.name} §7(${sizeText(rec.size)}) – auf den Boden schauen`);
        continue;
      }
      const p = plan(player, rec, hit.block.location, hit.face);
      drawBox(player, p.min, p.size, PARTICLE_ID);
      player.onScreenDisplay.setActionBar(`§6${rec.name} §f${sizeText(p.size)} §7Blick nach `
        + `${facingName(facingOf(player.getRotation().y))} – Rechtsklick setzt ein`);
    }
  }
}

// ---------- copies ----------

function inventoryCounts(player, c) {
  const counts = new Map();
  const add = (it) => {
    if (it?.typeId !== FILLED_ID) return;
    const sid = it.getDynamicProperty("sid");
    if (typeof sid === "string") counts.set(sid, (counts.get(sid) ?? 0) + 1);
  };
  for (let i = 0; i < c.size; i++) add(c.getItem(i));
  try { add(player.getComponent("minecraft:cursor_inventory")?.item); } catch { /* no cursor */ }
  return counts;
}

function rememberInventory(player) {
  const c = containerOf(player);
  const s = scans.get(player.id);
  if (c && s) s.counts = inventoryCounts(player, c);
}

function scanCopies() {
  const tick = system.currentTick;
  for (const player of world.getPlayers()) {
    if (!player.isValid) continue;
    const c = containerOf(player);
    if (!c) continue;
    let s = scans.get(player.id);
    const counts = inventoryCounts(player, c);
    if (!s) {
      scans.set(player.id, { counts, gone: [], copySince: -1 });
      continue;
    }
    updateGone(s.gone, s.counts, counts, tick);
    pruneGone(s.gone, tick, GONE_MAX_AGE);
    s.counts = counts;
    const copySlots = [];
    for (let i = 0; i < c.size; i++) if (c.getItem(i)?.typeId === COPY_ID) copySlots.push(i);
    if (!copySlots.length) {
      s.copySince = -1;
      continue;
    }
    if (s.copySince < 0) s.copySince = tick;
    for (const slot of copySlots) resolveCopy(player, c, s, slot, tick);
    s.counts = inventoryCounts(player, c);
  }
}

function resolveCopy(player, c, s, slot, tick) {
  const copy = c.getItem(slot);
  const amount = copy.amount;
  let rec = null;
  while (!rec && s.gone.length) rec = getRecord(s.gone.pop().sid);
  if (!rec) {
    if (tick - s.copySince < COPY_GIVE_UP_TICKS) return; // the source may still show up
    c.setItem(slot, new ItemStack(BLANK_ID, amount));
    player.sendMessage("§cZu dieser Kopie wurde keine Vorlage gefunden – du bekommst leere Blaupausen.");
    report("copy_unresolved", { player: player.name, amount });
    return;
  }
  c.setItem(slot, filledItem(rec));
  for (let i = 1; i < amount; i++) give(player, c, filledItem(rec));
  rec.refs += amount - 1; // the source went into the crafting grid
  putRecord(rec);
  player.sendMessage(`§6Bauplan §e${rec.name}§6 kopiert – du hast jetzt ${amount} Stück davon.`);
  report("copied", { player: player.name, sid: rec.sid, name: rec.name, amount });
}

world.afterEvents.playerLeave.subscribe((ev) => {
  scans.delete(ev.playerId);
  busy.delete(ev.playerId);
});

system.runInterval(draw, DRAW_TICKS);
system.runInterval(scanCopies, SCAN_TICKS);
system.run(() => console.warn(`${TAG} {"v":1,"started":true}`));
