"""Server files: allowlist.json, permissions.json, server.properties, the world seed, the world's pack lists."""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import leveldat


def _write_in_place(path: Path, entries: list[dict], **dump_args) -> None:
    """Rewrite a JSON file in place.

    In place (not rename) so owner and ACLs of the file stay untouched; the
    server runs as a different user and must keep write access. The caller
    makes a backup first; content is verified after writing.
    """
    payload = json.dumps(entries, ensure_ascii=False, **dump_args)
    with open(path, "r+", encoding="utf-8") as f:
        f.seek(0)
        f.write(payload)
        f.truncate()
        f.flush()
        os.fsync(f.fileno())
    if json.loads(path.read_text(encoding="utf-8")) != entries:
        raise IOError(f"{path.name}: Inhalt nach dem Schreiben stimmt nicht")


class ServerFiles:
    def __init__(self, server_dir: str):
        self.dir = Path(server_dir)
        self.allowlist = self.dir / "allowlist.json"
        self.permissions = self.dir / "permissions.json"
        self.properties = self.dir / "server.properties"
        self._seed: tuple[object, int | None] = (None, None)

    def read_allowlist(self) -> list[dict]:
        data = json.loads(self.allowlist.read_text(encoding="utf-8") or "[]")
        if not isinstance(data, list):
            raise ValueError("allowlist.json ist keine Liste")
        return data

    def allowlist_writable(self) -> bool:
        return os.access(self.allowlist, os.W_OK)

    def write_allowlist(self, entries: list[dict]) -> None:
        # compact, as written by the server itself
        _write_in_place(self.allowlist, entries, separators=(",", ":"))

    def read_permissions(self) -> list[dict]:
        data = json.loads(self.permissions.read_text(encoding="utf-8") or "[]")
        if not isinstance(data, list):
            raise ValueError("permissions.json ist keine Liste")
        return data

    def permissions_writable(self) -> bool:
        return os.access(self.permissions, os.W_OK)

    def write_permissions(self, entries: list[dict]) -> None:
        # same layout the server uses: indent 3, "key" : "value"
        _write_in_place(self.permissions, entries, indent=3, separators=(",", " : "))

    def operator_xuids(self) -> set[str]:
        try:
            data = self.read_permissions()
        except (OSError, ValueError):
            return set()
        return {str(p.get("xuid")) for p in data if p.get("permission") == "operator"}

    def read_properties(self) -> dict[str, str]:
        props: dict[str, str] = {}
        try:
            for line in self.properties.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
        except OSError:
            pass
        return props

    def world_dir(self) -> Path:
        return self.dir / "worlds" / self.read_properties().get("level-name", "Bedrock level")

    # ---------- packs of the world (behavior_packs/, resource_packs/, world_*_packs.json) ----------

    def world_packs_file(self, kind: str) -> Path:
        return self.world_dir() / f"world_{kind}_packs.json"

    def read_world_packs(self, kind: str) -> list[dict]:
        """Entries {pack_id, version} of world_<kind>_packs.json; a missing or empty file is an empty list."""
        try:
            text = self.world_packs_file(kind).read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        data = json.loads(text or "[]")
        if not isinstance(data, list):
            raise ValueError(f"world_{kind}_packs.json ist keine Liste")
        return data

    def world_packs_writable(self) -> bool:
        return all(os.access(self.world_packs_file(k), os.W_OK) for k in ("behavior", "resource"))

    def write_world_packs(self, kind: str, entries: list[dict]) -> None:
        # same layout as provision/setup.sh and deploy/world-pack.sh
        _write_in_place(self.world_packs_file(kind), entries, indent=2)

    def installed_packs(self) -> list[dict]:
        """Every pack folder in the world (whether switched on or not), from its manifest.json."""
        out = []
        for kind in ("behavior", "resource"):
            base = self.world_dir() / f"{kind}_packs"
            if not base.is_dir():
                continue
            for d in sorted(p for p in base.iterdir() if p.is_dir()):
                try:
                    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                    h = m["header"]
                    out.append({
                        "path": d,
                        "folder": d.name,
                        "kind": kind,
                        "uuid": str(h["uuid"]),
                        "version": [int(x) for x in h["version"]],
                        "name": str(h.get("name", d.name)),
                        "description": str(h.get("description", "")),
                        "depends": [str(x["uuid"]) for x in m.get("dependencies", []) if "uuid" in x],
                        "items": (d / "items").is_dir(),
                        "entities": (d / "entities").is_dir(),
                    })
                except (OSError, ValueError, KeyError, TypeError):
                    continue  # not a valid pack - Bedrock ignores it as well
        return out

    def seed(self) -> int | None:
        """RandomSeed from level.dat; re-read only when the file changed."""
        world = self.world_dir()
        try:
            st = (world / "level.dat").stat()
            stamp = (str(world), st.st_mtime_ns, st.st_size)
        except OSError:
            return None
        if self._seed[0] != stamp:
            self._seed = (stamp, leveldat.read_seed(world))
        return self._seed[1]
