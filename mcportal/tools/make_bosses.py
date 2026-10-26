"""Generate the Kopfgeld boss mobs from Mojang's vanilla definitions (bedrock-samples).

Run on the development PC after cloning bedrock-samples (see tools/make_colors.py), and again after Minecraft
updates that change zombies, skeletons or spiders:

    python -I tools/make_bosses.py <bedrock-samples> minecraft-pack

Writes
  mcportal_events/entities/boss_<mob>.json        behavior: vanilla mob (runtime_identifier) 50 % larger,
                                                   never despawns, only summoned by the events pack
  mcportal_events_rp/entity/boss_<mob>.entity.json client: vanilla geometry, textures and animations
  mcportal_events_rp/render_controllers/mcfs_bosses.render_controllers.json   colour shift (overlay colour)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCALE = 1.5
# overlay colour per boss: the vanilla texture tinted (alpha = strength)
BOSSES = {
    "zombie": {"r": 0.45, "g": 0.0, "b": 0.65, "a": 0.45},    # Bernd: dark purple
    "skeleton": {"r": 1.0, "g": 0.75, "b": 0.1, "a": 0.45},   # Sven: gold
    "spider": {"r": 0.85, "g": 0.0, "b": 0.1, "a": 0.45},     # Susi: blood red
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


def behavior(samples: Path, mob: str) -> dict:
    data = load(samples / "behavior_pack" / "entities" / f"{mob}.json")
    ent = data["minecraft:entity"]
    desc = ent["description"]
    desc["identifier"] = f"mcfs:boss_{mob}"
    desc["runtime_identifier"] = f"minecraft:{mob}"  # behaves exactly like the vanilla mob
    desc["is_spawnable"] = False
    desc["is_summonable"] = True
    comps = ent["components"]
    comps.pop("minecraft:despawn", None)   # a boss stays until it is defeated or the bounty ends
    comps["minecraft:persistent"] = {}
    comps["minecraft:scale"] = {"value": SCALE}
    return data


def client(samples: Path, mob: str) -> dict:
    data = load(samples / "resource_pack" / "entity" / f"{mob}.entity.json")
    desc = data["minecraft:client_entity"]["description"]
    desc["identifier"] = f"mcfs:boss_{mob}"
    desc["render_controllers"] = [f"controller.render.mcfs_boss_{mob}"]
    desc.pop("spawn_egg", None)
    return data


def render_controllers() -> dict:
    out = {}
    for mob, color in BOSSES.items():
        # values as Molang strings, like Mojang's own render controllers
        rc = {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
              "overlay_color": {k: str(v) for k, v in color.items()}}
        if mob == "spider":  # vanilla spider switches material when invisible
            rc["arrays"] = {"materials": {"Array.materials": ["Material.default", "Material.invisible"]}}
            rc["materials"] = [{"*": "Array.materials[query.is_invisible]"}]
        out[f"controller.render.mcfs_boss_{mob}"] = rc
    return {"format_version": "1.8.0", "render_controllers": out}


def main(samples: Path, packs: Path) -> None:
    for mob in BOSSES:
        write(packs / "mcportal_events" / "entities" / f"boss_{mob}.json", behavior(samples, mob))
        write(packs / "mcportal_events_rp" / "entity" / f"boss_{mob}.entity.json", client(samples, mob))
    write(packs / "mcportal_events_rp" / "render_controllers" / "mcfs_bosses.render_controllers.json", render_controllers())
    print(f"{len(BOSSES)} bosses written")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
