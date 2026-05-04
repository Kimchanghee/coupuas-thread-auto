# -*- coding: utf-8 -*-
"""로그인 없이 MainWindow 직접 띄워 페이지별 캡처 (rate-limit 우회)."""
import sys, os, io, logging
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette, QColor

from src.theme import Colors, global_stylesheet, resolve_fonts
from src.app_logging import setup_logging
from src.main_window import MainWindow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tour_nl")
OUT = os.path.dirname(os.path.abspath(__file__))


def shot(w, name):
    pix = w.grab()
    p = os.path.join(OUT, f"tour_{name}.png")
    pix.save(p, "PNG")
    log.info(f"  saved {p} ({pix.width()}x{pix.height()})")


def main():
    setup_logging(app_name="coupuas-tour-nl")
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_CARD))
    pal.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    app.setPalette(pal)
    resolve_fonts()
    app.setStyleSheet(global_stylesheet())

    win = MainWindow()
    win.move(100, 60); win.show(); win.raise_()

    # 자동 update dialog 자동 닫기 (5초간)
    from src.update_dialog import UpdateDialog
    def kill():
        for w in list(app.topLevelWidgets()):
            if isinstance(w, QMessageBox) and w.isVisible(): w.close()
            elif isinstance(w, UpdateDialog) and w.isVisible(): w.close()
    for d in (300, 1200, 2400, 3600, 5000): QTimer.singleShot(d, kill)

    def s1():
        log.info("page 0")
        win._switch_page(0)
        QTimer.singleShot(400, lambda: (shot(win, "v5_page0"), QTimer.singleShot(300, s2)))
    def s2():
        log.info("page 1")
        win._switch_page(1)
        QTimer.singleShot(400, lambda: (shot(win, "v5_page1"), QTimer.singleShot(300, s3)))
    def s3():
        log.info("page 2")
        win._switch_page(2)
        QTimer.singleShot(400, lambda: (shot(win, "v5_page2"), QTimer.singleShot(300, app.quit)))
    QTimer.singleShot(2500, s1)
    sys.exit(app.exec())


if __name__ == "__main__":
    sys.exit(main())
