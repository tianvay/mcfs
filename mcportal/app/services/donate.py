"""Tab "Spenden": the admin gives a player (or everybody online) items.

Only items from CATALOG can be given - the console command is built from fixed ids, never from user text.
The item pictures are Mojang's own textures from the official bedrock-samples repository. They are not in
this (public) repository: the portal downloads the few it needs once into /var/lib/mcportal/item-icons/
and shows a coloured placeholder until then.
"""
from __future__ import annotations

import asyncio
import logging
import re
import urllib.request
from pathlib import Path

from ..adapters.base import MinecraftAdapter
from ..adapters.bedrock.commands import valid_player_name
from ..audit import AuditLog
from .minecraft import MinecraftService, PortalError

log = logging.getLogger("mcportal.donate")

ALL_ONLINE = "@a"
MAX_AMOUNT = 999
MAX_STACKS = 36  # a full inventory
ICON_SOURCE = "https://raw.githubusercontent.com/Mojang/bedrock-samples/v1.26.60.5/resource_pack/textures/{}.png"
ICON_MAX_BYTES = 64 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
USER_AGENT = "mcportal (family server portal)"

CATEGORIES = [
    ("popular", "Beliebt"), ("tools", "Werkzeug"), ("armor", "Rüstung"), ("food", "Essen"),
    ("blocks", "Blöcke"), ("valuable", "Wertvoll"), ("misc", "Sonstiges"),
]

# (Bedrock item id, German name, category, texture below resource_pack/textures, stack size, popular)
_ITEMS = [
    # valuables
    ("diamond", "Diamant", "valuable", "items/diamond", 64, True),
    ("iron_ingot", "Eisenbarren", "valuable", "items/iron_ingot", 64, True),
    ("gold_ingot", "Goldbarren", "valuable", "items/gold_ingot", 64, False),
    ("copper_ingot", "Kupferbarren", "valuable", "items/copper_ingot", 64, False),
    ("netherite_ingot", "Netheritbarren", "valuable", "items/netherite_ingot", 64, False),
    ("emerald", "Smaragd", "valuable", "items/emerald", 64, True),
    ("coal", "Kohle", "valuable", "items/coal", 64, False),
    ("redstone", "Redstone", "valuable", "items/redstone_dust", 64, False),
    ("lapis_lazuli", "Lapislazuli", "valuable", "items/dye_powder_blue", 64, False),
    ("quartz", "Netherquarz", "valuable", "items/quartz", 64, False),
    ("amethyst_shard", "Amethystscherbe", "valuable", "items/amethyst_shard", 64, False),
    ("diamond_block", "Diamantblock", "valuable", "blocks/diamond_block", 64, False),
    ("iron_block", "Eisenblock", "valuable", "blocks/iron_block", 64, False),
    ("gold_block", "Goldblock", "valuable", "blocks/gold_block", 64, False),
    ("emerald_block", "Smaragdblock", "valuable", "blocks/emerald_block", 64, False),
    # tools and weapons
    ("diamond_sword", "Diamantschwert", "tools", "items/diamond_sword", 1, True),
    ("diamond_pickaxe", "Diamantspitzhacke", "tools", "items/diamond_pickaxe", 1, True),
    ("diamond_axe", "Diamantaxt", "tools", "items/diamond_axe", 1, False),
    ("diamond_shovel", "Diamantschaufel", "tools", "items/diamond_shovel", 1, False),
    ("diamond_hoe", "Diamanthacke", "tools", "items/diamond_hoe", 1, False),
    ("netherite_sword", "Netheritschwert", "tools", "items/netherite_sword", 1, False),
    ("netherite_pickaxe", "Netheritspitzhacke", "tools", "items/netherite_pickaxe", 1, False),
    ("iron_sword", "Eisenschwert", "tools", "items/iron_sword", 1, False),
    ("iron_pickaxe", "Eisenspitzhacke", "tools", "items/iron_pickaxe", 1, False),
    ("iron_axe", "Eisenaxt", "tools", "items/iron_axe", 1, False),
    ("iron_shovel", "Eisenschaufel", "tools", "items/iron_shovel", 1, False),
    ("bow", "Bogen", "tools", "items/bow_standby", 1, False),
    ("crossbow", "Armbrust", "tools", "items/crossbow_standby", 1, False),
    ("arrow", "Pfeil", "tools", "items/arrow", 64, False),
    ("trident", "Dreizack", "tools", "items/trident", 1, False),
    ("fishing_rod", "Angel", "tools", "items/fishing_rod_uncast", 1, False),
    ("shears", "Schere", "tools", "items/shears", 1, False),
    ("flint_and_steel", "Feuerzeug", "tools", "items/flint_and_steel", 1, False),
    ("bucket", "Eimer", "tools", "items/bucket_empty", 16, False),
    ("water_bucket", "Wassereimer", "tools", "items/bucket_water", 1, False),
    ("lava_bucket", "Lavaeimer", "tools", "items/bucket_lava", 1, False),
    # armour
    ("diamond_helmet", "Diamanthelm", "armor", "items/diamond_helmet", 1, False),
    ("diamond_chestplate", "Diamantharnisch", "armor", "items/diamond_chestplate", 1, False),
    ("diamond_leggings", "Diamantbeinschutz", "armor", "items/diamond_leggings", 1, False),
    ("diamond_boots", "Diamantstiefel", "armor", "items/diamond_boots", 1, False),
    ("netherite_helmet", "Netherithelm", "armor", "items/netherite_helmet", 1, False),
    ("netherite_chestplate", "Netheritharnisch", "armor", "items/netherite_chestplate", 1, False),
    ("netherite_leggings", "Netheritbeinschutz", "armor", "items/netherite_leggings", 1, False),
    ("netherite_boots", "Netheritstiefel", "armor", "items/netherite_boots", 1, False),
    ("iron_helmet", "Eisenhelm", "armor", "items/iron_helmet", 1, False),
    ("iron_chestplate", "Eisenharnisch", "armor", "items/iron_chestplate", 1, False),
    ("iron_leggings", "Eisenbeinschutz", "armor", "items/iron_leggings", 1, False),
    ("iron_boots", "Eisenstiefel", "armor", "items/iron_boots", 1, False),
    ("turtle_helmet", "Schildkrötenpanzer", "armor", "items/turtle_helmet", 1, False),
    ("elytra", "Elytren", "armor", "items/elytra", 1, True),
    # food
    ("bread", "Brot", "food", "items/bread", 64, True),
    ("cooked_beef", "Steak", "food", "items/beef_cooked", 64, True),
    ("cooked_porkchop", "Gebratenes Schweinefleisch", "food", "items/porkchop_cooked", 64, False),
    ("cooked_chicken", "Gebratenes Hühnchen", "food", "items/chicken_cooked", 64, False),
    ("cooked_salmon", "Gebratener Lachs", "food", "items/fish_salmon_cooked", 64, False),
    ("baked_potato", "Ofenkartoffel", "food", "items/potato_baked", 64, False),
    ("apple", "Apfel", "food", "items/apple", 64, False),
    ("golden_apple", "Goldener Apfel", "food", "items/apple_golden", 64, True),
    ("golden_carrot", "Goldene Karotte", "food", "items/carrot_golden", 64, False),
    ("melon_slice", "Melonenscheibe", "food", "items/melon", 64, False),
    ("sweet_berries", "Süßbeeren", "food", "items/sweet_berries", 64, False),
    ("cookie", "Keks", "food", "items/cookie", 64, False),
    ("pumpkin_pie", "Kürbiskuchen", "food", "items/pumpkin_pie", 64, False),
    ("cake", "Kuchen", "food", "items/cake", 1, False),
    ("honey_bottle", "Honigflasche", "food", "items/honey_bottle", 16, False),
    # blocks
    ("torch", "Fackel", "blocks", "blocks/torch_on", 64, True),
    ("oak_log", "Eichenstamm", "blocks", "blocks/log_oak", 64, True),
    ("oak_planks", "Eichenbretter", "blocks", "blocks/planks_oak", 64, False),
    ("cobblestone", "Bruchstein", "blocks", "blocks/cobblestone", 64, False),
    ("stone_bricks", "Steinziegel", "blocks", "blocks/stonebrick", 64, False),
    ("bricks", "Ziegelsteine", "blocks", "blocks/brick", 64, False),
    ("glass", "Glas", "blocks", "blocks/glass", 64, False),
    ("white_wool", "Weiße Wolle", "blocks", "blocks/wool_colored_white", 64, False),
    ("obsidian", "Obsidian", "blocks", "blocks/obsidian", 64, False),
    ("glowstone", "Leuchtstein", "blocks", "blocks/glowstone", 64, False),
    ("sea_lantern", "Seelaterne", "blocks", "blocks/sea_lantern", 64, False),
    ("lantern", "Laterne", "blocks", "items/lantern", 64, False),
    ("bookshelf", "Bücherregal", "blocks", "blocks/bookshelf", 64, False),
    ("crafting_table", "Werkbank", "blocks", "blocks/crafting_table_front", 64, False),
    ("furnace", "Ofen", "blocks", "blocks/furnace_front_off", 64, False),
    ("tnt", "TNT", "blocks", "blocks/tnt_side", 64, False),
    ("oak_sapling", "Eichensetzling", "blocks", "blocks/sapling_oak", 64, False),
    ("rail", "Schiene", "blocks", "blocks/rail_normal", 64, False),
    # other
    ("ender_pearl", "Enderperle", "misc", "items/ender_pearl", 16, False),
    ("ender_eye", "Enderauge", "misc", "items/ender_eye", 64, False),
    ("experience_bottle", "Erfahrungsfläschchen", "misc", "items/experience_bottle", 64, True),
    ("totem_of_undying", "Totem der Unsterblichkeit", "misc", "items/totem", 1, False),
    ("name_tag", "Namensschild", "misc", "items/name_tag", 64, False),
    ("lead", "Leine", "misc", "items/lead", 64, False),
    ("saddle", "Sattel", "misc", "items/saddle", 1, False),
    ("oak_boat", "Eichenboot", "misc", "items/boat_oak", 1, False),
    ("minecart", "Lore", "misc", "items/minecart_normal", 1, False),
    ("red_bed", "Rotes Bett", "misc", "items/bed_red", 1, False),
    ("book", "Buch", "misc", "items/book_normal", 64, False),
    ("empty_map", "Leere Karte", "misc", "items/map_empty", 64, False),
    ("firework_rocket", "Feuerwerksrakete", "misc", "items/fireworks", 64, False),
    ("bone_meal", "Knochenmehl", "misc", "items/dye_powder_white_new", 64, False),
]

CATALOG = {i[0]: {"id": i[0], "name": i[1], "cat": i[2], "texture": i[3], "stack": i[4], "popular": i[5]}
           for i in _ITEMS}
_ITEM_ID = re.compile(r"^[a-z0-9_]{1,40}$")


def max_amount(item: dict) -> int:
    return min(MAX_AMOUNT, item["stack"] * MAX_STACKS)


class DonateService:
    def __init__(self, adapter: MinecraftAdapter, mc: MinecraftService, audit: AuditLog, data_dir: Path):
        self.a = adapter
        self.mc = mc
        self.audit = audit
        self.icon_dir = data_dir / "item-icons"
        self._task: asyncio.Task | None = None

    async def startup(self) -> None:
        if self._missing_icons():
            self._task = asyncio.create_task(asyncio.to_thread(self._fetch_icons))

    # ---------- icons ----------

    def _missing_icons(self) -> list[dict]:
        return [i for i in CATALOG.values() if not (self.icon_dir / f"{i['id']}.png").exists()]

    def _fetch_icons(self) -> None:
        self.icon_dir.mkdir(parents=True, exist_ok=True)
        fetched = 0
        for item in self._missing_icons():
            try:
                req = urllib.request.Request(ICON_SOURCE.format(item["texture"]), headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read(ICON_MAX_BYTES + 1)
                if len(data) > ICON_MAX_BYTES or not data.startswith(PNG_MAGIC):
                    raise ValueError("kein passendes PNG")
                tmp = self.icon_dir / f"{item['id']}.png.tmp"
                tmp.write_bytes(data)
                tmp.replace(self.icon_dir / f"{item['id']}.png")
                fetched += 1
            except Exception as e:  # no internet, renamed texture ... - the page shows a placeholder
                log.warning("item icon %s not loaded: %s", item["id"], e)
        log.info("item icons: %d loaded, %d missing", fetched, len(self._missing_icons()))

    def icon_path(self, item_id: str) -> Path:
        if item_id not in CATALOG:
            raise PortalError("Unbekanntes Item", 404)
        path = self.icon_dir / f"{item_id}.png"
        if not path.exists():
            raise PortalError("Symbol noch nicht geladen", 404)
        return path

    # ---------- catalog / history ----------

    def summary(self) -> dict:
        online = sorted(self.mc.tracker.players.values(), key=lambda p: p.name.lower())
        online_names = {p.name.lower() for p in online}
        offline = []
        try:
            offline = sorted({e.get("name", "") for e in self.a.files.read_allowlist()
                              if e.get("name") and e["name"].lower() not in online_names}, key=str.lower)
        except (OSError, ValueError):
            pass
        icons = {i for i in CATALOG if (self.icon_dir / f"{i}.png").exists()}
        recent = [{"time": e["time"], "player": e.get("player"), "item": e.get("item"), "count": e.get("count")}
                  for e in self.audit.tail(200) if e.get("action") == "DONATE" and e.get("result") == "SUCCESS"][:8]
        return {
            "online": [p.name for p in online],
            "offline": offline,
            "console": self.a.console_available(),
            "categories": [{"id": c, "name": n} for c, n in CATEGORIES],
            "items": [{"id": i["id"], "name": i["name"], "cat": i["cat"], "stack": i["stack"],
                       "popular": i["popular"], "max": max_amount(i), "icon": i["id"] in icons}
                      for i in CATALOG.values()],
            "recent": recent,
        }

    # ---------- give ----------

    async def give(self, player: str, item_id: str, count: int, user: str) -> dict:
        item = CATALOG.get(item_id) if _ITEM_ID.match(item_id or "") else None
        if item is None:
            raise PortalError("Unbekanntes Item")
        if not 1 <= count <= max_amount(item):
            raise PortalError(f"Menge muss zwischen 1 und {max_amount(item)} liegen")
        online = {p.name.lower(): p.name for p in self.mc.tracker.players.values()}
        if player == ALL_ONLINE:
            if not online:
                raise PortalError("Gerade ist niemand online", 409)
            target, shown = ALL_ONLINE, "alle online"
        else:
            if not valid_player_name(player):
                raise PortalError("Ungültiger Spielername")
            if player.lower() not in online:
                raise PortalError(f"{player} ist nicht online – Geschenke gehen nur an Spieler im Spiel", 409)
            target = shown = online[player.lower()]
        if not self.a.console_available():
            raise PortalError("Die Server-Konsole ist nicht erreichbar (Server aus?)", 409)
        try:
            await asyncio.to_thread(self.a.give_live, target, item["id"], count, item["name"])
        except Exception as e:
            self.audit.write("DONATE", "FAILED", user, player=shown, item=item["id"], count=count, error=str(e))
            raise PortalError(f"Spenden fehlgeschlagen: {e}", 500) from e
        self.audit.write("DONATE", "SUCCESS", user, player=shown, item=item["id"], count=count)
        return {"player": shown, "item": item["id"], "name": item["name"], "count": count}
