"""Official Bedrock Dedicated Server releases: version check, download, validation.

Source: the download-links API used by https://www.minecraft.net/en-us/download/server/bedrock
Mojang publishes no checksums, so a download is accepted only if
  - it comes via HTTPS from minecraft.net under /bedrockdedicatedserver/bin-linux/,
  - the file name carries the version,
  - the zip is intact (CRC of every member), has no unsafe paths/links,
  - and contains the expected server files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

API_URL = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
DOWNLOAD_TYPE = "serverBedrockLinux"
ALLOWED_HOSTS = {"www.minecraft.net", "minecraft.net"}
PATH_PREFIX = "/bedrockdedicatedserver/bin-linux/"
_FILE_RE = re.compile(r"^bedrock-server-(?P<version>\d+(?:\.\d+){2,3})\.zip$")
MAX_ZIP_BYTES = 400 * 1024 * 1024
MAX_UNPACKED_BYTES = 1500 * 1024 * 1024
REQUIRED_MEMBERS = ("bedrock_server", "server.properties", "behavior_packs/", "resource_packs/")
USER_AGENT = "mcportal/1.0 (+family server updater)"


class ReleaseError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def release_from_url(url: str) -> Release:
    u = urlparse(url)
    name = PurePosixPath(u.path).name
    m = _FILE_RE.match(name)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS or not u.path.startswith(PATH_PREFIX) or not m:
        raise ReleaseError(f"Unerwartete Download-Adresse: {url}")
    return Release(version=m.group("version"), url=url)


def latest(timeout: float = 20) -> Release:
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    for link in data.get("result", {}).get("links", []):
        if link.get("downloadType") == DOWNLOAD_TYPE:
            return release_from_url(link["downloadUrl"])
    raise ReleaseError("Keine Linux-Serverversion in der Antwort von minecraft.net")


def download(release: Release, dest: Path, timeout: float = 60) -> str:
    """Download to `dest`; returns the SHA-256 (for the log)."""
    release_from_url(release.url)  # re-check
    req = urllib.request.Request(release.url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        final = urlparse(r.geturl())
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise ReleaseError(f"Download wurde umgeleitet nach {final.hostname}")
        length = int(r.headers.get("Content-Length") or 0)
        if length > MAX_ZIP_BYTES:
            raise ReleaseError("Download ist unerwartet groß")
        with open(dest, "wb") as f:
            while chunk := r.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_ZIP_BYTES:
                    raise ReleaseError("Download ist unerwartet groß")
                h.update(chunk)
                f.write(chunk)
    if length and size != length:
        raise ReleaseError(f"Download unvollständig ({size} von {length} Bytes)")
    return h.hexdigest()


def _safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and "\\" not in name


def stage(zip_path: Path, target: Path) -> None:
    """Validate the zip and extract it into an empty `target` directory.

    Permissions are set explicitly (dirs 755, files 644, executables 755) so
    the staged tree can be copied into the server directory as is.
    """
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as e:
        raise ReleaseError(f"Kein gültiges Zip: {e}") from e
    with zf:
        infos = zf.infolist()
        names = {i.filename for i in infos}
        for i in infos:
            if not _safe_member(i.filename):
                raise ReleaseError(f"Unsicherer Pfad im Zip: {i.filename!r}")
            mode = i.external_attr >> 16
            if mode and stat.S_ISLNK(mode):
                raise ReleaseError(f"Symbolischer Link im Zip: {i.filename!r}")
        for req in REQUIRED_MEMBERS:
            if req not in names and not any(n.startswith(req) for n in names):
                raise ReleaseError(f"Zip enthält {req} nicht – kein Bedrock-Server?")
        if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
            raise ReleaseError("Zip ist entpackt unerwartet groß")
        bad = zf.testzip()
        if bad:
            raise ReleaseError(f"Zip ist beschädigt (Prüfsumme falsch bei {bad})")

        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        os.chmod(target, 0o755)
        for i in infos:
            dest = target / i.filename
            if i.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                os.chmod(dest, 0o755)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(dest.parent, 0o755)
            with zf.open(i) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            executable = (i.external_attr >> 16) & 0o111 or i.filename == "bedrock_server"
            os.chmod(dest, 0o755 if executable else 0o644)
    if not os.access(target / "bedrock_server", os.X_OK):
        raise ReleaseError("bedrock_server ist nach dem Entpacken nicht ausführbar")
