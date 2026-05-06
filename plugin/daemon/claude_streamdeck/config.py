"""TOML config loader for the daemon."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _expand(p: str) -> Path:
    return Path(p).expanduser()


@dataclass
class DaemonConfig:
    socket_path: Path = field(
        default_factory=lambda: _expand("~/.config/claude-streamdeck/daemon.sock")
    )
    assets_dir: Path = field(
        default_factory=lambda: _expand("~/.config/claude-streamdeck/assets")
    )
    max_asset_bytes: int = 5 * 1024 * 1024
    extensions: list[dict[str, Any]] = field(default_factory=list)


def load_config(path: Optional[Path]) -> DaemonConfig:
    if path is None or not path.exists():
        return DaemonConfig()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    daemon = raw.get("daemon", {}) or {}
    cfg = DaemonConfig(
        socket_path=_expand(daemon.get("socket_path",
                                       "~/.config/claude-streamdeck/daemon.sock")),
        assets_dir=_expand(daemon.get("assets_dir",
                                      "~/.config/claude-streamdeck/assets")),
        max_asset_bytes=int(daemon.get("max_asset_bytes", 5 * 1024 * 1024)),
        extensions=list(raw.get("extensions", []) or []),
    )
    return cfg
