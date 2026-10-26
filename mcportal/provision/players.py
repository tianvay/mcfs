"""Take over the allowlist and operators from another server folder - for provision/import-players.sh.

    python3 players.py import <from dir> <to dir>     -> merges, writes <to dir>/allowlist.json + permissions.json
    python3 players.py count  <dir>                   -> "allowlist=N operators=N"

Both files are checked strictly and written in the server's own layout (in place, owner stays). Entries already in
the target are kept; for the same player the source wins. Prints counts only - names never end up in a log.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"[A-Za-z0-9 _#-]{1,32}")
XUID_RE = re.compile(r"\d{1,20}")
PERMISSIONS = ("operator", "member", "visitor")


class PlayersError(ValueError):
    pass


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
    except ValueError as e:
        raise PlayersError(f"{path.name} ist kein gültiges JSON: {e}") from e
    if not isinstance(data, list):
        raise PlayersError(f"{path.name} ist keine Liste")
    return data


def check_allowlist(data: list) -> list[dict]:
    out = []
    for n, e in enumerate(data, 1):
        if not isinstance(e, dict) or not isinstance(e.get("name"), str) or not NAME_RE.fullmatch(e["name"]):
            raise PlayersError(f"allowlist.json Eintrag {n}: ungültiger Name")
        entry = {"ignoresPlayerLimit": bool(e.get("ignoresPlayerLimit", False)), "name": e["name"]}
        if e.get("xuid") not in (None, ""):
            if not XUID_RE.fullmatch(str(e["xuid"])):
                raise PlayersError(f"allowlist.json Eintrag {n}: ungültige XUID")
            entry["xuid"] = str(e["xuid"])
        out.append(entry)
    return out


def check_permissions(data: list) -> list[dict]:
    out = []
    for n, e in enumerate(data, 1):
        if not isinstance(e, dict) or e.get("permission") not in PERMISSIONS \
                or not XUID_RE.fullmatch(str(e.get("xuid", ""))):
            raise PlayersError(f"permissions.json Eintrag {n}: ungültig")
        out.append({"permission": e["permission"], "xuid": str(e["xuid"])})
    return out


def _player_key(e: dict) -> str:
    return "x:" + e["xuid"] if e.get("xuid") else "n:" + e["name"].lower()


def merge_allowlist(target: list[dict], source: list[dict]) -> list[dict]:
    """Source entries replace target entries of the same player (XUID, else name); order: target first."""
    names = {e["name"].lower(): _player_key(e) for e in source}
    keys = {_player_key(e) for e in source}
    merged = [e for e in target if _player_key(e) not in keys and e["name"].lower() not in names]
    return merged + source


def merge_permissions(target: list[dict], source: list[dict]) -> list[dict]:
    xuids = {e["xuid"] for e in source}
    return [e for e in target if e["xuid"] not in xuids] + source


def _write(path: Path, payload: str) -> None:
    mode = "r+" if path.exists() else "w"
    with open(path, mode, encoding="utf-8", newline="\n") as f:
        f.seek(0)
        f.write(payload)
        f.truncate()
        f.flush()
        os.fsync(f.fileno())


def dump_allowlist(entries: list[dict]) -> str:
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))  # compact, like the server


def dump_permissions(entries: list[dict]) -> str:
    return json.dumps(entries, ensure_ascii=False, indent=3, separators=(",", " : "))  # like the server


def import_players(src: Path, dst: Path) -> dict[str, int]:
    src_allow = check_allowlist(_load(src / "allowlist.json"))
    src_perm = check_permissions(_load(src / "permissions.json"))
    dst_allow = check_allowlist(_load(dst / "allowlist.json"))
    dst_perm = check_permissions(_load(dst / "permissions.json"))
    allow = merge_allowlist(dst_allow, src_allow)
    perm = merge_permissions(dst_perm, src_perm)
    _write(dst / "allowlist.json", dump_allowlist(allow))
    _write(dst / "permissions.json", dump_permissions(perm))
    if check_allowlist(_load(dst / "allowlist.json")) != allow or check_permissions(_load(dst / "permissions.json")) != perm:
        raise PlayersError("Inhalt nach dem Schreiben stimmt nicht")
    return {"from_allowlist": len(src_allow), "from_operators": sum(e["permission"] == "operator" for e in src_perm),
            "kept": len(allow) - len(src_allow), "allowlist": len(allow),
            "operators": sum(e["permission"] == "operator" for e in perm)}


def main(argv: list[str]) -> int:
    try:
        if argv[1] == "import":
            counts = import_players(Path(argv[2]), Path(argv[3]))
            print(" ".join(f"{k}={v}" for k, v in counts.items()))
        elif argv[1] == "count":
            d = Path(argv[2])
            allow = check_allowlist(_load(d / "allowlist.json"))
            perm = check_permissions(_load(d / "permissions.json"))
            print(f"allowlist={len(allow)} operators={sum(e['permission'] == 'operator' for e in perm)}")
        else:
            raise PlayersError(f"unbekannter Befehl {argv[1]}")
    except (PlayersError, OSError, IndexError) as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
