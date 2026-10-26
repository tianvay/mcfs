"""Reading the server log from the systemd journal."""
from __future__ import annotations

import asyncio
import subprocess
from collections.abc import AsyncIterator

from .logparse import LogLine, parse_journal_line

_BASE = ["journalctl", "--no-pager", "-o", "short-unix", "-q"]


def read(unit: str, since: float | None = None) -> list[LogLine]:
    cmd = [*_BASE, "-u", unit]
    if since is not None:
        cmd += ["--since", f"@{int(since)}"]
    out = subprocess.run(cmd, capture_output=True, timeout=120, check=False).stdout
    lines = (parse_journal_line(l) for l in out.decode("utf-8", "replace").splitlines())
    return [l for l in lines if l is not None]


async def follow(unit: str) -> AsyncIterator[LogLine]:
    """Yield new log lines as they arrive. Ends if journalctl exits."""
    proc = await asyncio.create_subprocess_exec(
        *_BASE, "-u", unit, "-f", "-n", "0",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = parse_journal_line(raw.decode("utf-8", "replace"))
            if line is not None:
                yield line
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
