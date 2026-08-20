# -*- coding: utf-8 -*-
"""Audit visible Qt text against its rendered logical-pixel bounds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton, QWidget

from src import auth_client
from src.login_window import LoginWindow
from src.main_window import MainWindow
from src.settings_dialog import SettingsDialog
from src.theme import Colors, global_stylesheet, resolve_fonts
from src.update_dialog import UpdateDialog


def _plain_text(text: str) -> bool:
    return "<" not in text and ">" not in text


def _text_bounds(widget: QWidget, text: str, width: int, wrap: bool) -> QRect:
    flags = Qt.TextFlag.TextWordWrap if wrap else Qt.TextFlag.TextSingleLine
    return widget.fontMetrics().boundingRect(QRect(0, 0, max(1, width), 10000), int(flags), text)


def audit_window(window: QWidget, state: str) -> list[str]:
    failures: list[str] = []
    for widget in window.findChildren(QWidget):
        if not widget.isVisibleTo(window):
            continue
        text = str(getattr(widget, "text", lambda: "")() or "")
        if not text or not _plain_text(text):
            continue
        name = widget.objectName() or widget.accessibleName() or text.replace("\n", " / ")[:42]
        prefix = f"{state}: {type(widget).__name__} [{name}]"

        if isinstance(widget, QPushButton):
            lines = text.splitlines() or [""]
            compact_control = widget.width() <= 24 and widget.height() <= 24
            available_w = max(1, widget.width() - (0 if compact_control else 16))
            available_h = max(1, widget.height() - (0 if compact_control else 12))
            widest = max(widget.fontMetrics().horizontalAdvance(line) for line in lines)
            needed_h = widget.fontMetrics().lineSpacing() * len(lines)
            if widest > available_w or needed_h > available_h:
                failures.append(
                    f"{prefix} needs {widest}x{needed_h}, has {available_w}x{available_h}"
                )
            continue

        if isinstance(widget, QCheckBox):
            lines = text.splitlines() or [""]
            available_w = max(1, widget.width() - 28)
            available_h = widget.height()
            widest = max(widget.fontMetrics().horizontalAdvance(line) for line in lines)
            needed_h = widget.fontMetrics().lineSpacing() * len(lines)
            if widest > available_w or needed_h > available_h:
                failures.append(
                    f"{prefix} needs {widest}x{needed_h}, has {available_w}x{available_h}"
                )
            continue

        if isinstance(widget, QLabel):
            wrap = widget.wordWrap() or "\n" in text
            bounds = _text_bounds(widget, text, widget.width(), wrap)
            if bounds.height() > widget.height():
                failures.append(
                    f"{prefix} needs height {bounds.height()}, has {widget.height()}"
                )
            elif not wrap and bounds.width() > widget.width():
                failures.append(
                    f"{prefix} needs width {bounds.width()}, has {widget.width()}"
                )
    return failures


def _palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    app.setPalette(palette)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    resolve_fonts()
    _palette(app)
    app.setStyleSheet(global_stylesheet())
    auth_client.get_saved_credentials = lambda: None
    failures: list[str] = []

    main_window = MainWindow()
    main_window.show()
    main_window.toggle_inline_help(False)
    for size in ((900, 620), (960, 676), (1280, 800), (1360, 900)):
        main_window.resize(*size)
        main_window._switch_page(0)
        app.processEvents()
        failures.extend(audit_window(main_window, f"main automation {size[0]}x{size[1]}"))
        main_window._switch_page(1)
        for tab in range(4):
            main_window._settings_tab_bar.setCurrentIndex(tab)
            app.processEvents()
            failures.extend(audit_window(main_window, f"main settings{tab} {size[0]}x{size[1]}"))
    main_window.close()

    login = LoginWindow()
    login.resize(600, 600)
    login.show()
    app.processEvents()
    failures.extend(audit_window(login, "login 600x600"))
    login.stack.setCurrentIndex(1)
    app.processEvents()
    failures.extend(audit_window(login, "register 600x600"))
    login.close()

    settings = SettingsDialog()
    settings.resize(460, 560)
    settings.show()
    app.processEvents()
    failures.extend(audit_window(settings, "settings dialog 460x560"))
    settings.close()

    update = UpdateDialog(
        "3.0.62-beta.20260820",
        update_info={
            "version": "3.1.0-release-candidate.2",
            "size_mb": 48.2,
            "changelog": "글꼴 배율 및 긴 상태 문구 레이아웃을 개선했습니다.",
        },
    )
    update.resize(560, 520)
    update.show()
    app.processEvents()
    failures.extend(audit_window(update, "update dialog 560x520"))
    update.close()

    if failures:
        print("\n".join(failures))
        print(f"FAIL: {len(failures)} text-fit issue(s)")
        return 1
    print("PASS: visible text fits all audited windows and logical sizes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
