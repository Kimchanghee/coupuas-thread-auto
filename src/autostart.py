"""Windows startup registration for the desktop app."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_RUN_KEY_NAME = "CoupangThreadAuto"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return sys.platform == "win32"


def _quote(value: str) -> str:
    escaped = str(value).replace('"', r'\"')
    return f'"{escaped}"'


def _resolve_gui_python_executable() -> Path:
    executable = Path(sys.executable).resolve()
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return executable


def build_launch_command() -> str:
    """Return the command Windows should run at user login."""
    if getattr(sys, "frozen", False):
        return _quote(str(Path(sys.executable).resolve()))

    project_root = Path(__file__).resolve().parents[1]
    entrypoint = project_root / "login_main.py"
    return f"{_quote(str(_resolve_gui_python_executable()))} {_quote(str(entrypoint))}"


def _open_run_key(access: int):
    import winreg

    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, access)


def enable_auto_start(command: str | None = None) -> bool:
    if not is_supported():
        return False

    import winreg

    try:
        launch_command = command or build_launch_command()
        with _open_run_key(winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_RUN_KEY_NAME, 0, winreg.REG_SZ, launch_command)
        logger.info("Windows auto-start enabled: %s", launch_command)
        return True
    except Exception:
        logger.exception("Windows auto-start registration failed.")
        return False


def disable_auto_start() -> bool:
    if not is_supported():
        return False

    import winreg

    try:
        with _open_run_key(winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_RUN_KEY_NAME)
            except FileNotFoundError:
                pass
        logger.info("Windows auto-start disabled.")
        return True
    except Exception:
        logger.exception("Windows auto-start removal failed.")
        return False


def get_registered_command() -> str:
    if not is_supported():
        return ""

    import winreg

    try:
        with _open_run_key(winreg.KEY_READ) as key:
            value, _value_type = winreg.QueryValueEx(key, APP_RUN_KEY_NAME)
        return str(value or "")
    except FileNotFoundError:
        return ""
    except Exception:
        logger.exception("Windows auto-start lookup failed.")
        return ""


def sync_auto_start(enabled: bool) -> bool:
    if not is_supported():
        return True
    return enable_auto_start() if enabled else disable_auto_start()


def sync_configured_auto_start(enabled: bool) -> bool:
    """Apply the saved preference unless an isolated smoke test disabled registry writes."""
    if os.getenv("THREAD_AUTO_DISABLE_AUTOSTART_SYNC", "").strip() == "1":
        logger.info("Windows auto-start sync disabled for isolated verification.")
        return True
    return sync_auto_start(enabled)
