import sys
from pathlib import Path

from src import autostart
from src.config import Config


def test_config_auto_start_defaults_to_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = Config()

    assert cfg.auto_start_enabled is True


def test_config_persists_auto_start_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = Config()
    cfg.auto_start_enabled = False
    cfg.save()

    reloaded = Config()
    assert reloaded.auto_start_enabled is False


def test_build_launch_command_uses_login_entrypoint(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    command = autostart.build_launch_command()

    expected_executable = autostart._resolve_gui_python_executable()
    assert str(expected_executable) in command
    assert "login_main.py" in command


def test_build_launch_command_prefers_pythonw(monkeypatch, tmp_path):
    python_exe = tmp_path / "python.exe"
    pythonw_exe = tmp_path / "pythonw.exe"
    python_exe.write_text("", encoding="utf-8")
    pythonw_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(autostart.sys, "executable", str(python_exe))
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)

    command = autostart.build_launch_command()

    assert str(pythonw_exe.resolve()) in command
    assert str(python_exe.resolve()) not in command


def test_sync_auto_start_is_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "linux")

    assert autostart.sync_auto_start(True) is True
    assert autostart.sync_auto_start(False) is True
