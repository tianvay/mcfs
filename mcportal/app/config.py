from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = "/etc/mcportal/config.toml"


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    data_dir: Path
    pin: str
    adapter: str
    unit: str
    server_dir: str
    console_fifo: str
    allowlist_backups_keep: int
    update_backups_keep: int

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "audit.jsonl"


def load(path: str | None = None) -> Config:
    path = path or os.environ.get("MCPORTAL_CONFIG", DEFAULT_PATH)
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    portal = raw.get("portal", {})
    bedrock = raw.get("bedrock", {})
    return Config(
        host=portal.get("host", "0.0.0.0"),
        port=int(portal.get("port", 8080)),
        data_dir=Path(portal.get("data_dir", "/var/lib/mcportal")),
        pin=str(portal.get("pin", "")),
        adapter=portal.get("adapter", "bedrock"),
        unit=bedrock.get("unit", "minecraft-bedrock.service"),
        server_dir=bedrock["server_dir"],
        console_fifo=bedrock.get("console_fifo", "/run/minecraft-bedrock/console"),
        allowlist_backups_keep=int(portal.get("allowlist_backups_keep", 30)),
        update_backups_keep=int(portal.get("update_backups_keep", 1)),
    )
