# -*- coding: utf-8 -*-
"""
쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (PyQt6)
Stitch Blue 디자인 - 사이드바 + 스택 페이지 레이아웃
좌표 기반 배치 (setGeometry), 레이아웃 매니저 없음
"""
import re
import html
import os
import time
import logging
import threading
import queue
import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QListWidget, QFrame,
    QLineEdit, QSpinBox, QCheckBox, QButtonGroup,
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QEvent, QUrl
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen, QDesktopServices

from src.config import config
from src.coupang_uploader import CoupangPartnersPipeline
from src.gemini_keys import (
    MAX_GEMINI_API_KEYS,
    normalize_gemini_api_keys,
    save_configured_gemini_api_keys,
    select_working_gemini_api_key,
)
from src.theme import (Colors, Typography, Radius, Gradients,
                       global_stylesheet, badge_style, stat_card_style,
                       terminal_text_style,
                       muted_text_style,
                       hint_text_style, section_title_style)
from src.ui_messages import ask_yes_no, show_error, show_info, show_warning
from src.events import LoginStatusEvent
from src.threads_navigation import (
    goto_threads_with_fallback,
    friendly_threads_navigation_error,
    is_browser_launch_error,
)

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────

WIN_W = 1280
WIN_H = 800
HEADER_H = 68
SIDEBAR_W = 280
CONTENT_W = 1000  # WIN_W - SIDEBAR_W
CONTENT_H = 700   # WIN_H - HEADER_H - STATUSBAR_H
STATUSBAR_H = 32


# ─── Helpers ────────────────────────────────────────────────

def _format_interval(seconds):
    """Return a human-readable interval."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}시간 {m}분 {s}초"
    if m > 0:
        return f"{m}분 {s}초"
    return f"{s}초"


# ─── Signals ────────────────────────────────────────────────

class Signals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(str)
    results = pyqtSignal(int, int)
    product = pyqtSignal(str, bool)
    finished = pyqtSignal(dict)
    step_update = pyqtSignal(int, str)       # step_index, status
    link_status = pyqtSignal(str, str, str)  # url, status, product_name
    queue_progress = pyqtSignal(str)
    reset_steps = pyqtSignal()
    threads_login_launch = pyqtSignal(bool, str)  # success, detail
    threads_browser_closed = pyqtSignal()


# ─── Badge ──────────────────────────────────────────────────

class Badge(QLabel):
    """작은 알약형 상태 배지."""
    def __init__(self, text="", color=Colors.ACCENT, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(52)
        self._apply(color)

    def _apply(self, color):
        self.setStyleSheet(badge_style(color))

    def update_style(self, color, text=None):
        if text:
            self.setText(text)
        self._apply(color)


# ─── HeaderBar ──────────────────────────────────────────────

class HeaderBar(QFrame):
    """그라디언트 헤더 바 (accent 라인 포함)."""
    ACCENT_LINE_H = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(HEADER_H)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 배경 그라디언트
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#12203A"))
        grad.setColorAt(0.5, QColor("#162847"))
        grad.setColorAt(1, QColor("#12203A"))
        painter.fillRect(self.rect(), grad)

        # 상단 accent 라인
        accent = QLinearGradient(0, 0, w, 0)
        accent.setColorAt(0, QColor(13, 89, 242, 0))
        accent.setColorAt(0.2, QColor(Colors.ACCENT))
        accent.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        accent.setColorAt(0.8, QColor(Colors.ACCENT))
        accent.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, 0, w, self.ACCENT_LINE_H, accent)

        # 하단 border
        painter.setPen(QPen(QColor(13, 89, 242, 80), 1))
        painter.drawLine(0, h - 1, w, h - 1)


# ─── SidebarPanel ──────────────────────────────────────────

class SidebarPanel(QFrame):
    """어두운 사이드바 패널 (오른쪽 border 라인)."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 배경
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111827"))
        painter.drawRect(0, 0, w, h)

        # 오른쪽 border 라인
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawLine(w - 1, 0, w - 1, h)


# ─── SectionFrame ──────────────────────────────────────────

class SectionFrame(QFrame):
    """둥근 카드 프레임 (설정/Threads 섹션용)."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(QColor(Colors.BG_CARD))
        painter.drawRoundedRect(rect, 12, 12)


# ─── MainWindow ─────────────────────────────────────────────

class MainWindow(QMainWindow):
    """쿠팡 파트너스 스레드 자동화 메인 윈도우 - 사이드바 레이아웃."""

    MAX_LOG_LINES = 2000

    COUPANG_LINK_PATTERN = re.compile(
        r'https?://(?:link\.coupang\.com|www\.coupang\.com)[^\s<>"\']*',
        re.IGNORECASE
    )

    # Sidebar menu items
    _SIDEBAR_ITEMS = [
        "링크 입력",
        "업로드 설정",
        "설정",
    ]

    # Process steps for progress panel
    _PROCESS_STEPS = [
        "링크 분석",
        "콘텐츠 생성",
        "Threads 업로드",
        "완료 처리",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coupang Partners Thread Automation")
        self.setFixedSize(WIN_W, WIN_H)

        self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._urls_lock = threading.Lock()
        self.link_queue = queue.Queue()
        self.processed_urls = set()
        self._closed = False
        self._browser_cancel = threading.Event()
        self._link_url_row_map = {}  # url -> table row index
        self._active_pipeline = None
        self._session_expiry_notified = False
        self._redirecting_to_login = False
        self._force_close_for_relogin = False
        self._init_activity_logger()
        logger.info("메인 윈도우 초기화 완료")

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)
        self.signals.step_update.connect(self._update_step)
        self.signals.link_status.connect(self._update_link_table_status)
        self.signals.queue_progress.connect(self._set_queue_progress)
        self.signals.reset_steps.connect(self._reset_steps)
        self.signals.threads_login_launch.connect(self._on_threads_login_launch_result)
        self.signals.threads_browser_closed.connect(self._on_threads_browser_closed)

        self._current_page = 0
        # Apply global stylesheet before building widgets so sizeHint/metrics are correct
        # for any fixed-geometry placement that depends on styled font/padding.
        self.setStyleSheet(global_stylesheet())
        self._build_ui()
        self._switch_page(0)
        self._tutorial_overlay = None
        self._tutorial_widgets = {}
        self._app_version = self._resolve_app_version()

        # Heartbeat timer
        from PyQt6.QtCore import QTimer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(60_000)
        QTimer.singleShot(1000, self._send_heartbeat)

        # Auto update check
        QTimer.singleShot(3000, self._check_for_updates_silent)

        # Load settings into widgets
        self._load_settings()
        self._bind_ui_activity_logging()
        self._log_user_activity("ui_main_window_opened", f"version={self._app_version}")

        logger.info("메인 윈도우 UI 구성 완료")

    @property
    def is_running(self):
        return not self._stop_event.is_set()

    @is_running.setter
    def is_running(self, value):
        if value:
            self._stop_event.clear()
        else:
            self._stop_event.set()

    @staticmethod
    def _resolve_app_version():
        """Resolve app version from loaded entry modules."""
        for module_name in ("__main__", "main"):
            module = sys.modules.get(module_name)
            version = getattr(module, "VERSION", None)
            if isinstance(version, str) and version.strip():
                return version.strip()

        try:
            from main import VERSION
            if isinstance(VERSION, str) and VERSION.strip():
                return VERSION.strip()
        except Exception:
            pass

        return "unknown"

    def _init_activity_logger(self):
        self._activity_log_queue = queue.Queue(maxsize=1200)
        self._activity_log_stop = threading.Event()
        self._activity_log_thread = threading.Thread(
            target=self._activity_log_worker_loop,
            daemon=True,
            name="ui-activity-log-worker",
        )
        self._activity_log_last_sent = {}
        self._activity_log_last_sent_lock = threading.Lock()
        self._activity_log_bind_done = False
        self._activity_log_thread.start()

    def _activity_log_worker_loop(self):
        while True:
            if self._activity_log_stop.is_set() and self._activity_log_queue.empty():
                break
            try:
                action, content, level = self._activity_log_queue.get(timeout=0.4)
            except queue.Empty:
                continue

            try:
                from src import auth_client
                auth_client.log_action(action, content, level=level)
            except Exception:
                logger.debug("UI activity log enqueue/send failed", exc_info=True)
            finally:
                self._activity_log_queue.task_done()

    def _log_user_activity(
        self,
        action: str,
        content: str | None = None,
        *,
        level: str = "INFO",
        min_interval_sec: float = 0.0,
        dedupe_key: str | None = None,
    ):
        action_text = str(action or "").strip()
        if not action_text:
            return

        content_text = " ".join(str(content or "").split())
        if len(content_text) > 700:
            content_text = content_text[:697] + "..."

        if min_interval_sec > 0:
            key = str(dedupe_key or f"{level}:{action_text}:{content_text}")
            now = time.monotonic()
            with self._activity_log_last_sent_lock:
                last = float(self._activity_log_last_sent.get(key, 0.0))
                if now - last < float(min_interval_sec):
                    return
                self._activity_log_last_sent[key] = now

        try:
            self._activity_log_queue.put_nowait((action_text, content_text, str(level or "INFO")))
        except queue.Full:
            logger.debug("UI activity log queue full; drop action=%s", action_text)

    def _log_button_click(self, button_id: str, button_widget: QPushButton | None):
        label = ""
        if button_widget is not None:
            try:
                label = " ".join(str(button_widget.text() or "").split())
            except Exception:
                label = ""
        self._log_user_activity(
            "ui_button_click",
            f"id={button_id}; text={label}",
        )

    def _bind_ui_activity_logging(self):
        if getattr(self, "_activity_log_bind_done", False):
            return

        self._activity_log_bind_done = True
        button_bindings = (
            ("logout_btn", "header_logout"),
            ("tutorial_btn", "header_tutorial"),
            ("_work_label", "header_work_label"),
            ("_plan_badge", "header_plan_badge"),
            ("start_btn", "links_start_upload"),
            ("add_btn", "links_add_to_queue"),
            ("stop_btn", "links_stop_upload"),
            ("_upload_save_btn", "upload_settings_save"),
            ("threads_login_btn", "settings_threads_login"),
            ("check_login_btn", "settings_threads_login_check"),
            ("_add_gemini_key_btn", "settings_add_gemini_key"),
            ("_pay_monthly_btn", "settings_pay_monthly"),
            ("_tutorial_settings_btn", "settings_tutorial_replay"),
            ("_contact_btn", "settings_contact"),
            ("_settings_save_btn", "settings_save"),
        )

        for attr_name, button_id in button_bindings:
            button = getattr(self, attr_name, None)
            if isinstance(button, QPushButton):
                button.clicked.connect(
                    lambda _checked=False, bid=button_id, btn=button: self._log_button_click(bid, btn)
                )

        for row_index, row in enumerate(getattr(self, "_gemini_key_rows", []), start=1):
            toggle_btn = row.get("toggle") if isinstance(row, dict) else None
            if isinstance(toggle_btn, QPushButton):
                toggle_btn.clicked.connect(
                    lambda _checked=False, idx=row_index, btn=toggle_btn: self._log_button_click(
                        f"settings_gemini_key_toggle_{idx}",
                        btn,
                    )
                )

    def _open_external_link(self, url: str, context: str) -> bool:
        href = str(url or "").strip()
        context_text = str(context or "unknown")
        if not href:
            self._log_user_activity("ui_link_click", f"context={context_text}; url=(empty)", level="WARNING")
            return False

        self._log_user_activity("ui_link_click", f"context={context_text}; url={href}")
        opened = QDesktopServices.openUrl(QUrl(href))
        if not opened:
            self._log_user_activity(
                "ui_link_open_failed",
                f"context={context_text}; url={href}",
                level="WARNING",
            )
        return bool(opened)

    def _page_label(self, index: int) -> str:
        if 0 <= int(index) < len(self._SIDEBAR_ITEMS):
            return str(self._SIDEBAR_ITEMS[int(index)])
        return f"unknown-{index}"

    # ────────────────────────────────────────────────────────
    #  BUILD UI
    # ────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        self._build_header(central)
        self._build_sidebar(central)
        self._build_pages(central)
        self._build_statusbar(central)

    # ── Header ──────────────────────────────────────────────

    def _build_header(self, parent):
        header = HeaderBar(parent)
        header.setGeometry(0, 0, WIN_W, HEADER_H)

        # Brand glow
        brand_glow = QLabel("", header)
        brand_glow.setGeometry(14, 14, 40, 40)
        brand_glow.setStyleSheet(
            "QLabel { background-color: rgba(13, 89, 242, 0.25);"
            " border: 2px solid rgba(13, 89, 242, 0.4);"
            " border-radius: 20px; }"
        )

        # Brand icon
        brand_icon = QLabel("C", header)
        brand_icon.setGeometry(16, 16, 36, 36)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setStyleSheet(
            f"QLabel {{ background: {Gradients.ACCENT_BTN};"
            f" color: #FFFFFF; border-radius: 18px;"
            f" font-size: 15pt; font-weight: 800; }}"
        )

        # Title
        title_label = QLabel("스레드 쇼핑 자동화", header)
        title_label.setGeometry(62, 10, 220, 30)
        title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 15pt; font-weight: 800;"
            " letter-spacing: -0.5px; background: transparent;"
        )

        # Subtitle
        sub_label = QLabel("THREAD SHOPPING AUTOMATION", header)
        sub_label.setGeometry(62, 38, 260, 20)
        sub_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 700;"
            " letter-spacing: 2px; background: transparent;"
        )

        # Right-side elements (positioned from right edge)
        _nav_pill_style = (
            f"QPushButton {{ background: rgba(13, 89, 242, 0.08);"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid rgba(13, 89, 242, 0.15);"
            f" border-radius: 8px; font-size: 9pt; font-weight: 700;"
            f" padding: 6px 14px; }}"
            f" QPushButton:hover {{ background: rgba(13, 89, 242, 0.20);"
            f" color: #FFFFFF; border-color: rgba(13, 89, 242, 0.40); }}"
            f" QPushButton:focus {{ outline: none;"
            f" border-color: rgba(13, 89, 242, 0.15); }}"
        )

        # Logout button (far right)
        self.logout_btn = QPushButton("로그아웃", header)
        self.logout_btn.setGeometry(WIN_W - 80, 20, 64, 28)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(239, 68, 68, 0.08);"
            f" color: {Colors.TEXT_MUTED};"
            f" border: 1px solid rgba(239, 68, 68, 0.15);"
            f" border-radius: 14px; font-size: 9pt; font-weight: 600;"
            f" padding: 4px 12px; }}"
            f" QPushButton:hover {{ background: rgba(239, 68, 68, 0.25);"
            f" color: {Colors.ERROR}; border-color: {Colors.ERROR}; }}"
            f" QPushButton:focus {{ outline: none;"
            f" border-color: rgba(239, 68, 68, 0.15); }}"
        )
        self.logout_btn.clicked.connect(self._do_logout)

        # Tutorial button
        self.tutorial_btn = QPushButton("Tutorial", header)
        self.tutorial_btn.setGeometry(WIN_W - 80 - 12 - 56, 20, 56, 28)
        self.tutorial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tutorial_btn.setStyleSheet(_nav_pill_style)
        self.tutorial_btn.clicked.connect(self.open_tutorial)

        # Re-place header pills by sizeHint to avoid text clipping across fonts
        nav_y = 20
        nav_h = 28
        nav_gap = 10
        nav_right = WIN_W - 16
        for btn in (self.logout_btn, self.tutorial_btn):
            btn.ensurePolished()
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(nav_h)
            # Keep both buttons visually consistent with reference topbar proportions.
            w = 86
            nav_right -= w
            btn.setGeometry(nav_right, nav_y, w, nav_h)
            nav_right -= nav_gap


        # ── Top-right account controls (reference: NewshoppingShorts topbar) ──
        self._work_label = QPushButton("0 / 0 회", header)
        self._work_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._work_label.setStyleSheet(
            "QPushButton {"
            " background-color: #E31639;"
            " color: #FFFFFF;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 8px 16px;"
            " font-size: 9pt;"
            " font-weight: 700;"
            "}"
            "QPushButton:hover { background-color: #C41230; }"
            "QPushButton:pressed { background-color: #A31029; }"
        )
        self._work_label.clicked.connect(self.open_settings)

        self._header_username_label = QLabel("사용자", header)
        self._header_username_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; background: transparent;"
        )

        self._online_dot = QLabel("", header)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.TEXT_MUTED}; border-radius: 4px;"
        )

        self._connection_label = QLabel("접속 확인 중", header)
        self._connection_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600; background: transparent;"
        )

        self.status_badge = Badge("대기중", Colors.SUCCESS, header)
        self.status_badge.setStyleSheet(
            f"QLabel {{ background-color: rgba(59, 130, 246, 0.14);"
            f" color: {Colors.ACCENT_LIGHT}; border: 1px solid rgba(59, 130, 246, 0.35);"
            f" border-radius: 6px; font-size: 8pt; font-weight: 700; padding: 0 10px; }}"
        )
        self.status_badge.setVisible(False)

        self._plan_badge = QPushButton("무료계정", header)
        self._plan_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plan_badge.setStyleSheet(
            f"QPushButton {{"
            f" background-color: rgba(255, 255, 255, 0.05);"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER};"
            f" border-radius: 6px;"
            f" padding: 6px 12px;"
            f" font-size: 8pt;"
            f" font-weight: 700;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: rgba(255, 255, 255, 0.10);"
            f" border-color: #E31639;"
            f" color: #FFFFFF;"
            f"}}"
        )
        self._plan_badge.clicked.connect(self.open_settings)

        self._header_nav_buttons = (self.logout_btn, self.tutorial_btn)
        self._relayout_header_account_card()

        self._header = header
        self._brand_icon = brand_icon

    def _relayout_header_account_card(self):
        """Layout top-right account controls in a clear button-first hierarchy."""
        nav_buttons = getattr(self, "_header_nav_buttons", ())
        nav_left = min((btn.x() for btn in nav_buttons), default=WIN_W - 16)
        right = nav_left - 12
        top = 19
        control_h = 30
        min_left = 250
        self.status_badge.setVisible(False)

        plan_text = self._plan_badge.text() or "무료계정"
        plan_w = max(self._plan_badge.fontMetrics().horizontalAdvance(plan_text) + 24, 84)
        self._plan_badge.setGeometry(max(min_left, right - plan_w), top, plan_w, control_h)
        right = self._plan_badge.x() - 8

        conn_text = self._connection_label.text() or "접속 확인 중"
        conn_w = max(self._connection_label.fontMetrics().horizontalAdvance(conn_text) + 8, 84)
        self._connection_label.setGeometry(max(min_left, right - conn_w), top + 5, conn_w, 20)
        right = self._connection_label.x() - 7

        self._online_dot.setGeometry(max(min_left, right - 8), top + 11, 8, 8)
        right = self._online_dot.x() - 8

        user_text = self._header_username_label.text() or "사용자"
        user_w = min(max(self._header_username_label.fontMetrics().horizontalAdvance(user_text) + 10, 48), 120)
        self._header_username_label.setGeometry(max(min_left, right - user_w), top + 4, user_w, 20)
        right = self._header_username_label.x() - 8

        work_text = self._work_label.text() or "0 / 0 회"
        work_w = max(self._work_label.fontMetrics().horizontalAdvance(work_text) + 30, 106)
        self._work_label.setGeometry(max(min_left, right - work_w), top, work_w, control_h)
        self._work_label.setToolTip(work_text)

    # ── Sidebar ─────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sidebar = SidebarPanel(parent)
        sidebar.setGeometry(0, HEADER_H, SIDEBAR_W, WIN_H - HEADER_H)
        self._sidebar = sidebar

        # Button group for exclusive selection
        self._sidebar_group = QButtonGroup(self)
        self._sidebar_group.setExclusive(True)
        self._sidebar_buttons = []

        for i, label in enumerate(self._SIDEBAR_ITEMS):
            btn = QPushButton(f"  {label}", sidebar)
            btn.setGeometry(0, 20 + i * 48, SIDEBAR_W, 44)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_style())
            self._sidebar_group.addButton(btn, i)
            self._sidebar_buttons.append(btn)

        self._sidebar_buttons[0].setChecked(True)
        self._sidebar_group.idClicked.connect(
            lambda idx: self._switch_page(idx, source="sidebar_menu")
        )

        # Divider line below buttons
        divider_y = 20 + len(self._SIDEBAR_ITEMS) * 48 + 12
        divider = QFrame(sidebar)
        divider.setGeometry(20, divider_y, SIDEBAR_W - 40, 1)
        divider.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")

        # ── Progress Panel ─────────────────────────────────
        prog_y = divider_y + 16

        prog_title = QLabel("현재 진행 상황", sidebar)
        prog_title.setGeometry(24, prog_y, 200, 20)
        prog_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 700;"
            " letter-spacing: 1.5px; background: transparent;"
        )
        prog_y += 28

        # Queue progress
        self._progress_queue_label = QLabel("전체: 0 / 0", sidebar)
        self._progress_queue_label.setGeometry(24, prog_y, 240, 20)
        self._progress_queue_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 10pt; font-weight: 700;"
            " background: transparent;"
        )
        prog_y += 28

        # Step indicators
        self._step_dots = []
        self._step_labels = []
        for step_name in self._PROCESS_STEPS:
            dot = QLabel("○", sidebar)
            dot.setGeometry(28, prog_y, 16, 20)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 10pt; background: transparent;"
            )
            label = QLabel(step_name, sidebar)
            label.setGeometry(48, prog_y, 200, 20)
            label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 9pt; background: transparent;"
            )
            self._step_dots.append(dot)
            self._step_labels.append(label)
            prog_y += 24

        prog_y += 8

        # Divider before counts
        divider2 = QFrame(sidebar)
        divider2.setGeometry(20, prog_y, SIDEBAR_W - 40, 1)
        divider2.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        prog_y += 12

        # Status label
        self._sidebar_status_label = QLabel("대기중", sidebar)
        self._sidebar_status_label.setGeometry(24, prog_y, 240, 20)
        self._sidebar_status_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )
        prog_y += 26

        # Success / Failed / Total (compact horizontal)
        self._sidebar_success_dot = QLabel("", sidebar)
        self._sidebar_success_dot.setGeometry(24, prog_y + 4, 8, 8)
        self._sidebar_success_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
        )
        self._sidebar_success_label = QLabel("성공: 0", sidebar)
        self._sidebar_success_label.setGeometry(40, prog_y, 70, 20)
        self._sidebar_success_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        self._sidebar_failed_dot = QLabel("", sidebar)
        self._sidebar_failed_dot.setGeometry(120, prog_y + 4, 8, 8)
        self._sidebar_failed_dot.setStyleSheet(
            f"background-color: {Colors.ERROR}; border-radius: 4px;"
        )
        self._sidebar_failed_label = QLabel("실패: 0", sidebar)
        self._sidebar_failed_label.setGeometry(136, prog_y, 70, 20)
        self._sidebar_failed_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        self._sidebar_total_dot = QLabel("", sidebar)
        self._sidebar_total_dot.setGeometry(216, prog_y + 4, 8, 8)
        self._sidebar_total_dot.setStyleSheet(
            f"background-color: {Colors.INFO}; border-radius: 4px;"
        )
        self._sidebar_total_label = QLabel("전체: 0", sidebar)
        self._sidebar_total_label.setGeometry(232, prog_y, 70, 20)
        self._sidebar_total_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )
        prog_y += 30

        # ── Mini Log Area ──────────────────────────────────
        log_title = QLabel("작업 로그", sidebar)
        log_title.setGeometry(24, prog_y, 200, 20)
        log_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 700;"
            " letter-spacing: 1.5px; background: transparent;"
        )
        prog_y += 22

        log_h = max(WIN_H - HEADER_H - prog_y - STATUSBAR_H - 8, 80)
        self.log_text = QTextEdit(sidebar)
        self.log_text.setGeometry(12, prog_y, SIDEBAR_W - 24, log_h)
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(self.MAX_LOG_LINES)
        self.log_text.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: {Colors.BG_TERMINAL};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 8px;"
            f"  padding: 6px;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"  font-family: {Typography.FAMILY_MONO};"
            f"  font-size: 8pt;"
            f"}}"
        )

    @staticmethod
    def _sidebar_btn_style():
        """Sidebar button stylesheet."""
        return (
            f"QPushButton {{"
            f"  background: transparent;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"  border: none;"
            f"  border-left: 3px solid transparent;"
            f"  text-align: left;"
            f"  padding-left: 20px;"
            f"  font-size: 10pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(13, 89, 242, 0.08);"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: rgba(13, 89, 242, 0.12);"
            f"  color: #FFFFFF;"
            f"  border-left: 3px solid {Colors.ACCENT};"
            f"}}"
        )

    # ── Pages ───────────────────────────────────────────────

    def _build_pages(self, parent):
        """Build 3 pages as QWidgets positioned to the right of the sidebar."""
        page_x = SIDEBAR_W
        page_y = HEADER_H
        page_w = CONTENT_W
        page_h = CONTENT_H

        self._pages = []
        for i in range(3):
            page = QWidget(parent)
            page.setGeometry(page_x, page_y, page_w, page_h)
            page.setVisible(False)
            self._pages.append(page)

        self._build_page0_links(self._pages[0])
        self._build_page1_upload(self._pages[1])
        self._build_page2_settings(self._pages[2])

    def _make_page_header(self, page, icon_char, title_text):
        """Page header helper: icon + title + separator. Returns next y."""
        # Icon background
        icon_bg = QLabel("", page)
        icon_bg.setGeometry(28, 20, 36, 36)
        icon_bg.setStyleSheet(
            "QLabel { background-color: rgba(13, 89, 242, 0.15);"
            " border: 1px solid rgba(13, 89, 242, 0.3);"
            " border-radius: 18px; }"
        )
        # Icon text
        icon_label = QLabel(icon_char, page)
        icon_label.setGeometry(28, 20, 36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 14pt; background: transparent;"
        )
        # Title
        title = QLabel(title_text, page)
        title.setGeometry(76, 20, 400, 36)
        title.setStyleSheet(
            "color: #FFFFFF; font-size: 15pt; font-weight: 800;"
            " letter-spacing: -0.3px; background: transparent;"
        )
        # Separator
        sep = QFrame(page)
        sep.setGeometry(28, 66, 944, 1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")

        return 82  # next available y

    # ── Page 0: 링크 입력 ───────────────────────────────────

    def _build_page0_links(self, page):
        cy = self._make_page_header(page, "◈", "링크 입력")

        # Coupang Partners hyperlink (top right)
        self._coupang_link = QLabel(
            '<a href="https://partners.coupang.com/" '
            'style="color: #3B7BFF; text-decoration: none; font-weight: 600;">'
            '쿠팡 파트너스 바로가기 →</a>',
            page
        )
        self._coupang_link.setGeometry(CONTENT_W - 28 - 220, 28, 220, 24)
        self._coupang_link.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._coupang_link.setOpenExternalLinks(False)
        self._coupang_link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._coupang_link.setStyleSheet("background: transparent;")
        self._coupang_link.linkActivated.connect(
            lambda href: self._open_external_link(href, "page_links_coupang_partners")
        )

        # Link count badge
        self.link_count_badge = Badge("0개 링크", Colors.TEXT_MUTED, page)
        self.link_count_badge.setGeometry(CONTENT_W - 28 - 220 - 100, 28, 90, 24)

        # Hint text
        hint = QLabel("아래에 쿠팡 파트너스 URL을 붙여넣기 하세요 (한 줄에 하나씩)", page)
        hint.setGeometry(28, cy, 700, 20)
        hint.setStyleSheet(muted_text_style("9pt"))

        # Links text area (compact)
        self.links_text = QPlainTextEdit(page)
        self.links_text.setGeometry(28, cy + 24, 944, 160)
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://link.coupang.com/a/yyy"
        )
        self.links_text.textChanged.connect(self._update_link_count)

        # Buttons row
        btn_y = cy + 24 + 160 + 12

        # Start button
        self.start_btn = QPushButton("\u25B6  자동화 시작", page)
        self.start_btn.setGeometry(28, btn_y, 240, 44)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {Gradients.ACCENT_BTN};"
            f"  color: #FFFFFF;"
            f"  border: 2px solid rgba(59, 123, 255, 0.5);"
            f"  border-radius: {Radius.LG};"
            f"  font-size: 11pt; font-weight: 800; letter-spacing: 0.5px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Gradients.ACCENT_BTN_HOVER};"
            f"  border-color: rgba(59, 123, 255, 0.8);"
            f"}}"
            f"QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}"
            f"QPushButton:disabled {{"
            f"  background-color: {Colors.BG_ELEVATED};"
            f"  color: {Colors.TEXT_MUTED};"
            f"  border-color: {Colors.BORDER};"
            f"}}"
        )
        self.start_btn.clicked.connect(self.start_upload)

        # Add links button
        self.add_btn = QPushButton("링크 추가", page)
        self.add_btn.setGeometry(278, btn_y, 160, 44)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setEnabled(False)
        self.add_btn.setProperty("class", "outline-success")
        self.add_btn.clicked.connect(self.add_links_to_queue)

        # Stop button
        self.stop_btn = QPushButton("중지", page)
        self.stop_btn.setGeometry(448, btn_y, 120, 44)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "outline-danger")
        self.stop_btn.clicked.connect(self.stop_upload)

        # ── Status Table ───────────────────────────────────
        table_label = QLabel("작업 현황", page)
        table_label.setGeometry(28, btn_y + 54, 200, 20)
        table_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " letter-spacing: 1px; background: transparent;"
        )

        table_y = btn_y + 78
        table_h = CONTENT_H - table_y - 16

        self.link_table = QTableWidget(page)
        self.link_table.setGeometry(28, table_y, 944, table_h)
        self.link_table.setColumnCount(4)
        self.link_table.setHorizontalHeaderLabels(["#", "링크", "상태", "상품명"])
        self.link_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.link_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.link_table.setAlternatingRowColors(False)
        self.link_table.verticalHeader().setVisible(False)

        header = self.link_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.link_table.setColumnWidth(0, 40)
        self.link_table.setColumnWidth(2, 80)

        self.link_table.setStyleSheet(
            f"QTableWidget {{"
            f"  background-color: {Colors.BG_INPUT};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: {Radius.LG};"
            f"  gridline-color: {Colors.BORDER};"
            f"  font-size: 9pt;"
            f"}}"
            f"QTableWidget::item {{"
            f"  padding: 6px 8px;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {Colors.BG_ELEVATED};"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"  border: none;"
            f"  border-bottom: 1px solid {Colors.BORDER};"
            f"  border-right: 1px solid {Colors.BORDER};"
            f"  padding: 8px 6px;"
            f"  font-size: 9pt;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.link_table.cellClicked.connect(self._on_link_table_cell_clicked)

    # ── Page 1: 업로드 설정 ─────────────────────────────────

    def _build_page1_upload(self, page):
        cy = self._make_page_header(page, "⬆", "업로드 설정")

        _field_lbl_style = (
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # ── Upload Interval Section ────────────────────────
        sec1 = SectionFrame(page)
        sec1.setGeometry(28, cy, 944, 140)

        sec1_title = QLabel("업로드 간격", sec1)
        sec1_title.setGeometry(24, 16, 200, 22)
        sec1_title.setStyleSheet(section_title_style())

        interval_hint = QLabel("최소 30초 - 업로드 사이 대기 시간을 설정합니다", sec1)
        interval_hint.setGeometry(24, 42, 500, 16)
        interval_hint.setStyleSheet(hint_text_style())

        self.hour_spin = QSpinBox(sec1)
        self.hour_spin.setGeometry(24, 68, 120, 38)
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" 시간")

        self.min_spin = QSpinBox(sec1)
        self.min_spin.setGeometry(156, 68, 100, 38)
        self.min_spin.setRange(0, 59)
        self.min_spin.setSuffix(" 분")

        self.sec_spin = QSpinBox(sec1)
        self.sec_spin.setGeometry(268, 68, 100, 38)
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setSuffix(" 초")

        # ── Upload Options Section ─────────────────────────
        sec2 = SectionFrame(page)
        sec2.setGeometry(28, cy + 156, 944, 90)

        sec2_title = QLabel("업로드 옵션", sec2)
        sec2_title.setGeometry(24, 16, 200, 22)
        sec2_title.setStyleSheet(section_title_style())

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선", sec2)
        self.video_check.setGeometry(24, 48, 400, 24)

        # ── Save Button ────────────────────────────────────
        self._upload_save_btn = QPushButton("저장", page)
        self._upload_save_btn.setGeometry(832, cy + 268, 140, 42)
        self._upload_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_save_btn.clicked.connect(self._save_settings)

    # ── Page 2: 설정 ────────────────────────────────────────

    def _build_page2_settings(self, page):
        cy = self._make_page_header(page, "⚙", "설정")

        _section_style = (
            "QFrame {"
            " background-color: #141414;"
            " border: 1px solid rgba(255, 255, 255, 0.05);"
            " border-radius: 8px;"
            " outline: none;"
            "}"
        )
        _control_h = 40
        _action_btn_w = 196
        _section_title_style = (
            "color: #FFFFFF; font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        _field_lbl_style = (
            "color: #B8B8B8; font-size: 12px; font-weight: 400; background: transparent; border: none;"
        )
        _hint_lbl_style = (
            "color: #9CA3AF; font-size: 11px; font-weight: 400; background: transparent; border: none;"
        )
        _input_style = (
            "QLineEdit {"
            " background-color: #1A1A1A;"
            " color: #FFFFFF;"
            " border: 1px solid rgba(255, 255, 255, 0.05);"
            " border-radius: 8px;"
            " padding: 9px 12px;"
            " font-size: 12px;"
            " font-weight: 500;"
            "}"
            "QLineEdit:focus {"
            " border: 1px solid #E31639;"
            "}"
        )
        _primary_btn_style = (
            "QPushButton {"
            " background-color: #E31639;"
            " color: #FFFFFF;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 8px 16px;"
            " font-size: 12px;"
            " font-weight: 700;"
            "}"
            "QPushButton:hover {"
            " background-color: #C41231;"
            "}"
            "QPushButton:pressed {"
            " background-color: #A01028;"
            "}"
            "QPushButton:disabled {"
            " background-color: #2A2A2A;"
            " color: #7A7A7A;"
            "}"
        )
        _ghost_btn_style = (
            "QPushButton {"
            " background-color: #1A1A1A;"
            " color: #FFFFFF;"
            " border: 1px solid rgba(255, 255, 255, 0.05);"
            " border-radius: 8px;"
            " padding: 8px 14px;"
            " font-size: 12px;"
            " font-weight: 600;"
            "}"
            "QPushButton:hover {"
            " background-color: #222222;"
            " border-color: rgba(227, 22, 57, 0.7);"
            "}"
            "QPushButton:disabled {"
            " background-color: #161616;"
            " color: #7A7A7A;"
            " border-color: rgba(255, 255, 255, 0.04);"
            "}"
        )
        _tutorial_btn_style = (
            "QPushButton {"
            " background-color: #3B82F6;"
            " color: #FFFFFF;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 8px 16px;"
            " font-size: 12px;"
            " font-weight: 700;"
            "}"
            "QPushButton:hover {"
            " background-color: #2563EB;"
            "}"
            "QPushButton:pressed {"
            " background-color: #1D4ED8;"
            "}"
        )
        _contact_btn_style = (
            "QPushButton {"
            " background-color: #FACC15;"
            " color: #111827;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 8px 16px;"
            " font-size: 12px;"
            " font-weight: 700;"
            "}"
            "QPushButton:hover {"
            " background-color: #EAB308;"
            "}"
            "QPushButton:pressed {"
            " background-color: #CA8A04;"
            "}"
        )

        # Scroll area for settings content
        scroll = QScrollArea(page)
        scroll.setGeometry(0, cy, CONTENT_W, CONTENT_H - cy)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            " background-color: transparent;"
            " width: 10px;"
            " margin: 2px 0 2px 0;"
            "}"
            "QScrollBar::handle:vertical {"
            " background-color: rgba(255, 255, 255, 0.12);"
            " min-height: 28px;"
            " border-radius: 5px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            " background-color: rgba(255, 255, 255, 0.2);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " height: 0px;"
            "}"
        )

        content = QWidget()
        content.setFixedWidth(CONTENT_W)
        scroll.setWidget(content)

        sy = 12

        # ── Section 1: 계정 정보 ───────────────────────────
        acct = QFrame(content)
        acct.setGeometry(24, sy, 952, 104)
        acct.setFrameShape(QFrame.Shape.NoFrame)
        acct.setStyleSheet(_section_style)

        acct_icon = QLabel("U", acct)
        acct_icon.setGeometry(20, 26, 40, 40)
        acct_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acct_icon.setStyleSheet(
            "QLabel {"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E31639, stop:1 #FF4D6A);"
            " color: #FFFFFF;"
            " border-radius: 20px;"
            " font-size: 16px;"
            " font-weight: 700;"
            "}"
        )

        self._acct_username_label = QLabel("사용자", acct)
        self._acct_username_label.setGeometry(74, 24, 320, 24)
        self._acct_username_label.setStyleSheet(
            "color: #FFFFFF; font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )

        self._acct_status_label = QLabel("활성 계정", acct)
        self._acct_status_label.setGeometry(74, 52, 320, 20)
        self._acct_status_label.setStyleSheet(_hint_lbl_style)

        self._acct_plan_badge = QLabel("무료 체험", acct)
        self._acct_plan_badge.setGeometry(768, 24, 160, 28)
        self._acct_plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_plan_badge.setStyleSheet(
            "QLabel {"
            " background-color: rgba(255, 255, 255, 0.05);"
            " color: #B8B8B8;"
            " border: 1px solid rgba(255, 255, 255, 0.05);"
            " border-radius: 8px;"
            " font-size: 11px;"
            " font-weight: 700;"
            "}"
        )

        self._acct_work_label = QLabel("0 / 0 회 사용", acct)
        self._acct_work_label.setGeometry(768, 58, 160, 22)
        self._acct_work_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_work_label.setStyleSheet(
            "color: #9CA3AF; font-size: 11px; background: transparent; border: none;"
        )

        sy += 128

        # ── Section 2: Threads 계정 ────────────────────────
        threads_sec = QFrame(content)
        threads_sec.setGeometry(24, sy, 952, 252)
        threads_sec.setFrameShape(QFrame.Shape.NoFrame)
        threads_sec.setStyleSheet(_section_style)

        threads_title = QLabel("Threads 계정", threads_sec)
        threads_title.setGeometry(24, 14, 220, 24)
        threads_title.setStyleSheet(_section_title_style)

        name_label = QLabel("계정 이름", threads_sec)
        name_label.setGeometry(24, 46, 100, 20)
        name_label.setStyleSheet(_field_lbl_style)

        name_hint = QLabel("프로필 식별용", threads_sec)
        name_hint.setGeometry(124, 46, 220, 20)
        name_hint.setStyleSheet(_hint_lbl_style)

        self.username_edit = QLineEdit(threads_sec)
        self.username_edit.setGeometry(24, 70, 904, _control_h)
        self.username_edit.setPlaceholderText("예: myaccount")
        self.username_edit.setStyleSheet(_input_style)

        self._threads_status_dot = QLabel("", threads_sec)
        self._threads_status_dot.setGeometry(24, 122, 10, 10)
        self._threads_status_dot.setStyleSheet("background-color: #9CA3AF; border-radius: 5px;")

        self.login_status_label = QLabel("연결 안됨", threads_sec)
        self.login_status_label.setGeometry(42, 118, 320, 22)
        self.login_status_label.setStyleSheet(
            "color: #9CA3AF; font-size: 11px; font-weight: 500; background: transparent; border: none;"
        )

        self.threads_login_btn = QPushButton("Threads 로그인", threads_sec)
        self.threads_login_btn.setGeometry(576, 146, 170, _control_h)
        self.threads_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)

        self.check_login_btn = QPushButton("로그인 완료 안내", threads_sec)
        self.check_login_btn.setGeometry(758, 146, 170, _control_h)
        self.check_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_login_btn.clicked.connect(self._check_login_status)

        hint_text = (
            "1) Threads 로그인 버튼을 누르세요.\n"
            "2) 열린 브라우저에서 로그인 완료 후 창을 닫으세요.\n"
            "3) 닫으면 세션이 자동 저장되어 다음 작업에서 바로 사용됩니다."
        )
        self._threads_hint_label = QLabel(hint_text, threads_sec)
        self._threads_hint_label.setGeometry(24, 190, 904, 46)
        self._threads_hint_label.setWordWrap(True)
        self._threads_hint_label.setStyleSheet(_hint_lbl_style)

        sy += 266

        # ── Section 3: Gemini API 설정 (다중 키) ────────────
        self._settings_content = content
        self._settings_flow_start_y = sy
        self._settings_gap = 24
        self._settings_section_x = 24
        self._settings_section_w = 952

        self._settings_api_sec = QFrame(content)
        self._settings_api_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_api_sec.setStyleSheet(_section_style)

        self._settings_api_title = QLabel("Gemini API 설정", self._settings_api_sec)
        self._settings_api_title.setGeometry(24, 14, 220, 24)
        self._settings_api_title.setStyleSheet(_section_title_style)

        self._settings_api_guide = QLabel(
            '<a href="https://ssmaker.lovable.app/notice" '
            'style="color:#3B82F6; text-decoration:none;">API KEY 발급 안내 →</a>',
            self._settings_api_sec,
        )
        self._settings_api_guide.setGeometry(24, 40, 220, 20)
        self._settings_api_guide.setOpenExternalLinks(False)
        self._settings_api_guide.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._settings_api_guide.setStyleSheet("background: transparent; border: none; font-size: 11px;")
        self._settings_api_guide.linkActivated.connect(
            lambda href: self._open_external_link(href, "settings_api_key_guide")
        )

        self._settings_api_hint = QLabel(
            "여러 키를 저장하면 자동으로 다음 키로 전환됩니다. (최대 10개)",
            self._settings_api_sec,
        )
        self._settings_api_hint.setGeometry(252, 42, 650, 18)
        self._settings_api_hint.setStyleSheet(_hint_lbl_style)

        self._gemini_key_rows = []
        for index in range(MAX_GEMINI_API_KEYS):
            badge = QLabel(str(index + 1), self._settings_api_sec)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "QLabel {"
                " background-color: #1F2937;"
                " color: #B8B8B8;"
                " border: 1px solid rgba(255, 255, 255, 0.05);"
                " border-radius: 12px;"
                " font-size: 11px;"
                " font-weight: 700;"
                "}"
            )

            edit = QLineEdit(self._settings_api_sec)
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("Gemini API 키를 입력하세요")
            edit.setStyleSheet(_input_style)

            toggle = QPushButton("보기", self._settings_api_sec)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setStyleSheet(_ghost_btn_style)
            toggle.clicked.connect(
                lambda _checked=False, row_index=index: self._toggle_gemini_key_visibility(row_index)
            )

            self._gemini_key_rows.append(
                {
                    "badge": badge,
                    "edit": edit,
                    "toggle": toggle,
                    "visible": False,
                }
            )

        self._add_gemini_key_btn = QPushButton("키 추가", self._settings_api_sec)
        self._add_gemini_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_gemini_key_btn.clicked.connect(self._add_gemini_key_row)

        # ── Section 4: 앱 정보 ─────────────────────────────
        self._settings_info_sec = QFrame(content)
        self._settings_info_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_info_sec.setStyleSheet(_section_style)

        info_title = QLabel("앱 정보", self._settings_info_sec)
        info_title.setGeometry(24, 14, 200, 22)
        info_title.setStyleSheet(_section_title_style)

        self._version_label = QLabel("", self._settings_info_sec)
        self._version_label.setGeometry(24, 44, 320, 20)
        self._version_label.setStyleSheet("color: #B8B8B8; font-size: 12px; background: transparent; border: none;")

        dev_label = QLabel("개발: 와이엠", self._settings_info_sec)
        dev_label.setGeometry(24, 62, 420, 16)
        dev_label.setStyleSheet(_hint_lbl_style)

        # ── Section 5: 구독 결제 ───────────────────────────
        self._settings_payment_sec = QFrame(content)
        self._settings_payment_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_payment_sec.setStyleSheet(_section_style)

        payment_title = QLabel("구독 결제", self._settings_payment_sec)
        payment_title.setGeometry(24, 14, 220, 22)
        payment_title.setStyleSheet(_section_title_style)

        payment_desc = QLabel("스레드 쇼핑 자동화 정기결제 (월 49,000원)", self._settings_payment_sec)
        payment_desc.setGeometry(24, 42, 420, 20)
        payment_desc.setStyleSheet("color: #B8B8B8; font-size: 12px; font-weight: 500; background: transparent; border: none;")

        self._pay_phone_edit = QLineEdit(self._settings_payment_sec)
        self._pay_phone_edit.setGeometry(24, 70, 250, _control_h)
        self._pay_phone_edit.setPlaceholderText("휴대폰 번호 (예: 01012345678)")
        self._pay_phone_edit.setStyleSheet(_input_style)

        self._pay_monthly_btn = QPushButton("월 49,000원 결제하기", self._settings_payment_sec)
        self._pay_monthly_btn.setGeometry(286, 70, 230, _control_h)
        self._pay_monthly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_monthly_btn.clicked.connect(self._request_payapp_checkout)

        self._pay_hint_label = QLabel(
            "버튼을 누르면 PayApp 결제창으로 바로 이동합니다.",
            self._settings_payment_sec,
        )
        self._pay_hint_label.setGeometry(24, 116, 540, 20)
        self._pay_hint_label.setStyleSheet(_hint_lbl_style)

        # ── Section 6: 튜토리얼 ────────────────────────────
        self._settings_tutorial_sec = QFrame(content)
        self._settings_tutorial_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_tutorial_sec.setStyleSheet(_section_style)

        tutorial_title = QLabel("튜토리얼", self._settings_tutorial_sec)
        tutorial_title.setGeometry(24, 14, 200, 22)
        tutorial_title.setStyleSheet(_section_title_style)

        self._tutorial_settings_btn = QPushButton("튜토리얼 재실행", self._settings_tutorial_sec)
        self._tutorial_settings_btn.setGeometry(24, 40, _action_btn_w, _control_h)
        self._tutorial_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutorial_settings_btn.clicked.connect(self.open_tutorial)

        # ── Section 7: 문의하기 ────────────────────────────
        self._settings_contact_sec = QFrame(content)
        self._settings_contact_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_contact_sec.setStyleSheet(_section_style)

        contact_title = QLabel("문의하기", self._settings_contact_sec)
        contact_title.setGeometry(24, 14, 200, 22)
        contact_title.setStyleSheet(_section_title_style)

        self._contact_btn = QPushButton("카카오톡 문의하기", self._settings_contact_sec)
        self._contact_btn.setGeometry(24, 40, _action_btn_w, _control_h)
        self._contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._contact_btn.clicked.connect(self._open_contact)

        contact_desc = QLabel("문의 버튼을 누르면 카카오톡 상담 채널이 열립니다.", self._settings_contact_sec)
        contact_desc.setGeometry(236, 50, 560, 20)
        contact_desc.setStyleSheet(_hint_lbl_style)

        # ── Action Buttons Row ─────────────────────────────
        self._settings_save_btn = QPushButton("저장", content)
        self._settings_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_save_btn.clicked.connect(self._save_settings)

        self.threads_login_btn.setStyleSheet(_primary_btn_style)
        self._pay_monthly_btn.setStyleSheet(_primary_btn_style)
        self._settings_save_btn.setStyleSheet(_primary_btn_style)
        self.check_login_btn.setStyleSheet(_ghost_btn_style)
        self._add_gemini_key_btn.setStyleSheet(_ghost_btn_style)
        self._tutorial_settings_btn.setStyleSheet(_tutorial_btn_style)
        self._contact_btn.setStyleSheet(_contact_btn_style)

        for btn in (
            self.threads_login_btn,
            self.check_login_btn,
            self._pay_monthly_btn,
            self._tutorial_settings_btn,
            self._contact_btn,
            self._add_gemini_key_btn,
            self._settings_save_btn,
        ):
            btn.setFixedHeight(_control_h)

        self._visible_gemini_key_rows = 1
        self._set_visible_gemini_key_rows(1)

    # ── StatusBar ───────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = QFrame(parent)
        bar.setGeometry(0, WIN_H - STATUSBAR_H, WIN_W, STATUSBAR_H)
        bar.setStyleSheet(
            f"QFrame {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 #12203A, stop:0.5 #162847, stop:1 #12203A);"
            f"  border-top: 1px solid rgba(13, 89, 242, 0.22);"
            f"}}"
        )
        self._status_bar_frame = bar

        # Dot
        self._statusbar_dot = QLabel("", bar)
        self._statusbar_dot.setGeometry(16, 11, 10, 10)
        self._statusbar_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px;"
            f" border: 2px solid rgba(34, 197, 94, 0.3);"
        )

        # Status label
        self.status_label = QLabel("준비", bar)
        self.status_label.setGeometry(34, 6, 600, 20)
        self.status_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Server label (right side)
        self._server_label = QLabel("서버 연결: --", bar)
        self._server_label.setGeometry(WIN_W - 400, 6, 200, 20)
        self._server_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._server_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Progress label (far right)
        self.progress_label = QLabel("", bar)
        self.progress_label.setGeometry(WIN_W - 190, 6, 180, 20)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

    # ────────────────────────────────────────────────────────
    #  PAGE SWITCHING
    # ────────────────────────────────────────────────────────

    def _switch_page(self, index, source="programmatic"):
        """Show selected page, hide others. Also sync sidebar button."""
        try:
            index = int(index)
        except Exception:
            return
        for i, page in enumerate(self._pages):
            page.setVisible(i == index)
        self._current_page = index
        if hasattr(self, '_sidebar_buttons') and 0 <= index < len(self._sidebar_buttons):
            self._sidebar_buttons[index].setChecked(True)
        self._log_user_activity(
            "ui_tab_switch",
            f"index={index}; page={self._page_label(index)}; source={source}",
            min_interval_sec=0.12,
            dedupe_key=f"tab:{index}:{source}",
        )

    # ────────────────────────────────────────────────────────
    #  PROGRESS PANEL UPDATES
    # ────────────────────────────────────────────────────────

    def _update_step(self, index, status):
        """Update a step indicator in the sidebar progress panel."""
        if index < 0 or index >= len(self._step_dots):
            return

        style_map = {
            "pending": (f"color: {Colors.TEXT_MUTED};", "○",
                        f"color: {Colors.TEXT_MUTED};"),
            "active": (f"color: {Colors.WARNING};", "●",
                       f"color: {Colors.WARNING}; font-weight: 700;"),
            "done": (f"color: {Colors.SUCCESS};", "✓",
                     f"color: {Colors.SUCCESS};"),
            "error": (f"color: {Colors.ERROR};", "✗",
                      f"color: {Colors.ERROR};"),
        }

        dot_style, dot_char, label_style = style_map.get(
            status, style_map["pending"]
        )
        self._step_dots[index].setText(dot_char)
        self._step_dots[index].setStyleSheet(
            f"{dot_style} font-size: 10pt; background: transparent;"
        )
        self._step_labels[index].setStyleSheet(
            f"{label_style} font-size: 9pt; background: transparent;"
        )
        self._log_user_activity(
            "ui_process_step",
            f"index={index}; step={self._PROCESS_STEPS[index]}; status={status}",
            min_interval_sec=0.05,
            dedupe_key=f"step:{index}:{status}",
        )

    def _reset_steps(self):
        """Reset all step indicators to pending state."""
        for i in range(len(self._step_dots)):
            self._update_step(i, "pending")

    # ────────────────────────────────────────────────────────
    #  LINK TABLE MANAGEMENT
    # ────────────────────────────────────────────────────────

    def _populate_link_table(self, link_data):
        """Populate the link table with initial data (all '대기' status)."""
        self.link_table.setRowCount(0)
        self._link_url_row_map.clear()

        for idx, item in enumerate(link_data):
            url = item[0] if isinstance(item, tuple) else item
            row = self.link_table.rowCount()
            self.link_table.insertRow(row)

            # # column
            num_item = QTableWidgetItem(str(idx + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.link_table.setItem(row, 0, num_item)

            # URL column (shortened)
            short_url = url
            if len(url) > 50:
                short_url = url[:47] + "..."
            url_item = QTableWidgetItem(short_url)
            url_item.setToolTip(url)
            self.link_table.setItem(row, 1, url_item)

            # Status column
            status_item = QTableWidgetItem("대기")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(Colors.TEXT_MUTED))
            self.link_table.setItem(row, 2, status_item)

            # Product name column
            name_item = QTableWidgetItem("-")
            name_item.setForeground(QColor(Colors.TEXT_MUTED))
            self.link_table.setItem(row, 3, name_item)

            self._link_url_row_map[url] = row

    def _on_link_table_cell_clicked(self, row, column):
        if row < 0:
            return

        url_item = self.link_table.item(row, 1)
        status_item = self.link_table.item(row, 2)
        product_item = self.link_table.item(row, 3)
        url_text = ""
        if url_item:
            url_text = str(url_item.toolTip() or url_item.text() or "").strip()
        status_text = str(status_item.text() or "").strip() if status_item else ""
        product_text = str(product_item.text() or "").strip() if product_item else ""

        self._log_user_activity(
            "ui_link_table_click",
            (
                f"row={row}; column={column}; "
                f"url={url_text}; status={status_text}; product={product_text}"
            ),
            min_interval_sec=0.08,
            dedupe_key=f"table-click:{row}:{column}:{url_text}:{status_text}",
        )

    def _update_link_table_status(self, url, status, product_name):
        """Update status and product name for a specific URL in the table."""
        row = self._link_url_row_map.get(url)
        if row is None:
            return

        status_text = str(status)
        status_lower = status_text.lower()
        level = "INFO"
        if "fail" in status_lower or "error" in status_lower or "실패" in status_text:
            level = "WARNING"
        self._log_user_activity(
            "batch_link_status",
            f"url={url}; status={status}; product={product_name}",
            level=level,
        )

        status_item = self.link_table.item(row, 2)
        if status_item:
            status_item.setText(status)
            color_map = {
                "대기": Colors.TEXT_MUTED,
                "진행중": Colors.WARNING,
                "완료": Colors.SUCCESS,
                "실패": Colors.ERROR,
            }
            status_item.setForeground(QColor(color_map.get(status, Colors.TEXT_MUTED)))

        if product_name:
            name_item = self.link_table.item(row, 3)
            if name_item:
                name_item.setText(product_name[:40])
                if status == "완료":
                    name_item.setForeground(QColor(Colors.TEXT_PRIMARY))
                elif status == "실패":
                    name_item.setForeground(QColor(Colors.ERROR))

    # ────────────────────────────────────────────────────────
    #  BUSINESS LOGIC
    # ────────────────────────────────────────────────────────

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        clean_msg = str(message).strip()
        if not clean_msg:
            return

        logger.info("UI 로그 %s", clean_msg)

        safe_msg = html.escape(clean_msg)
        lower_msg = clean_msg.lower()
        color = Colors.TEXT_SECONDARY
        tag = "정보"
        tag_color = Colors.INFO
        if any(kw in lower_msg for kw in ("error", "fail", "exception", "cancel", "오류", "실패", "취소", "중단")):
            color = Colors.ERROR
            tag = "오류"
            tag_color = Colors.ERROR
        elif any(kw in lower_msg for kw in ("success", "done", "complete", "성공", "완료")):
            color = Colors.SUCCESS
            tag = "성공"
            tag_color = Colors.SUCCESS
        elif any(kw in lower_msg for kw in ("warn", "wait", "running", "start", "경고", "대기", "시작", "진행")):
            color = Colors.WARNING
            tag = "경고"
            tag_color = Colors.WARNING

        self.log_text.append(
            f'<span style="color:{Colors.TEXT_MUTED}">[{timestamp}]</span> '
            f'<span style="color:{tag_color};font-weight:700">{tag}</span> '
            f'<span style="color:{color}">{safe_msg}</span>'
        )

    def _set_status(self, message):
        logger.info("상태 갱신: %s", message)
        self.status_label.setText(message)
        self._log_user_activity(
            "ui_status_change",
            f"status={message}",
            min_interval_sec=0.15,
            dedupe_key=f"status:{message}",
        )

        lower_message = str(message).lower()
        if any(kw in lower_message for kw in ("error", "fail", "cancel", "오류", "취소", "실패", "중단")):
            self.status_badge.update_style(Colors.ERROR, str(message)[:14])
        elif any(kw in lower_message for kw in ("done", "ready", "complete", "success", "완료", "대기", "연결")):
            self.status_badge.update_style(Colors.SUCCESS, str(message)[:14])
        else:
            self.status_badge.update_style(Colors.WARNING, str(message)[:14])
        self._relayout_header_account_card()

    def _set_progress(self, message):
        message_text = str(message or "")
        self.progress_label.setText(message_text)
        self.progress_label.setVisible(bool(message_text.strip()))
        if message_text.strip():
            self._log_user_activity(
                "ui_progress_text",
                message_text,
                min_interval_sec=0.1,
                dedupe_key=f"progress:{message_text}",
            )

    def _set_results(self, success, failed):
        total = success + failed
        # Update sidebar progress labels
        self._sidebar_success_label.setText(f"성공: {success}")
        self._sidebar_failed_label.setText(f"실패: {failed}")
        self._sidebar_total_label.setText(f"전체: {total}")
        # Update queue progress
        self._set_queue_progress(f"전체: {total} 처리됨")

    def _set_queue_progress(self, message: str):
        text = str(message or "")
        self._progress_queue_label.setText(text)
        if text:
            self._log_user_activity(
                "ui_queue_progress",
                text,
                min_interval_sec=0.15,
                dedupe_key=f"queue-progress:{text}",
            )

    def _add_product(self, title, success):
        # No separate product list; table is updated via link_status signal
        pass

    def _on_finished(self, results):
        self._log_user_activity(
            "batch_finished",
            (
                f"uploaded={results.get('uploaded', 0)}; failed={results.get('failed', 0)}; "
                f"parse_failed={results.get('parse_failed', 0)}; cancelled={bool(results.get('cancelled'))}"
            ),
        )
        logger.info("업로드 완료: %s", results)
        self._active_pipeline = None
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "준비")
        self._relayout_header_account_card()
        self._sidebar_status_label.setText("완료")
        self._reset_steps()

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get("parse_failed", 0)
        uploaded = results.get("uploaded", 0)
        failed = results.get("failed", 0)

        # Stay on link page to see table results
        self._switch_page(0)
        self._sidebar_buttons[0].setChecked(True)

        if results.get("cancelled"):
            msg = (
                "업로드가 취소되었습니다.\n\n"
                f"  완료: {uploaded}\n"
                f"  실패: {failed}"
            )
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            show_info(self, "취소됨", msg)
        else:
            msg = (
                "업로드가 완료되었습니다.\n\n"
                f"  성공: {uploaded}\n"
                f"  실패: {failed}"
            )
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            show_info(self, "완료", msg)

    def _update_link_count(self):
        content = self.links_text.toPlainText()
        links = self.COUPANG_LINK_PATTERN.findall(content)
        unique_links = list(dict.fromkeys(links))
        count = len(unique_links)
        if count > 0:
            self.link_count_badge.update_style(Colors.ACCENT, f"{count}개 링크")
        else:
            self.link_count_badge.update_style(Colors.TEXT_MUTED, "0개 링크")

    def _extract_links(self, content: str) -> list:
        links = self.COUPANG_LINK_PATTERN.findall(content)
        unique_links = list(dict.fromkeys(links))
        return [(url, None) for url in unique_links]

    # ────────────────────────────────────────────────────────
    #  SETTINGS LOGIC
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리."""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def _get_profile_dir(self):
        username = self.username_edit.text().strip()
        if not username:
            username = str(getattr(config, "instagram_username", "") or "").strip()
        if username:
            profile_name = self._sanitize_profile_name(username)
            return f".threads_profile_{profile_name}"
        return ".threads_profile"

    def _resolve_runtime_gemini_api_key(self, validate: bool = False):
        key = str(select_working_gemini_api_key(validate=validate) or "").strip()
        if key:
            return key
        keys = []
        if hasattr(config, "get_gemini_api_keys"):
            try:
                keys = normalize_gemini_api_keys(config.get_gemini_api_keys())
            except Exception:
                logger.exception("Gemini API 키 목록 조회 중 오류가 발생했습니다.")
        if keys:
            return keys[0]
        return str(getattr(config, "gemini_api_key", "") or "").strip()

    def _toggle_gemini_key_visibility(self, row_index):
        if row_index < 0 or row_index >= len(getattr(self, "_gemini_key_rows", [])):
            return
        row = self._gemini_key_rows[row_index]
        edit = row.get("edit")
        toggle = row.get("toggle")
        if edit is None or toggle is None:
            return
        if edit.echoMode() == QLineEdit.EchoMode.Password:
            edit.setEchoMode(QLineEdit.EchoMode.Normal)
            toggle.setText("숨기기")
        else:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            toggle.setText("보기")

    def _add_gemini_key_row(self):
        rows = getattr(self, "_gemini_key_rows", [])
        if not rows:
            return
        if self._visible_gemini_key_rows >= len(rows):
            show_info(self, "안내", f"Gemini API 키는 최대 {len(rows)}개까지 등록할 수 있습니다.")
            return
        self._set_visible_gemini_key_rows(self._visible_gemini_key_rows + 1)
        new_row = self._gemini_key_rows[self._visible_gemini_key_rows - 1]
        new_row["edit"].setFocus()

    def _set_visible_gemini_key_rows(self, count):
        rows = getattr(self, "_gemini_key_rows", [])
        if not rows:
            return

        count = max(1, min(int(count or 1), len(rows)))
        self._visible_gemini_key_rows = count
        for index, row in enumerate(rows):
            visible = index < count
            row["visible"] = visible
            row["badge"].setVisible(visible)
            row["edit"].setVisible(visible)
            row["toggle"].setVisible(visible)

        if count >= len(rows):
            self._add_gemini_key_btn.setText(f"최대 {len(rows)}개")
            self._add_gemini_key_btn.setEnabled(False)
        else:
            self._add_gemini_key_btn.setText("키 추가")
            self._add_gemini_key_btn.setEnabled(True)
        self._relayout_settings_sections()

    def _relayout_settings_sections(self):
        if not hasattr(self, "_settings_content"):
            return

        x = getattr(self, "_settings_section_x", 24)
        w = getattr(self, "_settings_section_w", 952)
        gap = getattr(self, "_settings_gap", 24)
        sy = getattr(self, "_settings_flow_start_y", 12)

        row_count = max(1, int(getattr(self, "_visible_gemini_key_rows", 1)))
        row_start_y = 72
        row_step = 50
        row_height = 40
        badge_x = 24
        badge_w = 30
        key_x = 62
        toggle_w = 108
        key_w = w - key_x - 24 - toggle_w - 8
        toggle_x = key_x + key_w + 8

        for index, row in enumerate(getattr(self, "_gemini_key_rows", [])):
            row_y = row_start_y + (index * row_step)
            row["badge"].setGeometry(badge_x, row_y + 7, badge_w, 24)
            row["edit"].setGeometry(key_x, row_y, key_w, row_height)
            row["toggle"].setGeometry(toggle_x, row_y, toggle_w, row_height)

        add_btn_y = row_start_y + (row_count * row_step) + 4
        self._add_gemini_key_btn.setGeometry(24, add_btn_y, 134, 40)
        api_h = add_btn_y + 40 + 18
        self._settings_api_sec.setGeometry(x, sy, w, api_h)
        sy += api_h + gap

        self._settings_info_sec.setGeometry(x, sy, w, 96)
        sy += 96 + gap

        self._settings_payment_sec.setGeometry(x, sy, w, 164)
        sy += 164 + gap

        self._settings_tutorial_sec.setGeometry(x, sy, w, 104)
        sy += 104 + gap

        self._settings_contact_sec.setGeometry(x, sy, w, 108)
        sy += 108 + gap

        self._settings_save_btn.setGeometry(x + w - 160, sy, 160, 40)
        sy += 66

        self._settings_content.setFixedHeight(sy + 24)

    def _load_settings(self):
        """Load config values into widgets."""
        keys = []
        if hasattr(config, "get_gemini_api_keys"):
            try:
                keys = normalize_gemini_api_keys(config.get_gemini_api_keys())
            except Exception:
                logger.exception("Gemini API 키 로드 중 오류가 발생했습니다.")
                keys = []
        if not keys:
            single_key = str(getattr(config, "gemini_api_key", "") or "").strip()
            if single_key:
                keys = [single_key]
        if not keys:
            keys = [""]

        self._set_visible_gemini_key_rows(len(keys))
        for idx, row in enumerate(getattr(self, "_gemini_key_rows", [])):
            edit = row["edit"]
            edit.setText(keys[idx] if idx < len(keys) else "")
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            row["toggle"].setText("보기")

        total = config.upload_interval
        self.hour_spin.setValue(total // 3600)
        self.min_spin.setValue((total % 3600) // 60)
        self.sec_spin.setValue(total % 60)

        self.video_check.setChecked(config.prefer_video)
        self.username_edit.setText(config.instagram_username)

        # Keep top-right user status chips visually aligned with the reference app.
        def _apply_top_right_status_styles():
            if hasattr(self, "logout_btn"):
                self.logout_btn.setFixedSize(86, 30)
            if hasattr(self, "tutorial_btn"):
                self.tutorial_btn.setFixedSize(86, 30)
            if hasattr(self, "_work_label"):
                self._work_label.setStyleSheet(
                    "QPushButton {"
                    " background-color: #E31639;"
                    " color: #FFFFFF;"
                    " border: none;"
                    " border-radius: 8px;"
                    " padding: 8px 16px;"
                    " font-size: 11px;"
                    " font-weight: 700;"
                    "}"
                    "QPushButton:hover {"
                    " background-color: #C41231;"
                    "}"
                    "QPushButton:pressed {"
                    " background-color: #A01028;"
                    "}"
                )
                self._work_label.setFixedHeight(30)
                self._work_label.setMinimumWidth(110)
                self._work_label.setMaximumWidth(110)
            if hasattr(self, "_header_username_label"):
                self._header_username_label.setStyleSheet(
                    "color: #B8B8B8; font-size: 11px; font-weight: 500; background: transparent;"
                )
            if hasattr(self, "_online_dot"):
                self._online_dot.setStyleSheet("background-color: #9CA3AF; border-radius: 4px;")
                self._online_dot.setFixedSize(8, 8)
            if hasattr(self, "_connection_label"):
                self._connection_label.setStyleSheet(
                    "color: #9CA3AF; font-size: 10px; font-weight: 500; background: transparent;"
                )
            if hasattr(self, "_plan_badge"):
                self._plan_badge.setStyleSheet(
                    "QPushButton {"
                    " background-color: rgba(255, 255, 255, 0.05);"
                    " color: #B8B8B8;"
                    " border: 1px solid rgba(255, 255, 255, 0.05);"
                    " border-radius: 6px;"
                    " padding: 6px 12px;"
                    " font-size: 10px;"
                    " font-weight: 700;"
                    "}"
                    "QPushButton:hover {"
                    " background-color: rgba(255, 255, 255, 0.10);"
                    " border-color: #E31639;"
                    " color: #FFFFFF;"
                    "}"
                )
                self._plan_badge.setFixedHeight(30)
                self._plan_badge.setMinimumWidth(92)
                self._plan_badge.setMaximumWidth(92)
            if hasattr(self, "_relayout_header_account_card"):
                self._relayout_header_account_card()
            if all(
                hasattr(self, name)
                for name in (
                    "_work_label",
                    "_header_username_label",
                    "_online_dot",
                    "_connection_label",
                    "_plan_badge",
                    "_header_nav_buttons",
                )
            ):
                nav_buttons = [btn for btn in self._header_nav_buttons if btn is not None]
                if nav_buttons:
                    nav_left = min(btn.x() for btn in nav_buttons)
                    right = nav_left - 12
                    top = 19
                    control_h = 30
                    min_left = 250

                    plan_w = 92
                    work_w = 110
                    self._plan_badge.setGeometry(max(min_left, right - plan_w), top, plan_w, control_h)
                    right = self._plan_badge.x() - 8

                    conn_text = self._connection_label.text() or ""
                    conn_w = min(max(self._connection_label.fontMetrics().horizontalAdvance(conn_text) + 8, 84), 112)
                    self._connection_label.setGeometry(max(min_left, right - conn_w), top + 6, conn_w, 18)
                    right = self._connection_label.x() - 8

                    self._online_dot.setGeometry(max(min_left, right - 8), top + 11, 8, 8)
                    right = self._online_dot.x() - 8

                    user_text = self._header_username_label.text() or ""
                    user_w = min(max(self._header_username_label.fontMetrics().horizontalAdvance(user_text) + 6, 52), 110)
                    self._header_username_label.setGeometry(max(min_left, right - user_w), top + 4, user_w, 20)
                    right = self._header_username_label.x() - 8

                    self._work_label.setGeometry(max(min_left, right - work_w), top, work_w, control_h)
        self._apply_top_right_status_styles = _apply_top_right_status_styles
        _apply_top_right_status_styles()
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, _apply_top_right_status_styles)
            QTimer.singleShot(1400, _apply_top_right_status_styles)
        except Exception:
            pass

    def _save_settings(self):
        """Save widget values to config."""
        self._log_user_activity("settings_save_requested", "source=settings_page")
        interval = (
            self.hour_spin.value() * 3600 +
            self.min_spin.value() * 60 +
            self.sec_spin.value()
        )
        if interval < 30:
            self._log_user_activity("settings_save_adjusted", "upload_interval_clamped_to_30", level="WARNING")
            interval = 30
            show_info(self, "알림", "최소 업로드 간격은 30초입니다.")

        key_values = []
        for index, row in enumerate(getattr(self, "_gemini_key_rows", [])):
            if index >= getattr(self, "_visible_gemini_key_rows", 1):
                continue
            key_values.append(row["edit"].text().strip())
        key_values = normalize_gemini_api_keys(key_values)
        if not key_values:
            self._log_user_activity("settings_save_blocked", "reason=missing_gemini_keys", level="WARNING")
            show_warning(self, "설정 필요", "최소 1개의 Gemini API 키를 입력해주세요.")
            return
        save_configured_gemini_api_keys(key_values)

        config.upload_interval = interval
        config.prefer_video = self.video_check.isChecked()
        config.instagram_username = self.username_edit.text().strip()
        config.save()

        active_key = self._resolve_runtime_gemini_api_key(validate=False)

        if self.is_running:
            logger.info("실행 중 설정 저장됨; 파이프라인 재초기화는 보류합니다")
        else:
            self.pipeline = CoupangPartnersPipeline(active_key)

        if hasattr(self, "_relayout_header_account_card"):
            self._relayout_header_account_card()
        top_right_style_fn = getattr(self, "_apply_top_right_status_styles", None)
        if callable(top_right_style_fn):
            top_right_style_fn()

        show_info(self, "저장 완료", "설정이 저장되었습니다.")
        self._log_user_activity(
            "settings_saved",
            (
                f"upload_interval={interval}; prefer_video={bool(config.prefer_video)}; "
                f"username_set={bool(config.instagram_username)}; gemini_keys={len(key_values)}"
            ),
        )
        logger.info("설정 저장 완료")

    def _update_account_display(self):
        """Update header and settings page with auth data."""
        auth = getattr(self, '_auth_data', None) or {}
        username = auth.get("username") or getattr(self, '_auth_data', {}).get("id", "")
        plan_type = None
        is_paid = None
        subscription_status = None
        expires_at = None
        remaining_count = None

        # Resolve from auth_client state if not in auth_data
        try:
            from src import auth_client
            state = auth_client.get_auth_state()
            if not username:
                username = state.get("username", "")
            work_count = state.get("work_count", 0)
            work_used = state.get("work_used", 0)
            plan_type = state.get("plan_type")
            is_paid = state.get("is_paid")
            subscription_status = state.get("subscription_status")
            expires_at = state.get("expires_at")
            remaining_count = state.get("remaining_count")
        except Exception:
            work_count = auth.get("work_count", 0)
            work_used = auth.get("work_used", 0)
            plan_type = auth.get("plan_type")
            is_paid = auth.get("is_paid")
            subscription_status = auth.get("subscription_status")
            expires_at = auth.get("expires_at")
            remaining_count = auth.get("remaining_count")

        display_name = username or "사용자"
        plan_text = str(plan_type or "").strip().lower()
        status_text = str(subscription_status or "").strip().lower()
        if isinstance(is_paid, str):
            normalized = is_paid.strip().lower()
            if normalized in {"1", "true", "yes", "y", "paid", "pro", "premium", "active"}:
                paid_account = True
            elif normalized in {"0", "false", "no", "n", "free", "trial", "inactive", "expired"}:
                paid_account = False
            else:
                paid_account = None
        elif isinstance(is_paid, (int, float)):
            paid_account = bool(is_paid)
        elif isinstance(is_paid, bool):
            paid_account = is_paid
        else:
            paid_account = None

        if paid_account is None and plan_text:
            paid_account = plan_text not in {"free", "trial", "basic", "starter"}
        if status_text in {"expired", "inactive", "cancelled"}:
            paid_account = False
        if paid_account is None:
            paid_account = False

        # Header plan badge
        if paid_account:
            self._plan_badge.setText("유료계정")
            self._plan_badge.setStyleSheet(
                "QPushButton {"
                " background-color: rgba(227, 22, 57, 0.14);"
                " color: #FF8FA2;"
                " border: 1px solid rgba(227, 22, 57, 0.45);"
                " border-radius: 6px;"
                " padding: 6px 12px;"
                " font-size: 8pt;"
                " font-weight: 700;"
                "}"
                "QPushButton:hover {"
                " background-color: rgba(227, 22, 57, 0.24);"
                " color: #FFFFFF;"
                "}"
            )
        else:
            self._plan_badge.setText("무료계정")
            self._plan_badge.setStyleSheet(
                f"QPushButton {{"
                f" background-color: rgba(255, 255, 255, 0.05);"
                f" color: {Colors.TEXT_SECONDARY};"
                f" border: 1px solid {Colors.BORDER};"
                f" border-radius: 6px;"
                f" padding: 6px 12px;"
                f" font-size: 8pt;"
                f" font-weight: 700;"
                f"}}"
                f"QPushButton:hover {{"
                f" background-color: rgba(255, 255, 255, 0.10);"
                f" border-color: #E31639;"
                f" color: #FFFFFF;"
                f"}}"
            )

        def _to_int(value):
            try:
                return int(value)
            except Exception:
                return 0

        work_count = _to_int(work_count)
        work_used = _to_int(work_used)
        remaining_count_value = (
            _to_int(remaining_count)
            if isinstance(remaining_count, (int, float, str))
            else None
        )
        if remaining_count_value is not None and work_count <= 0:
            work_count = max(work_count, work_used + max(remaining_count_value, 0))
        if not paid_account and work_count <= 0:
            try:
                from src import auth_client
                work_count = max(work_count, int(auth_client.get_free_trial_work_count()))
            except Exception:
                work_count = max(work_count, 5)
        if work_used > work_count:
            work_count = work_used

        self._work_label.setText(f"{work_used} / {work_count} 회")
        self._header_username_label.setText(display_name)

        # Settings page account card
        self._acct_username_label.setText(display_name)
        self._acct_work_label.setText(f"{work_used} / {work_count} 회 사용")

        if paid_account:
            self._acct_plan_badge.setText("프로 구독")
            self._acct_plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(13, 89, 242, 0.15);"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid rgba(13, 89, 242, 0.3);"
                f" border-radius: 13px; font-size: 9pt; font-weight: 700; }}"
            )
        else:
            if status_text == "expired":
                self._acct_plan_badge.setText("구독 만료")
            else:
                self._acct_plan_badge.setText("무료 체험")

        if expires_at:
            self._acct_plan_badge.setToolTip(f"만료: {expires_at}")
        else:
            self._acct_plan_badge.setToolTip("")

        self._relayout_header_account_card()

        # Version label
        self._version_label.setText(f"현재 버전: {self._app_version}")

    def _open_contact(self):
        """Open contact/support dialog."""
        kakao_url = str(
            os.getenv("THREAD_AUTO_KAKAO_CONTACT_URL", "https://open.kakao.com/o/sVkZPsfi")
            or ""
        ).strip()
        if not kakao_url:
            self._log_user_activity("ui_contact_open_failed", "reason=empty_url", level="WARNING")
            show_warning(self, "문의하기", "카카오톡 문의 URL이 설정되지 않았습니다.")
            return
        if not self._open_external_link(kakao_url, "settings_kakao_contact"):
            show_error(self, "문의하기", f"카카오톡 문의 페이지를 열지 못했습니다.\n{kakao_url}")

    def _request_payapp_checkout(self):
        phone = re.sub(r"[^0-9]", "", self._pay_phone_edit.text().strip())
        phone_masked = phone
        if len(phone) >= 7:
            phone_masked = f"{phone[:3]}****{phone[-4:]}"
        self._log_user_activity(
            "payment_checkout_requested",
            f"phone={phone_masked}",
        )
        if not phone:
            self._log_user_activity(
                "payment_checkout_validation_failed",
                "reason=empty_phone",
                level="WARNING",
            )
            show_warning(self, "결제 요청", "휴대폰 번호를 입력해주세요. (예: 01012345678)")
            return

        try:
            from src import auth_client
            result = auth_client.create_payapp_checkout(phone)
        except Exception:
            self._log_user_activity("payment_checkout_request_failed", "reason=api_exception", level="ERROR")
            logger.exception("PayApp 결제 요청 중 예외가 발생했습니다.")
            show_error(self, "결제 요청 실패", "결제 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            return

        if not isinstance(result, dict):
            self._log_user_activity("payment_checkout_request_failed", "reason=invalid_response", level="ERROR")
            show_error(self, "결제 요청 실패", "결제 서버 응답 형식이 올바르지 않습니다.")
            return

        success = bool(result.get("success"))
        if not success:
            self._log_user_activity(
                "payment_checkout_request_failed",
                f"reason=api_rejected; message={str(result.get('message') or '').strip()}",
                level="WARNING",
            )
            message = str(result.get("message") or "결제 요청에 실패했습니다.").strip()
            show_error(self, "결제 요청 실패", message)
            logger.warning("결제 요청 실패: %s", message)
            return

        server_plan_id = str(result.get("plan_id") or "").strip()
        expected_plan_id = "stmaker_business_month"
        if server_plan_id and server_plan_id != expected_plan_id:
            self._log_user_activity(
                "payment_checkout_request_failed",
                f"reason=plan_id_mismatch; expected={expected_plan_id}; actual={server_plan_id}",
                level="ERROR",
            )
            logger.warning(
                "결제 플랜 불일치 감지: expected=%s actual=%s",
                expected_plan_id,
                server_plan_id,
            )
            show_error(
                self,
                "결제 요청 실패",
                "결제 서버 플랜 매핑이 올바르지 않습니다. 관리자에게 문의해주세요.",
            )
            return

        pay_url = ""
        for key in ("payurl", "payapp_url", "payment_url", "url"):
            value = str(result.get(key) or "").strip()
            if value:
                pay_url = value
                break

        if not pay_url:
            self._log_user_activity(
                "payment_checkout_request_failed",
                "reason=missing_payment_url",
                level="ERROR",
            )
            show_error(self, "결제 요청 실패", "결제 URL을 받지 못했습니다. 관리자에게 문의해주세요.")
            logger.warning("결제 성공 응답에 URL 누락: %s", result)
            return

        self._log_user_activity("payment_checkout_url_ready", f"url={pay_url}")
        opened = self._open_external_link(pay_url, "settings_payapp_checkout")
        if not opened:
            self._log_user_activity("payment_checkout_open_failed", f"url={pay_url}", level="WARNING")
            show_error(self, "결제 요청 실패", f"결제 페이지를 열지 못했습니다.\n{pay_url}")
            return

        self._log_user_activity("payment_checkout_opened", f"url={pay_url}")
        self.signals.log.emit(f"PayApp 결제 페이지가 열렸습니다: {pay_url}")

    def open_settings(self):
        """Switch to settings page (page 2) instead of opening dialog."""
        logger.info("설정 화면 열기 호출")
        self._switch_page(2, source="open_settings")

    # ────────────────────────────────────────────────────────
    #  THREADS LOGIN LOGIC
    # ────────────────────────────────────────────────────────

    def _open_threads_login(self):
        username = self.username_edit.text().strip()
        if username:
            config.instagram_username = username
            config.save()

        self.threads_login_btn.setEnabled(False)
        self.threads_login_btn.setText("여는 중...")
        self._update_login_status("pending", "브라우저 여는 중...")

        self._browser_cancel.clear()
        cancel_event = self._browser_cancel
        profile_dir = self._get_profile_dir()
        runtime_api_key = self._resolve_runtime_gemini_api_key(validate=False)
        self._log_user_activity(
            "threads_login_launch_requested",
            f"profile={profile_dir}; username_set={bool(username)}",
        )
        if not runtime_api_key or len(runtime_api_key.strip()) < 10:
            self._log_user_activity(
                "threads_login_launch_failed",
                "reason=missing_runtime_api_key",
                level="WARNING",
            )
            self._restore_login_btn()
            self._update_login_status("error", "Gemini API 키를 먼저 저장해주세요.")
            show_warning(self, "설정 필요", "설정에서 유효한 Gemini API 키를 저장한 뒤 다시 시도해주세요.")
            return
        logger.info(
            "Threads 로그인 브라우저 실행 요청: profile=%s username_provided=%s",
            profile_dir,
            bool(username),
        )

        def open_browser():
            launch_notified = False
            try:
                from src.computer_use_agent import ComputerUseAgent

                agent = ComputerUseAgent(
                    api_key=runtime_api_key,
                    headless=False,
                    profile_dir=profile_dir
                )
                agent.start_browser()
                opened_url = goto_threads_with_fallback(
                    agent.page,
                    path="/login",
                    timeout=30000,
                    retries_per_url=1,
                    logger=logger,
                )
                self.signals.threads_login_launch.emit(True, opened_url)
                self._log_user_activity("threads_login_browser_opened", f"url={opened_url}")
                launch_notified = True

                import time

                # Event-first close detection:
                # user closes tab/window, context closes, or browser disconnects.
                closed_event = threading.Event()

                def _mark_browser_closed(*_args, **_kwargs):
                    closed_event.set()

                try:
                    if agent.page is not None:
                        agent.page.on("close", _mark_browser_closed)
                except Exception:
                    pass
                try:
                    if agent.context is not None:
                        agent.context.on("close", _mark_browser_closed)
                except Exception:
                    pass
                try:
                    if agent.browser is not None:
                        agent.browser.on("disconnected", _mark_browser_closed)
                except Exception:
                    pass

                watch_deadline = time.monotonic() + (60 * 60 * 2)  # max 2 hours
                while not cancel_event.is_set() and not closed_event.is_set():
                    if time.monotonic() >= watch_deadline:
                        logger.info("Threads 로그인 브라우저 감시 타임아웃으로 세션 저장 후 종료합니다.")
                        break

                    try:
                        if agent.page is None or agent.page.is_closed():
                            closed_event.set()
                            break
                    except Exception:
                        closed_event.set()
                        break

                    try:
                        if agent.context is None or len(agent.context.pages) == 0:
                            closed_event.set()
                            break
                    except Exception:
                        closed_event.set()
                        break

                    try:
                        if agent.browser is None or not agent.browser.is_connected():
                            closed_event.set()
                            break
                    except Exception:
                        closed_event.set()
                        break

                    time.sleep(0.35)

                if cancel_event.is_set():
                    self._log_user_activity("threads_login_browser_watch_cancelled", "reason=cancel_event")
                    logger.info("Threads 로그인 브라우저 감시 중지: 취소 이벤트 감지")
                elif closed_event.is_set():
                    self._log_user_activity("threads_login_browser_closed_detected", "reason=browser_closed")
                    logger.info("Threads 로그인 브라우저 닫힘 감지")

                try:
                    agent.save_session()
                except Exception:
                    logger.exception("Threads 세션 저장에 실패했습니다")
                finally:
                    try:
                        agent.close()
                    except Exception:
                        logger.exception("Threads 브라우저 종료에 실패했습니다")

                if launch_notified:
                    self.signals.threads_browser_closed.emit()

            except Exception as e:
                self._log_user_activity(
                    "threads_login_launch_failed",
                    f"reason=browser_worker_exception; detail={str(e)[:240]}",
                    level="ERROR",
                )
                logger.exception("Threads 로그인 브라우저 흐름에서 오류 발생")
                if not launch_notified:
                    self.signals.threads_login_launch.emit(False, str(e))

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

    def _restore_login_btn(self):
        if self._closed:
            return
        self.threads_login_btn.setEnabled(True)
        self.threads_login_btn.setText("Threads 로그인")

    def _on_threads_login_launch_result(self, success: bool, detail: str):
        if self._closed:
            return

        self._restore_login_btn()

        if success:
            self._update_login_status("pending", "브라우저가 열렸습니다. 로그인 완료 후 창을 닫아주세요.")
            opened_url = str(detail or "").strip()
            self._log_user_activity("threads_login_browser_opened", f"url={opened_url or '(unknown)'}")
            if opened_url:
                self.signals.log.emit(f"Threads 로그인 브라우저가 열렸습니다. 로그인 후 창을 닫아주세요: {opened_url}")
            else:
                self.signals.log.emit("Threads 로그인 브라우저가 열렸습니다. 로그인 후 창을 닫아주세요.")
            return

        reason = str(detail or "").strip() or "원인을 확인할 수 없습니다."
        logger.warning("Threads 로그인 브라우저 실행 실패 원본: %s", reason)
        self._update_login_status("error", "브라우저 실행 실패")
        self._log_user_activity(
            "threads_login_launch_failed",
            f"reason={reason}",
            level="WARNING",
        )
        if is_browser_launch_error(reason):
            user_message = (
                "브라우저 실행에 실패했습니다.\n"
                "Google Chrome 또는 Microsoft Edge 설치 상태를 확인한 뒤 다시 시도해주세요."
            )
        else:
            user_message = friendly_threads_navigation_error(reason)
        self.signals.log.emit(f"Threads 로그인 브라우저 실행 실패: {user_message}")
        show_warning(
            self,
            "로그인 브라우저 오류",
            "Threads 로그인 브라우저를 열지 못했습니다.\n"
            f"{user_message}",
        )

    def _on_threads_browser_closed(self):
        if self._closed:
            return
        self._log_user_activity("threads_login_browser_closed", "session_saved=True")
        self._update_login_status(
            "success",
            "브라우저를 닫았습니다. 세션 저장이 완료되었습니다.",
        )
        self.signals.log.emit("Threads 브라우저가 닫혀 세션이 저장되었습니다.")

    def _check_login_status(self):
        self._log_user_activity("threads_login_check_help_opened", "source=settings_button")
        self._update_login_status("pending", "브라우저에서 로그인 후 창을 닫아주세요.")
        show_info(
            self,
            "로그인 안내",
            "1) Threads 로그인 버튼을 누릅니다.\n"
            "2) 열린 브라우저에서 로그인합니다.\n"
            "3) 브라우저 창을 닫으면 세션이 자동 저장됩니다.",
        )

    def _update_login_status(self, state, text):
        color_map = {
            "success": Colors.SUCCESS,
            "error": Colors.ERROR,
            "pending": Colors.WARNING,
            "unknown": Colors.TEXT_MUTED,
        }
        color = color_map.get(state, Colors.TEXT_MUTED)
        self._threads_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self.login_status_label.setText(text)
        self.login_status_label.setStyleSheet(
            f"color: {color}; font-size: 9pt; font-weight: 600; background: transparent;"
        )
        self._log_user_activity(
            "threads_login_status_ui",
            f"state={state}; text={text}",
            min_interval_sec=0.1,
            dedupe_key=f"threads-status:{state}:{text}",
        )

    def event(self, evt):
        if evt.type() == LoginStatusEvent.EventType:
            if self._closed:
                return True
            is_logged_in, username = evt.result
            self._log_user_activity(
                "threads_login_check_result",
                f"is_logged_in={bool(is_logged_in)}; username={username or ''}",
            )
            self.check_login_btn.setEnabled(True)
            self.check_login_btn.setText("로그인 완료 안내")

            if is_logged_in:
                name = f"@{username}" if username else "연결됨"
                self._update_login_status("success", name)
            else:
                self._update_login_status("error", "연결 안됨")
            return True
        return super().event(evt)

    # ────────────────────────────────────────────────────────
    #  UPLOAD LOGIC
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _is_work_allowed(work_response):
        if not isinstance(work_response, dict):
            return False
        if "available" in work_response:
            return bool(work_response.get("available"))
        if "success" in work_response:
            return bool(work_response.get("success"))
        if "status" in work_response:
            return bool(work_response.get("status"))
        return False

    def start_upload(self):
        logger.info("업로드 시작 호출")
        self._log_user_activity("batch_start_requested", "source=start_button")
        content = self.links_text.toPlainText().strip()
        if not content:
            self._log_user_activity("batch_start_blocked", "reason=empty_links_input", level="WARNING")
            logger.warning("업로드 시작 차단: 내용이 비어 있습니다")
            show_warning(self, "알림", "쿠팡 파트너스 링크를 입력하세요.")
            return

        api_key = self._resolve_runtime_gemini_api_key(validate=False)
        if not api_key or len(api_key.strip()) < 10:
            self._log_user_activity("batch_start_blocked", "reason=invalid_runtime_api_key", level="WARNING")
            logger.warning("업로드 시작 차단: API 키가 유효하지 않습니다")
            show_error(self, "설정 필요", "설정에서 유효한 Gemini API 키를 설정하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            self._log_user_activity("batch_start_blocked", "reason=no_valid_links", level="WARNING")
            logger.warning("업로드 시작 차단: 유효한 링크가 없습니다")
            show_warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
            return

        config.load()
        interval = max(config.upload_interval, 30)
        logger.info("업로드 준비 완료: links=%d interval=%d", len(link_data), interval)

        try:
            from src import auth_client
            work_check = auth_client.check_work_available()
            if not self._is_work_allowed(work_check):
                self._log_user_activity("batch_start_blocked", "reason=work_quota_unavailable", level="WARNING")
                quota_message = (
                    work_check.get("message", "사용 가능한 작업량이 없습니다.")
                    if isinstance(work_check, dict)
                    else "작업량 확인에 실패했습니다."
                )
                logger.warning("업로드 시작 차단: 작업 가능 수량 없음 message=%s", quota_message)
                show_warning(self, "작업 제한", quota_message)
                return
        except Exception:
            logger.exception("업로드 시작 차단: 작업량 사전 점검 실패")
            show_warning(self, "작업 제한", "작업량 확인에 실패했습니다. 잠시 후 다시 시도해주세요.")
            return

        self._log_user_activity(
            "batch_start_confirmation_prompt",
            f"links={len(link_data)}; interval={interval}",
        )
        if not ask_yes_no(
            self,
            "확인",
            f"{len(link_data)}개 링크를 처리하고 업로드할까요?\n"
            f"업로드 간격: {_format_interval(interval)}\n\n"
            "(실행 중에 링크를 추가할 수 있습니다)",
        ):
            logger.info("업로드 시작이 사용자에 의해 취소되었습니다")
            return

        self._log_user_activity("batch_start_confirmed", f"links={len(link_data)}; interval={interval}")
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_badge.update_style(Colors.WARNING, "실행중")
        self._sidebar_status_label.setText("실행중")

        self._sidebar_success_label.setText("성공: 0")
        self._sidebar_failed_label.setText("실패: 0")
        self._sidebar_total_label.setText("전체: 0")
        self._progress_queue_label.setText(f"전체: 0 / {len(link_data)}")
        self._reset_steps()

        # Populate link table
        self._populate_link_table(link_data)

        with self._urls_lock:
            self.processed_urls.clear()
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)

        clean_links = "\n".join([item[0] for item in link_data])
        self.links_text.setPlainText(clean_links)

        # 서버에 활동 로그 전송
        try:
            from src import auth_client
            auth_client.log_action("batch_start", f"링크 {len(link_data)}개, 간격 {interval}초")
        except Exception:
            pass

        ig_username = config.instagram_username
        if ig_username:
            profile_name = self._sanitize_profile_name(ig_username)
            profile_dir = f".threads_profile_{profile_name}"
        else:
            profile_dir = ".threads_profile"
        worker_config = {
            "api_key": api_key,
            "profile_dir": profile_dir,
        }
        self._active_pipeline = self.pipeline
        thread = threading.Thread(
            target=self._run_upload_queue,
            args=(interval, worker_config, self._active_pipeline),
            daemon=True,
        )
        thread.start()
        self._log_user_activity(
            "batch_worker_started",
            f"links={len(link_data)}; interval={interval}; profile_dir={profile_dir}",
        )
        logger.info("업로드 작업 스레드 시작")

    def add_links_to_queue(self):
        self._log_user_activity("queue_add_links_requested", "source=add_button")
        logger.info("링크 큐 추가 호출")
        content = self.links_text.toPlainText().strip()
        if not content:
            self._log_user_activity("queue_add_links_blocked", "reason=empty_links_input", level="WARNING")
            logger.warning("링크 큐 추가 차단: 내용이 비어 있습니다")
            show_warning(self, "알림", "추가할 링크를 입력하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            self._log_user_activity("queue_add_links_blocked", "reason=no_valid_links", level="WARNING")
            logger.warning("링크 큐 추가 차단: 유효한 링크가 없습니다")
            show_warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
            return

        added = 0
        with self._urls_lock:
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)
                    added += 1

                    # Add to table
                    row = self.link_table.rowCount()
                    self.link_table.insertRow(row)
                    num_item = QTableWidgetItem(str(row + 1))
                    num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.link_table.setItem(row, 0, num_item)
                    short_url = url if len(url) <= 50 else url[:47] + "..."
                    url_item = QTableWidgetItem(short_url)
                    url_item.setToolTip(url)
                    self.link_table.setItem(row, 1, url_item)
                    status_item = QTableWidgetItem("대기")
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_item.setForeground(QColor(Colors.TEXT_MUTED))
                    self.link_table.setItem(row, 2, status_item)
                    name_item = QTableWidgetItem("-")
                    name_item.setForeground(QColor(Colors.TEXT_MUTED))
                    self.link_table.setItem(row, 3, name_item)
                    self._link_url_row_map[url] = row

        if added > 0:
            self._log_user_activity(
                "queue_add_links_success",
                f"added={added}; queue_size={self.link_queue.qsize()}",
            )
            logger.info("링크 큐 추가 결과: added=%d queue=%d", added, self.link_queue.qsize())
            self.signals.log.emit(f"{added}개 새 링크 추가됨 (대기열: {self.link_queue.qsize()})")
            clean_links = "\n".join([item[0] for item in link_data])
            self.links_text.setPlainText(clean_links)
        else:
            self._log_user_activity("queue_add_links_noop", "reason=all_links_already_seen")
            logger.info("링크 큐 추가 결과: 새 링크가 없습니다")
            show_info(self, "알림", "모든 링크가 이미 대기열에 있거나 처리되었습니다.")

    def _run_upload_queue(self, interval, worker_config, pipeline_ref):
        logger.info("업로드 큐 작업자 시작: interval=%s", interval)
        from src.computer_use_agent import ComputerUseAgent
        from src.threads_playwright_helper import ThreadsPlaywrightHelper

        results = {
            "total": 0,
            "processed": 0,
            "parse_failed": 0,
            "uploaded": 0,
            "failed": 0,
            "cancelled": False,
            "details": [],
        }

        total_links = self.link_queue.qsize()

        def log(msg):
            message_text = str(msg or "").strip()
            if not message_text:
                return
            self.signals.log.emit(message_text)
            self.signals.progress.emit(message_text)
            self._log_user_activity("batch_runtime_log", message_text)

        agent = None
        try:
            log(f"업로드 시작 (대기열: {self.link_queue.qsize()})")
            self.signals.status.emit("처리중")

            api_key = str((worker_config or {}).get("api_key") or "")
            profile_dir = str((worker_config or {}).get("profile_dir") or ".threads_profile")

            log("브라우저 시작 중...")
            agent = ComputerUseAgent(
                api_key=api_key,
                headless=False,
                profile_dir=profile_dir,
            )
            agent.start_browser()

            try:
                goto_threads_with_fallback(
                    agent.page,
                    path="/",
                    timeout=15000,
                    retries_per_url=1,
                    logger=logger,
                )
                time.sleep(3)
            except Exception:
                logger.exception("Threads 초기 페이지 이동 실패")

            helper = ThreadsPlaywrightHelper(agent.page)

            if not helper.check_login_status():
                log("로그인이 필요합니다. 60초 안에 로그인해주세요.")
                for wait_sec in range(20):
                    time.sleep(3)
                    remaining = 60 - (wait_sec * 3)
                    if wait_sec % 3 == 0:
                        log(f"로그인 대기 중... {remaining}초 남음")
                    if helper.check_login_status():
                        log("로그인 확인됨")
                        break
                else:
                    log("60초 내 로그인되지 않아 업로드를 취소합니다.")
                    results["cancelled"] = True
                    self.signals.finished.emit(results)
                    return

            log("Threads 로그인 상태 확인 완료")

            processed_count = 0
            empty_count = 0

            while not self._stop_event.is_set():
                try:
                    item = self.link_queue.get(timeout=5)
                    empty_count = 0
                except queue.Empty:
                    empty_count += 1
                    if empty_count >= 6:
                        log("대기열이 비어 작업자를 종료합니다.")
                        break
                    log("새 링크를 기다리는 중...")
                    continue

                if self._stop_event.is_set():
                    results["cancelled"] = True
                    break

                try:
                    from src import auth_client
                    work_check = auth_client.check_work_available()
                    if not self._is_work_allowed(work_check):
                        quota_message = (
                            work_check.get("message", "사용 가능한 작업량이 없습니다.")
                            if isinstance(work_check, dict)
                            else "작업량 확인에 실패했습니다."
                        )
                        log(f"작업량 확인 실패: {quota_message}")
                        results["cancelled"] = True
                        break
                except Exception:
                    logger.exception("업로드 루프에서 작업량 확인 실패")
                    log("작업량 확인 실패로 업로드를 중단합니다.")
                    results["cancelled"] = True
                    break

                processed_count += 1
                url, keyword = item if isinstance(item, tuple) else (item, None)
                results["total"] += 1

                log(f"{processed_count}번째 항목 처리 중 (대기열: {self.link_queue.qsize()})")

                # Update progress
                self.signals.queue_progress.emit(f"전체: {processed_count} / {total_links}")

                # Step 0: Link analysis
                self.signals.step_update.emit(0, "active")
                self.signals.link_status.emit(url, "진행중", "")

                log("상품 정보 분석 중...")

                try:
                    # Step 1: Content generation (parse + AI)
                    self.signals.step_update.emit(0, "done")
                    self.signals.step_update.emit(1, "active")

                    post_data = pipeline_ref.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results["parse_failed"] += 1
                        log("분석 실패로 이 항목을 건너뜁니다.")
                        self.signals.step_update.emit(1, "error")
                        self.signals.link_status.emit(url, "실패", "분석 실패")
                        self.signals.reset_steps.emit()
                        continue

                    results["processed"] += 1
                    product_name = post_data.get("product_title", "")[:30]
                    log(f"분석 완료: {product_name}")
                    self.signals.step_update.emit(1, "done")
                except Exception as exc:
                    results["parse_failed"] += 1
                    log(f"분석 오류: {str(exc)[:80]}")
                    self.signals.step_update.emit(1, "error")
                    self.signals.link_status.emit(url, "실패", "오류")
                    self.signals.reset_steps.emit()
                    continue

                # Step 2: Upload to Threads
                self.signals.step_update.emit(2, "active")
                log("Threads 게시글 업로드 중...")
                reserved_work_id = None
                reservation_supported = False

                try:
                    goto_threads_with_fallback(
                        agent.page,
                        path="/",
                        timeout=15000,
                        retries_per_url=1,
                        logger=logger,
                    )
                    time.sleep(2)

                    posts_data = [
                        {
                            "text": post_data["first_post"]["text"],
                            "image_path": post_data["first_post"].get("media_path"),
                        },
                        {
                            "text": post_data["second_post"]["text"],
                            "image_path": None,
                        },
                    ]

                    # Reserve work token when backend supports atomic quota flow.
                    try:
                        from src import auth_client
                        reserve_result = auth_client.reserve_work()
                        if isinstance(reserve_result, dict) and reserve_result.get("unsupported"):
                            log("작업 예약 API를 지원하지 않아 기존 과금 동기화를 사용합니다.")
                            reservation_supported = False
                            reserved_work_id = None
                        elif not self._is_work_allowed(reserve_result):
                            quota_message = (
                                reserve_result.get("message", "사용 가능한 작업량이 없습니다.")
                                if isinstance(reserve_result, dict)
                                else "작업량 확인에 실패했습니다."
                            )
                            log(f"작업 예약 실패: {quota_message}")
                            results["cancelled"] = True
                            break
                        else:
                            reservation_supported = True
                            reserved_work_id = (
                                str(
                                    reserve_result.get("reservation_id")
                                    or reserve_result.get("reserve_id")
                                    or reserve_result.get("work_token")
                                    or ""
                                ).strip()
                                if isinstance(reserve_result, dict)
                                else ""
                            )
                            if not reserved_work_id:
                                log("작업 예약 ID가 없어 안전상 업로드를 중단합니다.")
                                results["cancelled"] = True
                                break
                    except Exception:
                        logger.exception("업로드 루프에서 작업량 예약 실패")
                        log("작업 예약 실패로 업로드를 중단합니다.")
                        results["cancelled"] = True
                        break

                    success = helper.create_thread_direct(posts_data)
                    recorded_success = bool(success)
                    stop_for_billing_sync = False
                    if success:
                        try:
                            from src import auth_client
                            if reservation_supported and reserved_work_id:
                                use_result = auth_client.commit_reserved_work(reserved_work_id)
                            else:
                                use_result = auth_client.use_work()
                            if not isinstance(use_result, dict) or not bool(use_result.get("success")):
                                billing_msg = (
                                    use_result.get("message", "알 수 없음")
                                    if isinstance(use_result, dict)
                                    else "알 수 없음"
                                )
                                recorded_success = False
                                stop_for_billing_sync = True
                                results["failed"] += 1
                                log(f"작업량 동기화 실패: {billing_msg}. 안전상 업로드를 중단합니다.")
                                self.signals.step_update.emit(3, "error")
                                self.signals.link_status.emit(url, "실패", f"과금 동기화 실패: {billing_msg}")
                            else:
                                results["uploaded"] += 1
                                log(f"업로드 성공: {product_name}")
                                self.signals.step_update.emit(2, "done")
                                self.signals.step_update.emit(3, "done")
                                self.signals.link_status.emit(url, "완료", product_name)
                        except Exception:
                            logger.exception("업로드 성공 후 작업량 동기화 실패")
                            recorded_success = False
                            stop_for_billing_sync = True
                            results["failed"] += 1
                            log("작업량 동기화 실패로 안전상 업로드를 중단합니다.")
                            self.signals.step_update.emit(3, "error")
                            self.signals.link_status.emit(url, "실패", "과금 동기화 실패")
                    else:
                        if reservation_supported and reserved_work_id:
                            try:
                                from src import auth_client
                                auth_client.release_reserved_work(reserved_work_id)
                            except Exception:
                                logger.exception("업로드 실패 후 예약 작업량 해제 실패")
                        results["failed"] += 1
                        log(f"업로드 실패: {product_name}")
                        self.signals.step_update.emit(2, "error")
                        self.signals.link_status.emit(url, "실패", product_name)

                    results["details"].append(
                        {
                            "product_title": product_name,
                            "url": url,
                            "success": recorded_success,
                        }
                    )
                    if stop_for_billing_sync:
                        results["cancelled"] = True
                        break
                except Exception as exc:
                    if reservation_supported and reserved_work_id:
                        try:
                            from src import auth_client
                            auth_client.release_reserved_work(reserved_work_id)
                        except Exception:
                            logger.exception("업로드 예외 처리 중 예약 작업량 해제 실패")
                    results["failed"] += 1
                    log(f"업로드 오류: {str(exc)[:80]}")
                    self.signals.step_update.emit(2, "error")
                    self.signals.link_status.emit(url, "실패", product_name)

                self.signals.results.emit(results["uploaded"], results["failed"])
                self.signals.reset_steps.emit()

                if not self._stop_event.is_set():
                    log(f"다음 항목까지 {_format_interval(interval)} 대기")
                    for sec in range(interval):
                        if self._stop_event.is_set():
                            results["cancelled"] = True
                            break
                        remaining = interval - sec
                        if remaining % 60 == 0 and remaining > 0:
                            log(f"대기 중... {_format_interval(remaining)} 남음")
                        time.sleep(1)

            log("=" * 40)
            log(
                "작업 종료 - "
                f"성공: {results['uploaded']} / "
                f"실패: {results['failed']} / "
                f"분석 실패: {results['parse_failed']}"
            )

            # 서버에 배치 완료 로그 전송
            try:
                from src import auth_client
                summary = (
                    f"성공: {results['uploaded']}, "
                    f"실패: {results['failed']}, "
                    f"파싱실패: {results['parse_failed']}"
                )
                if results["cancelled"]:
                    auth_client.log_action("batch_cancelled", summary)
                else:
                    auth_client.log_action("batch_complete", summary)
            except Exception:
                pass

            if results["cancelled"]:
                self.signals.status.emit("취소됨")
            else:
                self.signals.status.emit("완료")

            self.signals.finished.emit(results)

        except Exception as exc:
            logger.exception("_run_upload_queue에서 치명적 오류 발생")
            log(f"치명적 오류: {exc}")
            self.signals.status.emit("오류")
            self.signals.finished.emit(results)
            try:
                from src import auth_client
                auth_client.log_action("batch_error", str(exc)[:200], level="ERROR")
            except Exception:
                pass
        finally:
            if agent is not None:
                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    logger.exception("브라우저 정상 종료에 실패했습니다")

    def stop_upload(self):
        logger.info("업로드 중지 호출; is_running=%s", self.is_running)
        if self.is_running:
            self.signals.log.emit("중지 요청됨. 현재 항목 처리 후 중단합니다.")
            self.signals.status.emit("중지중...")
            self.status_badge.update_style(Colors.WARNING, "중지중")
            self._relayout_header_account_card()
            self._sidebar_status_label.setText("중지중...")
            self.is_running = False
            pipeline = self._active_pipeline or self.pipeline
            if pipeline is not None:
                pipeline.cancel()
            try:
                from src import auth_client
                auth_client.log_action("batch_stop", "사용자가 작업을 중지함")
            except Exception:
                pass

    # ────────────────────────────────────────────────────────
    #  HEARTBEAT / LOGOUT / UPDATE / TUTORIAL
    # ────────────────────────────────────────────────────────

    def _send_heartbeat(self):
        """Send heartbeat and reflect server connectivity in the UI."""
        logger.debug("하트비트 실행; is_running=%s", self.is_running)
        try:
            from src import auth_client

            if not auth_client.is_logged_in():
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.TEXT_MUTED}; border-radius: 4px;"
                )
                self._connection_label.setText("로그아웃")
                self._connection_label.setStyleSheet(
                    f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600; background: transparent;"
                )
                self.status_label.setText("로그아웃")
                self._server_label.setText("서버 연결: 로그아웃")
                if not self._session_expiry_notified:
                    show_warning(self, "세션 만료", "로그인 세션이 만료되었거나 로그아웃되었습니다. 다시 로그인해주세요.")
                    self._session_expiry_notified = True
                    self._redirect_to_login_window("세션이 만료되었습니다. 다시 로그인해주세요.")
                return

            task = "uploading" if self.is_running else "idle"
            result = auth_client.heartbeat(
                current_task=task,
                app_version=self._app_version
            )
            if isinstance(result, dict):
                self._update_account_display()
            if result.get("status") is True:
                self._session_expiry_notified = False
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
                )
                self._connection_label.setText("서버 접속 중")
                self._connection_label.setStyleSheet(
                    f"color: {Colors.SUCCESS}; font-size: 8pt; font-weight: 700; background: transparent;"
                )
                self._server_label.setText("서버 연결: 정상")
                if not self.is_running:
                    self.status_label.setText("연결됨")
            else:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.ERROR}; border-radius: 4px;"
                )
                self._connection_label.setText("연결 끊김")
                self._connection_label.setStyleSheet(
                    f"color: {Colors.ERROR}; font-size: 8pt; font-weight: 700; background: transparent;"
                )
                self._server_label.setText("서버 연결: 끊김")
                self.status_label.setText("연결 끊김")
        except Exception:
            logger.exception("하트비트 전송 실패")
            self._online_dot.setStyleSheet(
                f"background-color: {Colors.ERROR}; border-radius: 4px;"
            )
            self._connection_label.setText("연결 오류")
            self._connection_label.setStyleSheet(
                f"color: {Colors.ERROR}; font-size: 8pt; font-weight: 700; background: transparent;"
            )
            self._server_label.setText("서버 연결: 오류")
            self.status_label.setText("연결 오류")

    def _redirect_to_login_window(self, status_message: str = ""):
        """세션 만료 시 로그인 창으로 복귀하고 현재 메인 창을 정리한다."""
        if self._redirecting_to_login or self._closed:
            return
        self._redirecting_to_login = True
        logger.warning("세션 만료로 로그인 창 복귀를 시작합니다.")

        try:
            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer is not None:
                self._heartbeat_timer.stop()
        except Exception:
            logger.exception("세션 만료 복귀 중 하트비트 타이머 중지 실패")

        try:
            from src import auth_client
            auth_client.logout()
        except Exception:
            logger.debug("세션 만료 복귀 중 로그아웃 API 호출에 실패했습니다.", exc_info=True)

        login_win = getattr(self, "_login_ref", None)
        if login_win is not None:
            try:
                login_win.login_pw.clear()
                if status_message:
                    login_win.login_status.setText(status_message)
                login_win.show()
                login_win.raise_()
                login_win.activateWindow()
            except Exception:
                logger.exception("세션 만료 복귀 중 로그인 창 표시에 실패했습니다.")

        app = QApplication.instance()
        if app is not None and getattr(app, "_main_window", None) is self:
            app._main_window = None

        self._force_close_for_relogin = True
        self.close()

    def _do_logout(self):
        """로그아웃 처리 후 앱 종료."""
        logger.info("로그아웃 요청")
        if self.is_running:
            show_warning(self, "알림", "작업 중에는 로그아웃할 수 없습니다.\n먼저 작업을 중지해주세요.")
            return
        if ask_yes_no(
            self,
            "로그아웃",
            "로그아웃하고 프로그램을 종료하시겠습니까?",
        ):
            try:
                from src import auth_client
                auth_client.logout()
            except Exception:
                pass
            try:
                from src.computer_use_agent import ComputerUseAgent
                profile_dir = self._get_profile_dir()
                cleanup_agent = ComputerUseAgent(
                    api_key="dummy-key-for-session-setup",
                    headless=True,
                    profile_dir=profile_dir,
                )
                cleanup_agent.clear_saved_session()
            except Exception:
                logger.exception("로그아웃 중 저장된 브라우저 세션 삭제 실패")
            QApplication.quit()

    def check_for_updates(self):
        """업데이트 확인 (사용자 버튼 클릭)."""
        logger.info("수동 업데이트 확인 창 열림")
        from src.update_dialog import UpdateDialog

        dialog = UpdateDialog(self._app_version, self)
        dialog.exec()

    def _check_for_updates_silent(self):
        """백그라운드 자동 업데이트 체크 (알림만 표시)."""
        logger.info("백그라운드 업데이트 확인 시작")
        try:
            from src.auto_updater import AutoUpdater

            updater = AutoUpdater(self._app_version)
            update_info = updater.check_for_updates()

            if update_info:
                version_text = str(update_info.get("version", "") or "").strip()
                logger.info("자동 업데이트 발견, 즉시 업데이트를 시작합니다 (version=%s)", version_text)
                self._run_auto_update_flow(update_info)
        except Exception as e:
            logger.exception("백그라운드 업데이트 확인 실패")
            # Silent check: keep UI quiet; details are already in logs.
            return


    def _run_auto_update_flow(self, update_info: dict):
        """Run download/install immediately without confirmation prompts."""
        if not isinstance(update_info, dict) or not update_info:
            return

        def worker():
            try:
                from src.auto_updater import AutoUpdater

                updater = AutoUpdater(self._app_version)
                update_file = updater.download_update(update_info)
                if not update_file:
                    logger.warning("자동 업데이트 다운로드 실패")
                    return

                expected_sha256 = str(update_info.get("expected_sha256", "") or "")
                if updater.install_update(update_file, expected_sha256=expected_sha256):
                    logger.info("자동 업데이트 설치 프로그램 실행됨, 애플리케이션을 종료합니다")
                    app = QApplication.instance()
                    if app is not None:
                        app.quit()
                else:
                    logger.warning("자동 업데이트 설치 실패")
            except Exception:
                logger.exception("자동 업데이트 흐름 실패")

        threading.Thread(target=worker, daemon=True, name="auto-update-worker").start()

    def open_tutorial(self):
        logger.info("튜토리얼 열기 호출")
        from src.tutorial import TutorialDialog
        dialog = TutorialDialog(self)
        dialog.exec()

    # ────────────────────────────────────────────────────────
    #  EVENTS
    # ────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not config.tutorial_shown and self._tutorial_overlay is None:
            from src.tutorial import TutorialOverlay
            self._tutorial_overlay = TutorialOverlay(self.centralWidget())
            self._tutorial_overlay.show_overlay()

    def paintEvent(self, event):
        """메인 윈도우 하단 강조 라인."""
        super().paintEvent(event)
        painter = QPainter(self)
        w, h = self.width(), self.height()
        bot_grad = QLinearGradient(0, 0, w, 0)
        bot_grad.setColorAt(0, QColor(13, 89, 242, 0))
        bot_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        bot_grad.setColorAt(0.7, QColor(Colors.ACCENT))
        bot_grad.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, h - 4, w, 4, bot_grad)

    def closeEvent(self, event):
        """윈도우 종료 시 로그아웃 처리."""
        logger.info("종료 이벤트 호출; is_running=%s", self.is_running)
        forced_relogin = bool(getattr(self, "_force_close_for_relogin", False))
        self._log_user_activity(
            "ui_window_closing",
            f"forced_relogin={forced_relogin}; is_running={self.is_running}",
        )

        if self.is_running and not forced_relogin:
            if not ask_yes_no(
                self,
                "종료 확인",
                "작업이 진행 중입니다. 정말 종료하시겠습니까?",
            ):
                event.ignore()
                return
            self.stop_upload()
        elif self.is_running and forced_relogin:
            self.stop_upload()
        self._closed = True
        self._browser_cancel.set()
        try:
            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer is not None:
                self._heartbeat_timer.stop()
        except Exception:
            logger.exception("하트비트 타이머 중지 실패")

        if not forced_relogin:
            try:
                from src import auth_client
                auth_client.logout()
            except Exception:
                pass
        try:
            if hasattr(self, "_activity_log_stop") and self._activity_log_stop is not None:
                self._activity_log_stop.set()
            if hasattr(self, "_activity_log_thread") and self._activity_log_thread is not None:
                self._activity_log_thread.join(timeout=1.2)
        except Exception:
            logger.exception("UI activity logger 종료 처리 실패")

        event.accept()
