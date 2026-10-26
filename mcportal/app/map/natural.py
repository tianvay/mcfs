"""Which blocks a world generates by itself - everything else near the surface means "somebody built here".

Used by the map reader to find chunks with builds (also old ones from before the events pack's build register).
Generated structures (villages, ruined portals, trail ruins ...) count as built - on purpose: world-changing
events (meteor, treasure) stay away from them, too. Unknown blocks count as built (safe side).
"""
from __future__ import annotations

NATURAL = frozenset("""
air cave_air void_air water flowing_water lava flowing_lava bubble_column
stone granite diorite andesite deepslate tuff calcite dripstone_block pointed_dripstone smooth_basalt basalt
blackstone bedrock obsidian gravel sand red_sand sandstone red_sandstone clay mud dirt coarse_dirt rooted_dirt
podzol mycelium grass_block grass dirt_with_roots moss_block moss_carpet pale_moss_block pale_moss_carpet
pale_hanging_moss snow snow_layer powder_snow ice packed_ice blue_ice magma netherrack soul_sand soul_soil
terracotta white_terracotta orange_terracotta yellow_terracotta brown_terracotta red_terracotta
light_gray_terracotta hardened_clay stained_hardened_clay
amethyst_block budding_amethyst amethyst_cluster large_amethyst_bud medium_amethyst_bud small_amethyst_bud
sculk sculk_vein sculk_sensor sculk_shrieker sculk_catalyst
glow_lichen vine cave_vines cave_vines_body_with_berries cave_vines_head_with_berries twisting_vines weeping_vines
short_grass tall_grass fern large_fern deadbush dead_bush bush firefly_bush short_dry_grass tall_dry_grass
leaf_litter wildflowers pink_petals sweet_berry_bush cactus cactus_flower sugar_cane reeds bamboo
bamboo_sapling kelp seagrass tall_seagrass sea_pickle waterlily lily_pad azalea flowering_azalea
big_dripleaf small_dripleaf_block spore_blossom hanging_roots mangrove_roots muddy_mangrove_roots
mangrove_propagule brown_mushroom red_mushroom brown_mushroom_block red_mushroom_block mushroom_stem
pumpkin melon_block melon_stem pumpkin_stem cocoa beehive bee_nest
dandelion poppy blue_orchid allium azure_bluet oxeye_daisy cornflower lily_of_the_valley sunflower lilac
rose_bush peony torchflower pitcher_plant open_eyeblossom closed_eyeblossom red_flower yellow_flower
double_plant tallgrass
infested_stone infested_deepslate monster_egg
raw_copper_block raw_iron_block mossy_cobblestone
end_stone chorus_plant chorus_flower
""".split())

NATURAL_SUFFIXES = ("_ore", "_leaves", "_log", "_tulip", "_coral", "_coral_block", "_coral_fan", "_coral_wall_fan")
NATURAL_PREFIXES = ("dead_",)  # dead coral blocks/fans


def is_natural(name: str) -> bool:
    n = name.removeprefix("minecraft:")
    if n in NATURAL:
        return True
    if n.startswith("stripped_"):
        return False  # logs a player worked on
    return n.endswith(NATURAL_SUFFIXES) or (n.startswith(NATURAL_PREFIXES) and "coral" in n)
