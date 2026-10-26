"""Adapter for a Bedrock Dedicated Server managed by systemd."""
from __future__ import annotations

from collections.abc import AsyncIterator

from . import commands, console, journal, systemd
from .files import ServerFiles
from .logparse import LogLine
from .systemd import UnitState
from .updater import BedrockUpdater


class BedrockAdapter:
    def __init__(self, unit: str, server_dir: str, console_fifo: str):
        self.unit = unit
        self.fifo = console_fifo
        self.files = ServerFiles(server_dir)
        self.updater = BedrockUpdater(server_dir)

    def announce_update(self) -> None:
        console.send(self.fifo, commands.say_update())

    def unit_state(self) -> UnitState:
        return systemd.show(self.unit)

    def control(self, verb: str) -> tuple[bool, str]:
        return systemd.control(self.unit, verb)

    def read_log(self, since: float | None = None) -> list[LogLine]:
        return journal.read(self.unit, since)

    def follow_log(self) -> AsyncIterator[LogLine]:
        return journal.follow(self.unit)

    def console_available(self) -> bool:
        return console.available(self.fifo)

    def request_player_list(self) -> None:
        console.send(self.fifo, commands.list_players())

    def allowlist_add_live(self, name: str) -> None:
        console.send(self.fifo, commands.allowlist_add(name))

    def allowlist_remove_live(self, name: str) -> None:
        console.send(self.fifo, commands.allowlist_remove(name))

    def permissions_reload_live(self) -> None:
        console.send(self.fifo, commands.permission_reload())
