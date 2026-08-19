import sys
from pathlib import Path
from types import SimpleNamespace

from src import autostart
from src.config import Config


def test_config_auto_start_defaults_to_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = Config()

    assert cfg.auto_start_enabled is False


def test_config_persists_auto_start_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = Config()
    cfg.auto_start_enabled = True
    cfg.save()

    reloaded = Config()
    assert reloaded.auto_start_enabled is True


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


def test_isolated_smoke_can_disable_registry_sync(monkeypatch):
    calls = []
    monkeypatch.setenv("THREAD_AUTO_DISABLE_AUTOSTART_SYNC", "1")
    monkeypatch.setattr(autostart, "sync_auto_start", lambda enabled: calls.append(enabled))

    assert autostart.sync_configured_auto_start(True) is True
    assert calls == []


def test_configured_auto_start_delegates_and_returns_result(monkeypatch):
    calls = []
    monkeypatch.delenv("THREAD_AUTO_DISABLE_AUTOSTART_SYNC", raising=False)
    monkeypatch.setattr(
        autostart,
        "sync_auto_start",
        lambda enabled: calls.append(enabled) or False,
    )

    assert autostart.sync_configured_auto_start(True) is False
    assert calls == [True]


def test_registry_writes_only_the_application_run_value(monkeypatch):
    calls = []

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

    fake_winreg = SimpleNamespace(
        KEY_SET_VALUE=2,
        REG_SZ=1,
        SetValueEx=lambda _key, name, _reserved, value_type, value: calls.append(
            ("set", name, value_type, value)
        ),
        DeleteValue=lambda _key, name: calls.append(("delete", name)),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    monkeypatch.setattr(autostart, "is_supported", lambda: True)
    monkeypatch.setattr(autostart, "_open_run_key", lambda _access: FakeKey())

    assert autostart.enable_auto_start("pythonw app.py") is True
    assert autostart.disable_auto_start() is True
    assert calls == [
        ("set", autostart.APP_RUN_KEY_NAME, fake_winreg.REG_SZ, "pythonw app.py"),
        ("delete", autostart.APP_RUN_KEY_NAME),
    ]
