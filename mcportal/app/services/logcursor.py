"""Remembers which server log lines a service has already processed.

Stored inside the service's own JSON file as {"ts": <last timestamp>, "hashes": [...]}.
Journal timestamps are not unique, so lines at the newest timestamp are told
apart by a hash of their text. Catch-up after a portal restart and the live
stream may deliver the same line twice - it is applied only once.
"""
from __future__ import annotations

import hashlib

from ..adapters.bedrock.logparse import LogLine


class LogCursor:
    def __init__(self, state: dict):
        self.state = state
        state.setdefault("ts", 0.0)
        state.setdefault("hashes", [])

    @property
    def ts(self) -> float:
        return self.state["ts"]

    def first_time(self, line: LogLine) -> bool:
        """True (and remember the line) if it has not been processed before."""
        h = hashlib.sha1(f"{line.ts}|{line.text}".encode()).hexdigest()[:16]
        s = self.state
        if line.ts < s["ts"] or (line.ts == s["ts"] and h in s["hashes"]):
            return False
        if line.ts > s["ts"]:
            s["ts"], s["hashes"] = line.ts, []
        s["hashes"].append(h)
        return True
