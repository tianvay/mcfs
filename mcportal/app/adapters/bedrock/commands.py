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


# timed events (pack mcportal_events): fixed words only
EVENT_TYPES = ("storm", "mining_rush", "lucky_day", "blood_moon", "zombie_invasion", "bounty")

# weather and time of day from the portal: fixed values only
WEATHER = {"clear": "weather clear", "rain": "weather rain", "thunder": "weather thunder"}
DAYTIME = {"morning": 1000, "noon": 6000, "evening": 12000, "night": 13000, "midnight": 18000}


_REGISTER_KEY = re.compile(r"^[one]-?\d{1,7},-?\d{1,7}$")
REGISTER_BATCH = 100  # keys per console command (the pack accepts up to 200)


def event_register(keys: list[str]) -> str:
    """Chunks with builds (from the map reader) for the events pack's build register."""
    if not keys or len(keys) > REGISTER_BATCH or not all(_REGISTER_KEY.match(k) for k in keys):
        raise ValueError("invalid register keys")
    return "scriptevent mcfs:event register " + ";".join(keys)


def world_control(kind: str, value: str) -> str:
    if kind == "weather" and value in WEATHER:
        return WEATHER[value]
    if kind == "time" and value in DAYTIME:
        return f"time set {DAYTIME[value]}"
    raise ValueError("unknown world setting")


def event_control(action: str, event_type: str | None = None) -> str:
    if action in ("start", "stop"):
        if event_type not in EVENT_TYPES:
            raise ValueError("unknown event type")
        return f"scriptevent mcfs:event {action} {event_type}"
    if action in ("auto_on", "auto_off"):
        return f"scriptevent mcfs:event auto {action[5:]}"
    if action == "state":
        return "scriptevent mcfs:event state"
    raise ValueError("unknown event action")


def allowlist_remove(name: str) -> str:
    return f"allowlist remove {_name_arg(name)}"
