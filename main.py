"""
쿠팡 파트너스 스레드 자동화 - 메인 애플리케이션
Stitch Blue 테마

개발자 자동 진입 엔트리포인트입니다.
실제 로그인 시작 엔트리포인트는 login_main.py 입니다.
"""
# 환경과 경로를 먼저 고정한 뒤 GUI 모듈을 불러와야 합니다.
# ruff: noqa: E402
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

# 프로젝트 루트 .env 우선 로드 (다른 PC에서도 동작)
_PROJECT_ROOT = Path(__file__).resolve().parent
_LOCAL_ENV = _PROJECT_ROOT / ".env"
if _LOCAL_ENV.exists():
    load_dotenv(_LOCAL_ENV, override=False)


def _allow_external_env_loading() -> bool:
    return (
        os.getenv("THREAD_AUTO_LOAD_EXTERNAL_ENV", "").strip() == "1"
        and os.getenv("THREAD_AUTO_TRUST_EXTERNAL_ENV", "").strip() == "1"
    )

# project-user-dashboard 백엔드의 .env 로드 (형제 프로젝트)
_DASHBOARD_ENV = _PROJECT_ROOT.parent / "project-user-dashboard" / ".env"
if _allow_external_env_loading() and _DASHBOARD_ENV.exists() and not _DASHBOARD_ENV.is_symlink():
    load_dotenv(_DASHBOARD_ENV, override=False)

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QPixmap, QFont, QPainter, QColor, QLinearGradient,
    QPainterPath, QPen, QBrush, QFontDatabase
)

from src.theme import Colors, Typography, resolve_fonts
from src.app_logging import setup_logging
from src.app_icon import apply_app_icon_to_application
from src.hidpi import configure_high_dpi, center_window
VERSION = "v3.2.1"
logger = logging.getLogger(__name__)
APP_ICON_REL_PATH = Path("images") / "app_icon.ico"


def _exit_if_already_running():
    from src.single_instance import acquire_single_instance_guard

    guard = acquire_single_instance_guard()
    if guard.already_running:
        guard.activate_existing_window()
        print("프로그램이 이미 실행 중입니다.")
        return None
    return guard


def _sync_auto_start_setting() -> None:
    try:
        from src.autostart import sync_configured_auto_start
        from src.config import config

        sync_configured_auto_start(bool(getattr(config, "auto_start_enabled", False)))
    except Exception:
        logger.exception("자동 실행 설정을 반영하지 못했습니다.")


def _create_main_window(login_win, auth_result, main_window_cls=None):
    """Create/show MainWindow and attach auth/login references for session continuity."""
    logger.info("메인 윈도우를 생성합니다.")
    if main_window_cls is None:
        from src.main_window import MainWindow
        main_window_cls = MainWindow

    main_win = main_window_cls()
    main_win._auth_data = auth_result
    main_win._login_ref = login_win
    if hasattr(main_win, '_update_account_display'):
        main_win._update_account_display()
    center_window(main_win)
    main_win.show()
    logger.info("메인 윈도우 표시 완료")
    return main_win


def _init_qt_app_font(app: QApplication) -> None:
    """
    Make UI font match D:\\Dithub\\NewshoppingShorts-1 defaults:
    Pretendard -> Malgun Gothic -> Apple SD Gothic Neo (fallback).

    Also try loading bundled fonts from ./fonts if present.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(base_dir, "fonts")
    if os.path.isdir(fonts_dir):
        for name in os.listdir(fonts_dir):
            if name.lower().endswith((".ttf", ".otf")):
                try:
                    QFontDatabase.addApplicationFont(os.path.join(fonts_dir, name))
                except Exception:
                    pass

    available = set(QFontDatabase.families())
    candidates = ["Pretendard", "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", "Segoe UI"]
    family = next((n for n in candidates if n in available), "")
    qf = QFont(family, 10) if family else QFont()
    try:
        qf.setHintingPreference(QFont.PreferFullHinting)
    except Exception:
        pass
    app.setFont(qf)


def _resolve_runtime_path(relative_path: Path) -> Path:
    """Resolve resource path for source and frozen builds."""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass))
        candidates.append(Path(sys.executable).resolve().parent)
    candidates.append(Path(__file__).resolve().parent)

    for base in candidates:
        path = base / relative_path
        if path.exists():
            return path
    return candidates[0] / relative_path


def _apply_app_icon(app: QApplication) -> None:
    """Apply application icon when available."""
    try:
        apply_app_icon_to_application(app)
    except Exception:
        pass


class SplashScreen(QSplashScreen):
    """프리미엄 스플래시 화면 - Stitch Blue 테마"""

    WIDTH = 500
    HEIGHT = 300
    _FONT_FAMILY = None

    @classmethod
    def _resolve_font(cls):
        """theme.resolve_fonts()에서 설정된 Typography.FAMILY를 반환"""
        if cls._FONT_FAMILY is not None:
            return cls._FONT_FAMILY
        cls._FONT_FAMILY = Typography.FAMILY
        return cls._FONT_FAMILY

    def __init__(self):
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(QColor(Colors.BG_DARK))
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.progress = 0
        self._status_msg = ""

    def drawContents(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
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
        painter.setPen(Qt.PenStyle.NoPen)
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
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(cx - cr, cy - cr, cr * 2, cr * 2, 30 * 16, 300 * 16)

        # Letter inside
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 19, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - cr, cy - cr, cr * 2, cr * 2), Qt.AlignmentFlag.AlignCenter, "C")

        # ---- Title ----
        painter.setPen(QColor(Colors.TEXT_PRIMARY))
        painter.setFont(QFont(fn, 18, QFont.Weight.Bold))
        painter.drawText(0, 112, w, 30, Qt.AlignmentFlag.AlignCenter, "쿠팡 파트너스")

        # ---- Subtitle ----
        painter.setPen(QColor(Colors.ACCENT))
        painter.setFont(QFont(fn, 12, QFont.Weight.DemiBold))
        painter.drawText(0, 142, w, 22, Qt.AlignmentFlag.AlignCenter, "스레드 자동화")

        # ---- Tagline ----
        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.setFont(QFont(fn, 9))
        painter.drawText(0, 172, w, 18, Qt.AlignmentFlag.AlignCenter, "쿠팡 파트너스 Threads 자동 업로드")

        # ---- Status message ----
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        painter.setFont(QFont(fn, 9))
        painter.drawText(0, 210, w, 18, Qt.AlignmentFlag.AlignCenter, self._status_msg)

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
        painter.drawText(0, 262, w, 16, Qt.AlignmentFlag.AlignCenter, VERSION)

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


def _parse_int_env(env_name: str, default: int) -> int:
    raw_value = str(os.getenv(env_name, "")).strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _parse_bool_env(env_name: str, default: bool) -> bool:
    raw_value = str(os.getenv(env_name, "")).strip().lower()
    if not raw_value:
        return default
    if raw_value in {"1", "true", "yes", "y", "on"}:
        return True
    if raw_value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _build_developer_auth_result() -> dict:
    username = str(os.getenv("THREAD_AUTO_DEV_USERNAME", "developer") or "").strip() or "developer"
    user_id = str(os.getenv("THREAD_AUTO_DEV_USER_ID", username) or "").strip() or username
    token = str(os.getenv("THREAD_AUTO_DEV_TOKEN", f"dev-session-{user_id}") or "").strip()
    if not token:
        token = f"dev-session-{user_id}"

    work_count = max(_parse_int_env("THREAD_AUTO_DEV_WORK_COUNT", 999_999), 0)
    work_used = max(_parse_int_env("THREAD_AUTO_DEV_WORK_USED", 0), 0)
    if work_used > work_count:
        work_count = work_used
    remaining_count = max(work_count - work_used, 0)

    plan_type = str(os.getenv("THREAD_AUTO_DEV_PLAN_TYPE", "pro") or "").strip() or "pro"
    subscription_status = str(
        os.getenv("THREAD_AUTO_DEV_SUBSCRIPTION_STATUS", "active") or ""
    ).strip() or "active"
    is_paid = _parse_bool_env("THREAD_AUTO_DEV_IS_PAID", True)

    return {
        "status": True,
        "id": user_id,
        "user_id": user_id,
        "username": username,
        "key": token,
        "token": token,
        "work_count": work_count,
        "work_used": work_used,
        "remaining_count": remaining_count,
        "plan_type": plan_type,
        "subscription_status": subscription_status,
        "is_paid": is_paid,
    }


def _inject_developer_auth_state(auth_result: dict) -> None:
    try:
        from src import auth_client

        merge_fn = getattr(auth_client, "_merge_account_state", None)
        if callable(merge_fn):
            merge_fn(auth_result)
            logger.info(
                "개발자 세션 주입 완료 (username=%s, user_id=%s)",
                auth_result.get("username"),
                auth_result.get("user_id"),
            )
            return

        state = getattr(auth_client, "_auth_state", None)
        state_lock = getattr(auth_client, "_AUTH_STATE_LOCK", None)
        if isinstance(state, dict) and state_lock is not None:
            with state_lock:
                state.update(
                    {
                        "user_id": auth_result.get("user_id"),
                        "username": auth_result.get("username"),
                        "token": auth_result.get("token"),
                        "token_issued_at": time.time(),
                        "work_count": int(auth_result.get("work_count", 0)),
                        "work_used": int(auth_result.get("work_used", 0)),
                        "remaining_count": int(auth_result.get("remaining_count", 0)),
                        "plan_type": auth_result.get("plan_type"),
                        "subscription_status": auth_result.get("subscription_status"),
                        "is_paid": bool(auth_result.get("is_paid", True)),
                    }
                )
            logger.info("개발자 세션 메모리 상태 주입 완료")
            return
    except Exception:
        logger.exception("개발자 세션 주입에 실패했습니다.")


def main():
    # Environment changes belong to the executable entrypoint. Importing this
    # module for VERSION or helpers must never enable quota bypass implicitly.
    os.environ.setdefault("THREAD_AUTO_DEV_ENTRYPOINT", "1")
    os.environ.setdefault("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")

    single_instance_guard = _exit_if_already_running()
    if single_instance_guard is None:
        return

    log_file = setup_logging(capture_print=True)
    logger.info("애플리케이션을 시작합니다.")
    logger.info("로그 파일 경로: %s", log_file)
    _sync_auto_start_setting()

    # High-DPI + 화면 맞춤 스케일: 어떤 해상도/배율(125·150%)·작은 화면에서도
    # UI가 동일 비율로 보이고 창이 잘리지 않도록 (QApplication 생성 전에 호출)
    configure_high_dpi()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    _apply_app_icon(app)
    _init_qt_app_font(app)

    # Resolve system fonts for consistent rendering (fixes broken font-family in QSS)
    resolve_fonts()
    base_font = QFont(Typography.FAMILY, 10)
    base_font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(base_font)

    # Dark palette base
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    # Splash
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    steps = [
        ("설정 불러오는 중...", 20),
        ("서비스 초기화 중...", 40),
        ("인터페이스 구성 중...", 60),
        ("브라우저 세션 확인 중...", 80),
        ("준비 완료!", 100),
    ]

    for message, progress in steps:
        splash.showMessage(message)
        splash.setProgress(progress)
        app.processEvents()
        for _ in range(3):
            time.sleep(0.05)
            app.processEvents()

    auth_result = _build_developer_auth_result()
    _inject_developer_auth_state(auth_result)
    app._login_window = None
    app._main_window = _create_main_window(None, auth_result)
    splash.finish(app._main_window)
    logger.info(
        "개발자 자동 진입 완료 (username=%s, user_id=%s)",
        auth_result.get("username"),
        auth_result.get("user_id"),
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
