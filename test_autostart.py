import sys
from pathlib import Path

from src import autostart
from src.config import Config


def test_config_auto_start_defaults_to_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg = Config()

    assert cfg.auto_start_enabled is True


def test_config_persists_auto_start_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg = Config()
    cfg.auto_start_enabled = False
    cfg.save()

    reloaded = Config()
    assert reloaded.auto_start_enabled is False


def test_build_launch_command_uses_login_entrypoint(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    command = autostart.build_launch_command()

    assert str(Path(sys.executable).resolve()) in command
    assert "login_main.py" in command


def test_sync_auto_start_is_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "linux")

    assert autostart.sync_auto_start(True) is True
    assert autostart.sync_auto_start(False) is True
