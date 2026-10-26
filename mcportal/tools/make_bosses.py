"""Generate the events pack's own mobs (Kopfgeld bosses, coven witches) from Mojang's vanilla definitions.

Run on the development PC after cloning bedrock-samples (see tools/make_colors.py), and again after Minecraft
updates that change zombies, skeletons or spiders:

    python -I tools/make_bosses.py <bedrock-samples> minecraft-pack

Writes for every mob in MOBS
  mcportal_events/entities/<name>.json             behavior: vanilla mob (runtime_identifier), larger,
                                                   never despawns, only summoned by the events pack
  mcportal_events_rp/entity/<name>.entity.json     client: vanilla geometry, textures and animations
  mcportal_events_rp/render_controllers/mcfs_bosses.render_controllers.json   colour shift (overlay colour)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# own mob -> vanilla mob, size, overlay colour (the vanilla texture tinted, alpha = strength)
MOBS = {
    "boss_zombie": ("zombie", 1.5, {"r": 0.45, "g": 0.0, "b": 0.65, "a": 0.45}),    # Bernd: dark purple
    "boss_skeleton": ("skeleton", 1.5, {"r": 1.0, "g": 0.75, "b": 0.1, "a": 0.45}),  # Sven: gold
    "boss_spider": ("spider", 1.5, {"r": 0.85, "g": 0.0, "b": 0.1, "a": 0.45}),      # Susi: blood red
    "coven_witch": ("witch", 1.15, {"r": 0.2, "g": 0.8, "b": 0.25, "a": 0.35}),      # Hexenzirkel: green
}


def strip_comments(text: str) -> str:
    """JSON with // and /* */ comments (Mojang's files have them) -> plain JSON; strings are kept as they are."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            i = text.index("*/", i) + 2
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def load(path: Path):
    return json.loads(strip_comments(path.read_text(encoding="utf-8-sig")))


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def behavior(samples: Path, name: str, mob: str, scale: float) -> dict:
    data = load(samples / "behavior_pack" / "entities" / f"{mob}.json")
    ent = data["minecraft:entity"]
    desc = ent["description"]
    desc["identifier"] = f"mcfs:{name}"
    desc["runtime_identifier"] = f"minecraft:{mob}"  # behaves exactly like the vanilla mob
    desc["is_spawnable"] = False
    desc["is_summonable"] = True
    comps = ent["components"]
    comps.pop("minecraft:despawn", None)   # a boss stays until it is defeated or the bounty ends
    comps["minecraft:persistent"] = {}
    comps["minecraft:scale"] = {"value": scale}
    return data


def client(samples: Path, name: str, mob: str) -> dict:
    data = load(samples / "resource_pack" / "entity" / f"{mob}.entity.json")
    desc = data["minecraft:client_entity"]["description"]
    desc["identifier"] = f"mcfs:{name}"
    desc["render_controllers"] = [f"controller.render.mcfs_{name}"]
    desc.pop("spawn_egg", None)
    return data


def render_controllers() -> dict:
    out = {}
    for name, (mob, _, color) in MOBS.items():
        # values as Molang strings, like Mojang's own render controllers
        rc = {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
              "overlay_color": {k: str(v) for k, v in color.items()}}
        if mob == "spider":  # vanilla spider switches material when invisible
            rc["arrays"] = {"materials": {"Array.materials": ["Material.default", "Material.invisible"]}}
            rc["materials"] = [{"*": "Array.materials[query.is_invisible]"}]
        out[f"controller.render.mcfs_{name}"] = rc
    return {"format_version": "1.8.0", "render_controllers": out}


def main(samples: Path, packs: Path) -> None:
    for name, (mob, scale, _) in MOBS.items():
        write(packs / "mcportal_events" / "entities" / f"{name}.json", behavior(samples, name, mob, scale))
        write(packs / "mcportal_events_rp" / "entity" / f"{name}.entity.json", client(samples, name, mob))
    write(packs / "mcportal_events_rp" / "render_controllers" / "mcfs_bosses.render_controllers.json", render_controllers())
    print(f"{len(MOBS)} mobs written")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
