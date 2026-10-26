"""Generate app/map/colors.json: one map colour per block, from Mojang's official vanilla textures.

Run on the development PC (needs Pillow), not on the server:

    git clone --depth 1 --filter=blob:none --sparse https://github.com/Mojang/bedrock-samples.git
    (sparse paths: resource_pack/blocks.json, resource_pack/textures/terrain_texture.json,
     resource_pack/textures/blocks/)
    python -I tools/make_colors.py <bedrock-samples>/resource_pack app/map/colors.json

Colour = alpha-weighted average of the block's top texture. Grey textures that the game tints by
biome (grass, leaves, water ...) get the default plains tint until biome colouring exists (K4).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

TINTS = [  # (keyword, rgb) - checked in order, first match wins
    ("water", (63, 118, 228)),
    ("birch_leaves", (128, 167, 85)),
    ("spruce_leaves", (97, 153, 97)),
    ("leaves", (119, 171, 47)),
    ("vine", (119, 171, 47)),
    ("lily_pad", (32, 128, 48)),
    ("grass", (145, 189, 89)),
    ("fern", (145, 189, 89)),
    ("sugar_cane", (145, 189, 89)),
    ("stem", (145, 189, 89)),
]
ALIASES = {"grass_block": "grass", "dirt_path": "grass_path", "sea_lantern": "seaLantern", "flowing_water": "water", "flowing_lava": "lava"}


def load_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))


def first_path(entry) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, list):
        return first_path(entry[0]) if entry else None
    if isinstance(entry, dict):
        for key in ("path", "textures", "variations"):
            if key in entry:
                return first_path(entry[key])
    return None


def top_texture(block: dict) -> str | None:
    tex = block.get("textures")
    if isinstance(tex, dict):
        return tex.get("up") or tex.get("side") or next(iter(tex.values()), None)
    return tex


def average(path: Path) -> tuple[int, int, int, float] | None:
    for ext in (".png", ".tga"):
        p = path.with_suffix(ext)
        if p.exists():
            img = Image.open(p).convert("RGBA")
            break
    else:
        return None
    w, h = img.size
    img = img.crop((0, 0, w, min(h, w)))  # animated textures: first frame
    r = g = b = a = 0
    for pr, pg, pb, pa in img.getdata():
        r += pr * pa
        g += pg * pa
        b += pb * pa
        a += pa
    if a == 0:
        return None
    return round(r / a), round(g / a), round(b / a), a / (255 * img.width * img.height)


def tint_for(name: str):
    for kw, rgb in TINTS:
        if kw in name:
            return rgb
    return None


def main(rp: Path, out: Path) -> None:
    blocks = load_json(rp / "blocks.json")
    terrain = load_json(rp / "textures" / "terrain_texture.json")["texture_data"]
    colors: dict[str, list[int]] = {}
    missing = []
    for name, block in sorted(blocks.items()):
        if not isinstance(block, dict) or name == "format_version":
            continue
        key = top_texture(block)
        rel = first_path(terrain.get(key, {})) if isinstance(key, str) else None
        avg = average(rp / rel) if rel else None
        if avg is None:
            missing.append(name)
            continue
        r, g, b, coverage = avg
        tint = tint_for(name)
        if tint and max(r, g, b) - min(r, g, b) < 24:  # grey texture the game colours itself
            # textures are mid grey; full tint brightness reads better on a map than the in-game product
            f = min(1.0, (r + g + b) / 3 / 180) if "water" not in name else 1.0
            r, g, b = (round(t * f) for t in tint)
        colors[name] = [r, g, b] if coverage > 0.25 else [r, g, b, round(coverage, 2)]
    for alias, target in ALIASES.items():
        if target in colors:
            colors.setdefault(alias, colors[target])
    out.write_text(json.dumps(colors, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(colors)} colours, {len(missing)} without texture: {', '.join(missing[:40])}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
