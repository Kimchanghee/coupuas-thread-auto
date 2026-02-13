"""
쿠팡 파트너스 스레드 자동화 - 메인 애플리케이션
Stitch Blue 테마

백엔드 project-user-dashboard(.env)를 함께 로드합니다.
"""
import sys
import os
import io
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

def _to_utf8_text_stream(stream, std_stream=None):
    """
    Wrap stream buffer with UTF-8 TextIOWrapper when possible.
    Some captured streams (e.g. pytest) do not expose .buffer.
    """
    if std_stream is not None and stream is not std_stream:
        return stream
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream
    return io.TextIOWrapper(
        buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True,
    )

# Windows console UTF-8
if sys.platform == 'win32':
    sys.stdout = _to_utf8_text_stream(sys.stdout, sys.__stdout__)
    sys.stderr = _to_utf8_text_stream(sys.stderr, sys.__stderr__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# project-user-dashboard 백엔드의 .env 로드
_DASHBOARD_ENV = Path(__file__).resolve().parent.parent / "project-user-dashboard" / ".env"
if _DASHBOARD_ENV.exists():
    load_dotenv(_DASHBOARD_ENV, override=False)

# DPI 스케일링: 모든 화면에서 동일한 물리 크기로 표시
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import (
    QPixmap, QFont, QPainter, QColor, QLinearGradient,
    QPainterPath, QPen, QBrush, QFontDatabase
)

from src.theme import Colors
from src.app_logging import setup_logging

VERSION = "v2.2.0"
logger = logging.getLogger(__name__)


def _create_main_window(login_win, auth_result, main_window_cls=None):
    """Create/show MainWindow and attach auth/login references for session continuity."""
    logger.info("Creating main window")
    if main_window_cls is None:
        from src.main_window import MainWindow
        main_window_cls = MainWindow

    main_win = main_window_cls()
    main_win._auth_data = auth_result
    main_win._login_ref = login_win
    main_win.show()
    logger.info("Main window visible")
    return main_win


class SplashScreen(QSplashScreen):
    """프리미엄 스플래시 화면 - Stitch Blue 테마"""

    WIDTH = 500
    HEIGHT = 300
    _FONT_FAMILY = None

    @classmethod
    def _resolve_font(cls):
        """테마 폴백 목록에서 사용 가능한 첫 번째 폰트를 찾습니다."""
        if cls._FONT_FAMILY is not None:
            return cls._FONT_FAMILY
        candidates = ["Pretendard", "맑은 고딕", "Malgun Gothic", "Apple SD Gothic Neo", "Segoe UI"]
        available = QFontDatabase().families()
        for name in candidates:
            if name in available:
                cls._FONT_FAMILY = name
                return name
        cls._FONT_FAMILY = ""
        return cls._FONT_FAMILY

    def __init__(self):
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(QColor(Colors.BG_DARK))
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.progress = 0
        self._status_msg = ""

    def drawContents(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.WIDTH, self.HEIGHT
        fn = self._resolve_font()

        # ---- Background gradient ----
        bg_grad = QLinearGradient(0, 0, w, h)
        bg_grad.setColorAt(0, QColor("#0C1220"))
        bg_grad.setColorAt(0.4, QColor(Colors.BG_DARK))
        bg_grad.setColorAt(1, QColor("#0A0F1A"))
        painter.fillRect(0, 0, w, h, bg_grad)

        # ---- Ambient glow behind brand ----
        glow = QLinearGradient(w * 0.25, 20, w * 0.75, 130)
        glow.setColorAt(0, QColor(13, 89, 242, 18))
        glow.setColorAt(1, QColor(13, 89, 242, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(w * 0.1, 5, w * 0.8, 150))

        # ---- Top accent line ----
        top_grad = QLinearGradient(0, 0, w, 0)
        top_grad.setColorAt(0, QColor(13, 89, 242, 0))
        top_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        top_grad.setColorAt(0.7, QColor(Colors.ACCENT_LIGHT))
        top_grad.setColorAt(1, QColor(59, 123, 255, 0))
        painter.fillRect(0, 0, w, 3, top_grad)

        # ---- Brand icon (stylized "C" arc) ----
        cx, cy, cr = w // 2, 72, 26
        ring_pen = QPen(QColor(Colors.ACCENT), 3)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(cx - cr, cy - cr, cr * 2, cr * 2, 30 * 16, 300 * 16)

        # Letter inside
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 19, QFont.Bold))
        painter.drawText(QRectF(cx - cr, cy - cr, cr * 2, cr * 2), Qt.AlignCenter, "C")

        # ---- Title ----
        painter.setPen(QColor(Colors.TEXT_PRIMARY))
        painter.setFont(QFont(fn, 18, QFont.Bold))
        painter.drawText(0, 112, w, 30, Qt.AlignCenter, "\ucfe0\ud321 \ud30c\ud2b8\ub108\uc2a4")

        # ---- Subtitle ----
        painter.setPen(QColor(Colors.ACCENT))
        painter.setFont(QFont(fn, 12, QFont.DemiBold))
        painter.drawText(0, 142, w, 22, Qt.AlignCenter, "\uc2a4\ub808\ub4dc \uc790\ub3d9\ud654")

        # ---- Tagline ----
        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.setFont(QFont(fn, 9))
        painter.drawText(0, 172, w, 18, Qt.AlignCenter, "\ucfe0\ud321 \ud30c\ud2b8\ub108\uc2a4 Threads \uc790\ub3d9 \uc5c5\ub85c\ub4dc")

        # ---- Status message ----
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        painter.setFont(QFont(fn, 9))
        painter.drawText(0, 210, w, 18, Qt.AlignCenter, self._status_msg)

        # ---- Progress bar ----
        bar_x = 90
        bar_y = 240
        bar_w = w - 180
        bar_h = 4

        # Track
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)
        painter.fillPath(track_path, QColor(Colors.BORDER))

        # Fill
        if self.progress > 0:
            fill_w = int(bar_w * self.progress / 100)
            fill_grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            fill_grad.setColorAt(0, QColor(Colors.ACCENT))
            fill_grad.setColorAt(1, QColor(Colors.ACCENT_LIGHT))
            fill_path = QPainterPath()
            fill_path.addRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)
            painter.fillPath(fill_path, fill_grad)

        # ---- Version ----
        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.setFont(QFont(fn, 8))
        painter.drawText(0, 262, w, 16, Qt.AlignCenter, VERSION)

        # ---- Bottom accent line ----
        bot_grad = QLinearGradient(0, 0, w, 0)
        bot_grad.setColorAt(0, QColor(13, 89, 242, 0))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_DARK))
        bot_grad.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, h - 2, w, 2, bot_grad)

    def setProgress(self, value):
        self.progress = value
        self.repaint()

    def showMessage(self, message, *args, **kwargs):
        self._status_msg = message
        super().showMessage(message, *args, **kwargs)
        self.repaint()


def main():
    log_file = setup_logging()
    logger.info("Application startup")
    logger.info("Log file path: %s", log_file)

    # 모든 모니터에서 동일한 물리적 크기 보장
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Dark palette base
    from PyQt5.QtGui import QPalette
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

    # Splash
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    steps = [
        ("\uc124\uc815 \ubd88\ub7ec\uc624\ub294 \uc911...", 20),
        ("\uc11c\ube44\uc2a4 \ucd08\uae30\ud654 \uc911...", 40),
        ("\uc778\ud130\ud398\uc774\uc2a4 \uad6c\uc131 \uc911...", 60),
        ("\ube0c\ub77c\uc6b0\uc800 \uc138\uc158 \ud655\uc778 \uc911...", 80),
        ("\uc900\ube44 \uc644\ub8cc!", 100),
    ]

    for message, progress in steps:
        splash.showMessage(message)
        splash.setProgress(progress)
        app.processEvents()
        for _ in range(3):
            time.sleep(0.05)
            app.processEvents()

    # Login window
    from src.login_window import LoginWindow
    login_win = LoginWindow()
    logger.info("Login window displayed")
    app._login_window = login_win
    app._main_window = None

    def on_login_success(result):
        logger.info("Login success callback received")
        login_win.hide()
        app._main_window = _create_main_window(login_win, result)
        logger.info("Main window created and shown")
    login_win.login_success.connect(on_login_success)
    login_win.show()
    splash.finish(login_win)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
