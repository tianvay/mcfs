// Minecraft Family Portal - Sterntaler & shop (behavior pack, change M19)
//
//  * Sterntaler are earned at the timed events: the events pack tells every pack what happened
//    (system.sendScriptEvent "mcfs:event_news"); core.REWARDS says what it is worth (5 for taking part ...).
//  * The account of each player lives in the world (dynamic property "mcfs_shop:<name>", survives restarts).
//  * /shop (mcfs:shop) opens the shop: balance, offer, buying. Items of this pack (items/*.json):
//      Bergbrecher     pickaxe, takes natural rock and ores in 3 x 3 x 3 along (sneaking: one block)
//      Holzfäller-Axt  fells the whole tree (logs with leaves only; sneaking: one block)
//      Magnet-Amulett  pulls items lying around within 8 blocks while in the hotbar or off hand (sneaking: pause)
//      Ernte-Sichel    use on a field: ripe crops in 3 x 3 are harvested and planted again
//  * Console / portal: /scriptevent mcfs:shop grant <+/-n> <name> | seed <n> <name> | balances
//  * Log lines for the portal: [mcportal-shop] {"v":1,"event":"booking","player":..,"delta":..,"reason":..,
//    "detail":..,"balance":..,"earned":..}; at startup the catalog and all balances.
// Uses only stable APIs (@minecraft/server, @minecraft/server-ui) - no experiments in the world.
// console.warn on purpose: the server runs with content-log-level=warning.
import {
  CommandPermissionLevel, CustomCommandStatus, EquipmentSlot, GameMode, ItemStack, Player, ScriptEventSource, system,
  world,
} from "@minecraft/server";
import { ActionFormData, MessageFormData } from "@minecraft/server-ui";
import {
  book, canAfford, CURRENCY, isCrop, isCubeBlock, isLog, ITEMS, MAGNET_RADIUS, MAGNET_WAIT_TICKS, parseControl,
  PROP_PREFIX, readAccount, REASON_TEXT, REWARDS, rewardsFor, wear,
} from "./core.js";
import { breakBlock, breakCube, fellTree, harvest } from "./work.js";

const TAG = "[mcportal-shop]";
const PICKAXE = "mcfs:bergbrecher";
const AXE = "mcfs:holzfaeller";
const MAGNET = "mcfs:magnet";
const SICKLE = "mcfs:erntesichel";
const FORM_RETRIES = 15; // a form can't open while the chat (where /shop was typed) is still open
const MAGNET_TICKS = 10;

function report(event, data) {
  console.warn(`${TAG} ${JSON.stringify({ v: 1, event, ...data })}`);
}

// ---------- accounts ----------

/** name -> account; read lazily (dynamic properties are not readable during early execution) */
const accounts = new Map();

function account(name) {
  let a = accounts.get(name);
  if (!a) {
    a = readAccount(world.getDynamicProperty(PROP_PREFIX + name));
    accounts.set(name, a);
  }
  return a;
}

/** book Sterntaler for a player (online or not); returns what was really booked */
function booking(name, amount, reason, detail) {
  const before = account(name);
  if (reason === "seed" && before.s) {
    report("seed_skipped", { player: name }); // the portal asked twice - once is enough
    return 0;
  }
  const { account: after, delta } = book(before, amount, reason);
  accounts.set(name, after);
  world.setDynamicProperty(PROP_PREFIX + name, JSON.stringify(after));
  report("booking", { player: name, delta, reason, detail, balance: after.b, earned: after.e });
  const player = world.getAllPlayers().find((p) => p.name === name);
  if (player && delta && reason !== "buy") {
    const sign = delta > 0 ? `§a+${delta}` : `§c${delta}`;
    try {
      player.sendMessage(`§6[${CURRENCY}] ${sign} §f${REASON_TEXT[reason] ?? reason} §7– Kontostand ${after.b}. `
        + "Einkaufen mit /shop");
      if (delta > 0) player.playSound("random.orb");
    } catch { /* left */ }
  }
  return delta;
}

function reportBalances() {
  const players = {};
  for (const id of world.getDynamicPropertyIds()) {
    if (!id.startsWith(PROP_PREFIX)) continue;
    const a = account(id.slice(PROP_PREFIX.length));
    players[id.slice(PROP_PREFIX.length)] = { balance: a.b, earned: a.e };
  }
  report("balances", { players });
}

// ---------- news from the events pack, commands from the console ----------

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  // only scripts and the console (Server source); /scriptevent typed by a player can't mint Sterntaler
  if (ev.sourceType !== ScriptEventSource.Server) return;
  if (ev.id === "mcfs:event_news") {
    let n;
    try { n = JSON.parse(ev.message); } catch { return; }
    for (const r of rewardsFor(n)) booking(r.player, r.amount, r.reason, r.detail);
  } else if (ev.id === "mcfs:shop") {
    const cmd = parseControl(ev.message);
    if (cmd.action === "balances") reportBalances();
    else if (cmd.action === "grant") booking(cmd.name, cmd.amount, "admin");
    else if (cmd.action === "seed") booking(cmd.name, cmd.amount, "seed");
    else report("control", { error: cmd.message });
  }
});

// ---------- /shop ----------

system.beforeEvents.startup.subscribe((ev) => {
  ev.customCommandRegistry.registerCommand({
    name: "mcfs:shop",
    description: `${CURRENCY}-Shop: Kontostand ansehen und einkaufen`,
    permissionLevel: CommandPermissionLevel.Any,
  }, (origin) => {
    const player = origin.sourceEntity;
    if (!(player instanceof Player)) {
      return { status: CustomCommandStatus.Failure, message: "Nur für Spieler." };
    }
    // command callbacks run read-only; open the form in the next tick
    system.run(() => openShop(player, 0));
    return { status: CustomCommandStatus.Success };
  });
});

/** show a form; while the player is busy (chat still open) try again for a few seconds */
function show(form, player, attempt, then) {
  form.show(player).then((res) => {
    if (res.canceled) {
      if (res.cancelationReason === "UserBusy" && attempt < FORM_RETRIES) {
        system.runTimeout(() => { if (player.isValid) show(form, player, attempt + 1, then); }, 20);
      }
      return;
    }
    then(res);
  }).catch(() => { /* player left */ });
}

function openShop(player, attempt) {
  const a = account(player.name);
  const form = new ActionFormData()
    .title(`${CURRENCY}-Shop`)
    .body(`Dein Kontostand: §6${a.b} ${CURRENCY}§r\n${CURRENCY} gibt es für die Events auf dem Server.`);
  for (const item of ITEMS) {
    form.button(`${item.name}\n§6${item.price} ${CURRENCY}`, `textures/items/${item.id.replace(":", "_")}`);
  }
  form.button(`Wie bekomme ich ${CURRENCY}?`);
  show(form, player, attempt, (res) => {
    const item = ITEMS[res.selection];
    if (item) return offer(player, item);
    if (res.selection === ITEMS.length) return explain(player);
  });
}

function offer(player, item) {
  const a = account(player.name);
  const enough = canAfford(a, item);
  const form = new MessageFormData()
    .title(item.name)
    .body(`${item.desc}\n\nPreis: §6${item.price} ${CURRENCY}§r\nDein Kontostand: §6${a.b}§r\n`
      + (enough ? `Danach: ${a.b - item.price}` : `§cDir fehlen noch ${item.price - a.b} ${CURRENCY}.`))
    .button1(enough ? "Kaufen" : "Schade")
    .button2("Zurück");
  show(form, player, 0, (res) => {
    if (res.selection === 1) return openShop(player, 0);
    if (enough) buy(player, item);
  });
}

function explain(player) {
  const lines = [
    `Bei einem Event dabei sein: ${REWARDS.participation}`,
    `Kopfgeld-Boss besiegen (alle Jäger): +${REWARDS.bounty}`,
    `Schatz finden: +${REWARDS.treasure_found}`,
    `Hexenzirkel sprengen, Fluch brechen: +${REWARDS.coven_defeated}`,
    `Meteoriteneinschlag miterleben: +${REWARDS.meteor_hit}`,
    `Blitz im Unwetter überleben: +${REWARDS.lightning_survived}`,
    `Sternstück aufsammeln: +${REWARDS.star}`,
  ];
  const form = new MessageFormData().title(`${CURRENCY} verdienen`).body(lines.join("\n"))
    .button1("Schließen").button2("Zurück");
  show(form, player, 0, (res) => { if (res.selection === 1) openShop(player, 0); });
}

function buy(player, item) {
  if (!player.isValid) return;
  if (!canAfford(account(player.name), item)) {
    return player.sendMessage(`§cDafür reichen deine ${CURRENCY} nicht mehr.`);
  }
  let stack;
  try {
    stack = new ItemStack(item.id, 1);
  } catch (e) {
    report("error", { error: `item ${item.id}: ${e}` });
    return player.sendMessage("§cDieser Gegenstand ist gerade nicht zu haben.");
  }
  booking(player.name, -item.price, "buy", item.id);
  const rest = player.getComponent("minecraft:inventory")?.container?.addItem(stack);
  if (rest) player.dimension.spawnItem(rest, player.location); // inventory full: it lies at the feet
  player.sendMessage(`§6[${CURRENCY}] §fGekauft: §e${item.name}§f für ${item.price} ${CURRENCY} `
    + `§7– Kontostand ${account(player.name).b}`);
  try { player.playSound("random.levelup"); } catch { /* sound id may vary */ }
}

// ---------- tools: wear ----------

const equipment = (player) => player.getComponent("minecraft:equippable");
const isCreative = (player) => player.getGameMode() === GameMode.Creative;

const damageOf = (item) => {
  try { return item?.getComponent("minecraft:durability")?.damage; } catch { return undefined; }
};

/** the tool of type `id` in the main hand takes `uses` damage and breaks when it is worn out */
function wearHeld(player, id, uses) {
  if (uses <= 0 || isCreative(player)) return;
  try {
    const eq = equipment(player);
    const item = eq?.getEquipment(EquipmentSlot.Mainhand);
    if (item?.typeId !== id) return;
    const d = item.getComponent("minecraft:durability");
    if (!d) return;
    const w = wear(d.damage, d.maxDurability, uses);
    if (w.broken) {
      eq.setEquipment(EquipmentSlot.Mainhand, undefined);
      player.playSound("random.break");
      return;
    }
    d.damage = w.damage;
    eq.setEquipment(EquipmentSlot.Mainhand, item);
  } catch (e) {
    report("error", { error: `wear ${id}: ${e}` });
  }
}

// ---------- Bergbrecher, Holzfäller-Axt ----------

let hedged = false;

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  const tool = ev.itemStackBeforeBreak?.typeId;
  if (tool !== PICKAXE && tool !== AXE) return;
  const { player, block } = ev;
  const dim = block.dimension;
  const at = block.location;
  const brokenId = ev.brokenBlockPermutation.type.id;
  // own items lose nothing by themselves when mining - unless a later game version starts doing it
  const before = damageOf(ev.itemStackBeforeBreak);
  const after = damageOf(ev.itemStackAfterBreak);
  const own = after !== undefined && before !== undefined && after > before ? 0 : 1;
  let extra = 0;
  if (!player.isSneaking) {
    if (tool === PICKAXE && isCubeBlock(brokenId)) extra = breakCube(dim, at);
    if (tool === AXE && isLog(brokenId)) extra = fellTree(dim, at);
  }
  wearHeld(player, tool, own + extra);
  if (tool === PICKAXE && isCubeBlock(brokenId) && !isCreative(player)) {
    // safety net: should the game not accept the Bergbrecher as a diamond pickaxe for this block, nothing drops.
    // Then the block comes back for a moment and is broken like the ones around it.
    const perm = ev.brokenBlockPermutation;
    system.runTimeout(() => {
      try {
        const center = { x: at.x + 0.5, y: at.y + 0.5, z: at.z + 0.5 };
        if (dim.getEntities({ type: "minecraft:item", location: center, maxDistance: 1.5 }).length) return;
        const b = dim.getBlock(at);
        if (!b?.isAir) return;
        b.setPermutation(perm);
        breakBlock(dim, at);
        if (!hedged) report("hedge", { block: brokenId }); // once per run: worth a look at the item definition
        hedged = true;
      } catch { /* unloaded */ }
    }, 1);
  }
});

// ---------- Ernte-Sichel ----------

world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.itemStack?.typeId !== SICKLE || !ev.isFirstEvent) return;
  const { player, block } = ev;
  const dim = block.dimension;
  // on the plant itself or on the farmland / soul sand under it
  const at = isCrop(block.typeId) ? block.location : { ...block.location, y: block.location.y + 1 };
  system.run(() => {
    if (!player.isValid) return;
    const n = harvest(dim, at);
    if (!n) {
      try { player.onScreenDisplay.setActionBar("§7Hier ist nichts reif."); } catch { /* left */ }
      return;
    }
    wearHeld(player, SICKLE, n);
    try { dim.playSound("dig.grass", at); } catch { /* sound id may vary */ }
  });
});

// ---------- Magnet-Amulett ----------

/** item entity id -> tick it was first seen near a magnet */
const seen = new Map();

function hasMagnet(player) {
  try {
    if (equipment(player)?.getEquipment(EquipmentSlot.Offhand)?.typeId === MAGNET) return true;
    const c = player.getComponent("minecraft:inventory")?.container;
    for (let i = 0; c && i < 9; i++) if (c.getItem(i)?.typeId === MAGNET) return true;
  } catch { /* left */ }
  return false;
}

system.runInterval(() => {
  const now = system.currentTick;
  for (const player of world.getAllPlayers()) {
    if (!player.isValid || player.isSneaking || !hasMagnet(player)) continue;
    let items = [];
    try {
      items = player.dimension.getEntities({ type: "minecraft:item", location: player.location,
        maxDistance: MAGNET_RADIUS });
    } catch { continue; }
    for (const item of items) {
      const first = seen.get(item.id);
      if (first === undefined) { seen.set(item.id, now); continue; }
      if (now - first < MAGNET_WAIT_TICKS) continue;
      try { item.teleport(player.location); } catch { /* picked up meanwhile */ }
    }
  }
  if (seen.size > 400) for (const [id, t] of seen) if (now - t > 20 * 300) seen.delete(id);
}, MAGNET_TICKS);

// ---------- start ----------

system.run(() => {
  report("catalog", { currency: CURRENCY, items: ITEMS, rewards: REWARDS });
  reportBalances();
  console.warn(`${TAG} {"v":1,"started":true}`);
});
