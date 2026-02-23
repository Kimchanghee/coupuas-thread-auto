# -*- coding: utf-8 -*-
"""Shared application icon helpers."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon

APP_ICON_REL_PATH = Path("images") / "app_icon.ico"


@lru_cache(maxsize=1)
def resolve_app_icon_path() -> Optional[Path]:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass))
        candidates.append(Path(sys.executable).resolve().parent)

    # src/app_icon.py -> project root
    candidates.append(Path(__file__).resolve().parent.parent)

    for base in candidates:
        icon_path = base / APP_ICON_REL_PATH
        if icon_path.exists():
            return icon_path
    return None


@lru_cache(maxsize=1)
def get_app_icon() -> QIcon:
    icon_path = resolve_app_icon_path()
    if icon_path is None:
        return QIcon()
    return QIcon(str(icon_path))


def apply_window_icon(widget) -> None:
    """Apply app icon to any widget/window if available."""
    if widget is None:
        return
    icon = get_app_icon()
    if icon.isNull():
        return
    try:
        widget.setWindowIcon(icon)
    except Exception:
        pass


def apply_app_icon_to_application(app) -> None:
    """Apply app icon to QApplication if available."""
    if app is None:
        return
    icon = get_app_icon()
    if icon.isNull():
        return
    try:
        app.setWindowIcon(icon)
    except Exception:
        pass

