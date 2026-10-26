"""The only console commands the portal can build. Never pass user input through unchecked."""
from __future__ import annotations

import re

# Xbox gamertags: letters, digits, spaces (not leading/trailing), optional #1234 suffix.
_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9 _-]{0,30}[A-Za-z0-9_-])?(?:#\d{1,4})?$")


def valid_player_name(name: str) -> bool:
    return bool(_NAME_RE.match(name)) and "  " not in name


def _name_arg(name: str) -> str:
    if not valid_player_name(name):
        raise ValueError("Ungültiger Spielername")
    return f'"{name}"' if " " in name else name


def list_players() -> str:
    return "list"


def allowlist_add(name: str) -> str:
    return f"allowlist add {_name_arg(name)}"


def say_update() -> str:
    # fixed text - no user input reaches the console
    return "say Der Server wird gleich für ein Update neu gestartet (ca. 1 Minute)."


def permission_reload() -> str:
    # re-read permissions.json (documented in bedrock_server_how_to.html)
    return "permission reload"


def allowlist_remove(name: str) -> str:
    return f"allowlist remove {_name_arg(name)}"
