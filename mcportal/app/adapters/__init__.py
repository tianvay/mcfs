from __future__ import annotations

from ..config import Config
from .base import MinecraftAdapter


def create_adapter(cfg: Config) -> MinecraftAdapter:
    if cfg.adapter == "fake":
        from .fake import FakeAdapter
        return FakeAdapter(cfg.server_dir)
    from .bedrock import BedrockAdapter
    return BedrockAdapter(cfg.unit, cfg.server_dir, cfg.console_fifo)
