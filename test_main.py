"""
메인 윈도우 테스트 실행 (로그인 없이)
"""
import sys
import os
import io
import logging

# Windows console UTF-8
def _to_utf8_text_stream(stream, std_stream=None):
    buffer = getattr(stream, "buffer", None)
    if std_stream is not None and stream is not std_stream:
        return stream
    if buffer is None:
        return stream
    return io.TextIOWrapper(buffer, encoding='utf-8', errors='replace', line_buffering=True)


if sys.platform == 'win32':
    sys.stdout = _to_utf8_text_stream(sys.stdout, sys.__stdout__)
    sys.stderr = _to_utf8_text_stream(sys.stderr, sys.__stderr__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── DPI 스케일링 ──
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor

from src.theme import Colors, global_stylesheet
from src.main_window import MainWindow
from src.app_logging import setup_logging

logger = logging.getLogger(__name__)


def main():
    log_file = setup_logging(app_name="coupuas-thread-auto-test")
    logger.info("Test main startup")
    logger.info("Log file path: %s", log_file)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Dark palette base
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.AlternateBase, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(Colors.ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    # 메인 윈도우 직접 실행
    main_win = MainWindow()
    main_win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
