"""Scaffold a Bedrock behavior pack with a script module for the family server.

usage: python new_pack.py <target_dir> "<Pack-Name>" "<Beschreibung>"

Creates manifest.json (fresh UUIDs, @SERVER_API@ placeholder that the install
script replaces with the stable @minecraft/server version) and scripts/main.js
with the reporting skeleton used by mcportal (console.warn + JSON, batched).
Files are written with LF line endings (they run on Linux).
"""
import json
import re
import sys
import uuid
from pathlib import Path

MAIN_JS = """\
// {name} - behavior pack for the Minecraft Family Portal
//
// Reports to the server log as ONE line per flush:
//   [{tag}] {{"v":1,...}}
// console.warn on purpose: the server runs with content-log-level=warning.
// Uses only the stable @minecraft/server API - no experiments in the world.
import {{ system, world }} from "@minecraft/server";

const FLUSH_TICKS = 20 * 20; // 20 s
const TAG = "[{tag}]";

let pending = new Map(); // player name -> counters

// TODO: subscribe to the events you need, e.g.
// world.afterEvents.playerPlaceBlock.subscribe((ev) => {{ ... ev.player.name ... }});

function flush() {{
  if (pending.size === 0) return;
  const players = Object.fromEntries(pending);
  pending = new Map();
  console.warn(`${{TAG}} ${{JSON.stringify({{ v: 1, players }})}}`);
}}

system.runInterval(flush, FLUSH_TICKS);
system.run(() => console.warn(`${{TAG}} {{"v":1,"started":true}}`));
"""


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    target, name, description = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    if target.exists():
        sys.exit(f"{target} existiert bereits")
    slug = re.sub(r"[^a-z0-9]+", "-", target.name.lower()).strip("-").removeprefix("mcportal-")
    tag = f"mcportal-{slug}"
    manifest = {
        "format_version": 2,
        "header": {"name": name, "description": description, "uuid": str(uuid.uuid4()),
                   "version": [1, 0, 0], "min_engine_version": [1, 21, 0]},
        "modules": [{"type": "script", "language": "javascript", "uuid": str(uuid.uuid4()),
                     "version": [1, 0, 0], "entry": "scripts/main.js"}],
        "dependencies": [{"module_name": "@minecraft/server", "version": "@SERVER_API@"}],
    }
    (target / "scripts").mkdir(parents=True)
    (target / "manifest.json").write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
    (target / "scripts" / "main.js").write_bytes(MAIN_JS.format(name=name, tag=tag).encode())
    print(f"angelegt: {target}  (Log-Tag: [{tag}], pack_id: {manifest['header']['uuid']})")


if __name__ == "__main__":
    main()
