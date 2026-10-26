"""Sending commands to the server console.

The console is a FIFO provided by `minecraft-bedrock.socket` (change M2) and
connected to the server's stdin. Only commands built in `commands.py` are sent.
"""
from __future__ import annotations

import os
import stat


class ConsoleUnavailable(RuntimeError):
    pass


def available(fifo: str) -> bool:
    try:
        return stat.S_ISFIFO(os.stat(fifo).st_mode) and os.access(fifo, os.W_OK)
    except OSError:
        return False


def send(fifo: str, command: str) -> None:
    if "\n" in command or "\r" in command:
        raise ValueError("command must be a single line")
    if not available(fifo):
        raise ConsoleUnavailable("Server-Konsole nicht verfügbar")
    try:
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError as e:  # ENXIO: nobody reading
        raise ConsoleUnavailable(f"Server-Konsole nicht erreichbar: {e.strerror}") from e
    try:
        os.write(fd, (command + "\n").encode("utf-8"))
    finally:
        os.close(fd)
