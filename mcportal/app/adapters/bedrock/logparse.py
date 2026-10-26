"""Parsing of Bedrock Dedicated Server log lines (as stored in the systemd journal).

Pure functions only - no I/O - so they can be unit-tested anywhere.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# "[2026-09-20 13:54:34:524 INFO] Player connected: Steve, xuid: 2535400000000001"
_PREFIX_RE = re.compile(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d:\d+ (?P<level>[A-Z]+)\] ?(?P<msg>.*)$")
_CONNECT_RE = re.compile(r"^Player connected: (?P<name>.+?), xuid: (?P<xuid>\d*)")
_SPAWNED_RE = re.compile(r"^Player Spawned: (?P<name>.+?) xuid:")
_DISCONNECT_RE = re.compile(r"^Player disconnected: (?P<name>.+?), xuid: (?P<xuid>\d*)")
_VERSION_RE = re.compile(r"^Version: (?P<version>\d+(?:\.\d+)+)\s*$")
_LIST_RE = re.compile(r"^There are (?P<count>\d+)/(?P<max>\d+) players online:")


@dataclass
class LogLine:
    ts: float          # unix timestamp (journal)
    source: str        # "server" (bedrock stdout) or "systemd"
    text: str          # message without journal prefix

    @property
    def message(self) -> str:
        """Message without the bedrock "[date LEVEL]" prefix."""
        m = _PREFIX_RE.match(self.text)
        return m.group("msg") if m else self.text


def parse_journal_line(raw: str) -> LogLine | None:
    """Parse one line of `journalctl -o short-unix`.

    Format: "<ts> <host> <ident>[pid]: <message>"
    """
    parts = raw.rstrip("\n").split(" ", 3)
    if len(parts) < 4:
        return None
    try:
        ts = float(parts[0])
    except ValueError:
        return None
    ident = parts[2]
    source = "systemd" if ident.startswith("systemd") else "server"
    return LogLine(ts=ts, source=source, text=parts[3])


def parse_spawned(line: LogLine) -> str | None:
    """Name from "Player Spawned: <name> xuid: ..." - the player is in the world now."""
    if line.source != "server":
        return None
    m = _SPAWNED_RE.match(line.message)
    return m.group("name") if m else None


def parse_version(line: LogLine) -> str | None:
    if line.source != "server":
        return None
    m = _VERSION_RE.match(line.message)
    return m.group("version") if m else None


@dataclass
class OnlinePlayer:
    name: str
    xuid: str
    since: float


@dataclass
class PlayerTracker:
    """Reconstructs the set of online players from the server log of the current run."""

    players: dict[str, OnlinePlayer] = field(default_factory=dict)  # key: lower-case name
    server_started: bool = False
    _awaiting_list: int | None = None
    _list_ts: float = 0.0

    def reset(self) -> None:
        self.players.clear()
        self.server_started = False
        self._awaiting_list = None

    def feed(self, line: LogLine) -> bool:
        """Process one log line. Returns True if the player set / started flag changed."""
        if line.source == "systemd":
            t = line.text
            # not on "Started ...": with the start check (M8) systemd reports it only after the
            # server's own "Server started." - a reset there would hide a running server
            if t.startswith(("Stopped ", "Stopping ")) or "Deactivated" in t or "Failed" in t:
                had = bool(self.players) or self.server_started
                self.reset()
                return had
            return False

        msg = line.message

        if self._awaiting_list is not None:
            # The names follow the "There are n/m players online:" header as a bare line.
            self._awaiting_list = None
            if not _PREFIX_RE.match(line.text):
                names = [n.strip() for n in msg.split(",") if n.strip()]
                return self._apply_list(names, line.ts)

        m = _LIST_RE.match(msg)
        if m:
            count = int(m.group("count"))
            if count == 0:
                return self._apply_list([], line.ts)
            self._awaiting_list = count
            return False

        return self._feed_regular(msg, line)

    def _feed_regular(self, msg: str, line: LogLine) -> bool:
        if msg.startswith("Starting Server"):
            self.reset()
            return True
        if msg.startswith("Server started."):
            self.server_started = True
            return True
        m = _CONNECT_RE.match(msg)
        if m:
            name = m.group("name")
            self.players[name.lower()] = OnlinePlayer(name=name, xuid=m.group("xuid"), since=line.ts)
            return True
        m = _DISCONNECT_RE.match(msg)
        if m:
            return self.players.pop(m.group("name").lower(), None) is not None
        return False

    def _apply_list(self, names: list[str], ts: float) -> bool:
        """Reconcile with the authoritative output of the `list` command."""
        wanted = {n.lower(): n for n in names}
        changed = False
        for key in list(self.players):
            if key not in wanted:
                del self.players[key]
                changed = True
        for key, name in wanted.items():
            if key not in self.players:
                self.players[key] = OnlinePlayer(name=name, xuid="", since=ts)
                changed = True
        return changed


def version_history(lines: list[LogLine]) -> list[tuple[float, str]]:
    """Return [(first_seen_ts, version)] in order, one entry per version change."""
    history: list[tuple[float, str]] = []
    for line in lines:
        v = parse_version(line)
        if v and (not history or history[-1][1] != v):
            history.append((line.ts, v))
    return history


def parse_pack_line(line: LogLine, tag: str, versions: tuple[int, ...] = (1,)) -> dict | None:
    """Payload of a "[Scripting] [<tag>] {...}" line written by one of our behavior packs, or None."""
    if line.source != "server":
        return None
    prefix = f"[Scripting] [{tag}] "
    msg = line.message
    if not msg.startswith(prefix):
        return None
    try:
        data = json.loads(msg[len(prefix):])
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("v") in versions else None


def parse_stats(line: LogLine) -> dict | None:
    """Line of the stats pack (minecraft-pack/mcportal_stats); v2 since pack 2.0."""
    return parse_pack_line(line, "mcportal-stats", (1, 2))


def parse_achievements(line: LogLine) -> dict | None:
    """Line of the achievements pack (minecraft-pack/mcportal_achievements)."""
    return parse_pack_line(line, "mcportal-ach")
