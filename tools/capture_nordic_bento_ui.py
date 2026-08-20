# -*- coding: utf-8 -*-
"""Create deterministic Nordic Bento UI screenshots without a live login."""

from __future__ import annotations

import os
import sys
from pathlib import Path


if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from src import auth_client
from src.hidpi import configure_high_dpi
from src.login_window import LoginWindow
from src.main_window import MainWindow
from src.settings_dialog import SettingsDialog
from src.theme import Colors, global_stylesheet, resolve_fonts
from src.update_dialog import UpdateDialog


def _capture(window: QWidget, output_dir: Path, name: str) -> Path:
    QApplication.processEvents()
    path = output_dir / f"{name}.png"
    if not window.grab().save(str(path), "PNG"):
        raise RuntimeError(f"Could not save screenshot: {path}")
    return path


def main() -> int:
    configure_high_dpi()
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    resolve_fonts()

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    app.setPalette(palette)
    app.setStyleSheet(global_stylesheet())

    output_dir = ROOT / "output" / "ui-nordic"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Avoid using or auto-submitting any credentials while capturing the shell.
    auth_client.get_saved_credentials = lambda: None
    login = LoginWindow()
    login.resize(720, 760)
    login.show()
    app.processEvents()
    _capture(login, output_dir, "login")
    login.stack.setCurrentIndex(1)
    app.processEvents()
    _capture(login, output_dir, "register")
    login.hide()

    window = MainWindow()
    window._header_username_full_text = "Nordic Studio"
    window._header_username_label.setText("Nordic Studio")
    window._connection_label.setText("온라인")
    window._online_dot.setStyleSheet(
        f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
    )
    window._work_label.setText("3 / 20 회")
    window._plan_badge.setText("쇼핑 프로")
    window.links_text.setPlainText(
        "https://link.coupang.com/a/sample\n"
        "https://naver.me/sample\n"
        "https://www.aliexpress.com/item/100500.html"
    )
    window._append_log("대기열을 확인했습니다.")
    window._append_log("3개 링크의 채널 분류가 완료되었습니다.")
    window._set_results(2, 0)
    window.show()
    app.processEvents()
    window.toggle_inline_help(False)

    window.resize(1360, 900)
    window._switch_page(0)
    app.processEvents()
    _capture(window, output_dir, "automation-wide")

    window._switch_page(1)
    for index, name in enumerate(
        (
            "settings-writing",
            "settings-accounts",
            "settings-ai-app",
            "settings-subscription-support",
        )
    ):
        window._settings_tab_bar.setCurrentIndex(index)
        app.processEvents()
        _capture(window, output_dir, name)

    window.resize(900, 620)
    window._switch_page(0)
    app.processEvents()
    _capture(window, output_dir, "automation-compact")

    settings_dialog = SettingsDialog(window)
    settings_dialog.resize(580, 720)
    settings_dialog.show()
    app.processEvents()
    _capture(settings_dialog, output_dir, "settings-dialog")
    settings_dialog.hide()

    update_dialog = UpdateDialog(
        "3.0.62",
        window,
        update_info={
            "version": "3.1.0",
            "size_mb": 48.2,
            "changelog": "Nordic Bento UI\n고해상도 화면 대응\n접근성 및 안정성 개선",
        },
    )
    update_dialog.resize(640, 580)
    update_dialog.show()
    app.processEvents()
    _capture(update_dialog, output_dir, "update-dialog")
    update_dialog.hide()

    login.deleteLater()
    settings_dialog.deleteLater()
    update_dialog.deleteLater()
    window.close()
    window.deleteLater()
    app.processEvents()
    for path in sorted(output_dir.glob("*.png")):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
