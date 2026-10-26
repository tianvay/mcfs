"""Server files: allowlist.json, permissions.json, server.properties, the world seed."""
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
