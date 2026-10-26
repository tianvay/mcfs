"""The only console commands the portal can build. Never pass user input through unchecked."""
from __future__ import annotations

import json
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


def gamemode_survival(name: str) -> str:
    return f"gamemode survival {_name_arg(name)}"


# fixed texts - only the validated player name comes from outside
OPERATOR_MESSAGES = {True: "§6Du bist jetzt Operator.", False: "§6Du bist nicht mehr Operator."}


def tell_operator_status(name: str, granted: bool) -> str:
    raw = json.dumps({"rawtext": [{"text": OPERATOR_MESSAGES[granted]}]}, ensure_ascii=False)
    return f"tellraw {_name_arg(name)} {raw}"


def permission_reload() -> str:
    # re-read permissions.json (documented in bedrock_server_how_to.html)
    return "permission reload"


SAVE_STEPS = ("hold", "query", "resume")


def world_save(step: str) -> str:
    # consistent copy of the running world (documented in bedrock_server_how_to.html)
    if step not in SAVE_STEPS:
        raise ValueError("unknown save step")
    return f"save {step}"


def allowlist_remove(name: str) -> str:
    return f"allowlist remove {_name_arg(name)}"
