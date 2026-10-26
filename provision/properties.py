"""Helpers for provision/setup.sh - pure Python, no third-party modules (runs with the system python3).

    python3 properties.py conf      <server.conf>                         -> checked KEY=value lines
    python3 properties.py merge     <server.properties> <overrides> <server.conf>   (file changed in place)
    python3 properties.py render    <template> <server.conf> [KEY=value ...]       -> rendered text on stdout

Values are checked strictly, because they end up in a systemd unit and in server.properties.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# allowed values per key in server.conf
RULES = {
    "SERVER_NAME": r"[\w ÄÖÜäöüß'!.-]{1,40}",
    "WORLD_NAME": r"[\w ÄÖÜäöüß'-]{1,40}",
    "LEVEL_SEED": r"-?[\w]{0,30}",
    "GAMEMODE": r"survival|creative|adventure",
    "DIFFICULTY": r"peaceful|easy|normal|hard",
    "MAX_PLAYERS": r"[1-9]\d?",
    "VIEW_DISTANCE": r"(?:[5-9]|[1-9]\d)",
    "TICK_DISTANCE": r"[4-9]|1[0-2]",
    "PORT_V4": r"\d{4,5}",
    "PORT_V6": r"\d{4,5}",
    "LAN_VISIBILITY": r"true|false",
    "MC_USER": r"[a-z_][a-z0-9_-]{0,30}",
    "MC_DIR": r"/[A-Za-z0-9_./-]+",
}
REQUIRED = set(RULES)


class ConfError(ValueError):
    pass


def read_conf(text: str) -> dict[str, str]:
    conf: dict[str, str] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfError(f"Zeile {n}: KEY=Wert erwartet")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in RULES:
            raise ConfError(f"Zeile {n}: unbekannte Einstellung {key}")
        if not re.fullmatch(RULES[key], value):
            raise ConfError(f"Zeile {n}: ungültiger Wert für {key}: {value!r}")
        conf[key] = value
    missing = REQUIRED - set(conf)
    if missing:
        raise ConfError(f"fehlende Einstellungen: {', '.join(sorted(missing))}")
    for key in ("PORT_V4", "PORT_V6"):
        if not 1024 <= int(conf[key]) <= 65535:
            raise ConfError(f"{key} muss zwischen 1024 und 65535 liegen")
    if conf["PORT_V4"] == conf["PORT_V6"]:
        raise ConfError("PORT_V4 und PORT_V6 müssen verschieden sein")
    if ".." in conf["MC_DIR"].split("/") or conf["MC_DIR"].rstrip("/") in ("", "/opt", "/home", "/usr", "/var", "/etc"):
        raise ConfError("MC_DIR muss ein eigener Ordner sein")
    return conf


def render(template: str, values: dict[str, str]) -> str:
    """Replace @KEY@; every placeholder must be known (a typo must not end up in a file)."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            raise ConfError(f"unbekannter Platzhalter @{key}@")
        return values[key]
    return re.sub(r"@([A-Z0-9_]+)@", sub, template)


def parse_overrides(text: str) -> list[tuple[str, str]]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        out.append((key.strip(), value.strip()))
    return out


def merge(properties: str, overrides: list[tuple[str, str]]) -> str:
    """Set the keys in Mojang's server.properties (comments and order stay), append unknown ones at the end."""
    lines = properties.splitlines()
    pending = dict(overrides)
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    if pending:
        lines += ["", "# added by provision/setup.sh"] + [f"{k}={v}" for k, v in pending.items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    try:
        if argv[1] == "conf":
            for k, v in read_conf(Path(argv[2]).read_text(encoding="utf-8")).items():
                print(f"{k}={v}")
        elif argv[1] == "merge":
            props, over, conf = (Path(a) for a in argv[2:5])
            values = read_conf(conf.read_text(encoding="utf-8"))
            overrides = parse_overrides(render(over.read_text(encoding="utf-8"), values))
            props.write_text(merge(props.read_text(encoding="utf-8"), overrides), encoding="utf-8", newline="\n")
        elif argv[1] == "render":
            values = read_conf(Path(argv[3]).read_text(encoding="utf-8"))
            for extra in argv[4:]:
                k, v = extra.split("=", 1)
                values[k] = v
            sys.stdout.write(render(Path(argv[2]).read_text(encoding="utf-8"), values))
        else:
            raise ConfError(f"unbekannter Befehl {argv[1]}")
    except (ConfError, OSError, IndexError) as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
