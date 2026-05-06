"""Tests for the TOML config loader."""

from pathlib import Path

import pytest

from claude_streamdeck.config import DaemonConfig, load_config


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(None)
    assert isinstance(cfg, DaemonConfig)
    assert cfg.socket_path.name == "daemon.sock"
    assert cfg.extensions == []


def test_loads_from_toml(tmp_path: Path):
    f = tmp_path / "cfg.toml"
    f.write_text("""
[daemon]
socket_path = "/tmp/x.sock"
assets_dir = "/tmp/assets"

[[extensions]]
module = "claude_streamdeck.extensions.echo"
config = { log_level = "debug" }
""")
    cfg = load_config(f)
    assert str(cfg.socket_path) == "/tmp/x.sock"
    assert str(cfg.assets_dir) == "/tmp/assets"
    assert cfg.extensions == [
        {"module": "claude_streamdeck.extensions.echo", "config": {"log_level": "debug"}}
    ]


def test_user_path_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "cfg.toml"
    f.write_text("""
[daemon]
socket_path = "~/sock"
""")
    cfg = load_config(f)
    assert str(cfg.socket_path) == str(tmp_path / "sock")
