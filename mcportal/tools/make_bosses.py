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
    strip_transformations(ent)
    return data


def _refs(obj, key: str) -> set[str]:
    """all string values of `key` anywhere below obj (event names in triggers/timers, group names in add/remove)"""
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            found |= _refs(v, key)
    elif isinstance(obj, list):
        for v in obj:
            found |= _refs(v, key)
    return found


def _prune(obj, events: set[str], groups: set[str]):
    """remove triggers of dropped events and add/remove entries of dropped groups"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "component_groups" and isinstance(v, list):
                v = [g for g in v if g not in groups]
            v = _prune(v, events, groups)
            if isinstance(v, dict) and v.get("event") in events:
                continue  # e.g. a timer's time_down_event
            out[k] = v
        return out
    if isinstance(obj, list):
        return [_prune(v, events, groups) for v in obj
                if not (isinstance(v, dict) and v.get("event") in events)]
    return obj


def strip_transformations(ent: dict) -> None:
    """Own mobs never turn into vanilla ones: a zombie boss under water would become a plain drowned, a skeleton
    in powder snow a stray (seen 27.10.: Zombie-Bernd in water). Drops every component group with a
    minecraft:transformation, every event that adds such a group or only leads there, and all references."""
    groups = {name for name, g in ent.get("component_groups", {}).items() if "minecraft:transformation" in g}
    events: set[str] = set()
    while True:
        # events that add a group with a transformation (directly or through a sequence)
        new_events = {name for name, e in ent.get("events", {}).items()
                      if name not in events and (set(_flat(e, "add")) & groups)}
        # component groups whose only purpose is to fire such an event (timer / environment sensor)
        new_groups = {name for name, g in ent.get("component_groups", {}).items()
                      if name not in groups and _refs(g, "event") and _refs(g, "event") <= events | new_events}
        if not new_events and not new_groups:
            break
        events |= new_events
        groups |= new_groups
    # events that now only add/remove dropped groups (e.g. "stop transforming")
    for name, e in list(ent.get("events", {}).items()):
        touched = set(_flat(e, "add")) | set(_flat(e, "remove"))
        if touched and touched <= groups:
            events.add(name)
    for name in groups:
        ent["component_groups"].pop(name, None)
    for name in events:
        ent["events"].pop(name, None)
    ent["components"] = _prune(ent["components"], events, groups)
    ent["component_groups"] = _prune(ent["component_groups"], events, groups)
    ent["events"] = _prune(ent["events"], events, groups)
    left = json.dumps(ent)
    assert "minecraft:transformation" not in left and not any(f'"{x}"' in left for x in events | groups), \
        "transformation not removed completely"


def _flat(obj, key: str) -> list[str]:
    """group names listed under `key` ("add"/"remove") anywhere in an event"""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, dict):
                out += [g for g in v.get("component_groups", []) if isinstance(g, str)]
            else:
                out += _flat(v, key)
    elif isinstance(obj, list):
        for v in obj:
            out += _flat(v, key)
    return out


def client(samples: Path, name: str, mob: str) -> dict:
    data = load(samples / "resource_pack" / "entity" / f"{mob}.entity.json")
    if mob == "zombie":
        data = legacy_zombie(data)
    desc = data["minecraft:client_entity"]["description"]
    desc["identifier"] = f"mcfs:{name}"
    desc["render_controllers"] = [f"controller.render.mcfs_{name}"]
    desc.pop("spawn_egg", None)
    return data


def legacy_zombie(data: dict) -> dict:
    """Mojang's zombie in the 1.26 client format (baby model, spear animations, "animate" list) stays invisible
    under an own identifier (seen 27.10.: particles yes, body no), while skeleton, spider and witch in the
    1.8.0 format render. So the boss zombie gets the 1.8.0 form of the same model, texture and animations:
    adults only, no spear, animation controllers instead of "animate"."""
    desc = data["minecraft:client_entity"]["description"]
    drop = ("melee_spear", "baby", "big_head")
    animations = {k: v for k, v in desc["animations"].items()
                  if not k.endswith("_controller") and not any(d in k for d in drop)}
    controllers = [c for c in desc["animation_controllers"] if not any(d in next(iter(c)) for d in drop)]
    return {"format_version": "1.8.0", "minecraft:client_entity": {"description": {
        "identifier": desc["identifier"],
        "min_engine_version": "1.8.0",
        "materials": {"default": desc["materials"]["default"]},
        "textures": {"default": desc["textures"]["default"]},
        "geometry": {"default": desc["geometry"]["default"]},
        "scripts": {"pre_animation": [
            "variable.tcos0 = (Math.cos(query.modified_distance_moved * 38.17) * query.modified_move_speed / variable.gliding_speed_value) * 57.3;",
            "variable.riding_y_offset_with_respect_to_player = 1.0;",
            "variable.riding_y_offset_on_vehicle_where_other_entites_can_stand = query.is_riding_any_entity_of_type('minecraft:minecart', 'minecraft:boat', 'minecraft:chest_boat') ? -3.0 : 0.0;",
            "variable.riding_y_offset = variable.riding_y_offset_with_respect_to_player + variable.riding_y_offset_on_vehicle_where_other_entites_can_stand;",
        ]},
        "animations": animations,
        "animation_controllers": controllers,
        "render_controllers": desc["render_controllers"],
        "enable_attachables": True,
    }}}


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
