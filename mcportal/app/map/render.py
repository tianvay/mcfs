"""Top-down map of a world snapshot as 256 x 256 PNG tiles (Leaflet-like levels, level 0 = 1 block per pixel).

    python -m app.map.render <snapshot world dir> <map dir>

Writes <map dir>/build-<stamp>/{index.json, <dim>/<level>/<tx>_<tz>.png}, then points
<map dir>/current.json at it and removes older builds. Reads only the snapshot copy.
Progress lines on stdout: {"progress": <dim>, "chunks": n}; the last line is {"done": index} or {"error": text}.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from array import array
from pathlib import Path

from ..adapters.bedrock import leveldat
from .chunk import AIR, DIMENSIONS, MIN_Y, Chunk, chunks
from .natural import is_natural
from .png import encode_rgba

TILE = 256
MAX_LEVELS = 8
WATER = {"minecraft:water", "minecraft:flowing_water", "minecraft:bubble_column",
         "minecraft:seagrass", "minecraft:kelp", "minecraft:tall_seagrass"}
INVISIBLE = {AIR, "minecraft:structure_void", "minecraft:barrier", "minecraft:light_block"}
WATER_RGB = (63, 118, 228)
UNKNOWN_RGB = (128, 128, 128)
FALLBACK = [("leaves", (95, 137, 38)), ("log", (110, 85, 50)), ("planks", (160, 130, 80)), ("wool", (220, 220, 220)),
            ("concrete", (170, 170, 170)), ("terracotta", (152, 94, 67)), ("copper", (190, 110, 80)),
            ("brick", (150, 90, 75)), ("glass", (176, 214, 219)), ("coral", (200, 80, 150)), ("stone", (125, 125, 125))]
COLORS_FILE = Path(__file__).with_name("colors.json")


def _pack(r: int, g: int, b: int) -> int:
    return r | g << 8 | b << 16 | 0xFF000000


class Palette:
    """Block name -> (rgb, coverage); coverage < 1 means the block below shows through (crops, torches)."""

    def __init__(self, table: dict[str, list]):
        self.table = table
        self.cache: dict[str, tuple[tuple[int, int, int], float] | None] = {}
        self.unknown: dict[str, int] = {}

    def get(self, name: str):
        hit = self.cache.get(name, False)
        if hit is not False:
            return hit
        short = name.removeprefix("minecraft:")
        if name in INVISIBLE or short.startswith("light_block"):
            res = None
        elif short in self.table:
            c = self.table[short]
            res = ((c[0], c[1], c[2]), c[3] if len(c) > 3 else 1.0)
        else:
            rgb = next((c for kw, c in FALLBACK if kw in short), UNKNOWN_RGB)
            res = (rgb, 1.0)
            self.unknown[short] = 0
        self.cache[name] = res
        return res


class DimensionImage:
    def __init__(self):
        self.tiles: dict[tuple[int, int], tuple[array, array]] = {}
        self.chunks = 0
        self.bounds = [None, None, None, None]

    def tile(self, tx: int, tz: int):
        t = self.tiles.get((tx, tz))
        if t is None:
            t = (array("I", bytes(TILE * TILE * 4)), array("h", [-32768]) * (TILE * TILE))
            self.tiles[(tx, tz)] = t
        return t

    def height(self, bx: int, bz: int) -> int | None:
        t = self.tiles.get((bx >> 8, bz >> 8))
        if t is None:
            return None
        h = t[1][(bz & 255) * TILE + (bx & 255)]
        return None if h == -32768 else h


def column(chunk: Chunk, x: int, z: int, y_from: int):
    """(y, block name) from y_from downwards to the bottom of the world."""
    base = (x << 8) | (z << 4)
    bottom = MIN_Y[chunk.dim]
    y = y_from
    while y >= bottom:
        sc = chunk.subchunk(y >> 4)
        if sc is None:
            y = (y & ~15) - 1
            continue
        idx, pal = sc.indices, sc.palette
        for ly in range(y & 15, -1, -1):
            yield (y & ~15) + ly, pal[idx[base | ly]]
        y = (y & ~15) - 1


def shade(palette: Palette, chunk: Chunk, x: int, z: int) -> tuple[int, int] | None:
    """(packed colour, surface height) of one column, or None if there is nothing."""
    top = chunk.top_y(x, z)
    if top is None:
        return None
    it = column(chunk, x, z, top)
    overlay = c = None
    depth = 0
    surface = None
    for y, name in it:
        if name in WATER:
            depth += 1
            if surface is None:
                surface = y
            if depth >= 16:
                break
            continue
        c = palette.get(name)
        if c is None:
            if depth:
                break
            continue
        if surface is None:
            surface = y
        rgb, cover = c
        if cover < 1.0 and overlay is None and not depth:
            overlay = (rgb, max(cover, 0.35))
            continue
        break
    else:
        if surface is None:
            return None
        c = None
    rgb = c[0] if c else (40, 40, 40)
    if overlay:
        o, a = overlay
        rgb = tuple(round(b * (1 - a) + t * a) for b, t in zip(rgb, o))
    if depth:
        # shallow water shows a bit of the ground, deeper water gets darker
        a = 0.6 if depth <= 2 else 0.85
        f = max(0.6, 1 - depth * 0.03)
        rgb = tuple(round((b * (1 - a) + w * a) * f) for b, w in zip(rgb, WATER_RGB))
    return _pack(*rgb), surface


def draw_chunk(img: DimensionImage, palette: Palette, chunk: Chunk) -> None:
    pixels, heights = img.tile(chunk.x >> 4, chunk.z >> 4)
    ox, oz = (chunk.x & 15) * 16, (chunk.z & 15) * 16
    drawn = False
    for z in range(16):
        row = (oz + z) * TILE + ox
        for x in range(16):
            res = shade(palette, chunk, x, z)
            if res:
                pixels[row + x], heights[row + x] = res
                drawn = True
    if drawn:
        img.chunks += 1
        bx, bz = chunk.x * 16, chunk.z * 16
        b = img.bounds
        b[0] = bx if b[0] is None else min(b[0], bx)
        b[1] = bz if b[1] is None else min(b[1], bz)
        b[2] = bx + 15 if b[2] is None else max(b[2], bx + 15)
        b[3] = bz + 15 if b[3] is None else max(b[3], bz + 15)


def relief(img: DimensionImage) -> None:
    """Lighter where the ground rises towards the north-west, darker where it falls."""
    for (tx, tz), (pixels, heights) in img.tiles.items():
        bx0, bz0 = tx * TILE, tz * TILE
        for pz in range(TILE):
            for px in range(TILE):
                i = pz * TILE + px
                h = heights[i]
                if h == -32768:
                    continue
                if px and pz:
                    n = heights[i - TILE - 1]
                    n = None if n == -32768 else n
                else:
                    n = img.height(bx0 + px - 1, bz0 + pz - 1)
                if n is None or n == h:
                    continue
                f = 1.12 if h > n else 0.86
                p = pixels[i]
                r, g, b = p & 255, p >> 8 & 255, p >> 16 & 255
                pixels[i] = _pack(min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)))


def downsample(children: dict[tuple[int, int], array], tx: int, tz: int) -> array | None:
    """Level n+1 tile from up to four level n tiles (every second pixel)."""
    out = array("I", bytes(TILE * TILE * 4))
    half = TILE // 2
    any_ = False
    for qz in range(2):
        for qx in range(2):
            child = children.get((tx * 2 + qx, tz * 2 + qz))
            if child is None:
                continue
            any_ = True
            for r in range(half):
                src = child[(2 * r) * TILE:(2 * r + 1) * TILE:2]
                dst = (qz * half + r) * TILE + qx * half
                out[dst:dst + half] = src
    return out if any_ else None


def write_levels(img: DimensionImage, target: Path) -> dict[str, list]:
    level = {k: v[0] for k, v in img.tiles.items() if any(v[0])}
    listing: dict[str, list] = {}
    for n in range(MAX_LEVELS + 1):
        d = target / str(n)
        d.mkdir(parents=True, exist_ok=True)
        for (tx, tz), px in level.items():
            (d / f"{tx}_{tz}.png").write_bytes(encode_rgba(TILE, TILE, px.tobytes()))
        listing[str(n)] = sorted([tx, tz] for tx, tz in level)
        if len(level) <= 4 or n == MAX_LEVELS:
            break
        parents = {(tx >> 1, tz >> 1) for tx, tz in level}
        level = {p: t for p in parents if (t := downsample(level, *p)) is not None}
    return listing


BUILT_FILE = "built_chunks.json"
DIM_KEY = {0: "o", 1: "n", 2: "e"}  # same chunk keys as the events pack's build register


def is_built(chunk: Chunk) -> bool:
    """Non-natural blocks near the surface (from 8 below the lowest to the highest column top)?"""
    if not chunk.heightmap:
        return False
    tops = [h + MIN_Y[chunk.dim] - 1 for h in chunk.heightmap]
    for sy in range((min(tops) - 8) >> 4, (max(tops) >> 4) + 1):
        sc = chunk.subchunk(sy)
        if sc and not all(is_natural(n) for n in sc.palette):
            return True
    return False


def render(world: Path, map_dir: Path, progress=lambda dim, n: None) -> dict:
    t0 = time.time()
    palette = Palette(json.loads(COLORS_FILE.read_text(encoding="utf-8")))
    images = {dim: DimensionImage() for dim in DIMENSIONS}
    built: list[str] = []
    seen = 0
    for chunk in chunks(world / "db"):
        draw_chunk(images[chunk.dim], palette, chunk)
        if is_built(chunk):
            built.append(f"{DIM_KEY[chunk.dim]}{chunk.x},{chunk.z}")
        seen += 1
        if seen % 1000 == 0:
            progress(DIMENSIONS[chunk.dim], seen)
    t = time.time()
    while (build := map_dir / f"build-{time.strftime('%Y%m%d-%H%M%S', time.localtime(t))}").exists():
        t += 1  # two runs in the same second
    stamp = build.name.removeprefix("build-")
    tmp = map_dir / f".tmp-{stamp}"
    shutil.rmtree(tmp, ignore_errors=True)
    dims = {}
    for dim, img in images.items():
        if not img.chunks:
            continue
        relief(img)
        name = DIMENSIONS[dim]
        dims[name] = {"chunks": img.chunks, "bounds": img.bounds, "tiles": write_levels(img, tmp / name)}
    level = {}
    try:
        level = leveldat.parse((world / "level.dat").read_bytes())
    except (OSError, ValueError):
        pass
    index = {
        "version": 1,
        "build": build.name,
        "rendered_at": time.time(),
        "duration": round(time.time() - t0, 1),
        "tile_size": TILE,
        "dims": dims,
        "spawn": [level["SpawnX"], level["SpawnZ"]] if "SpawnX" in level and "SpawnZ" in level else None,
        "unknown_blocks": sorted(palette.unknown)[:50],
    }
    (tmp / "index.json").write_text(json.dumps(index), encoding="utf-8")
    os.replace(tmp, build)
    cur = map_dir / "current.json"
    (map_dir / "current.json.tmp").write_text(json.dumps({"build": build.name}), encoding="utf-8")
    os.replace(map_dir / "current.json.tmp", cur)
    for old in map_dir.glob("build-*"):
        if old.name != build.name:
            shutil.rmtree(old, ignore_errors=True)
    # chunks with builds - the portal hands them to the events pack (also builds from before its register)
    (map_dir / f"{BUILT_FILE}.tmp").write_text(json.dumps({"at": time.time(), "chunks": sorted(built)}), encoding="utf-8")
    os.replace(map_dir / f"{BUILT_FILE}.tmp", map_dir / BUILT_FILE)
    index["built_chunks"] = len(built)
    return index


def main(argv: list[str]) -> int:
    world, map_dir = Path(argv[1]), Path(argv[2])

    def progress(dim, n):
        print(json.dumps({"progress": dim, "chunks": n}), flush=True)

    try:
        index = render(world, map_dir, progress)
    except Exception as e:  # reported to the portal, which shows it
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), flush=True)
        return 1
    summary = {k: index[k] for k in ("build", "duration")}
    summary["chunks"] = {d: v["chunks"] for d, v in index["dims"].items()}
    summary["built"] = index["built_chunks"]
    print(json.dumps({"done": summary}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
