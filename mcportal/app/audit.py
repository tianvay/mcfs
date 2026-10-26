"""Append-only log of the portal's own actions (one JSON object per line)."""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, action: str, result: str, user: str = "local", **details: object) -> dict:
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,
            "action": action,
            "result": result,
            **{k: v for k, v in details.items() if v not in (None, "")},
        }
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def tail(self, limit: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        with self._lock, open(self.path, encoding="utf-8") as f:
            last = deque(f, maxlen=limit)
        out = []
        for line in reversed(last):
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
