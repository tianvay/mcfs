"""Builds app/services/items.json - the item catalog of the tab "Spenden" - from Mojang's bedrock-samples.

    python tools/make_item_catalog.py            # uses the release pinned in app/services/donate.py

Sources (all from https://github.com/Mojang/bedrock-samples at the pinned release tag):
  metadata/vanilladata_modules/mojang-items.json   every item id the game knows
  resource_pack/texts/en_US.lang                   English names (fallback: the id in words)
  resource_pack/textures/item_texture.json,
  resource_pack/textures/terrain_texture.json,
  resource_pack/blocks.json                        which picture belongs to which item
Only ids, names and texture paths end up in items.json; the pictures themselves are fetched by the portal
on demand (they are Mojang's and stay out of this public repository).
Run again after a Minecraft update: new items appear, the tag in donate.py says which release is used.
"""
from __future__ import annotations

import itertools
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.services.donate import SAMPLES_TAG  # noqa: E402

RAW = f"https://raw.githubusercontent.com/Mojang/bedrock-samples/{SAMPLES_TAG}/"
API = "https://api.github.com/repos/Mojang/bedrock-samples/"
OUT = ROOT / "app" / "services" / "items.json"
UA = {"User-Agent": "mcportal catalog builder"}

# not something to hand out: admin/technical blocks, education edition, things without a usable item
EXCLUDE = re.compile(
    r"^(allow|deny|barrier|border_block|structure_block|structure_void|jigsaw|command_block|chain_command_block|"
    r"repeating_command_block|command_block_minecart|light_block_\d+|mob_spawner|trial_spawner|vault|"
    r"frosted_ice|ice_crystal|icicle|filled_map|agent_spawn_egg|npc_spawn_egg|farmland|"
    r"unknown|info_update\d*|reserved\d*|moving_block|camera|chalkboard|board|portfolio|"
    r"element_\d+|compound|.*_glow_stick|balloon|sparkler|medicine|bleach|ice_bomb|rapid_fertilizer)$")
# experimental in this release (need world experiments, "give" would fail)
EXPERIMENTAL = re.compile(r"^(poplar_.*|.*sulfur.*|.*cinnabar.*)$")

# items whose picture does not follow from the id
TEXTURE_OVERRIDES = {
    "beef": "items/beef_raw", "chicken": "items/chicken_raw", "mutton": "items/mutton_raw",
    "porkchop": "items/porkchop_raw", "cod": "items/fish_raw", "cooked_cod": "items/fish_cooked",
    "tropical_fish": "items/fish_clownfish_raw", "tropical_fish_bucket": "items/bucket_tropical",
    "tropical_fish_spawn_egg": "items/egg_clownfish", "zombie_pigman_spawn_egg": "items/egg_pigzombie",
    "book": "items/book_normal", "bow": "items/bow_standby", "crossbow": "items/crossbow_standby",
    "clock": "items/clock_item", "compass": "items/compass_item", "lodestone_compass": "items/lodestonecompass_item",
    "enchanted_golden_apple": "items/apple_golden", "fire_charge": "items/fireball",
    "firework_rocket": "items/fireworks", "firework_star": "items/fireworks_charge",
    "glass_bottle": "items/potion_bottle_empty", "potion": "items/potion_bottle_drinkable",
    "splash_potion": "items/potion_bottle_splash", "lingering_potion": "items/potion_bottle_lingering",
    "glistering_melon_slice": "items/melon_speckled", "melon_slice": "items/melon",
    "ink_sac": "items/dye_powder_black", "glow_ink_sac": "items/dye_powder_glow", "cocoa_beans": "items/dye_powder_brown",
    "lapis_lazuli": "items/dye_powder_blue", "bone_meal": "items/dye_powder_white",
    "black_dye": "items/dye_powder_black_new", "blue_dye": "items/dye_powder_blue_new",
    "brown_dye": "items/dye_powder_brown_new", "white_dye": "items/dye_powder_white_new",
    "light_gray_dye": "items/dye_powder_silver",
    "redstone": "items/redstone_dust", "slime_ball": "items/slimeball", "sugar_cane": "items/reeds",
    "totem_of_undying": "items/totem", "turtle_scute": "items/turtle_shell_piece", "minecart": "items/minecart_normal",
    "iron_chain": "items/chain", "sea_lantern": "blocks/sea_lantern", "grass_block": "blocks/grass_side_carried",
    "oak_sign": "items/sign", "dark_oak_sign": "items/sign_darkoak", "banner": "items/banner_pattern",
    "leather_helmet": "items/leather_chestplate", "leather_leggings": "items/leather_chestplate",
    "leather_boots": "items/leather_chestplate", "frostbite_spawn_egg": "items/egg_frostbite",
    "shield": None,  # only an entity texture sheet exists
    "short_grass": "blocks/tallgrass", "oak_leaves": "blocks/leaves_oak_opaque",
    "dark_oak_leaves": "blocks/leaves_big_oak_opaque", "mangrove_leaves": "blocks/mangrove_leaves_opaque",
    "pale_oak_leaves": "blocks/pale_oak_leaves_opaque", "shelf_mushroom": "blocks/shelf_mushroom_small",
}
for wood in ("acacia", "birch", "jungle", "spruce"):
    TEXTURE_OVERRIDES[f"{wood}_leaves"] = f"blocks/leaves_{wood}_opaque"
for color in ("cyan", "gray", "green", "light_blue", "lime", "magenta", "orange", "pink", "purple", "red", "yellow"):
    TEXTURE_OVERRIDES[f"{color}_dye"] = f"items/dye_powder_{color}"
for disc in ("11", "13", "5", "blocks", "cat", "chirp", "far", "mall", "mellohi", "otherside", "pigstep", "stal",
             "strad", "wait", "ward"):
    TEXTURE_OVERRIDES[f"music_disc_{disc}"] = f"items/record_{disc}"

FOOD = set("""apple golden_apple enchanted_golden_apple bread cookie cake pumpkin_pie beef cooked_beef porkchop
cooked_porkchop chicken cooked_chicken mutton cooked_mutton rabbit cooked_rabbit cod cooked_cod salmon cooked_salmon
tropical_fish pufferfish potato baked_potato poisonous_potato carrot golden_carrot beetroot beetroot_soup
mushroom_stew rabbit_stew suspicious_stew melon_slice glistering_melon_slice sweet_berries glow_berries dried_kelp
honey_bottle chorus_fruit popped_chorus_fruit rotten_flesh spider_eye milk_bucket""".split())
VALUABLE = re.compile(r"^(diamond|emerald|coal|charcoal|redstone|lapis_lazuli|quartz|amethyst_shard|netherite_scrap|"
                      r"ancient_debris|nether_star|heart_of_the_sea|echo_shard|experience_bottle|enchanted_book|"
                      r"\w+_ingot|raw_\w+|\w+_nugget|(diamond|emerald|gold|iron|netherite|lapis|redstone|coal|copper|"
                      r"raw_iron|raw_gold|raw_copper)_block)$")
ARMOR = re.compile(r"(_helmet|_chestplate|_leggings|_boots|^elytra|_horse_armor|_nautilus_armor|^wolf_armor)$")
TOOLS = re.compile(r"(_sword|_pickaxe|_axe|_shovel|_hoe|_spear|^bow|^crossbow|^trident|^mace|arrow|^fishing_rod|"
                   r"^shears|^flint_and_steel|^brush|^spyglass|^shield|^compass|^recovery_compass|^lodestone_compass|"
                   r"^clock|bucket|_on_a_stick|^lead|^name_tag|^wind_charge|^fire_charge|^totem_of_undying|^saddle)$")
# Bedrock stack sizes that are not 64
STACK_1 = re.compile(r"(_sword|_pickaxe|_axe|_shovel|_hoe|_spear|_helmet|_chestplate|_leggings|_boots|_horse_armor|"
                     r"_nautilus_armor|^bed|^bow|^crossbow|^trident|^mace|^fishing_rod|^shears|^flint_and_steel|^brush|"
                     r"^spyglass|^shield|^elytra|^wolf_armor|_bucket|_boat|_raft|minecart|^saddle|_harness|_bed|^cake|"
                     r"_soup|_stew|potion|^music_disc_\w+|^enchanted_book|^writable_book|^written_book|^totem_of_undying|"
                     r"_on_a_stick|bundle|^goat_horn|_banner_pattern)$")
STACK_16 = re.compile(r"^(bucket|ender_pearl|snowball|egg|blue_egg|brown_egg|honey_bottle|armor_stand|banner|"
                      r"\w+_banner|\w+_sign|\w+_hanging_sign|wind_charge)$")
POPULAR = ["diamond", "iron_ingot", "emerald", "golden_apple", "bread", "cooked_beef", "torch", "oak_log",
           "diamond_sword", "diamond_pickaxe", "elytra", "experience_bottle", "ender_pearl", "cow_spawn_egg",
           "totem_of_undying", "saddle"]


def fetch(path: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(path, headers=UA), timeout=60) as r:
        return r.read()


def jload(data: bytes):
    text = re.sub(r"^\s*//.*$", "", data.decode("utf-8-sig"), flags=re.M)
    return json.loads(text)


def png_list() -> set[str]:
    res = jload(fetch(f"{API}contents/resource_pack?ref={SAMPLES_TAG}"))
    sha = next(x["sha"] for x in res if x["name"] == "textures")
    tree = jload(fetch(f"{API}git/trees/{sha}?recursive=1"))
    if tree.get("truncated"):
        raise SystemExit("texture list truncated")
    return {x["path"][:-4] for x in tree["tree"] if x["type"] == "blob" and x["path"].endswith(".png")}


def first_path(entry) -> str | None:
    t = entry.get("textures") if isinstance(entry, dict) else entry
    if isinstance(t, list):
        t = t[0] if t else None
    if isinstance(t, dict):
        t = t.get("path")
    return t if isinstance(t, str) else None


def main() -> None:
    items = jload(fetch(RAW + "metadata/vanilladata_modules/mojang-items.json"))["data_items"]
    lang = {}
    for line in fetch(RAW + "resource_pack/texts/en_US.lang").decode("utf-8-sig").splitlines():
        line = line.split("\t#")[0].strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            lang[k] = v.strip()
    item_tex = jload(fetch(RAW + "resource_pack/textures/item_texture.json"))["texture_data"]
    terrain = jload(fetch(RAW + "resource_pack/textures/terrain_texture.json"))["texture_data"]
    blocks = jload(fetch(RAW + "resource_pack/blocks.json"))
    pngs = png_list()

    def usable(path: str | None) -> str | None:
        if not path:
            return None
        path = path.removeprefix("textures/")
        return path if path in pngs else None

    def texture(id_: str) -> str | None:
        """texture path below textures/"""
        if id_ in TEXTURE_OVERRIDES:
            return usable(TEXTURE_OVERRIDES[id_])
        if id_.endswith("_spawn_egg") and usable(f"items/egg_{id_[:-10]}"):
            return f"items/egg_{id_[:-10]}"
        if id_ in item_tex and usable(first_path(item_tex[id_])):
            return usable(first_path(item_tex[id_]))
        if usable(f"items/{id_}"):
            return f"items/{id_}"
        renamed = id_.replace("golden_", "gold_").replace("wooden_", "wood_")
        for toks in dict.fromkeys([tuple(id_.split("_")), tuple(renamed.split("_"))]):
            if len(toks) > 4:
                continue
            for perm in itertools.permutations(toks):
                n = "_".join(perm)
                if n in item_tex and usable(first_path(item_tex[n])):
                    return usable(first_path(item_tex[n]))
                if usable(f"items/{n}"):
                    return f"items/{n}"
        b = blocks.get(id_)
        if b:
            t = b.get("carried_textures") or b.get("textures")
            if isinstance(t, dict):
                t = t.get("side") or t.get("north") or t.get("up") or next(iter(t.values()), None)
            if isinstance(t, str) and t in terrain:
                return usable(first_path(terrain[t]))
            return None
        return None

    def name(i: dict, id_: str) -> str:
        keys = [i["serialization_id"] + ".name", f"item.{id_}.name", f"tile.{id_}.name"]
        if id_.endswith("_spawn_egg"):
            keys.append(f"item.spawn_egg.entity.{id_[:-10]}.name")
        for k in keys:
            if lang.get(k):
                return re.sub(r"§.", "", lang[k])
        return " ".join(w.capitalize() for w in id_.split("_"))

    out, no_icon = [], []
    for i in items:
        id_ = i["name"].removeprefix("minecraft:")
        if not re.fullmatch(r"[a-z0-9_]{1,40}", id_) or EXCLUDE.match(id_) or EXPERIMENTAL.match(id_):
            continue
        tex, is_block = texture(id_), id_ in blocks
        if id_.endswith("_spawn_egg"):
            cat = "spawn"
        elif VALUABLE.match(id_):
            cat = "valuable"
        elif ARMOR.search(id_):
            cat = "armor"
        elif TOOLS.search(id_):
            cat = "tools"
        elif id_ in FOOD:
            cat = "food"
        elif is_block:
            cat = "blocks"
        else:
            cat = "misc"
        stack = 1 if STACK_1.search(id_) else 16 if STACK_16.match(id_) else 64
        out.append({"id": id_, "name": name(i, id_), "cat": cat, "stack": stack, "texture": tex,
                    "popular": id_ in POPULAR})
        if not tex:
            no_icon.append(id_)
    out.sort(key=lambda e: (POPULAR.index(e["id"]) if e["popular"] else len(POPULAR), e["name"].lower()))
    missing = [p for p in POPULAR if p not in {e["id"] for e in out}]
    if missing:
        raise SystemExit(f"popular items missing: {missing}")
    # one item per line: small, and a diff after a Minecraft update shows exactly what changed
    lines = ",\n".join(json.dumps(e, ensure_ascii=False) for e in out)
    OUT.write_text(f'{{"source": "{SAMPLES_TAG}", "items": [\n{lines}\n]}}\n', encoding="utf-8", newline="\n")
    print(f"{len(out)} items ({len(no_icon)} without picture) -> {OUT}")
    if no_icon:
        print("without picture:", " ".join(no_icon))


if __name__ == "__main__":
    main()
