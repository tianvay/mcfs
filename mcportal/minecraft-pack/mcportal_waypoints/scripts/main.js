// Minecraft Family Portal - waypoints / warps (behavior pack, change M9)
//
//  * Crafting: 4 lanterns + 4 stone brick walls + 1 diamond block -> item "mcfs:waypoint" (Wegpunkt)
//  * Using the item on the ground builds the structure (3x3 stone bricks, diamond block in the middle,
//    2-high walls with a lantern on each corner) and asks for a name.
//  * /warp <Name> | list | delete <Name> | rename <alt> <neu> - for everybody
//    /warp set <Name> - operators only: waypoint without structure at the current position
//  * Mining the diamond block removes the waypoint; explosions don't damage waypoint structures.
//  * Stored in world dynamic properties (survives restarts and updates).
//  * Log lines for the portal: [mcportal-warp] {"v":1,"event":...}
// Uses only stable APIs (@minecraft/server, @minecraft/server-ui) - no experiments in the world.
import {
  CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, Direction, GameMode,
  Player, PlayerPermissionLevel, system, world,
} from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import {
  arrival, formatList, HELP, ITEM_ID, keyOf, parseCommand, PROP_PREFIX, provisionalName, structureKeys, validateName,
} from "./core.js";
import { build, placementProblem } from "./structure.js";

const TAG = "[mcportal-warp]";
const NAME_FORM_RETRIES = 15; // the form can't open while the player has another screen open

/** key -> waypoint; loaded lazily (dynamic properties are not readable during early execution) */
let cache;
/** cell keys of all physical waypoint structures -> waypoint key */
let cells;

function report(event, data) {
  console.warn(`${TAG} ${JSON.stringify({ v: 1, event, ...data })}`);
}

// ---------- storage ----------

function all() {
  if (!cache) {
    cache = new Map();
    for (const id of world.getDynamicPropertyIds()) {
      if (!id.startsWith(PROP_PREFIX)) continue;
      try {
        const wp = JSON.parse(String(world.getDynamicProperty(id)));
        cache.set(keyOf(wp.name), wp);
      } catch { /* ignore broken entries */ }
    }
    rebuildCells();
  }
  return cache;
}

function rebuildCells() {
  cells = new Map();
  for (const [key, wp] of cache) {
    if (wp.physical) for (const c of structureKeys(wp)) cells.set(c, key);
  }
}

function store(wp, oldKey) {
  all();
  if (oldKey && oldKey !== keyOf(wp.name)) {
    world.setDynamicProperty(PROP_PREFIX + oldKey, undefined);
    cache.delete(oldKey);
  }
  world.setDynamicProperty(PROP_PREFIX + keyOf(wp.name), JSON.stringify(wp));
  cache.set(keyOf(wp.name), wp);
  rebuildCells();
}

function remove(key) {
  all();
  world.setDynamicProperty(PROP_PREFIX + key, undefined);
  cache.delete(key);
  rebuildCells();
}

function keys() {
  return new Set(all().keys());
}

const isOperator = (p) => p.playerPermissionLevel === PlayerPermissionLevel.Operator;
const mayChange = (p, wp) => wp.owner === p.name || isOperator(p);

// ---------- /warp ----------

system.beforeEvents.startup.subscribe((ev) => {
  ev.customCommandRegistry.registerCommand({
    name: "mcfs:warp",
    description: "Wegpunkte: /warp <Name> | list | delete <Name> | rename <alt> <neu> | set <Name>",
    permissionLevel: CommandPermissionLevel.Any,
    optionalParameters: [
      { name: "name_oder_befehl", type: CustomCommandParamType.String },
      { name: "name", type: CustomCommandParamType.String },
      { name: "neuer_name", type: CustomCommandParamType.String },
    ],
  }, (origin, a, b, c) => {
    const player = origin.sourceEntity;
    if (!(player instanceof Player)) {
      return { status: CustomCommandStatus.Failure, message: "Nur für Spieler." };
    }
    // command callbacks run read-only; do the work in the next tick
    system.run(() => handle(player, parseCommand(a, b, c)));
    return { status: CustomCommandStatus.Success };
  });
});

function handle(player, cmd) {
  switch (cmd.action) {
    case "help": return HELP.forEach((l) => player.sendMessage(l));
    case "error": return player.sendMessage(`§c${cmd.message}`);
    case "list": return formatList([...all().values()]).forEach((l) => player.sendMessage(l));
    case "teleport": return teleport(player, cmd.name);
    case "set": return setVirtual(player, cmd.name);
    case "delete": return del(player, cmd.name);
    case "rename": return rename(player, cmd.name, cmd.newName);
  }
}

function teleport(player, name) {
  const wp = all().get(keyOf(name));
  if (!wp) return player.sendMessage(`§cKeinen Wegpunkt „${name}“ gefunden. §7/warp list zeigt alle.`);
  const dim = world.getDimension(wp.dim);
  const to = arrival(wp);
  if (wp.physical) {
    // don't teleport into blocks someone built on top of the waypoint
    for (const dy of [0, 1]) {
      const b = dim.getBlock({ x: wp.x, y: wp.y + 1 + dy, z: wp.z });
      if (b && !b.isAir) return player.sendMessage(`§cDer Wegpunkt „${wp.name}“ ist zugebaut.`);
    }
  }
  player.teleport(to, { dimension: dim });
  system.runTimeout(() => {
    try { player.playSound("mob.endermen.portal"); } catch { /* player left */ }
  }, 2);
  player.sendMessage(`§6Wegpunkt §e${wp.name}§r`);
  report("teleport", { player: player.name, name: wp.name });
}

function setVirtual(player, name) {
  if (!isOperator(player)) {
    return player.sendMessage("§cNur Operatoren können Wegpunkte ohne Bauwerk setzen. Crafte ein Wegpunkt-Item!");
  }
  const error = validateName(name, keys());
  if (error) return player.sendMessage(`§c${error}`);
  const l = player.location;
  const wp = { v: 1, name: name.trim(), x: l.x, y: l.y, z: l.z, dim: player.dimension.id,
    owner: player.name, created: new Date().toISOString(), physical: false };
  store(wp);
  player.sendMessage(`§6Wegpunkt §e${wp.name}§6 gesetzt (ohne Bauwerk).`);
  report("created", { player: player.name, name: wp.name, physical: false });
}

function del(player, name) {
  const wp = all().get(keyOf(name));
  if (!wp) return player.sendMessage(`§cKeinen Wegpunkt „${name}“ gefunden.`);
  if (!mayChange(player, wp)) return player.sendMessage(`§cDer Wegpunkt „${wp.name}“ gehört ${wp.owner}.`);
  remove(keyOf(wp.name));
  player.sendMessage(`§6Wegpunkt §e${wp.name}§6 gelöscht.${wp.physical ? " Das Bauwerk bleibt stehen." : ""}`);
  report("deleted", { player: player.name, name: wp.name });
}

function rename(player, name, newName) {
  const wp = all().get(keyOf(name));
  if (!wp) return player.sendMessage(`§cKeinen Wegpunkt „${name}“ gefunden.`);
  if (!mayChange(player, wp)) return player.sendMessage(`§cDer Wegpunkt „${wp.name}“ gehört ${wp.owner}.`);
  const error = validateName(newName, keys(), keyOf(wp.name));
  if (error) return player.sendMessage(`§c${error}`);
  const oldKey = keyOf(wp.name);
  const old = wp.name;
  store({ ...wp, name: newName.trim() }, oldKey);
  player.sendMessage(`§6Wegpunkt §e${old}§6 heißt jetzt §e${newName.trim()}§6.`);
  report("renamed", { player: player.name, from: old, name: newName.trim() });
}

// ---------- placing the item builds the structure ----------

world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.itemStack?.typeId !== ITEM_ID) return;
  ev.cancel = true; // the item itself is never placed or used up by the game
  if (!ev.isFirstEvent) return;
  const { player, block, blockFace } = ev;
  system.run(() => place(player, block, blockFace));
});

function place(player, block, face) {
  if (face !== Direction.Up) return player.sendMessage("§cDen Wegpunkt bitte auf den Boden setzen (von oben).");
  const dim = block.dimension;
  const center = { x: block.location.x, y: block.location.y + 1, z: block.location.z };

  const problem = placementProblem(dim, center);
  if (problem) return player.sendMessage(`§c${problem}`);
  if (!consumeOne(player)) return;
  build(dim, center);
  try { dim.playSound("block.beacon.activate", center); } catch { /* sound id may vary */ }

  // registered at once with an automatic name, so nothing is lost if the name dialog is cancelled
  const name = provisionalName(keys());
  const wp = { v: 1, name, x: center.x, y: center.y, z: center.z, dim: dim.id,
    owner: player.name, created: new Date().toISOString(), physical: true };
  store(wp);
  report("created", { player: player.name, name, physical: true });
  askName(player, keyOf(name), 0, "");
}

function consumeOne(player) {
  if (player.getGameMode() === GameMode.Creative) return true;
  const container = player.getComponent("minecraft:inventory")?.container;
  const slot = player.selectedSlotIndex;
  const item = container?.getItem(slot);
  if (!item || item.typeId !== ITEM_ID) {
    player.sendMessage("§cDas Wegpunkt-Item muss in der Hand sein.");
    return false;
  }
  if (item.amount > 1) {
    item.amount -= 1;
    container.setItem(slot, item);
  } else {
    container.setItem(slot, undefined);
  }
  return true;
}

function askName(player, key, attempt, error) {
  const form = new ModalFormData()
    .title("Neuer Wegpunkt")
    .textField(`${error ? `§c${error}§r\n` : ""}Wie soll dieser Wegpunkt heißen?`, "z. B. Zuhause");
  form.show(player).then((res) => {
    const wp = all().get(key);
    if (!wp) return; // removed in the meantime
    if (res.canceled) {
      if (res.cancelationReason === "UserBusy" && attempt < NAME_FORM_RETRIES) {
        return system.runTimeout(() => askName(player, key, attempt + 1, error), 20);
      }
      return player.sendMessage(`§6Wegpunkt §e${wp.name}§6 gespeichert. Umbenennen: §e/warp rename "${wp.name}" <Name>`);
    }
    const name = String(res.formValues?.[0] ?? "").trim();
    const problem = validateName(name, keys(), key);
    if (problem) return askName(player, key, 0, problem);
    store({ ...wp, name }, key);
    player.sendMessage(`§6Wegpunkt §e${name}§6 gespeichert. Reisen mit §e/warp ${name.includes(" ") ? `"${name}"` : name}`);
    report("renamed", { player: player.name, from: wp.name, name });
  }).catch(() => { /* player left */ });
}

// ---------- mining the diamond removes the waypoint; explosions spare waypoints ----------

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  if (ev.brokenBlockPermutation.type.id !== "minecraft:diamond_block") return;
  const l = ev.block.location;
  for (const [key, wp] of all()) {
    if (wp.physical && wp.dim === ev.block.dimension.id && wp.x === l.x && wp.y === l.y && wp.z === l.z) {
      remove(key);
      world.sendMessage(`§6Der Wegpunkt §e${wp.name}§6 wurde abgebaut.`);
      report("destroyed", { player: ev.player.name, name: wp.name });
    }
  }
});

world.beforeEvents.explosion.subscribe((ev) => {
  if (!cells || cells.size === 0) return; // nothing loaded yet means no waypoint was touched since start
  const dim = ev.dimension.id;
  const blocks = ev.getImpactedBlocks();
  const kept = blocks.filter((b) => !cells.has(`${dim}|${b.location.x}|${b.location.y}|${b.location.z}`));
  if (kept.length !== blocks.length) ev.setImpactedBlocks(kept);
});

system.run(() => {
  all(); // load once the world is ready, also for the explosion protection
  console.warn(`${TAG} {"v":1,"started":true}`);
  report("loaded", { count: cache.size });
});
