"""Server-side update steps for a Bedrock installation.

The portal user may read the server directory but not change program files
(they belong to the Minecraft user). Copying the staged release in, and
restoring a backup, is done by deploy/mcportal-update-helper, started via two
fixed systemd units that run as the Minecraft user (change M4).
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from . import release, systemd

APPLY_UNIT = "mcportal-update-apply.service"
ROLLBACK_UNIT = "mcportal-update-rollback.service"

# Must stay byte-identical across an update (also excluded by the helper).
PRESERVED_FILES = ("allowlist.json", "permissions.json", "server.properties")
# Leftovers in the server directory that are not part of the server and need no backup.
BACKUP_EXCLUDES = ("./*.zip", "./*.run", "./wget-log*")


class BedrockUpdater:
    def __init__(self, server_dir: str):
        self.dir = Path(server_dir)

    def latest(self) -> release.Release:
        return release.latest()

    def download(self, rel: release.Release, dest: Path) -> str:
        return release.download(rel, dest)

    def stage(self, zip_path: Path, target: Path) -> None:
        release.stage(zip_path, target)

    def preflight(self) -> None:
        """Before anything is stopped: the helper runs as the owner of the server
        directory and must be able to replace every file in it."""
        owner = self.dir.stat().st_uid
        foreign = [p for p in self.dir.rglob("*")
                   if not p.is_symlink() and p.stat().st_uid != owner
                   and not p.relative_to(self.dir).parts[0] == "worlds"]
        if foreign:
            sample = ", ".join(str(p.relative_to(self.dir)) for p in foreign[:3])
            raise RuntimeError(
                f"{len(foreign)} Dateien/Ordner im Serververzeichnis gehören nicht dem Minecraft-Benutzer "
                f"(z. B. {sample}). Update abgebrochen, nichts verändert. Beheben mit: "
                f"sudo chown -R {self.dir.owner()}: '{self.dir}'")

    def checksums(self) -> dict[str, str]:
        out = {}
        for name in PRESERVED_FILES:
            p = self.dir / name
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        return out

    def backup(self, target_dir: Path) -> Path:
        """Full backup of the server directory (world, config, program) as tar.gz, ACLs included."""
        target_dir.mkdir(parents=True, exist_ok=True)
        tar = target_dir / "server.tar.gz"
        cmd = ["tar", "--acls", "--anchored", "--no-wildcards-match-slash"]
        for pattern in BACKUP_EXCLUDES:
            cmd.append(f"--exclude={pattern}")
        cmd += ["-czf", str(tar), "-C", str(self.dir), "."]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if res.returncode != 0:
            raise RuntimeError(f"Backup fehlgeschlagen: {res.stderr.strip()[:300]}")
        test = subprocess.run(["tar", "-tzf", str(tar)], capture_output=True, text=True, timeout=1800)
        members = test.stdout.splitlines()
        if test.returncode != 0 or not any(m.startswith("./worlds/") for m in members) \
                or "./allowlist.json" not in members:
            raise RuntimeError("Backup-Prüfung fehlgeschlagen (Archiv unvollständig)")
        return tar

    def apply(self) -> tuple[bool, str]:
        return systemd.run_helper(APPLY_UNIT)

    def rollback(self) -> tuple[bool, str]:
        return systemd.run_helper(ROLLBACK_UNIT)
