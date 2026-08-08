# -*- coding: utf-8 -*-
"""Multi-market Threads automation desktop window.

The interface uses a responsive two-page workspace: Automation and Settings.
Upload behavior and writing style live in one Settings source of truth, while
contextual guidance expands inside the current page instead of opening a modal.
"""
from __future__ import annotations

import json
import hashlib
import re
import html
import os
import tempfile
import time
import logging
import threading
import queue
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QFrame,
    QLineEdit, QSpinBox, QCheckBox, QButtonGroup, QComboBox,
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QTabBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QUrl, QTimer
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QLinearGradient,
    QPen,
    QDesktopServices,
    QRegularExpressionValidator,
    QKeySequence,
)

from src.ai_provider import (
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_GROK_CLI,
    AI_PROVIDER_MANAGED,
    normalize_ai_provider,
)
from src.config import config
from src.coupang_uploader import CancelledException, CoupangPartnersPipeline
from src.gemini_keys import (
    MAX_GEMINI_API_KEYS,
    normalize_gemini_api_keys,
    save_configured_gemini_api_keys,
    select_working_gemini_api_key,
)
from src.services.post_concepts import POST_CONCEPTS, normalize_concept_id
from src.services.marketplaces import (
    extract_supported_product_links,
    marketplace_for_url,
)
from src.services.thread_payload import build_product_thread_payload
from src.services.account_queue import AccountQueueStore
from src.services.multi_account_runtime import MultiAccountRuntime
from src.update_resume import UpdateResumeStore, active_account_ids, update_completed
from src.update_dialog import UpdateDialog
from src.theme import (
    Colors,
    Typography,
    Radius,
    Gradients,
    global_stylesheet,
    badge_style,
    muted_text_style,
    hint_text_style,
    section_title_style,
)
from src.ui_messages import ask_yes_no, show_error, show_info, show_warning
from src.events import LoginStatusEvent
from src.autostart import sync_auto_start
from src.hidpi import apply_window_size_policy
from src.ui_components import HelpButton, InlineHelpPanel
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
UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000


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
    run_state = pyqtSignal(dict)
    results = pyqtSignal(int, int)
    product = pyqtSignal(str, bool)
    finished = pyqtSignal(dict)
    step_update = pyqtSignal(int, str)       # step_index, status
    link_status = pyqtSignal(str, str, str)  # url, status, product_name
    queue_progress = pyqtSignal(str)
    reset_steps = pyqtSignal()
    threads_login_launch = pyqtSignal(bool, str)  # success, detail
    threads_browser_closed = pyqtSignal()
    heartbeat_complete = pyqtSignal(object)
    update_check_complete = pyqtSignal(object)
    update_install_progress = pyqtSignal(object)
    update_install_complete = pyqtSignal(object)
    grok_status = pyqtSignal(str, str, str)
    account_runtime_state = pyqtSignal(str, object)
    account_runtime_log = pyqtSignal(str, str)


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
    """Quiet midnight header with a single restrained accent line."""
    ACCENT_LINE_H = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(HEADER_H)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Low-contrast surface gradient keeps the title readable without glare.
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(Colors.BG_HEADER))
        grad.setColorAt(0.55, QColor(Colors.BG_ELEVATED))
        grad.setColorAt(1, QColor(Colors.BG_HEADER))
        painter.fillRect(self.rect(), grad)

        # 상단 accent 라인
        accent = QLinearGradient(0, 0, w, 0)
        accent.setColorAt(0, QColor(45, 212, 191, 0))
        accent.setColorAt(0.2, QColor(Colors.ACCENT))
        accent.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        accent.setColorAt(0.8, QColor(Colors.ACCENT))
        accent.setColorAt(1, QColor(45, 212, 191, 0))
        painter.fillRect(0, 0, w, self.ACCENT_LINE_H, accent)

        # 하단 border
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawLine(0, h - 1, w, h - 1)


# ─── SidebarPanel ──────────────────────────────────────────

class SidebarPanel(QFrame):
    """Midnight sidebar panel with a quiet separator."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 배경
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.BG_SIDEBAR))
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
    """멀티 쇼핑몰 스레드 자동화 메인 윈도우 - 사이드바 레이아웃."""

    MAX_LOG_LINES = 2000

    PRODUCT_LINK_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
    # Compatibility for tests/extensions that referenced the old constant.
    COUPANG_LINK_PATTERN = PRODUCT_LINK_PATTERN

    # Sidebar menu items
    _SIDEBAR_ITEMS = ["자동화", "설정"]

    # Process steps for progress panel
    _PROCESS_STEPS = [
        "링크 분석",
        "콘텐츠 생성",
        "Threads 업로드",
        "완료 처리",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thread Auto - Multi-market Shopping Automation")
        apply_window_size_policy(self)

        self.pipeline = CoupangPartnersPipeline(
            config.gemini_api_key,
            ai_provider=getattr(config, "ai_provider", AI_PROVIDER_GROK_CLI),
        )
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._urls_lock = threading.Lock()
        self.link_queue = queue.Queue()
        self.processed_urls = set()
        self._closed = False
        self._browser_cancel = threading.Event()
        self._link_url_row_map = {}  # url -> table row index
        self._active_pipeline = None
        self._resume_state_path = Path(config.config_dir) / "upload_resume_queue.json"
        self._resume_state_lock = threading.RLock()
        self._resume_items = []
        self._resume_recovered_idempotency_keys = {}
        self._resume_interval = max(int(getattr(config, "upload_interval", 60) or 60), 30)
        self._resume_next_allowed_at = None
        self._session_expiry_notified = False
        self._redirecting_to_login = False
        self._force_close_for_relogin = False
        self._force_close_for_update = False
        self._update_installing = False
        self._pending_update_info = None
        self._update_notice_version = ""
        self._update_dialog = None
        self._update_resume_store = UpdateResumeStore(
            Path(config.config_dir) / "update_resume.json"
        )
        self._latest_run_state = {}
        self._account_drafts = {}
        self._upload_tab_syncing = False
        self._multi_account_runtime = None
        self._init_activity_logger()
        logger.info("메인 윈도우 초기화 완료")

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.run_state.connect(self._set_run_state)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)
        self.signals.step_update.connect(self._update_step)
        self.signals.link_status.connect(self._update_link_table_status)
        self.signals.queue_progress.connect(self._set_queue_progress)
        self.signals.reset_steps.connect(self._reset_steps)
        self.signals.threads_login_launch.connect(self._on_threads_login_launch_result)
        self.signals.threads_browser_closed.connect(self._on_threads_browser_closed)
        self.signals.heartbeat_complete.connect(self._apply_heartbeat_result)
        self.signals.update_check_complete.connect(self._apply_update_check_result)
        self.signals.update_install_progress.connect(self._apply_update_install_progress)
        self.signals.update_install_complete.connect(self._apply_update_install_result)
        self.signals.grok_status.connect(self._apply_grok_status)
        self.signals.account_runtime_state.connect(self._on_account_runtime_state)
        self.signals.account_runtime_log.connect(self._on_account_runtime_log)

        self._current_page = 0
        self._inline_help_enabled = False
        self._inline_help_panels = {}
        self._heartbeat_in_flight = False
        self._update_check_in_flight = False
        # Apply global stylesheet before building widgets so sizeHint/metrics are correct
        # for any fixed-geometry placement that depends on styled font/padding.
        self.setStyleSheet(global_stylesheet())
        self._build_ui()
        self._relayout_main_window()
        self._switch_page(0)
        self._app_version = self._resolve_app_version()

        # Heartbeat timer
        from PyQt6.QtCore import QTimer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(60_000)
        QTimer.singleShot(1000, self._send_heartbeat)

        # Check on startup and periodically so already-running users see updates.
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._check_for_updates_silent)
        self._update_timer.start(UPDATE_CHECK_INTERVAL_MS)
        QTimer.singleShot(3000, self._check_for_updates_silent)

        # Load settings into widgets
        self._load_settings()
        self._init_multi_account_runtime()
        QTimer.singleShot(1200, self._resume_after_completed_update)
        QTimer.singleShot(1800, self._prompt_resume_queue_if_needed)
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
            ("_pay_weekly_btn", "settings_pay_weekly_basic"),
            ("_pay_monthly_btn", "settings_pay_monthly"),
            ("_pay_shopping_weekly_btn", "settings_pay_weekly_shopping_pro"),
            ("_pay_shopping_monthly_btn", "settings_pay_monthly_shopping_pro"),
            ("_pay_refresh_btn", "settings_payment_refresh"),
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
            f"QLabel {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" border: 1px solid {Colors.ACCENT};"
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
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14pt; font-weight: 700;"
            " letter-spacing: -0.5px; background: transparent;"
        )

        # Subtitle
        sub_label = QLabel("THREAD SHOPPING AUTOMATION", header)
        sub_label.setGeometry(62, 38, 260, 20)
        sub_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600;"
            " letter-spacing: 1.4px; background: transparent;"
        )

        # Right-side elements (positioned from right edge)
        _nav_pill_style = (
            f"QPushButton {{ background: {Colors.BG_ELEVATED};"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER};"
            f" border-radius: 8px; font-size: 9pt; font-weight: 700;"
            f" padding: 6px 12px; min-height: 20px; }}"
            f" QPushButton:hover, QPushButton:focus {{ background: {Colors.ACCENT_SUBTLE};"
            f" color: {Colors.TEXT_PRIMARY}; border: 2px solid {Colors.ACCENT}; }}"
            f" QPushButton:checked {{ background: {Colors.ACCENT}; color: {Colors.BG_DARK}; }}"
        )

        # Logout button (far right)
        self.logout_btn = QPushButton("로그아웃", header)
        self.logout_btn.setGeometry(WIN_W - 80, 20, 64, 28)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BG_ELEVATED};"
            f" color: {Colors.TEXT_MUTED};"
            f" border: 1px solid {Colors.BORDER};"
            f" border-radius: 8px; font-size: 9pt; font-weight: 600;"
            f" padding: 6px 12px; min-height: 20px; }}"
            f" QPushButton:hover, QPushButton:focus {{ background: {Colors.ERROR_BG};"
            f" color: {Colors.ERROR}; border: 2px solid {Colors.ERROR}; }}"
        )
        self.logout_btn.clicked.connect(self._do_logout)

        # Tutorial button
        self.tutorial_btn = QPushButton("도움말", header)
        self.tutorial_btn.setCheckable(True)
        self.tutorial_btn.setAccessibleName("현재 화면 도움말")
        self.tutorial_btn.setGeometry(WIN_W - 80 - 12 - 56, 20, 56, 28)
        self.tutorial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tutorial_btn.setShortcut(QKeySequence("F1"))
        self.tutorial_btn.setStyleSheet(_nav_pill_style)
        self.tutorial_btn.clicked.connect(self.toggle_inline_help)

        self.update_btn = QPushButton("업데이트", header)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet(
            "QPushButton { background-color: #F6C945; color: #111827; border: none;"
            " border-radius: 8px; padding: 4px 12px; font-size: 9pt; font-weight: 800; }"
            "QPushButton:hover { background-color: #FFD968; }"
            "QPushButton:disabled { background-color: #5A6170; color: #D1D5DB; }"
        )
        self.update_btn.clicked.connect(self._activate_pending_update)
        self.update_btn.setVisible(False)

        # Re-place header pills by sizeHint to avoid text clipping across fonts
        nav_y = 20
        nav_h = 28
        nav_gap = 10
        nav_right = WIN_W - 16
        for btn in (self.logout_btn, self.tutorial_btn, self.update_btn):
            btn.ensurePolished()
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            btn.setFixedHeight(32)
            # Keep both buttons visually consistent with reference topbar proportions.
            w = 82
            nav_right -= w
            btn.setGeometry(nav_right, nav_y, w, nav_h)
            nav_right -= nav_gap


        # ── Top-right account controls (reference: NewshoppingShorts topbar) ──
        self._work_label = QPushButton("0 / 0 회", header)
        self._work_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._work_label.setStyleSheet(
            "QPushButton {"
            f" background-color: {Colors.ACCENT};"
            f" color: {Colors.BG_DARK};"
            " border: none;"
            " border-radius: 8px;"
            " padding: 8px 16px;"
            " font-size: 9pt;"
            " font-weight: 700;"
            "}"
            f"QPushButton:hover {{ background-color: {Colors.ACCENT_LIGHT}; }}"
            f"QPushButton:pressed {{ background-color: {Colors.ACCENT_DARK}; }}"
        )
        self._work_label.clicked.connect(self.open_settings)

        self._header_username_label = QLabel("사용자", header)
        self._header_username_full_text = "사용자"
        self._header_username_label.setToolTip(self._header_username_full_text)
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
            f"QLabel {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" color: {Colors.ACCENT_LIGHT}; border: 1px solid {Colors.ACCENT};"
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
            f" background-color: {Colors.ACCENT_SUBTLE};"
            f" border-color: {Colors.ACCENT};"
            f" color: {Colors.TEXT_PRIMARY};"
            f"}}"
        )
        self._plan_badge.clicked.connect(self.open_settings)

        self._header_nav_buttons = (self.logout_btn, self.tutorial_btn, self.update_btn)
        self._relayout_header_account_card()

        self._header = header
        self._brand_icon = brand_icon

    def _relayout_header_account_card(self):
        """Lay out header controls without clipping at compact window widths."""
        width = max(1, self.centralWidget().width() if self.centralWidget() else self.width())
        nav_buttons = [btn for btn in getattr(self, "_header_nav_buttons", ()) if btn is not None]
        right = width - 16
        for btn in nav_buttons:
            if btn is self.update_btn and not btn.isVisible():
                continue
            button_w = 88
            if btn is self.update_btn:
                btn.ensurePolished()
                button_w = max(96, btn.sizeHint().width())
            btn.setGeometry(right - button_w, 18, button_w, 32)
            right = btn.x() - 8

        nav_left = right + 8
        right = nav_left - 12
        top = 19
        control_h = 30
        min_left = 306
        self.status_badge.setVisible(False)

        plan_text = self._plan_badge.text() or "무료계정"
        plan_w = max(self._plan_badge.fontMetrics().horizontalAdvance(plan_text) + 24, 84)
        conn_text = self._connection_label.text() or "접속 확인 중"
        conn_w = max(self._connection_label.fontMetrics().horizontalAdvance(conn_text) + 8, 84)
        user_text = str(getattr(self, "_header_username_full_text", "") or "사용자")
        user_metrics = self._header_username_label.fontMetrics()
        user_w = min(max(user_metrics.horizontalAdvance(user_text) + 10, 48), 180)
        work_text = self._work_label.text() or "0 / 0 회"
        work_w = max(self._work_label.fontMetrics().horizontalAdvance(work_text) + 30, 106)
        detail_width = plan_w + 8 + conn_w + 7 + 8 + 8 + user_w + 8 + work_w
        show_account_detail = width >= 1110 and right - min_left >= detail_width
        self._header_username_label.setVisible(show_account_detail)
        self._online_dot.setVisible(show_account_detail)
        self._connection_label.setVisible(show_account_detail)

        self._plan_badge.setGeometry(max(min_left, right - plan_w), top, plan_w, control_h)
        right = self._plan_badge.x() - 8

        if show_account_detail:
            self._connection_label.setGeometry(max(min_left, right - conn_w), top + 5, conn_w, 20)
            right = self._connection_label.x() - 7

            self._online_dot.setGeometry(max(min_left, right - 8), top + 11, 8, 8)
            right = self._online_dot.x() - 8

            self._header_username_label.setGeometry(max(min_left, right - user_w), top + 4, user_w, 20)
            self._header_username_label.setText(
                user_metrics.elidedText(user_text, Qt.TextElideMode.ElideRight, user_w)
            )
            self._header_username_label.setToolTip(user_text)
            right = self._header_username_label.x() - 8

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

        self._sidebar_buttons[0].setShortcut(QKeySequence("Alt+1"))
        self._sidebar_buttons[1].setShortcut(QKeySequence("Alt+2"))
        self._sidebar_buttons[0].setToolTip("자동화 화면 · Alt+1")
        self._sidebar_buttons[1].setToolTip("통합 설정 화면 · Alt+2")

        self._sidebar_buttons[0].setChecked(True)
        self._sidebar_group.idClicked.connect(
            lambda idx: self._switch_page(idx, source="sidebar_menu")
        )

        # Divider line below buttons
        divider_y = 20 + len(self._SIDEBAR_ITEMS) * 48 + 12
        divider = QFrame(sidebar)
        divider.setGeometry(20, divider_y, SIDEBAR_W - 40, 1)
        divider.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self._sidebar_divider_top = divider

        # ── Progress Panel ─────────────────────────────────
        prog_y = divider_y + 16

        prog_title = QLabel("현재 진행 상황", sidebar)
        prog_title.setGeometry(24, prog_y, 200, 20)
        prog_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 700;"
            " letter-spacing: 1.5px; background: transparent;"
        )
        self._sidebar_progress_title = prog_title
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
        self._sidebar_divider_counts = divider2
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
        self._sidebar_log_title = log_title
        prog_y += 22

        log_h = max(WIN_H - HEADER_H - prog_y - STATUSBAR_H - 8, 80)
        self.log_text = QTextEdit(sidebar)
        self.log_text.setGeometry(12, prog_y, SIDEBAR_W - 24, log_h)
        self.log_text.setReadOnly(True)
        self.log_text.setTabChangesFocus(True)
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
            f"  background: {Colors.ACCENT_SUBTLE};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: {Colors.ACCENT_SUBTLE};"
            f"  color: {Colors.ACCENT_LIGHT};"
            f"  border-left: 3px solid {Colors.ACCENT};"
            f"}}"
        )

    # ── Pages ───────────────────────────────────────────────

    def _build_pages(self, parent):
        """Build the Automation and Settings workspaces."""
        page_x = SIDEBAR_W
        page_y = HEADER_H
        page_w = CONTENT_W
        page_h = CONTENT_H

        self._pages = []
        for _ in range(2):
            page = QWidget(parent)
            page.setGeometry(page_x, page_y, page_w, page_h)
            page.setVisible(False)
            self._pages.append(page)

        self._build_page0_links(self._pages[0])
        self._build_page2_settings(self._pages[1])

    def _make_page_header(self, page, icon_char, title_text):
        """Page header helper: icon + title + separator. Returns next y."""
        # Icon background
        icon_bg = QLabel("", page)
        icon_bg.setGeometry(28, 20, 36, 36)
        icon_bg.setStyleSheet(
            f"QLabel {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" border: 1px solid {Colors.ACCENT};"
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
            f"color: {Colors.TEXT_PRIMARY}; font-size: 15pt; font-weight: 800;"
            " letter-spacing: -0.3px; background: transparent;"
        )
        # Separator
        sep = QFrame(page)
        sep.setGeometry(28, 66, 944, 1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")

        page._page_header_widgets = (icon_bg, icon_label, title, sep)

        return 82  # next available y

    # ── Page 0: 링크 입력 ───────────────────────────────────

    def _build_page0_links(self, page):
        # Account tabs sit above the draft editor.  Account IDs, never labels,
        # are stored as tab data so renamed accounts cannot cross-contaminate.
        self._upload_account_tabs = QTabBar(page)
        self._upload_account_tabs.setGeometry(28, 82, 944, 30)
        self._upload_account_tabs.setExpanding(False)
        self._upload_account_tabs.setUsesScrollButtons(True)
        self._upload_account_tabs.setAccessibleName("Threads 계정별 자동화")
        self._upload_account_tabs.setStyleSheet(
            "QTabBar { background: transparent; border: none; }"
            f"QTabBar::tab {{ background-color: {Colors.BG_CARD}; color: {Colors.TEXT_MUTED};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 7px; padding: 6px 14px;"
            " margin-right: 6px; min-height: 18px; font-size: 9pt; font-weight: 650; }"
            f"QTabBar::tab:hover {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY}; }}"
            f"QTabBar::tab:selected {{ background-color: {Colors.ACCENT_SUBTLE}; color: {Colors.ACCENT_LIGHT};"
            f" border: 1px solid {Colors.ACCENT}; }}"
            f"QTabBar::tab:focus {{ border: 2px solid {Colors.ACCENT_LIGHT}; }}"
        )
        self._upload_account_tabs.currentChanged.connect(self._on_upload_account_tab_changed)
        cy = self._make_page_header(page, "◈", "링크 입력")

        self._page_help_btn = HelpButton("자동화 화면 도움말", page)
        self._page_help_btn.setGeometry(0, 22, 32, 32)
        self._page_help_btn.setToolTip("현재 화면 사용법을 바로 표시합니다")
        self._page_help_btn.toggled.connect(self.toggle_inline_help)

        self._link_help_panel = InlineHelpPanel(
            "링크 자동화 사용법",
            "상품 링크를 한 줄에 하나씩 붙여넣고 자동화 시작을 누르세요. 여러 계정은 위 탭에서 각각 대기열을 관리하며, 업로드 간격·영상 우선·글 작성 방식은 설정에서 한 번만 지정합니다.",
            page,
        )
        self._link_help_panel.setVisible(False)
        self._inline_help_panels[0] = self._link_help_panel

        cy += 38

        # Supported marketplaces summary (top right)
        self._coupang_link = QLabel(
            '<a href="https://coupuas-thread-auto-three.vercel.app/support" '
            f'style="color: {Colors.ACCENT_LIGHT}; text-decoration: none; font-weight: 600;">'
            '지원 쇼핑몰 안내 →</a>',
            page
        )
        self._coupang_link.setGeometry(CONTENT_W - 28 - 220, 28, 220, 24)
        self._coupang_link.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._coupang_link.setOpenExternalLinks(False)
        self._coupang_link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._coupang_link.setStyleSheet("background: transparent;")
        self._coupang_link.linkActivated.connect(
            lambda href: self._open_external_link(href, "page_links_supported_marketplaces")
        )

        # Link count badge
        self.link_count_badge = Badge("0개 링크", Colors.TEXT_MUTED, page)
        self.link_count_badge.setGeometry(CONTENT_W - 28 - 220 - 100, 28, 90, 24)

        # Hint text
        hint = QLabel(
            "상품 링크를 한 줄에 하나씩 붙여넣으세요 · 쿠팡 외 쇼핑몰은 쇼핑 프로에서 지원",
            page,
        )
        hint.setGeometry(28, cy, 700, 20)
        hint.setStyleSheet(muted_text_style("9pt"))
        self._links_hint = hint

        # Links text area (compact)
        self.links_text = QPlainTextEdit(page)
        self.links_text.setGeometry(28, cy + 24, 944, 160)
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://smartstore.naver.com/.../products/...\n"
            "https://www.aliexpress.com/item/...html"
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
            f"  border: 2px solid {Colors.ACCENT_DARK};"
            f"  border-radius: {Radius.LG};"
            f"  font-size: 11pt; font-weight: 800; letter-spacing: 0.5px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Gradients.ACCENT_BTN_HOVER};"
            f"  border-color: {Colors.ACCENT_LIGHT};"
            f"}}"
            f"QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}"
            f"QPushButton:disabled {{"
            f"  background-color: {Colors.BG_ELEVATED};"
            f"  color: {Colors.TEXT_MUTED};"
            f"  border-color: {Colors.BORDER};"
            f"}}"
        )
        self.start_btn.clicked.connect(self.start_upload)
        self.start_btn.setToolTip("현재 계정의 링크를 분석해 글 작성과 업로드를 시작합니다")
        self.start_btn.setAccessibleDescription(self.start_btn.toolTip())

        # Add links button
        self.add_btn = QPushButton("링크 추가", page)
        self.add_btn.setGeometry(278, btn_y, 160, 44)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setEnabled(False)
        self.add_btn.setProperty("class", "outline-success")
        self.add_btn.clicked.connect(self.add_links_to_queue)
        self.add_btn.setToolTip("실행 중인 현재 계정 대기열에 새 링크를 추가합니다")

        # Stop button
        self.stop_btn = QPushButton("중지", page)
        self.stop_btn.setGeometry(448, btn_y, 120, 44)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "outline-danger")
        self.stop_btn.clicked.connect(self.stop_upload)
        self.stop_btn.setToolTip("현재 계정의 자동화를 안전하게 중지합니다")

        self.start_all_btn = QPushButton("전체 시작", page)
        self.start_all_btn.setGeometry(578, btn_y, 180, 44)
        self.start_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_all_btn.setProperty("class", "outline-success")
        self.start_all_btn.clicked.connect(self.start_all_accounts)
        self.start_all_btn.setToolTip("링크가 준비된 모든 Threads 계정을 시작합니다")

        self.stop_all_btn = QPushButton("전체 중지", page)
        self.stop_all_btn.setGeometry(768, btn_y, 204, 44)
        self.stop_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_all_btn.setEnabled(False)
        self.stop_all_btn.setProperty("class", "outline-danger")
        self.stop_all_btn.clicked.connect(self.stop_all_accounts)
        self.stop_all_btn.setToolTip("실행 중인 모든 계정의 자동화를 중지합니다")

        # ── Live Run State Banner ───────────────────────────
        state_y = btn_y + 56
        self._run_state_frame = QFrame(page)
        self._run_state_frame.setObjectName("runStateFrame")
        self._run_state_frame.setGeometry(28, state_y, 944, 78)
        self._run_state_frame.setStyleSheet(
            f"QFrame#runStateFrame {{"
            f"  background-color: {Colors.INFO_BG};"
            f"  border: none;"
            f"  border-radius: {Radius.LG};"
            f"}}"
        )

        self._run_state_title = QLabel("자동화 대기", self._run_state_frame)
        self._run_state_title.setGeometry(18, 12, 160, 20)
        self._run_state_title.setStyleSheet(
            f"color: {Colors.INFO}; font-size: 9pt; font-weight: 800;"
            " background: transparent; border: none;"
        )

        self._run_state_main = QLabel("아직 실행 중인 대기열이 없습니다.", self._run_state_frame)
        self._run_state_main.setGeometry(18, 36, 420, 24)
        self._run_state_main.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 12pt; font-weight: 800;"
            " background: transparent; border: none;"
        )

        self._run_state_detail = QLabel("링크를 넣고 자동화 시작을 누르면 현재 상태가 여기에 표시됩니다.", self._run_state_frame)
        self._run_state_detail.setGeometry(456, 14, 456, 20)
        self._run_state_detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._run_state_detail.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent; border: none;"
        )

        self._run_state_next = QLabel("다음 작업: --", self._run_state_frame)
        self._run_state_next.setGeometry(456, 42, 456, 20)
        self._run_state_next.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._run_state_next.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
            " background: transparent; border: none;"
        )

        # ── Status Table ───────────────────────────────────
        table_label = QLabel("작업 현황", page)
        table_label.setGeometry(28, state_y + 88, 200, 20)
        table_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " letter-spacing: 1px; background: transparent;"
        )
        self._link_table_label = table_label

        table_y = state_y + 112
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
        sec2.setGeometry(28, cy + 156, 944, 150)

        sec2_title = QLabel("업로드 옵션", sec2)
        sec2_title.setGeometry(24, 16, 200, 22)
        sec2_title.setStyleSheet(section_title_style())

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선", sec2)
        self.video_check.setGeometry(24, 48, 400, 24)

        concept_label = QLabel("본문 작성 방식", sec2)
        concept_label.setGeometry(24, 82, 120, 22)
        concept_label.setStyleSheet(_field_lbl_style)

        self.post_concept_combo = QComboBox(sec2)
        self.post_concept_combo.setObjectName("uploadPostConceptCombo")
        self.post_concept_combo.setGeometry(144, 78, 250, 36)
        for concept in POST_CONCEPTS:
            self.post_concept_combo.addItem(concept.display_label, concept.id)
        self.post_concept_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background-color: {Colors.BG_INPUT};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: {Radius.MD};"
            f"  padding: 7px 10px;"
            f"  font-size: 10pt;"
            f"}}"
            f"QComboBox:focus {{ border-color: {Colors.ACCENT}; }}"
        )
        self.post_concept_combo.currentIndexChanged.connect(
            lambda _idx: self._sync_post_concept_combos(self.post_concept_combo)
        )

        concept_hint = QLabel("본문 1개를 생성하고, 상품·링크는 바로 아래 상품 댓글에 고정합니다", sec2)
        concept_hint.setGeometry(410, 85, 460, 18)
        concept_hint.setStyleSheet(hint_text_style())

        # ── Save Button ────────────────────────────────────
        self._upload_save_btn = QPushButton("저장", page)
        self._upload_save_btn.setGeometry(832, cy + 328, 140, 42)
        self._upload_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_save_btn.clicked.connect(self._save_settings)

    # ── Page 2: 설정 ────────────────────────────────────────

    def _build_page2_settings(self, page):
        cy = self._make_page_header(page, "⚙", "설정")

        _section_style = (
            f"QFrame {{ background-color: {Colors.BG_CARD};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 12px;"
            " outline: none;"
            "}"
        )
        _control_h = 40
        _action_btn_w = 196
        _section_title_style = (
            f"color: {Colors.TEXT_PRIMARY}; font-size: 10pt; font-weight: 700; background: transparent; border: none;"
        )
        _field_lbl_style = (
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; background: transparent; border: none;"
        )
        _hint_lbl_style = (
            f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 400; background: transparent; border: none;"
        )
        _input_style = (
            f"QLineEdit {{ background-color: {Colors.BG_INPUT}; color: {Colors.TEXT_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 9px 12px;"
            " font-size: 9pt; font-weight: 500; }"
            f"QLineEdit:focus {{ border: 2px solid {Colors.ACCENT}; }}"
        )
        _combo_style = (
            f"QComboBox {{ background-color: {Colors.BG_INPUT}; color: {Colors.TEXT_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 8px 12px;"
            " font-size: 9pt; font-weight: 600; }"
            f"QComboBox:focus {{ border: 2px solid {Colors.ACCENT}; }}"
            "QComboBox::drop-down { border: none; width: 28px; }"
            f"QComboBox QAbstractItemView {{ background-color: {Colors.BG_ELEVATED};"
            f" color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER};"
            f" selection-background-color: {Colors.ACCENT_DARK}; }}"
        )
        _primary_btn_style = (
            f"QPushButton {{ background-color: {Colors.ACCENT}; color: {Colors.BG_DARK};"
            " border: none; border-radius: 8px; padding: 8px 16px; font-size: 9pt; font-weight: 800; }"
            f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_LIGHT};"
            f" border: 2px solid {Colors.TEXT_PRIMARY}; }}"
            f"QPushButton:pressed {{ background-color: {Colors.ACCENT_DARK}; }}"
            f"QPushButton:disabled {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_MUTED}; }}"
        )
        _ghost_btn_style = (
            f"QPushButton {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 8px 14px;"
            " font-size: 9pt; font-weight: 650; }"
            f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" border: 2px solid {Colors.ACCENT}; }}"
            f"QPushButton:disabled {{ background-color: {Colors.BG_CARD}; color: {Colors.TEXT_MUTED}; }}"
        )
        _contact_btn_style = (
            f"QPushButton {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 8px 16px;"
            " font-size: 9pt; font-weight: 700; }"
            f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" border: 2px solid {Colors.ACCENT}; }}"
        )

        self._settings_tab_bar = QTabBar(page)
        self._settings_tab_bar.setObjectName("settingsTabBar")
        self._settings_tab_bar.setGeometry(24, cy, 952, 44)
        self._settings_tab_bar.setDrawBase(False)
        self._settings_tab_bar.setExpanding(True)
        self._settings_tab_bar.setUsesScrollButtons(False)
        self._settings_tab_bar.setAccessibleName("설정 카테고리")
        for tab_label in ("업로드 · 글쓰기", "계정 · 연결", "AI · 앱", "구독 · 지원"):
            self._settings_tab_bar.addTab(tab_label)
        self._settings_tab_bar.setStyleSheet(
            "QTabBar {"
            " background: transparent;"
            " border: none;"
            "}"
            "QTabBar::tab {"
            f" background-color: {Colors.BG_CARD};"
            f" color: {Colors.TEXT_MUTED};"
            f" border: 1px solid {Colors.BORDER};"
            " border-bottom: 2px solid transparent;"
            " padding: 10px 16px;"
            " margin-right: 6px;"
            " min-height: 20px;"
            " font-size: 9pt;"
            " font-weight: 700;"
            "}"
            "QTabBar::tab:first {"
            " border-top-left-radius: 8px;"
            " border-bottom-left-radius: 8px;"
            "}"
            "QTabBar::tab:last {"
            " border-top-right-radius: 8px;"
            " border-bottom-right-radius: 8px;"
            " margin-right: 0px;"
            "}"
            "QTabBar::tab:hover {"
            f" color: {Colors.TEXT_PRIMARY};"
            f" background-color: {Colors.BG_ELEVATED};"
            "}"
            "QTabBar::tab:selected {"
            f" color: {Colors.ACCENT_LIGHT};"
            f" background-color: {Colors.ACCENT_SUBTLE};"
            f" border-color: {Colors.ACCENT_DARK};"
            f" border-bottom-color: {Colors.ACCENT};"
            "}"
            "QTabBar::tab:focus {"
            f" border-color: {Colors.ACCENT};"
            "}"
        )

        self._settings_help_panel = InlineHelpPanel(
            "설정 도움말",
            "업로드 간격, 영상 우선순위와 글 작성 방식을 이 화면에서 한 번만 저장합니다.",
            page,
        )
        self._settings_help_panel.setVisible(False)
        self._inline_help_panels[1] = self._settings_help_panel

        # Scroll area for the selected settings category
        scroll = QScrollArea(page)
        scroll.setGeometry(0, cy + 56, CONTENT_W, CONTENT_H - cy - 116)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BG_DARK}; border: none; }}"
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
        scroll.viewport().setStyleSheet(f"background-color: {Colors.BG_DARK}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background-color: {Colors.BG_DARK};")
        content.setFixedWidth(CONTENT_W)
        scroll.setWidget(content)
        self._settings_scroll = scroll

        sy = 12

        # ── Section 1: 계정 정보 ───────────────────────────
        acct = QFrame(content)
        acct.setGeometry(24, sy, 952, 104)
        acct.setFrameShape(QFrame.Shape.NoFrame)
        acct.setStyleSheet(_section_style)
        self._settings_account_sec = acct

        acct_icon = QLabel("U", acct)
        acct_icon.setGeometry(20, 26, 40, 40)
        acct_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acct_icon.setStyleSheet(
            "QLabel {"
            f" background: {Gradients.ACCENT_BTN};"
            f" color: {Colors.BG_DARK};"
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
        threads_sec.setGeometry(24, sy, 952, 300)
        threads_sec.setFrameShape(QFrame.Shape.NoFrame)
        threads_sec.setStyleSheet(_section_style)
        self._settings_threads_sec = threads_sec

        threads_title = QLabel("Threads 계정", threads_sec)
        threads_title.setGeometry(24, 14, 220, 24)
        threads_title.setStyleSheet(_section_title_style)

        name_label = QLabel("계정 이름", threads_sec)
        name_label.setGeometry(24, 46, 100, 20)
        name_label.setStyleSheet(_field_lbl_style)

        name_hint = QLabel("프로필 식별용", threads_sec)
        name_hint.setGeometry(124, 46, 220, 20)
        name_hint.setStyleSheet(_hint_lbl_style)

        self.threads_account_combo = QComboBox(threads_sec)
        self.threads_account_combo.setGeometry(24, 70, 430, _control_h)
        self.threads_account_combo.currentIndexChanged.connect(self._on_threads_account_selected)

        self.threads_account_add_btn = QPushButton("계정 추가", threads_sec)
        self.threads_account_add_btn.setGeometry(466, 70, 140, _control_h)
        self.threads_account_add_btn.clicked.connect(self._add_threads_account_from_ui)
        self.threads_account_remove_btn = QPushButton("계정 삭제", threads_sec)
        self.threads_account_remove_btn.setGeometry(618, 70, 140, _control_h)
        self.threads_account_remove_btn.clicked.connect(self._remove_selected_threads_account)

        self.username_edit = QLineEdit(threads_sec)
        self.username_edit.setGeometry(24, 122, 904, _control_h)
        self.username_edit.setPlaceholderText("예: myaccount")
        self.username_edit.setStyleSheet(_input_style)

        self._threads_status_dot = QLabel("", threads_sec)
        self._threads_status_dot.setGeometry(24, 174, 10, 10)
        self._threads_status_dot.setStyleSheet("background-color: #9CA3AF; border-radius: 5px;")

        self.login_status_label = QLabel("연결 안됨", threads_sec)
        self.login_status_label.setGeometry(42, 170, 320, 22)
        self.login_status_label.setStyleSheet(
            "color: #9CA3AF; font-size: 11px; font-weight: 500; background: transparent; border: none;"
        )

        self.threads_login_btn = QPushButton("Threads 로그인", threads_sec)
        self.threads_login_btn.setGeometry(576, 198, 170, _control_h)
        self.threads_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)

        self.check_login_btn = QPushButton("로그인 상태 확인", threads_sec)
        self.check_login_btn.setGeometry(758, 198, 170, _control_h)
        self.check_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_login_btn.clicked.connect(self._check_login_status)

        hint_text = (
            "1) Threads 로그인 버튼을 누르세요.\n"
            "2) 열린 브라우저에서 로그인 완료 후 창을 닫으세요.\n"
            "3) 닫으면 세션이 자동 저장되어 다음 작업에서 바로 사용됩니다."
        )
        self._threads_hint_label = QLabel(hint_text, threads_sec)
        self._threads_hint_label.setGeometry(24, 242, 904, 46)
        self._threads_hint_label.setWordWrap(True)
        self._threads_hint_label.setStyleSheet(_hint_lbl_style)

        sy += 314

        # ── Upload + writing: one source of truth ───────────
        concept_sec = QFrame(content)
        concept_sec.setGeometry(24, sy, 952, 238)
        concept_sec.setFrameShape(QFrame.Shape.NoFrame)
        concept_sec.setStyleSheet(_section_style)
        self._settings_automation_sec = concept_sec
        self._settings_concept_sec = concept_sec

        concept_title = QLabel("업로드 · 글쓰기", concept_sec)
        concept_title.setGeometry(24, 14, 220, 24)
        concept_title.setStyleSheet(_section_title_style)

        interval_label = QLabel("업로드 간격", concept_sec)
        interval_label.setGeometry(24, 48, 140, 20)
        interval_label.setStyleSheet(_field_lbl_style)

        interval_hint = QLabel("상품 사이 대기 시간 · 최소 30초", concept_sec)
        interval_hint.setGeometry(164, 48, 320, 20)
        interval_hint.setStyleSheet(_hint_lbl_style)

        self.hour_spin = QSpinBox(concept_sec)
        self.hour_spin.setGeometry(24, 72, 112, _control_h)
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" 시간")
        self.hour_spin.setAccessibleName("업로드 간격 시간")

        self.min_spin = QSpinBox(concept_sec)
        self.min_spin.setGeometry(148, 72, 104, _control_h)
        self.min_spin.setRange(0, 59)
        self.min_spin.setSuffix(" 분")
        self.min_spin.setAccessibleName("업로드 간격 분")

        self.sec_spin = QSpinBox(concept_sec)
        self.sec_spin.setGeometry(264, 72, 104, _control_h)
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setSuffix(" 초")
        self.sec_spin.setAccessibleName("업로드 간격 초")

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선", concept_sec)
        self.video_check.setGeometry(404, 80, 300, 24)
        self.video_check.setToolTip("상품 페이지에 영상이 있으면 이미지보다 먼저 사용합니다")

        concept_label = QLabel("본문 작성 방식", concept_sec)
        concept_label.setGeometry(24, 138, 120, 20)
        concept_label.setStyleSheet(_field_lbl_style)

        self.settings_post_concept_combo = QComboBox(concept_sec)
        self.settings_post_concept_combo.setObjectName("settingsPostConceptCombo")
        self.settings_post_concept_combo.setGeometry(24, 162, 344, _control_h)
        for concept in POST_CONCEPTS:
            self.settings_post_concept_combo.addItem(concept.display_label, concept.id)
        self.settings_post_concept_combo.setStyleSheet(_combo_style)
        self.settings_post_concept_combo.setAccessibleName("글 작성 방식")

        self._concept_desc = QLabel(
            "본문 1개를 자동 생성하고 상품·링크는 바로 아래 상품 댓글에 고정합니다. 2번은 현재 이슈와 상품을 연결합니다.",
            concept_sec,
        )
        self._concept_desc.setGeometry(392, 166, 520, 42)
        self._concept_desc.setWordWrap(True)
        self._concept_desc.setStyleSheet(_hint_lbl_style)

        sy += 262

        # ── Section 4: AI 글 생성 설정 ─────────────────────
        self._settings_content = content
        self._settings_flow_start_y = sy
        self._settings_gap = 24
        self._settings_section_x = 24
        self._settings_section_w = 952

        self._settings_api_sec = QFrame(content)
        self._settings_api_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_api_sec.setStyleSheet(_section_style)

        self._settings_api_title = QLabel("AI 글 생성 설정", self._settings_api_sec)
        self._settings_api_title.setGeometry(24, 14, 220, 24)
        self._settings_api_title.setStyleSheet(_section_title_style)

        self._ai_provider_label = QLabel("사용할 AI", self._settings_api_sec)
        self._ai_provider_label.setGeometry(24, 48, 120, 20)
        self._ai_provider_label.setStyleSheet(_field_lbl_style)

        self._ai_provider_combo = QComboBox(self._settings_api_sec)
        self._ai_provider_combo.setObjectName("aiProviderCombo")
        self._ai_provider_combo.setGeometry(24, 72, 320, _control_h)
        self._ai_provider_combo.addItem("AI 자동 작성 (구독 포함)", AI_PROVIDER_MANAGED)
        if str(os.getenv("THREAD_AUTO_ALLOW_LOCAL_AI_PROVIDERS", "")).strip().lower() in {
            "1", "true", "yes", "on"
        }:
            self._ai_provider_combo.addItem("Grok CLI (개발용)", AI_PROVIDER_GROK_CLI)
        self._ai_provider_combo.setStyleSheet(_combo_style)

        self._ai_provider_hint = QLabel(
            "별도 API 키 없이 로그인과 구독만으로 자동 작성됩니다.",
            self._settings_api_sec,
        )
        self._ai_provider_hint.setGeometry(368, 82, 540, 20)
        self._ai_provider_hint.setStyleSheet(_hint_lbl_style)

        self._settings_api_guide = QLabel(
            '<a href="https://ssmaker.lovable.app/notice" '
            f'style="color:{Colors.ACCENT_LIGHT}; text-decoration:none;">Gemini API KEY 발급 안내 →</a>',
            self._settings_api_sec,
        )
        self._settings_api_guide.setGeometry(24, 124, 260, 20)
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
        self._settings_api_hint.setGeometry(306, 124, 596, 18)
        self._settings_api_hint.setStyleSheet(_hint_lbl_style)

        self._grok_status_label = QLabel("Grok 상태를 확인해주세요.", self._settings_api_sec)
        self._grok_status_label.setGeometry(24, 124, 500, 22)
        self._grok_status_label.setStyleSheet(
            "color: #B8B8B8; font-size: 12px; background: transparent; border: none;"
        )

        self._grok_install_btn = QPushButton("설치 안내", self._settings_api_sec)
        self._grok_install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grok_install_btn.setStyleSheet(_ghost_btn_style)
        self._grok_install_btn.clicked.connect(self._open_grok_install_guide)

        self._grok_login_btn = QPushButton("Grok 로그인", self._settings_api_sec)
        self._grok_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grok_login_btn.setStyleSheet(_ghost_btn_style)
        self._grok_login_btn.clicked.connect(self._start_grok_login)

        self._grok_check_btn = QPushButton("연결 확인", self._settings_api_sec)
        self._grok_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grok_check_btn.setStyleSheet(_ghost_btn_style)
        self._grok_check_btn.clicked.connect(self._refresh_grok_status)

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
            edit.setAccessibleName(f"Gemini API 키 {index + 1}")
            edit.setStyleSheet(_input_style)

            toggle = QPushButton("보기", self._settings_api_sec)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setCheckable(True)
            toggle.setAccessibleName(f"Gemini API 키 {index + 1} 표시")
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
        self._ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)

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

        # ── Section 5: 이용권 · 결제 ───────────────────────
        self._settings_payment_sec = QFrame(content)
        self._settings_payment_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_payment_sec.setStyleSheet(_section_style)

        payment_title = QLabel("이용권 선택", self._settings_payment_sec)
        payment_title.setGeometry(24, 14, 220, 22)
        payment_title.setStyleSheet(_section_title_style)

        payment_desc = QLabel(
            "쿠팡 기본 또는 네이버쇼핑·토스쇼핑·AliExpress까지 지원하는 쇼핑 프로를 선택하세요.",
            self._settings_payment_sec,
        )
        payment_desc.setGeometry(24, 40, 880, 20)
        payment_desc.setStyleSheet("color: #B8B8B8; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        self._payment_desc = payment_desc

        self._shopping_offer_label = QLabel(
            "무료 첫 작업에서 쇼핑 프로를 체험할 수 있습니다.",
            self._settings_payment_sec,
        )
        self._shopping_offer_label.setGeometry(24, 66, 880, 30)
        self._shopping_offer_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._shopping_offer_label.setStyleSheet(
            f"QLabel {{ background-color: {Colors.ACCENT_SUBTLE}; color: {Colors.ACCENT_LIGHT};"
            f" border: 1px solid {Colors.ACCENT_DARK}; border-radius: 7px;"
            " padding: 0 12px; font-size: 11px; font-weight: 700; }"
        )

        phone_label = QLabel("결제 휴대폰 번호", self._settings_payment_sec)
        phone_label.setGeometry(24, 106, 150, 18)
        phone_label.setStyleSheet(_hint_lbl_style)
        self._payment_phone_label = phone_label

        self._pay_phone_edit = QLineEdit(self._settings_payment_sec)
        self._pay_phone_edit.setGeometry(24, 128, 250, _control_h)
        self._pay_phone_edit.setPlaceholderText("01012345678")
        self._pay_phone_edit.setStyleSheet(_input_style)
        self._pay_phone_edit.setMaxLength(11)
        self._pay_phone_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"01[016789]?\d{0,8}"), self._pay_phone_edit)
        )
        self._pay_phone_edit.setAccessibleName("결제 휴대폰 번호")
        self._pay_phone_edit.setAccessibleDescription("PayApp 결제창을 받을 본인 휴대폰 번호")
        phone_label.setBuddy(self._pay_phone_edit)

        basic_label = QLabel("쿠팡 기본", self._settings_payment_sec)
        basic_label.setGeometry(296, 106, 300, 18)
        basic_label.setStyleSheet("color: #D1D5DB; font-size: 11px; font-weight: 800;")
        self._payment_basic_label = basic_label

        pro_label = QLabel("쇼핑 프로 · 전체 쇼핑몰", self._settings_payment_sec)
        pro_label.setGeometry(296, 180, 320, 18)
        pro_label.setStyleSheet(f"color: {Colors.ACCENT_LIGHT}; font-size: 11px; font-weight: 800;")
        self._payment_pro_label = pro_label

        self._pay_weekly_btn = QPushButton("7일 19,000원 · Threads 1개", self._settings_payment_sec)
        self._pay_weekly_btn.setGeometry(296, 128, 306, _control_h)
        self._pay_weekly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_weekly_btn.clicked.connect(
            lambda: self._request_payapp_checkout("stmaker_pro_week")
        )

        self._pay_monthly_btn = QPushButton("월 49,000원 · Threads 10개", self._settings_payment_sec)
        self._pay_monthly_btn.setGeometry(614, 128, 306, _control_h)
        self._pay_monthly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_monthly_btn.clicked.connect(
            lambda: self._request_payapp_checkout("stmaker_pro_month")
        )

        self._pay_shopping_weekly_btn = QPushButton(
            "7일 29,000원 · Threads 3개",
            self._settings_payment_sec,
        )
        self._pay_shopping_weekly_btn.setGeometry(296, 202, 306, _control_h)
        self._pay_shopping_weekly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_shopping_weekly_btn.clicked.connect(
            lambda: self._request_payapp_checkout("stmaker_shopping_pro_week")
        )

        self._pay_shopping_monthly_btn = QPushButton(
            "월 69,000원 · Threads 10개",
            self._settings_payment_sec,
        )
        self._pay_shopping_monthly_btn.setGeometry(614, 202, 306, _control_h)
        self._pay_shopping_monthly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_shopping_monthly_btn.clicked.connect(
            lambda: self._request_payapp_checkout(self._shopping_pro_month_plan_id())
        )

        for button, accessible_name in (
            (self._pay_weekly_btn, "7일 쿠팡 이용권 결제"),
            (self._pay_monthly_btn, "월간 쿠팡 기본 이용권 결제"),
            (self._pay_shopping_weekly_btn, "7일 쇼핑 프로 이용권 결제"),
            (self._pay_shopping_monthly_btn, "월간 쇼핑 프로 이용권 결제"),
        ):
            button.setAccessibleName(accessible_name)

        self._pay_hint_label = QLabel(
            "7일권은 일회결제, 월간은 30일마다 정기결제됩니다. 쇼핑 프로는 쿠팡·네이버·토스·Ali 링크를 지원합니다.",
            self._settings_payment_sec,
        )
        self._pay_hint_label.setGeometry(24, 258, 900, 20)
        self._pay_hint_label.setStyleSheet(_hint_lbl_style)

        self._pay_status_label = QLabel("이용권을 선택하면 PayApp 보안 결제창이 열립니다.", self._settings_payment_sec)
        self._pay_status_label.setGeometry(24, 284, 900, 24)
        self._pay_status_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        self._pay_status_label.setAccessibleName("결제 진행 상태")

        self._pay_cancel_btn = QPushButton("월 정기결제 해지", self._settings_payment_sec)
        self._pay_cancel_btn.setGeometry(24, 316, 190, _control_h)
        self._pay_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_cancel_btn.clicked.connect(self._cancel_payapp_subscription)

        self._pay_refresh_btn = QPushButton("결제 상태 새로고침", self._settings_payment_sec)
        self._pay_refresh_btn.setGeometry(226, 316, 190, _control_h)
        self._pay_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pay_refresh_btn.clicked.connect(self._send_heartbeat)

        # ── Section 6: 실행 설정 ────────────────────────────
        self._settings_startup_sec = QFrame(content)
        self._settings_startup_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_startup_sec.setStyleSheet(_section_style)

        startup_title = QLabel("실행 설정", self._settings_startup_sec)
        startup_title.setGeometry(24, 14, 200, 22)
        startup_title.setStyleSheet(_section_title_style)

        self._auto_start_check = QCheckBox("Windows 시작 시 자동 실행", self._settings_startup_sec)
        self._auto_start_check.setGeometry(24, 44, 260, 24)

        startup_desc = QLabel("컴퓨터가 꺼졌다 켜져도 로그인 후 프로그램을 다시 실행합니다.", self._settings_startup_sec)
        startup_desc.setGeometry(304, 46, 560, 20)
        startup_desc.setStyleSheet(_hint_lbl_style)
        self._startup_desc = startup_desc

        # ── Section 7: contextual help ────────────────────
        self._settings_tutorial_sec = QFrame(content)
        self._settings_tutorial_sec.setFrameShape(QFrame.Shape.NoFrame)
        self._settings_tutorial_sec.setStyleSheet(_section_style)

        tutorial_title = QLabel("화면 도움말", self._settings_tutorial_sec)
        tutorial_title.setGeometry(24, 14, 200, 22)
        tutorial_title.setStyleSheet(_section_title_style)

        self._tutorial_settings_btn = QPushButton("현재 화면에서 도움말 보기", self._settings_tutorial_sec)
        self._tutorial_settings_btn.setGeometry(24, 40, _action_btn_w, _control_h)
        self._tutorial_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutorial_settings_btn.clicked.connect(self.open_tutorial)

        # ── Section 8: 문의하기 ────────────────────────────
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
        self._contact_desc = contact_desc

        # ── Action Buttons Row ─────────────────────────────
        self._settings_save_btn = QPushButton("설정 저장", page)
        self._settings_save_btn.setGeometry(816, CONTENT_H - 52, 160, 40)
        self._settings_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_save_btn.clicked.connect(self._save_settings)

        self.threads_login_btn.setStyleSheet(_primary_btn_style)
        self._pay_weekly_btn.setStyleSheet(_ghost_btn_style)
        self._pay_monthly_btn.setStyleSheet(_ghost_btn_style)
        self._pay_shopping_weekly_btn.setStyleSheet(_ghost_btn_style)
        self._pay_shopping_monthly_btn.setStyleSheet(_primary_btn_style)
        self._pay_cancel_btn.setStyleSheet(_ghost_btn_style)
        self._pay_refresh_btn.setStyleSheet(_ghost_btn_style)
        self._settings_save_btn.setStyleSheet(_primary_btn_style)
        self.check_login_btn.setStyleSheet(_ghost_btn_style)
        self._add_gemini_key_btn.setStyleSheet(_ghost_btn_style)
        self._tutorial_settings_btn.setStyleSheet(_ghost_btn_style)
        self._contact_btn.setStyleSheet(_contact_btn_style)

        for btn in (
            self.threads_login_btn,
            self.check_login_btn,
            self._pay_weekly_btn,
            self._pay_monthly_btn,
            self._pay_shopping_weekly_btn,
            self._pay_shopping_monthly_btn,
            self._pay_cancel_btn,
            self._pay_refresh_btn,
            self._tutorial_settings_btn,
            self._contact_btn,
            self._add_gemini_key_btn,
            self._settings_save_btn,
        ):
            btn.setFixedHeight(_control_h)

        self._visible_gemini_key_rows = 1
        self._settings_scroll_positions = {}
        self._settings_active_tab = 0
        self._set_visible_gemini_key_rows(1)
        self._settings_tab_bar.currentChanged.connect(self._on_settings_tab_changed)
        self._settings_tab_bar.setCurrentIndex(0)
        self._relayout_settings_sections()

    # ── StatusBar ───────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = QFrame(parent)
        bar.setGeometry(0, WIN_H - STATUSBAR_H, WIN_W, STATUSBAR_H)
        bar.setStyleSheet(
            f"QFrame {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {Colors.BG_SIDEBAR}, stop:0.5 {Colors.BG_ELEVATED}, stop:1 {Colors.BG_SIDEBAR});"
            f"  border-top: 1px solid {Colors.BORDER};"
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

    def _relayout_main_window(self):
        """Fit the workspace to the current logical window size and DPI."""
        central = self.centralWidget()
        if central is None:
            return
        width = max(1, central.width())
        height = max(1, central.height())
        sidebar_w = 240 if width >= 1180 else 210 if width >= 980 else 190
        page_w = max(1, width - sidebar_w)
        page_h = max(1, height - HEADER_H - STATUSBAR_H)

        self._header.setGeometry(0, 0, width, HEADER_H)
        self._sidebar.setGeometry(0, HEADER_H, sidebar_w, page_h)
        for page in self._pages:
            page.setGeometry(sidebar_w, HEADER_H, page_w, page_h)
        self._status_bar_frame.setGeometry(0, height - STATUSBAR_H, width, STATUSBAR_H)
        self._server_label.setGeometry(max(320, width - 410), 6, 200, 20)
        self.progress_label.setGeometry(max(520, width - 200), 6, 184, 20)
        self.status_label.setGeometry(34, 6, max(200, width - 460), 20)

        self._relayout_header_account_card()
        self._relayout_sidebar(sidebar_w, page_h)
        self._relayout_link_page(page_w, page_h)
        self._relayout_settings_page(page_w, page_h)

    def _relayout_sidebar(self, width, height):
        for index, button in enumerate(self._sidebar_buttons):
            button.setGeometry(0, 20 + index * 48, width, 44)
        for divider in (self._sidebar_divider_top, self._sidebar_divider_counts):
            divider.setGeometry(16, divider.y(), max(1, width - 32), 1)
        for label in (self._sidebar_progress_title, self._progress_queue_label,
                      self._sidebar_status_label, self._sidebar_log_title):
            label.setFixedWidth(max(80, width - label.x() - 12))
        for label in self._step_labels:
            label.setFixedWidth(max(80, width - label.x() - 12))

        columns = (
            (self._sidebar_success_dot, self._sidebar_success_label),
            (self._sidebar_failed_dot, self._sidebar_failed_label),
            (self._sidebar_total_dot, self._sidebar_total_label),
        )
        col_w = max(52, (width - 24) // 3)
        for index, (dot, label) in enumerate(columns):
            x = 12 + index * col_w
            dot.move(x, dot.y())
            label.setGeometry(x + 13, label.y(), max(38, col_w - 14), 20)
        self.log_text.setGeometry(10, self.log_text.y(), max(80, width - 20),
                                  max(52, height - self.log_text.y() - 8))

    def _relayout_link_page(self, width, height):
        page = self._pages[0]
        margin = 24 if width < 820 else 28
        inner_w = max(280, width - margin * 2)
        icon_bg, icon_label, title, sep = page._page_header_widgets
        sep.setGeometry(margin, 66, inner_w, 1)
        icon_bg.move(margin, 20)
        icon_label.move(margin, 20)
        title.move(margin + 48, 20)
        self._page_help_btn.move(max(margin, width - margin - 32), 22)
        self._coupang_link.setGeometry(max(margin, width - margin - 220), 28, 180, 24)
        self.link_count_badge.setGeometry(max(margin, width - margin - 314), 28, 88, 24)

        y = 82
        self._upload_account_tabs.setGeometry(margin, y, inner_w, 30)
        y += 38
        help_visible = bool(self._inline_help_enabled)
        self._link_help_panel.setVisible(help_visible)
        if help_visible:
            self._link_help_panel.setGeometry(margin, y, inner_w, 68)
            y += 78
        self._links_hint.setGeometry(margin, y, inner_w, 20)
        y += 24

        compact_h = height < 610
        links_h = 92 if compact_h else 138 if height < 730 else 160
        self.links_text.setGeometry(margin, y, inner_w, links_h)
        y += links_h + 12

        two_rows = inner_w < 790
        gap = 10
        if two_rows:
            first_widths = (max(160, int(inner_w * .42)), max(100, int(inner_w * .25)))
            stop_w = max(90, inner_w - first_widths[0] - first_widths[1] - gap * 2)
            self.start_btn.setGeometry(margin, y, first_widths[0], 42)
            self.add_btn.setGeometry(margin + first_widths[0] + gap, y, first_widths[1], 42)
            self.stop_btn.setGeometry(margin + first_widths[0] + first_widths[1] + gap * 2, y, stop_w, 42)
            row2_y = y + 50
            all_w = (inner_w - gap) // 2
            self.start_all_btn.setGeometry(margin, row2_y, all_w, 42)
            self.stop_all_btn.setGeometry(margin + all_w + gap, row2_y, inner_w - all_w - gap, 42)
            y = row2_y + 52
        else:
            widths = (240, 150, 112, 160)
            used = sum(widths) + gap * 4
            final_w = max(150, inner_w - used)
            x = margin
            for button, button_w in zip(
                (self.start_btn, self.add_btn, self.stop_btn, self.start_all_btn, self.stop_all_btn),
                (*widths, final_w),
            ):
                button.setGeometry(x, y, button_w, 44)
                x += button_w + gap
            y += 56

        state_h = 66 if compact_h else 76
        self._run_state_frame.setGeometry(margin, y, inner_w, state_h)
        split = max(240, inner_w // 2)
        self._run_state_main.setGeometry(18, 34, max(160, split - 28), 22)
        self._run_state_detail.setGeometry(split, 10, max(120, inner_w - split - 18), 20)
        self._run_state_next.setGeometry(split, 36, max(120, inner_w - split - 18), 20)
        y += state_h + 10
        self._link_table_label.setGeometry(margin, y, 180, 20)
        y += 24
        self.link_table.setGeometry(margin, y, inner_w, max(42, height - y - 12))

    def _relayout_settings_page(self, width, height):
        page = self._pages[1]
        margin = 24
        inner_w = max(320, width - margin * 2)
        icon_bg, icon_label, title, sep = page._page_header_widgets
        sep.setGeometry(margin, 66, inner_w, 1)
        icon_bg.move(margin, 20)
        icon_label.move(margin, 20)
        title.move(margin + 48, 20)
        self._settings_tab_bar.setGeometry(margin, 82, inner_w, 44)
        y = 136
        help_visible = bool(self._inline_help_enabled)
        self._settings_help_panel.setVisible(help_visible)
        if help_visible:
            self._settings_help_panel.setGeometry(margin, y, inner_w, 68)
            y += 76
        footer_h = 58
        self._settings_scroll.setGeometry(0, y, width, max(80, height - y - footer_h))
        self._settings_content.setFixedWidth(width)
        self._settings_section_w = inner_w
        self._settings_section_x = margin
        self._settings_save_btn.setGeometry(max(margin, width - margin - 172), height - 50, 172, 40)
        self._relayout_settings_sections()
        self._relayout_settings_section_contents(inner_w)

    def _relayout_settings_section_contents(self, width):
        """Keep the settings controls within their cards on narrow screens."""
        content_w = max(200, width - 48)
        self.username_edit.setFixedWidth(content_w)
        self._threads_hint_label.setFixedWidth(content_w)
        combo_w = max(220, min(430, content_w - 304))
        self.threads_account_combo.setFixedWidth(combo_w)
        self.threads_account_add_btn.move(24 + combo_w + 12, 70)
        self.threads_account_remove_btn.move(24 + combo_w + 164, 70)
        right_btn_x = max(24, width - 376)
        self.threads_login_btn.move(right_btn_x, 198)
        self.check_login_btn.move(right_btn_x + 182, 198)
        self._acct_plan_badge.move(max(24, width - 184), 24)
        self._acct_work_label.move(max(24, width - 184), 58)

        if width < 760:
            self.video_check.setGeometry(24, 122, content_w, 24)
            self.settings_post_concept_combo.setGeometry(24, 178, min(344, content_w), 40)
            self._concept_desc.setGeometry(24, 224, content_w, 42)
        else:
            self.video_check.setGeometry(404, 80, min(300, width - 428), 24)
            self.settings_post_concept_combo.setGeometry(24, 162, 344, 40)
            self._concept_desc.setGeometry(392, 166, max(180, width - 416), 42)

        self._ai_provider_hint.setGeometry(368, 82, max(180, width - 392), 20)
        self._settings_api_hint.setGeometry(306, 124, max(180, width - 330), 18)
        self._pay_hint_label.setFixedWidth(content_w)
        self._pay_status_label.setFixedWidth(content_w)
        self._payment_desc.setFixedWidth(content_w)
        self._shopping_offer_label.setFixedWidth(content_w)
        self._startup_desc.setGeometry(304, 46, max(180, width - 328), 20)
        self._contact_desc.setGeometry(236, 50, max(160, width - 260), 20)

        if width < 760:
            button_w = max(150, (content_w - 12) // 2)
            self._pay_phone_edit.setGeometry(24, 128, min(250, content_w), 40)
            self._payment_basic_label.setGeometry(24, 184, content_w, 18)
            self._pay_weekly_btn.setGeometry(24, 206, button_w, 40)
            self._pay_monthly_btn.setGeometry(36 + button_w, 206, content_w - button_w - 12, 40)
            self._payment_pro_label.setGeometry(24, 260, content_w, 18)
            self._pay_shopping_weekly_btn.setGeometry(24, 282, button_w, 40)
            self._pay_shopping_monthly_btn.setGeometry(36 + button_w, 282, content_w - button_w - 12, 40)
            self._pay_hint_label.setGeometry(24, 330, content_w, 20)
            self._pay_status_label.setGeometry(24, 354, content_w, 24)
            self._pay_cancel_btn.setGeometry(24, 386, min(190, button_w), 40)
            self._pay_refresh_btn.setGeometry(226, 386, min(190, max(120, content_w - 202)), 40)
        else:
            self._payment_basic_label.move(296, 106)
            self._pay_weekly_btn.setGeometry(296, 128, 306, 40)
            self._pay_monthly_btn.setGeometry(614, 128, 306, 40)
            self._payment_pro_label.move(296, 180)
            self._pay_shopping_weekly_btn.setGeometry(296, 202, 306, 40)
            self._pay_shopping_monthly_btn.setGeometry(614, 202, 306, 40)
            self._pay_hint_label.setGeometry(24, 258, content_w, 20)
            self._pay_status_label.setGeometry(24, 284, content_w, 24)
            self._pay_cancel_btn.setGeometry(24, 316, 190, 40)
            self._pay_refresh_btn.setGeometry(226, 316, 190, 40)

    def toggle_inline_help(self, checked=None):
        """Toggle contextual guidance inside the current page."""
        enabled = (not self._inline_help_enabled) if checked is None else bool(checked)
        self._inline_help_enabled = enabled
        for button in (getattr(self, "tutorial_btn", None), getattr(self, "_page_help_btn", None)):
            if button is not None and button.isChecked() != enabled:
                blocked = button.blockSignals(True)
                button.setChecked(enabled)
                button.blockSignals(blocked)
        self._relayout_main_window()
        self._log_user_activity("inline_help_toggled", f"enabled={enabled}; page={self._current_page}")

    # ────────────────────────────────────────────────────────
    #  PAGE SWITCHING
    # ────────────────────────────────────────────────────────

    def _switch_page(self, index, source="programmatic"):
        """Show selected page, hide others. Also sync sidebar button."""
        try:
            index = int(index)
        except Exception:
            return
        if not 0 <= index < len(self._pages):
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
        self._relayout_main_window()

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
                "중복": Colors.TEXT_MUTED,
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
        elif any(kw in lower_msg for kw in ("wait", "waiting", "대기")):
            color = Colors.TEXT_SECONDARY
            tag = "상태"
            tag_color = Colors.INFO
        elif any(kw in lower_msg for kw in ("warn", "warning", "경고", "주의")):
            color = Colors.WARNING
            tag = "경고"
            tag_color = Colors.WARNING
        elif any(kw in lower_msg for kw in ("running", "start", "progress", "processing", "시작", "진행", "처리")):
            color = Colors.TEXT_SECONDARY
            tag = "진행"
            tag_color = Colors.INFO

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

    @staticmethod
    def _safe_int(value, default=0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_clock(value) -> str:
        timestamp = MainWindow._safe_float(value)
        if timestamp is None or timestamp <= 0:
            return "--"
        try:
            return datetime.fromtimestamp(timestamp).astimezone().strftime("%H:%M:%S")
        except Exception:
            return "--"

    def _set_run_state(self, state: dict):
        payload = dict(state or {})
        self._latest_run_state = payload

        phase = str(payload.get("phase") or "idle")
        message = str(payload.get("message") or "").strip()
        current_item = str(payload.get("current_item") or "").strip()
        pending = self._safe_int(payload.get("pending"), 0)
        total = self._safe_int(payload.get("total"), pending)
        completed = self._safe_int(payload.get("completed"), max(total - pending, 0))
        failed = self._safe_int(payload.get("failed"), 0)
        next_allowed_at = payload.get("next_allowed_at")
        remaining = self._safe_int(payload.get("remaining"), 0)
        if remaining <= 0:
            next_timestamp = self._safe_float(next_allowed_at)
            if next_timestamp:
                remaining = max(0, int(next_timestamp - time.time()))

        if phase == "waiting":
            title = "예약 대기 중"
            main = f"다음 업로드까지 {_format_interval(remaining)}"
            detail = f"남은 작업 {pending}개"
            color = Colors.INFO
            bg = Colors.INFO_BG
            sidebar_status = f"예약 대기 · {pending}개 남음"
            progress_text = f"다음 {self._format_clock(next_allowed_at)}"
        elif phase in {"processing", "uploading"}:
            title = "현재 업로드 중"
            main = current_item[:42] if current_item else (message or "항목 처리 중")
            detail = message or f"대기열 {pending}개 남음"
            color = Colors.WARNING
            bg = Colors.WARNING_BG
            sidebar_status = f"처리 중 · {pending}개 남음"
            progress_text = "업로드 중"
        elif phase == "running":
            title = "자동화 실행 중"
            main = message or f"대기열 {pending}개 준비"
            detail = f"총 {total}개 · 4시간 간격"
            color = Colors.WARNING
            bg = Colors.WARNING_BG
            sidebar_status = f"실행중 · {pending}개 대기"
            progress_text = "실행중"
        elif phase == "finished":
            title = "작업 완료"
            main = message or "대기열 작업이 종료되었습니다."
            detail = f"성공 {completed} · 실패 {failed}"
            color = Colors.SUCCESS
            bg = Colors.SUCCESS_BG
            sidebar_status = "완료"
            progress_text = "완료"
        elif phase in {"blocked", "error"}:
            title = "확인 필요"
            main = message or "자동화가 멈췄습니다."
            detail = current_item[:48] if current_item else "로그를 확인하세요"
            color = Colors.ERROR
            bg = Colors.ERROR_BG
            sidebar_status = "확인 필요"
            progress_text = "확인 필요"
        else:
            title = "자동화 대기"
            main = message or "아직 실행 중인 대기열이 없습니다."
            detail = "링크를 넣고 자동화 시작을 누르면 현재 상태가 여기에 표시됩니다."
            color = Colors.INFO
            bg = Colors.INFO_BG
            sidebar_status = "대기중"
            progress_text = ""

        next_text = "다음 작업: --"
        if phase == "waiting":
            next_text = f"다음 작업: {self._format_clock(next_allowed_at)} · {_format_interval(remaining)} 남음"
        elif current_item and phase in {"processing", "uploading"}:
            next_text = f"현재 항목: {current_item[:52]}"
        elif pending:
            next_text = f"남은 작업: {pending}개"

        self._run_state_frame.setStyleSheet(
            f"QFrame#runStateFrame {{"
            f"  background-color: {bg};"
            f"  border: none;"
            f"  border-radius: {Radius.LG};"
            f"}}"
        )
        self._run_state_title.setText(title)
        self._run_state_title.setStyleSheet(
            f"color: {color}; font-size: 9pt; font-weight: 800;"
            f" background: transparent; border: none;"
        )
        self._run_state_main.setText(main)
        self._run_state_detail.setText(detail)
        self._run_state_next.setText(next_text)

        if total or pending:
            self._progress_queue_label.setText(f"완료 {completed} / 총 {max(total, completed + pending)} · 남음 {pending}")
        self._sidebar_status_label.setText(sidebar_status)
        self.progress_label.setText(progress_text)
        self.progress_label.setVisible(bool(progress_text))
        self._statusbar_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px; border: none;"
        )

        self._log_user_activity(
            "ui_run_state",
            (
                f"phase={phase}; pending={pending}; total={total}; "
                f"next={next_allowed_at}; message={message[:120]}"
            ),
            min_interval_sec=0.5,
            dedupe_key=f"run-state:{phase}:{pending}:{remaining // 60}:{message[:40]}",
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
        # Keep accepting links after a completed/cancelled batch.  Those links
        # are persisted as pending work and can be started as the next batch.
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "준비")
        self._relayout_header_account_card()
        self._sidebar_status_label.setText("완료")
        self._reset_steps()
        self._save_resume_state("batch_finished")

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get("parse_failed", 0)
        uploaded = results.get("uploaded", 0)
        failed = results.get("failed", 0)
        skipped = results.get("skipped", 0)

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
            if skipped > 0:
                msg += f"\n  중복 스킵: {skipped}"
            show_info(self, "취소됨", msg)
        else:
            msg = (
                "업로드가 완료되었습니다.\n\n"
                f"  성공: {uploaded}\n"
                f"  실패: {failed}"
            )
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            if skipped > 0:
                msg += f"\n  중복 스킵: {skipped}"
            show_info(self, "완료", msg)

        if isinstance(self._pending_update_info, dict):
            QTimer.singleShot(300, self._maybe_show_update_notice)

    def _update_link_count(self):
        content = self.links_text.toPlainText()
        count = len(extract_supported_product_links(content))
        if count > 0:
            self.link_count_badge.update_style(Colors.ACCENT, f"{count}개 링크")
        else:
            self.link_count_badge.update_style(Colors.TEXT_MUTED, "0개 링크")

    def _extract_links(self, content: str) -> list:
        return [(url, None) for url in extract_supported_product_links(content)]

    def _normalize_link_data(self, link_data) -> list:
        normalized = []
        seen = set()
        for item in link_data or []:
            if isinstance(item, tuple):
                url = str(item[0] or "").strip()
                keyword = str(item[1] or "").strip() or None
            elif isinstance(item, dict):
                url = str(item.get("url") or "").strip()
                keyword = str(item.get("keyword") or item.get("title") or "").strip() or None
            else:
                url = str(item or "").strip()
                keyword = None
            if not url or url in seen:
                continue
            if marketplace_for_url(url) is None:
                logger.warning("지원하지 않는 상품 링크를 건너뜁니다: %s", url[:80])
                continue
            seen.add(url)
            normalized.append((url, keyword))
        return normalized

    def _ensure_marketplace_links_allowed(self, link_data) -> bool:
        """Fail closed when the server entitlement does not cover a marketplace."""
        try:
            from src import auth_client
            from src.subscription_plans import marketplace_access_decision

            state = auth_client.get_auth_state()
        except Exception:
            logger.exception("쇼핑몰 이용권 상태를 확인하지 못했습니다.")
            show_warning(self, "이용권 확인", "쇼핑몰 이용권 상태를 확인하지 못했습니다.")
            return False

        for item in link_data or []:
            url = str(item[0] if isinstance(item, tuple) else item or "").strip()
            marketplace = marketplace_for_url(url)
            allowed, message = marketplace_access_decision(state, url)
            if allowed:
                continue
            show_warning(
                self,
                "쇼핑 프로 이용권 필요",
                f"{message}\n\n설정 → 구독 · 지원에서 쇼핑 프로 이용권을 선택해주세요.",
            )
            self.open_settings()
            if hasattr(self, "_settings_tab_bar"):
                self._settings_tab_bar.setCurrentIndex(3)
            self._log_user_activity(
                "marketplace_access_blocked",
                (
                    f"marketplace={getattr(marketplace, 'marketplace_id', 'unknown')}; "
                    f"label={getattr(marketplace, 'label', 'unknown')}"
                ),
                level="WARNING",
            )
            return False
        return True

    @staticmethod
    def _is_resume_unfinished(status: str) -> bool:
        return str(status or "").lower() in {
            "pending",
            "running",
            "posting",
            "posting_unknown",
            "posted_commit_pending",
        }

    def _load_resume_state_file(self) -> dict:
        try:
            if not self._resume_state_path.exists():
                return {}
            with self._resume_state_path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            logger.exception("저장된 업로드 대기열을 불러오지 못했습니다.")
            return {}

    def _resume_pending_link_data(self, state: dict) -> list:
        items = state.get("items", []) if isinstance(state, dict) else []
        pending = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").lower() not in {"pending", "running"}:
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            keyword = str(item.get("keyword") or item.get("title") or "").strip() or None
            request_id = str(item.get("idempotency_key") or "").strip()
            if request_id:
                recovered = getattr(self, "_resume_recovered_idempotency_keys", None)
                if recovered is None:
                    recovered = self._resume_recovered_idempotency_keys = {}
                recovered[url] = request_id
            pending.append((url, keyword))
        return self._normalize_link_data(pending)

    def _reconcile_posted_commit_items(self, state: dict) -> dict:
        """Retry quota commits for posts that already succeeded externally."""
        items = state.get("items", []) if isinstance(state, dict) else []
        changed = False
        for item in items:
            if not isinstance(item, dict) or str(item.get("status") or "").lower() != "posted_commit_pending":
                continue
            reservation_id = str(item.get("reservation_id") or "").strip()
            if not reservation_id:
                item["last_error"] = "missing_reservation_id"
                continue
            try:
                from src import auth_client

                result = auth_client.commit_reserved_work(reservation_id)
            except Exception:
                logger.exception("Posted item quota commit recovery failed")
                result = {"success": False}
            if isinstance(result, dict) and self._is_work_allowed(result):
                item["status"] = "completed"
                item["updated_at"] = datetime.now().astimezone().isoformat()
                item.pop("reservation_id", None)
                item.pop("idempotency_key", None)
                item.pop("last_error", None)
                changed = True
            else:
                item["last_error"] = "quota_commit_retry_pending"

        if changed or any(
            isinstance(item, dict)
            and str(item.get("status") or "").lower() == "posted_commit_pending"
            for item in items
        ):
            with self._resume_state_lock:
                self._resume_items = [dict(item) for item in items if isinstance(item, dict)]
                self._resume_interval = max(int(state.get("interval") or 60), 30)
                self._resume_next_allowed_at = state.get("next_allowed_at")
            self._save_resume_state("posted_commit_reconcile")
        return state

    def _reconcile_ambiguous_post_items(self, state: dict) -> dict:
        """Let the user resolve an external post whose result is unknowable."""
        items = state.get("items", []) if isinstance(state, dict) else []
        changed = False
        for item in items:
            if not isinstance(item, dict) or str(item.get("status") or "").lower() not in {
                "posting",
                "posting_unknown",
            }:
                continue
            title = str(item.get("product_title") or item.get("url") or "게시글")
            choice = QMessageBox.question(
                self,
                "게시 결과 확인",
                (
                    f"'{title[:60]}' 게시 중 프로그램이 중단되었거나 결과를 확인하지 못했습니다.\n\n"
                    "Threads에서 게시됐는지 확인한 뒤 선택하세요.\n"
                    "예: 게시됨(작업량 확정)\n"
                    "아니요: 게시 안 됨(예약 해제 후 다시 대기)\n"
                    "취소: 지금은 그대로 보관"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            reservation_id = str(item.get("reservation_id") or "").strip()
            if choice == QMessageBox.StandardButton.Yes:
                if reservation_id:
                    try:
                        from src import auth_client

                        result = auth_client.commit_reserved_work(reservation_id)
                    except Exception:
                        logger.exception("Ambiguous post quota commit failed")
                        result = {"success": False}
                    if not isinstance(result, dict) or not self._is_work_allowed(result):
                        item["last_error"] = "quota_commit_retry_pending"
                        continue
                item["status"] = "completed"
                item["updated_at"] = datetime.now().astimezone().isoformat()
                item.pop("reservation_id", None)
                item.pop("idempotency_key", None)
                item.pop("last_error", None)
                changed = True
            elif choice == QMessageBox.StandardButton.No:
                if reservation_id:
                    try:
                        from src import auth_client

                        result = auth_client.release_reserved_work(reservation_id)
                    except Exception:
                        logger.exception("Ambiguous post quota release failed")
                        result = {"success": False}
                    if not isinstance(result, dict) or not self._is_work_allowed(result):
                        item["last_error"] = "quota_release_retry_pending"
                        continue
                item["status"] = "pending"
                item["updated_at"] = datetime.now().astimezone().isoformat()
                item.pop("reservation_id", None)
                item.pop("idempotency_key", None)
                item.pop("last_error", None)
                changed = True

        if changed:
            with self._resume_state_lock:
                self._resume_items = [dict(item) for item in items if isinstance(item, dict)]
                self._resume_interval = max(int(state.get("interval") or 60), 30)
                self._resume_next_allowed_at = state.get("next_allowed_at")
            self._save_resume_state("ambiguous_post_reconcile")
        return state

    def _save_resume_state(self, reason: str = "") -> None:
        with self._resume_state_lock:
            items = [dict(item) for item in self._resume_items]
            unfinished = [item for item in items if self._is_resume_unfinished(item.get("status"))]
            if not unfinished:
                try:
                    self._resume_state_path.unlink(missing_ok=True)
                except Exception:
                    logger.debug("완료된 업로드 대기열 파일 삭제 실패", exc_info=True)
                return

            payload = {
                "version": 1,
                "updated_at": datetime.now().astimezone().isoformat(),
                "reason": str(reason or ""),
                "interval": int(self._resume_interval or 60),
                "next_allowed_at": self._resume_next_allowed_at,
                "items": items,
            }

            temp_path = None
            try:
                self._resume_state_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=str(self._resume_state_path.parent),
                    prefix="upload_resume_queue_",
                    suffix=".tmp",
                    delete=False,
                ) as tmp:
                    json.dump(payload, tmp, ensure_ascii=False, indent=2)
                    temp_path = tmp.name
                os.replace(temp_path, self._resume_state_path)
            except Exception:
                logger.exception("업로드 대기열 저장에 실패했습니다.")
                if temp_path:
                    try:
                        Path(temp_path).unlink(missing_ok=True)
                    except Exception:
                        pass

    def _initialize_resume_state(
        self,
        link_data,
        interval: int,
        *,
        source: str = "manual",
        next_allowed_at=None,
    ) -> None:
        normalized = self._normalize_link_data(link_data)
        now_text = datetime.now().astimezone().isoformat()
        with self._resume_state_lock:
            self._resume_interval = max(int(interval or 60), 30)
            self._resume_next_allowed_at = next_allowed_at
            self._resume_items = [
                {
                    "url": url,
                    "keyword": keyword or "",
                    "status": "pending",
                    "product_title": "",
                    "updated_at": now_text,
                    "source": source,
                    "idempotency_key": str(
                        getattr(self, "_resume_recovered_idempotency_keys", {}).get(url)
                        or ""
                    ),
                }
                for url, keyword in normalized
            ]
        self._save_resume_state(f"{source}_start")

    def _mark_resume_item(
        self,
        url: str,
        status: str,
        product_title: str = "",
        error: str = "",
        *,
        reservation_id: str = "",
        idempotency_key: str = "",
    ) -> None:
        url_text = str(url or "").strip()
        if not url_text:
            return
        with self._resume_state_lock:
            for item in self._resume_items:
                if item.get("url") != url_text:
                    continue
                item["status"] = str(status or "")
                item["updated_at"] = datetime.now().astimezone().isoformat()
                if product_title:
                    item["product_title"] = str(product_title)
                if error:
                    item["last_error"] = str(error)[:300]
                if reservation_id:
                    item["reservation_id"] = str(reservation_id)
                if idempotency_key:
                    item["idempotency_key"] = str(idempotency_key)
                    recovered = getattr(self, "_resume_recovered_idempotency_keys", None)
                    if recovered is None:
                        recovered = self._resume_recovered_idempotency_keys = {}
                    recovered[url_text] = str(idempotency_key)
                if str(status).lower() == "completed":
                    item.pop("reservation_id", None)
                    item.pop("idempotency_key", None)
                    item.pop("last_error", None)
                    getattr(self, "_resume_recovered_idempotency_keys", {}).pop(url_text, None)
                break
        self._save_resume_state(f"item_{status}")

    def _set_resume_next_allowed_at(self, value) -> None:
        with self._resume_state_lock:
            self._resume_next_allowed_at = value
        self._save_resume_state("next_allowed_at")

    def _wait_for_resume_interval_if_needed(self, log, total_links: int | None = None) -> None:
        try:
            wait_until = float(self._resume_next_allowed_at or 0)
        except (TypeError, ValueError):
            wait_until = 0
        remaining = int(wait_until - time.time())
        if remaining <= 0:
            self._set_resume_next_allowed_at(None)
            return

        def emit_wait_state(seconds_left: int) -> None:
            pending = self.link_queue.qsize()
            total = max(int(total_links or 0), pending)
            self.signals.run_state.emit(
                {
                    "phase": "waiting",
                    "message": "저장된 예약 시간을 이어서 대기 중입니다.",
                    "pending": pending,
                    "total": total,
                    "completed": max(total - pending, 0),
                    "next_allowed_at": wait_until,
                    "remaining": max(0, seconds_left),
                }
            )

        log(f"저장된 업로드 간격을 이어서 적용합니다. 다음 항목까지 {_format_interval(remaining)} 대기")
        emit_wait_state(remaining)
        while remaining > 0 and not self._stop_event.is_set():
            if remaining % 60 == 0 or remaining < 60:
                log(f"대기 중... {_format_interval(remaining)} 남음")
            time.sleep(1)
            remaining = int(wait_until - time.time())
            if remaining > 0:
                emit_wait_state(remaining)
        if not self._stop_event.is_set():
            self._set_resume_next_allowed_at(None)

    def _clear_resume_state(self) -> None:
        with self._resume_state_lock:
            self._resume_items = []
            self._resume_next_allowed_at = None
        try:
            self._resume_state_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("업로드 대기열 파일 삭제 실패", exc_info=True)

    def _archive_legacy_resume_state(self) -> None:
        """Retire the old global resume file after account-queue import."""
        if not self._resume_state_path.exists():
            return
        archived = self._resume_state_path.with_name(
            self._resume_state_path.stem + ".migrated.json"
        )
        try:
            os.replace(self._resume_state_path, archived)
        except OSError:
            logger.exception("Legacy upload resume state could not be archived.")

    def _prompt_resume_queue_if_needed(self) -> None:
        if os.getenv("THREAD_AUTO_DISABLE_RESUME_PROMPT", "").strip() == "1":
            return
        if self.is_running:
            return
        state = self._load_resume_state_file()
        state = self._reconcile_posted_commit_items(state)
        state = self._reconcile_ambiguous_post_items(state)
        pending = self._resume_pending_link_data(state)
        if not pending:
            return

        interval = max(int(state.get("interval") or config.upload_interval or 60), 30)
        if not ask_yes_no(
            self,
            "이어하기",
            (
                f"완료되지 않은 업로드 작업 {len(pending)}개가 저장되어 있습니다.\n"
                f"업로드 간격: {_format_interval(interval)}\n\n"
                "남은 작업을 이어서 시작할까요?"
            ),
        ):
            self._clear_resume_state()
            self.signals.log.emit("저장된 미완료 업로드 대기열을 삭제했습니다.")
            return

        imported = self.start_link_data_batch(
            pending,
            interval=interval,
            source="resume",
            next_allowed_at=state.get("next_allowed_at"),
        )
        if imported:
            self._archive_legacy_resume_state()

    def start_link_data_batch(
        self,
        link_data,
        *,
        interval: int | None = None,
        source: str = "manual",
        next_allowed_at=None,
    ) -> bool:
        link_data = self._normalize_link_data(link_data)
        if not link_data:
            show_warning(self, "알림", "지원하는 상품 링크를 찾을 수 없습니다.")
            return False
        if not self._ensure_marketplace_links_allowed(link_data):
            return False
        if self.is_running:
            show_warning(self, "알림", "이미 업로드 작업이 실행 중입니다.")
            return False

        config.load()
        interval = max(int(interval or config.upload_interval or 60), 30)
        selected_provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
        api_key = (
            self._resolve_runtime_gemini_api_key(validate=True)
            if selected_provider == AI_PROVIDER_GEMINI
            else ""
        )
        if selected_provider == AI_PROVIDER_GEMINI and (
            not api_key or len(api_key.strip()) < 10
        ):
            self._log_user_activity("batch_start_key_fallback", "reason=invalid_runtime_api_key", level="WARNING")
            logger.warning("Gemini API 키 검증 실패: 제목 기반 fallback 문구로 계속 진행합니다.")
            api_key = ""

        return self._start_selected_account_batch(
            link_data,
            interval=interval,
            selected_provider=selected_provider,
            api_key=api_key,
            next_allowed_at=next_allowed_at,
        )

        self._log_user_activity("batch_start_confirmed", f"links={len(link_data)}; interval={interval}; source={source}")
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
        next_timestamp = self._safe_float(next_allowed_at)
        self.signals.run_state.emit(
            {
                "phase": "running",
                "message": f"대기열 {len(link_data)}개 준비됨 · {_format_interval(interval)} 간격",
                "pending": len(link_data),
                "total": len(link_data),
                "completed": 0,
                "next_allowed_at": next_timestamp,
                "remaining": max(0, int(next_timestamp - time.time())) if next_timestamp else 0,
            }
        )
        self._reset_steps()
        self._populate_link_table(link_data)

        with self._urls_lock:
            self.processed_urls.clear()
            while not self.link_queue.empty():
                try:
                    self.link_queue.get_nowait()
                except queue.Empty:
                    break
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)

        self.links_text.setPlainText("\n".join([item[0] for item in link_data]))
        self._initialize_resume_state(
            link_data,
            interval,
            source=source,
            next_allowed_at=next_allowed_at,
        )

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
        if hasattr(self.pipeline, "set_google_api_key"):
            self.pipeline.set_google_api_key(api_key)
        if hasattr(self.pipeline, "set_ai_provider"):
            self.pipeline.set_ai_provider(selected_provider)
        self._active_pipeline = self.pipeline
        thread = threading.Thread(
            target=self._run_upload_queue,
            args=(interval, worker_config, self._active_pipeline),
            daemon=True,
        )
        thread.start()
        self._log_user_activity(
            "batch_worker_started",
            f"links={len(link_data)}; interval={interval}; profile_dir={profile_dir}; source={source}",
        )
        logger.info("업로드 작업 스레드 시작")
        return True

    # ────────────────────────────────────────────────────────
    #  SETTINGS LOGIC
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_threads_username(value):
        """Extract a clean Threads/Instagram username from id or profile URL."""
        raw = str(value or "").strip()
        if not raw:
            return ""

        candidate = raw
        lower_candidate = candidate.lower()
        if "://" in candidate or lower_candidate.startswith("www."):
            url_text = candidate if "://" in candidate else f"https://{candidate}"
            try:
                parsed = urlparse(url_text)
                path = unquote(str(parsed.path or ""))
                segments = [seg.strip() for seg in path.split("/") if seg.strip()]
                if segments:
                    candidate = segments[-1]
                else:
                    candidate = str(parsed.netloc or "")
            except Exception:
                pass

        if "/" in candidate:
            candidate = candidate.rsplit("/", 1)[-1]

        candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip()
        if candidate.startswith("@"):
            candidate = candidate[1:]

        # Threads/Instagram username character set
        candidate = re.sub(r"[^A-Za-z0-9._]", "", candidate)
        return candidate[:30]

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리."""
        name = MainWindow._normalize_threads_username(username)
        if not name:
            name = str(username or "")
        return re.sub(r"[^\w\-.]", "_", name)

    def _get_profile_dir(self):
        account = self.selected_threads_account()
        if account is not None:
            return account.profile_id
        username = self._normalize_threads_username(self.username_edit.text().strip())
        if not username:
            username = self._normalize_threads_username(str(getattr(config, "instagram_username", "") or "").strip())
        if username:
            profile_name = self._sanitize_profile_name(username)
            return f".threads_profile_{profile_name}"
        return ".threads_profile"

    def _resolve_runtime_gemini_api_key(self, validate: bool = False):
        key = str(select_working_gemini_api_key(validate=validate) or "").strip()
        if key:
            return key
        if validate:
            return ""
        keys = []
        if hasattr(config, "get_gemini_api_keys"):
            try:
                keys = normalize_gemini_api_keys(config.get_gemini_api_keys())
            except Exception:
                logger.exception("Gemini API 키 목록 조회 중 오류가 발생했습니다.")
        if keys:
            return keys[0]
        return str(getattr(config, "gemini_api_key", "") or "").strip()

    def _selected_ai_provider(self):
        combo = getattr(self, "_ai_provider_combo", None)
        if combo is not None:
            return normalize_ai_provider(combo.currentData())
        return normalize_ai_provider(getattr(config, "ai_provider", ""))

    def _on_ai_provider_changed(self, _index=None):
        provider = self._selected_ai_provider()
        if hasattr(self, "_ai_provider_hint"):
            if provider == AI_PROVIDER_MANAGED:
                self._ai_provider_hint.setText(
                    "AI 사용료는 구독에 포함됩니다. 별도 API 키나 프로그램 설치가 필요하지 않습니다."
                )
            elif provider == AI_PROVIDER_GROK_CLI:
                self._ai_provider_hint.setText(
                    "Grok은 API 키 없이 사용자 본인의 무료 Grok 계정으로 로그인합니다."
                )
            else:
                self._ai_provider_hint.setText(
                    "Gemini는 사용자가 발급한 API 키를 사용하며 여러 키를 순서대로 전환합니다."
                )
        self._relayout_settings_sections()
        if provider == AI_PROVIDER_GROK_CLI:
            self._refresh_grok_status()

    def _open_grok_install_guide(self):
        from src.services.grok_cli_provider import GROK_INSTALL_URL

        QDesktopServices.openUrl(QUrl(GROK_INSTALL_URL))
        self._log_user_activity("grok_install_guide_opened", GROK_INSTALL_URL)

    def _set_grok_buttons_enabled(self, enabled):
        for name in ("_grok_install_btn", "_grok_login_btn", "_grok_check_btn"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(bool(enabled))

    def _refresh_grok_status(self):
        if getattr(self, "_grok_status_check_running", False):
            return
        self._grok_status_check_running = True
        self._set_grok_buttons_enabled(False)
        if hasattr(self, "_grok_status_label"):
            self._grok_status_label.setText("Grok CLI 상태 확인 중...")
            self._grok_status_label.setStyleSheet(
                "color: #F59E0B; font-size: 12px; background: transparent; border: none;"
            )

        def worker():
            try:
                from src.services.grok_cli_provider import get_grok_cli_status

                status = get_grok_cli_status()
                self.signals.grok_status.emit(status.code, status.message, "check")
            except Exception as exc:
                logger.exception("Grok CLI 상태 확인에 실패했습니다.")
                self.signals.grok_status.emit(
                    "error",
                    f"Grok 상태 확인 실패: {exc}",
                    "check",
                )

        threading.Thread(target=worker, daemon=True, name="grok-status-check").start()

    def _start_grok_login(self):
        if getattr(self, "_grok_login_running", False):
            return

        from src.services.grok_cli_provider import find_grok_cli

        if not find_grok_cli():
            show_warning(
                self,
                "Grok CLI 설치 필요",
                "Grok CLI를 먼저 설치해주세요. 공식 설치 안내 페이지를 엽니다.",
            )
            self._open_grok_install_guide()
            return

        self._grok_login_running = True
        self._set_grok_buttons_enabled(False)
        self._grok_status_label.setText("브라우저에서 Grok 로그인을 완료해주세요...")
        self._grok_status_label.setStyleSheet(
            "color: #F59E0B; font-size: 12px; background: transparent; border: none;"
        )
        self._log_user_activity("grok_login_started", "source=settings_page")

        def worker():
            try:
                from src.services.grok_cli_provider import login_to_grok_cli

                status = login_to_grok_cli()
                self.signals.grok_status.emit(status.code, status.message, "login")
            except Exception as exc:
                code = str(getattr(exc, "code", "error") or "error")
                self.signals.grok_status.emit(code, str(exc), "login")

        threading.Thread(target=worker, daemon=True, name="grok-login").start()

    def _apply_grok_status(self, code, message, source="check"):
        self._grok_status_check_running = False
        if source == "check" and getattr(self, "_grok_login_running", False):
            # A status check may have started just before OAuth login. Its stale
            # result must not overwrite the active login instructions.
            return
        if source == "login":
            self._grok_login_running = False
        self._set_grok_buttons_enabled(True)
        label = getattr(self, "_grok_status_label", None)
        if label is None:
            return

        colors = {
            "ready": "#10B981",
            "not_installed": "#F59E0B",
            "not_logged_in": "#F59E0B",
            "free_limit": "#F59E0B",
        }
        color = colors.get(str(code), "#EF4444")
        label.setText(str(message or "Grok 상태를 확인할 수 없습니다."))
        label.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent; border: none;"
        )
        self._log_user_activity(
            "grok_status_updated",
            f"status={str(code)[:40]}",
            level="INFO" if code == "ready" else "WARNING",
        )

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
            toggle.setChecked(True)
        else:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            toggle.setText("보기")
            toggle.setChecked(False)

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
        sy = 12

        provider = self._selected_ai_provider()
        is_grok = provider == AI_PROVIDER_GROK_CLI
        is_gemini = provider == AI_PROVIDER_GEMINI
        is_managed = provider == AI_PROVIDER_MANAGED
        row_count = max(1, int(getattr(self, "_visible_gemini_key_rows", 1)))
        row_start_y = 154
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
            visible = is_gemini and index < row_count
            row["badge"].setVisible(visible)
            row["edit"].setVisible(visible)
            row["toggle"].setVisible(visible)

        for widget in (
            getattr(self, "_settings_api_guide", None),
            getattr(self, "_settings_api_hint", None),
            getattr(self, "_add_gemini_key_btn", None),
        ):
            if widget is not None:
                widget.setVisible(is_gemini)

        for widget in (
            getattr(self, "_grok_status_label", None),
            getattr(self, "_grok_install_btn", None),
            getattr(self, "_grok_login_btn", None),
            getattr(self, "_grok_check_btn", None),
        ):
            if widget is not None:
                widget.setVisible(is_grok)

        self._grok_install_btn.setGeometry(24, 158, 134, 40)
        self._grok_login_btn.setGeometry(170, 158, 150, 40)
        self._grok_check_btn.setGeometry(332, 158, 134, 40)

        add_btn_y = row_start_y + (row_count * row_step) + 4
        self._add_gemini_key_btn.setGeometry(24, add_btn_y, 134, 40)
        if is_managed:
            api_h = 128
        elif is_grok:
            api_h = 220
        else:
            api_h = add_btn_y + 40 + 18

        narrow = w < 760
        automation_h = 286 if narrow else 238
        payment_h = 438 if narrow else 374

        section_specs = {
            0: (
                (self._settings_automation_sec, automation_h),
            ),
            1: (
                (self._settings_account_sec, 104),
                (self._settings_threads_sec, 300),
            ),
            2: (
                (self._settings_api_sec, api_h),
                (self._settings_startup_sec, 96),
                (self._settings_info_sec, 96),
            ),
            3: (
                (self._settings_payment_sec, payment_h),
                (self._settings_tutorial_sec, 104),
                (self._settings_contact_sec, 108),
            ),
        }
        all_sections = tuple(
            section
            for specs in section_specs.values()
            for section, _height in specs
        )
        active_tab = int(getattr(self, "_settings_active_tab", 0) or 0)
        active_specs = section_specs.get(active_tab, section_specs[0])

        for section in all_sections:
            section.setVisible(False)
        for section, section_height in active_specs:
            section.setGeometry(x, sy, w, section_height)
            section.setVisible(True)
            sy += section_height + gap

        content_height = max(sy, 120)
        self._settings_content.setFixedHeight(content_height)
        self._update_settings_help_panel()

    def _on_settings_tab_changed(self, index):
        try:
            tab_index = int(index)
        except (TypeError, ValueError):
            return

        scroll = getattr(self, "_settings_scroll", None)
        positions = getattr(self, "_settings_scroll_positions", {})
        previous_index = int(getattr(self, "_settings_active_tab", 0) or 0)
        if scroll is not None:
            positions[previous_index] = scroll.verticalScrollBar().value()

        self._settings_active_tab = max(0, min(tab_index, 3))
        self._settings_scroll_positions = positions
        self._relayout_settings_sections()

        if scroll is not None:
            scroll.verticalScrollBar().setValue(
                int(positions.get(self._settings_active_tab, 0) or 0)
            )
        self._log_user_activity(
            "settings_inner_tab_switch",
            f"index={self._settings_active_tab}",
            min_interval_sec=0.08,
            dedupe_key=f"settings-tab:{self._settings_active_tab}",
        )

    def _set_post_concept_combo_value(self, combo, concept_id):
        selected_concept = normalize_concept_id(concept_id)
        index = combo.findData(selected_concept)
        previous_blocked = combo.blockSignals(True)
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(previous_blocked)

    def _update_settings_help_panel(self):
        panel = getattr(self, "_settings_help_panel", None)
        if panel is None:
            return
        help_content = {
            0: (
                "업로드 · 글쓰기",
                "업로드 간격은 상품 하나를 올린 뒤 다음 상품까지 기다리는 시간입니다. 영상 우선과 글 작성 방식도 여기서 한 번만 저장되며 모든 자동화 화면에 적용됩니다.",
            ),
            1: (
                "계정 · 연결",
                "Threads 계정을 추가하고 계정별 로그인을 완료하세요. 계정 탭마다 링크 대기열과 진행 상태가 독립적으로 유지됩니다.",
            ),
            2: (
                "AI · 앱",
                "기본 AI 자동 작성은 별도 키 없이 구독에 포함됩니다. Windows 자동 실행과 앱 버전도 이 탭에서 확인할 수 있습니다.",
            ),
            3: (
                "구독 · 지원",
                "지원 쇼핑몰과 계정 수에 맞는 이용권을 선택하고, 결제 상태 확인이나 문의를 진행할 수 있습니다.",
            ),
        }
        panel.set_content(*help_content.get(int(getattr(self, "_settings_active_tab", 0)), help_content[0]))

    # ── Threads accounts / account-scoped upload drafts ─────────────────

    def _threads_accounts(self):
        """Return configured accounts across the small config API transition."""
        getter = getattr(config, "list_threads_accounts", None) or getattr(config, "get_threads_accounts", None)
        return list(getter()) if callable(getter) else []

    def _threads_account_limit(self):
        from src import auth_client
        from src.subscription_plans import resolve_account_limit

        return resolve_account_limit(auth_client.get_auth_state())

    def _is_threads_account_allowed(self, account_id):
        account_ids = [item.account_id for item in self._threads_accounts()]
        try:
            return account_ids.index(str(account_id or "")) < self._threads_account_limit()
        except ValueError:
            return False

    def _ensure_threads_account_allowed(self, account_id=None):
        account_id = str(account_id or self.selected_threads_account_id() or "")
        if self._is_threads_account_allowed(account_id):
            return True
        show_warning(
            self,
            "요금제 계정 제한",
            f"현재 요금제는 Threads 계정 {self._threads_account_limit()}개까지 사용할 수 있습니다. "
            "월 정기권을 결제하면 기존 계정과 대기열을 그대로 다시 사용할 수 있습니다.",
        )
        return False

    def selected_threads_account_id(self):
        """Stable account ID currently selected by the settings or upload UI."""
        tabs = getattr(self, "_upload_account_tabs", None)
        if tabs is not None and tabs.currentIndex() >= 0:
            account_id = tabs.tabData(tabs.currentIndex())
            if account_id:
                return str(account_id)
        combo = getattr(self, "threads_account_combo", None)
        return str(combo.currentData() or "") if combo is not None else ""

    def selected_threads_account(self):
        """Return the selected configured account, or ``None`` when unset."""
        account_id = self.selected_threads_account_id()
        return next((item for item in self._threads_accounts() if item.account_id == account_id), None)

    @staticmethod
    def _upload_tab_index(tabs, account_id):
        target = str(account_id or "")
        for index in range(tabs.count()):
            if str(tabs.tabData(index) or "") == target:
                return index
        return -1

    def _refresh_threads_account_ui(self, selected_id=None):
        accounts = self._threads_accounts()
        preferred = str(selected_id or getattr(config, "active_threads_account_id", "") or "")
        if preferred not in {account.account_id for account in accounts}:
            preferred = accounts[0].account_id if accounts else ""

        combo = getattr(self, "threads_account_combo", None)
        if combo is not None:
            blocked = combo.blockSignals(True)
            combo.clear()
            for account in accounts:
                label = account.display_name or account.expected_username
                if not self._is_threads_account_allowed(account.account_id):
                    label += " (잠김)"
                combo.addItem(label, account.account_id)
            combo.setCurrentIndex(max(combo.findData(preferred), 0))
            combo.blockSignals(blocked)

        tabs = getattr(self, "_upload_account_tabs", None)
        if tabs is not None:
            blocked = tabs.blockSignals(True)
            while tabs.count():
                tabs.removeTab(0)
            for account in accounts:
                label = account.display_name or account.expected_username
                if not self._is_threads_account_allowed(account.account_id):
                    label += " (잠김)"
                index = tabs.addTab(label)
                tabs.setTabData(index, account.account_id)
            tabs.setCurrentIndex(max(self._upload_tab_index(tabs, preferred), 0))
            tabs.blockSignals(blocked)

        self._apply_selected_threads_account(preferred)
        add_btn = getattr(self, "threads_account_add_btn", None)
        if add_btn is not None:
            can_add = len(accounts) < self._threads_account_limit()
            add_btn.setEnabled(can_add)
            add_btn.setToolTip(
                "" if can_add else f"현재 요금제는 계정 {self._threads_account_limit()}개까지 가능합니다."
            )

    def _apply_selected_threads_account(self, account_id):
        account = next((item for item in self._threads_accounts() if item.account_id == str(account_id or "")), None)
        if account is not None:
            self.username_edit.setText(account.expected_username)
            if hasattr(self, "hour_spin"):
                total = int(account.upload_interval)
                self.hour_spin.setValue(total // 3600)
                self.min_spin.setValue((total % 3600) // 60)
                self.sec_spin.setValue(total % 60)
        elif not self._threads_accounts():
            self.username_edit.setText(str(getattr(config, "instagram_username", "") or ""))
        if hasattr(self, "links_text"):
            self._visible_upload_account_id = str(account_id or "")
            blocked = self.links_text.blockSignals(True)
            self.links_text.setPlainText(self._account_drafts.get(str(account_id or ""), ""))
            self.links_text.blockSignals(blocked)
            self._update_link_count()
        self._render_account_queue(str(account_id or ""))

    def _on_threads_account_selected(self, index):
        combo = self.threads_account_combo
        account_id = str(combo.itemData(index) or "")
        previous_id = getattr(self, "_visible_upload_account_id", "")
        if previous_id and hasattr(self, "links_text"):
            self._account_drafts[previous_id] = self.links_text.toPlainText()
        if account_id:
            config.set_active_threads_account(account_id)
            config.save()
        tabs = getattr(self, "_upload_account_tabs", None)
        tab_index = self._upload_tab_index(tabs, account_id) if tabs is not None else -1
        if tabs is not None and tabs.currentIndex() != tab_index:
            tabs.setCurrentIndex(max(tab_index, 0))
        self._apply_selected_threads_account(account_id)

    def _on_upload_account_tab_changed(self, index):
        if self._upload_tab_syncing:
            return
        tabs = self._upload_account_tabs
        previous_id = getattr(self, "_visible_upload_account_id", "")
        if previous_id:
            self._account_drafts[previous_id] = self.links_text.toPlainText()
        account_id = str(tabs.tabData(index) or "")
        self._visible_upload_account_id = account_id
        self._upload_tab_syncing = True
        self.links_text.setPlainText(self._account_drafts.get(account_id, ""))
        self._upload_tab_syncing = False
        combo = getattr(self, "threads_account_combo", None)
        if combo is not None and combo.currentIndex() != combo.findData(account_id):
            combo.setCurrentIndex(max(combo.findData(account_id), 0))
        self._render_account_queue(account_id)

    def _render_account_queue(self, account_id):
        if not account_id or not hasattr(self, "link_table"):
            return
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None:
            state = runtime.queue_store(account_id).get_state()
        else:
            state = AccountQueueStore(account_id, root=Path(config.config_dir) / "queues").get_state()
        items = list(state.pending_items)
        if state.current_item:
            items.insert(0, state.current_item)
        self.link_table.setRowCount(0)
        self._link_url_row_map.clear()
        for row, item in enumerate(items):
            url = str(item.get("url", ""))
            self.link_table.insertRow(row)
            self.link_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.link_table.setItem(row, 1, QTableWidgetItem(url))
            self.link_table.setItem(row, 2, QTableWidgetItem("진행 중" if item == state.current_item else "대기"))
            self.link_table.setItem(row, 3, QTableWidgetItem(str(item.get("title", ""))))
            self._link_url_row_map[url] = row

    def _init_multi_account_runtime(self):
        if self._multi_account_runtime is not None:
            return
        self._multi_account_runtime = MultiAccountRuntime(
            config=config,
            pipeline=self.pipeline,
            queue_root=Path(config.config_dir) / "queues",
            history_root=Path(config.config_dir) / "history",
            on_state=lambda account_id, state: self.signals.account_runtime_state.emit(
                str(account_id), state
            ),
            on_log=lambda account_id, message: self.signals.account_runtime_log.emit(
                str(account_id), str(message)
            ),
        )
        self._multi_account_runtime.refresh_accounts()
        account_id = self.selected_threads_account_id()
        if account_id:
            self._render_account_queue(account_id)

    def _refresh_multi_account_runtime(self):
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None:
            runtime.refresh_accounts()

    def _on_account_runtime_log(self, account_id, message):
        account = next(
            (item for item in self._threads_accounts() if item.account_id == account_id),
            None,
        )
        label = (
            account.display_name or account.expected_username
            if account is not None
            else account_id[:8]
        )
        self.signals.log.emit(f"[{label}] {message}")

    def _on_account_runtime_state(self, account_id, state):
        payload = dict(state or {})
        schedule = payload.get("schedule")
        pending = len(payload.get("pending_items") or []) + (
            1 if payload.get("current_item") else 0
        )
        phase = str(payload.get("phase") or "idle")
        next_allowed_at = payload.get("next_allowed_at")
        blocked_reason = ""
        running = False
        enabled = False
        if schedule is not None:
            running = bool(getattr(schedule, "running", False))
            enabled = bool(getattr(schedule, "enabled", False))
            blocked_reason = str(getattr(schedule, "blocked_reason", "") or "")
            next_allowed_at = getattr(schedule, "next_allowed_at", next_allowed_at)
            if running:
                phase = "processing"
            elif blocked_reason:
                phase = "blocked"
            elif enabled and pending:
                phase = "waiting" if float(next_allowed_at or 0) > time.time() else "running"
            elif pending == 0:
                phase = "finished"

        if account_id == self.selected_threads_account_id():
            self._render_account_queue(account_id)
            stats = payload.get("stats") or {}
            self.signals.run_state.emit(
                {
                    "phase": phase,
                    "message": blocked_reason or (
                        f"계정별 대기열 {pending}개"
                        if pending
                        else "이 계정의 대기열 작업이 완료되었습니다."
                    ),
                    "pending": pending,
                    "total": pending + sum(int(stats.get(key, 0) or 0) for key in ("success", "failed", "skipped")),
                    "completed": int(stats.get("success", 0) or 0) + int(stats.get("skipped", 0) or 0),
                    "failed": int(stats.get("failed", 0) or 0),
                    "next_allowed_at": next_allowed_at,
                    "current_item": str((payload.get("current_item") or {}).get("url", "")),
                }
            )
            self.start_btn.setEnabled(not running)
            self.add_btn.setEnabled(True)
            self.stop_btn.setEnabled(running or enabled)

        tabs = getattr(self, "_upload_account_tabs", None)
        if tabs is not None:
            tab_index = self._upload_tab_index(tabs, account_id)
            account = next(
                (item for item in self._threads_accounts() if item.account_id == account_id),
                None,
            )
            if tab_index >= 0 and account is not None:
                label = account.display_name or account.expected_username
                marker = " ●" if running or enabled else (" !" if blocked_reason else "")
                tabs.setTabText(tab_index, label + marker)

        runtime = getattr(self, "_multi_account_runtime", None)
        snapshots = runtime.snapshots().values() if runtime is not None else []
        any_active = any(
            bool(getattr(item.get("schedule"), "running", False))
            or bool(getattr(item.get("schedule"), "enabled", False))
            for item in snapshots
        )
        self.is_running = any_active
        if hasattr(self, "stop_all_btn"):
            self.stop_all_btn.setEnabled(any_active)
        if not any_active and isinstance(self._pending_update_info, dict):
            QTimer.singleShot(300, self._maybe_show_update_notice)

    def _add_threads_account_from_ui(self):
        if len(self._threads_accounts()) >= self._threads_account_limit():
            show_warning(
                self,
                "계정 추가 제한",
                f"현재 요금제는 Threads 계정 {self._threads_account_limit()}개까지 추가할 수 있습니다.",
            )
            return
        username = self._normalize_threads_username(self.username_edit.text())
        if not username:
            show_warning(self, "계정 이름", "Threads 사용자명을 먼저 입력하세요.")
            return
        try:
            account = config.add_threads_account(username, display_name=username, upload_interval=max(30, int(config.upload_interval)))
            config.set_active_threads_account(account.account_id)
            config.save()
        except (ValueError, KeyError) as exc:
            show_warning(self, "계정 추가", str(exc))
            return
        self._refresh_multi_account_runtime()
        self._refresh_threads_account_ui(account.account_id)

    def _remove_selected_threads_account(self):
        account_id = self.selected_threads_account_id()
        if not account_id:
            return
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None:
            try:
                account_state = runtime.snapshot(account_id)
                schedule = account_state.get("schedule")
            except KeyError:
                account_state = {}
                schedule = None
            if schedule is not None and (
                getattr(schedule, "running", False)
                or getattr(schedule, "enabled", False)
            ):
                show_warning(self, "계정 삭제", "실행 중인 계정은 먼저 중지해 주세요.")
                return
            if (
                account_state.get("current_item")
                or account_state.get("pending_items")
            ):
                show_warning(
                    self,
                    "계정 삭제",
                    "대기열이 남아 있는 계정은 삭제할 수 없습니다. 먼저 작업을 완료해 주세요.",
                )
                return
        try:
            config.remove_threads_account(account_id)
            config.save()
        except KeyError:
            return
        self._account_drafts.pop(account_id, None)
        self._refresh_multi_account_runtime()
        self._refresh_threads_account_ui()

    def _load_settings(self):
        """Load config values into widgets."""
        provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
        provider_combo = getattr(self, "_ai_provider_combo", None)
        if provider_combo is not None:
            provider_index = provider_combo.findData(provider)
            provider_combo.setCurrentIndex(max(provider_index, 0))

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
            row["toggle"].setChecked(False)
        self._on_ai_provider_changed()

        total = config.upload_interval
        self.hour_spin.setValue(total // 3600)
        self.min_spin.setValue((total % 3600) // 60)
        self.sec_spin.setValue(total % 60)

        self.video_check.setChecked(config.prefer_video)
        if hasattr(self, "_auto_start_check"):
            self._auto_start_check.setChecked(bool(getattr(config, "auto_start_enabled", True)))
        selected_concept = normalize_concept_id(getattr(config, "post_concept", ""))
        self._set_post_concept_combo_value(self.settings_post_concept_combo, selected_concept)
        self.username_edit.setText(config.instagram_username)
        self._refresh_threads_account_ui()

        # Keep top-right user status chips visually aligned with the reference app.
        def _apply_top_right_status_styles():
            self._work_label.setStyleSheet(
                f"QPushButton {{ background-color: {Colors.ACCENT}; color: {Colors.BG_DARK};"
                " border: none; border-radius: 8px; padding: 7px 14px; font-size: 9pt; font-weight: 800; }"
                f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_LIGHT};"
                f" border: 2px solid {Colors.TEXT_PRIMARY}; }}"
            )
            self._header_username_label.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; background: transparent;"
            )
            self._online_dot.setStyleSheet(f"background-color: {Colors.TEXT_MUTED}; border-radius: 4px;")
            self._connection_label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600; background: transparent;"
            )
            self._plan_badge.setStyleSheet(
                f"QPushButton {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_SECONDARY};"
                f" border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 6px 12px;"
                " font-size: 8pt; font-weight: 700; }"
                f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_SUBTLE};"
                f" border: 2px solid {Colors.ACCENT}; color: {Colors.TEXT_PRIMARY}; }}"
            )
            self._relayout_header_account_card()
            return
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

        selected_provider = self._selected_ai_provider()
        key_values = []
        for index, row in enumerate(getattr(self, "_gemini_key_rows", [])):
            if index >= getattr(self, "_visible_gemini_key_rows", 1):
                continue
            key_values.append(row["edit"].text().strip())
        key_values = normalize_gemini_api_keys(key_values)
        if selected_provider == AI_PROVIDER_GEMINI and not key_values:
            self._log_user_activity("settings_save_blocked", "reason=missing_gemini_keys", level="WARNING")
            tab_bar = getattr(self, "_settings_tab_bar", None)
            if tab_bar is not None:
                tab_bar.setCurrentIndex(1)
            rows = getattr(self, "_gemini_key_rows", [])
            if rows:
                rows[0]["edit"].setFocus()
            show_warning(self, "설정 필요", "최소 1개의 Gemini API 키를 입력해주세요.")
            return
        if key_values:
            save_configured_gemini_api_keys(key_values)

        config.upload_interval = interval
        config.ai_provider = selected_provider
        config.prefer_video = self.video_check.isChecked()
        config.auto_start_enabled = (
            self._auto_start_check.isChecked()
            if hasattr(self, "_auto_start_check")
            else bool(getattr(config, "auto_start_enabled", True))
        )
        config.post_concept = normalize_concept_id(self.settings_post_concept_combo.currentData())
        username = self._normalize_threads_username(self.username_edit.text().strip())
        account_id = self.selected_threads_account_id()
        if account_id:
            try:
                config.update_threads_account(
                    account_id,
                    expected_username=username,
                    upload_interval=interval,
                )
            except (KeyError, ValueError) as exc:
                show_warning(self, "계정 설정", str(exc))
                return
        config.instagram_username = username
        config.save()
        self._refresh_multi_account_runtime()
        self._refresh_threads_account_ui(account_id)
        auto_start_synced = sync_auto_start(bool(config.auto_start_enabled))

        active_key = self._resolve_runtime_gemini_api_key(validate=False)

        if self.is_running:
            logger.info("실행 중 설정 저장됨; 파이프라인 재초기화는 보류합니다")
        else:
            self.pipeline = CoupangPartnersPipeline(
                active_key,
                ai_provider=selected_provider,
            )
            runtime = getattr(self, "_multi_account_runtime", None)
            if runtime is not None:
                runtime.set_pipeline(self.pipeline)

        if hasattr(self, "_relayout_header_account_card"):
            self._relayout_header_account_card()
        top_right_style_fn = getattr(self, "_apply_top_right_status_styles", None)
        if callable(top_right_style_fn):
            top_right_style_fn()

        show_info(self, "저장 완료", "설정이 저장되었습니다.")
        if bool(config.auto_start_enabled) and not auto_start_synced:
            show_warning(self, "자동 실행", "Windows 자동 실행 등록에 실패했습니다. 로그를 확인해주세요.")
        self._log_user_activity(
            "settings_saved",
            (
                f"upload_interval={interval}; prefer_video={bool(config.prefer_video)}; "
                f"auto_start_enabled={bool(config.auto_start_enabled)}; "
                f"post_concept={normalize_concept_id(getattr(config, 'post_concept', ''))}; "
                f"username_set={bool(config.instagram_username)}; "
                f"ai_provider={selected_provider}; gemini_keys={len(key_values)}"
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
        state = dict(auth)

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

        from src.subscription_plans import resolve_plan

        resolved_plan = resolve_plan(state)
        paid_plan_label = resolved_plan.label if resolved_plan else "유료 계정"
        header_plan_label = "쇼핑 프로" if resolved_plan and resolved_plan.is_shopping_pro else paid_plan_label

        # Header plan badge
        if paid_account:
            self._plan_badge.setText(header_plan_label)
            self._plan_badge.setStyleSheet(
                f"QPushButton {{ background-color: {Colors.ACCENT_SUBTLE};"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid {Colors.ACCENT_DARK};"
                " border-radius: 6px;"
                " padding: 6px 12px;"
                " font-size: 8pt;"
                " font-weight: 700;"
                "}"
                f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.ACCENT_DARK};"
                f" color: {Colors.TEXT_PRIMARY}; border: 2px solid {Colors.ACCENT_LIGHT}; }}"
            )
        else:
            self._plan_badge.setText("무료계정")
            self._plan_badge.setStyleSheet(
                f"QPushButton {{"
                f" background-color: {Colors.BG_ELEVATED};"
                f" color: {Colors.TEXT_SECONDARY};"
                f" border: 1px solid {Colors.BORDER};"
                f" border-radius: 6px;"
                f" padding: 6px 12px;"
                f" font-size: 8pt;"
                f" font-weight: 700;"
                f"}}"
                f"QPushButton:hover, QPushButton:focus {{"
                f" background-color: {Colors.ACCENT_SUBTLE};"
                f" border: 2px solid {Colors.ACCENT};"
                f" color: {Colors.TEXT_PRIMARY};"
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
        self._header_username_full_text = str(display_name)
        self._header_username_label.setText(display_name)
        self._header_username_label.setToolTip(str(display_name))

        # Settings page account card
        self._acct_username_label.setText(display_name)
        self._acct_work_label.setText(f"{work_used} / {work_count} 회 사용")

        if paid_account:
            self._acct_plan_badge.setText(paid_plan_label)
            self._acct_plan_badge.setStyleSheet(
                f"QLabel {{ background-color: {Colors.ACCENT_SUBTLE};"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid {Colors.ACCENT_DARK};"
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

        if hasattr(self, "_shopping_offer_label"):
            offer_eligible = bool(state.get("offer_eligible"))
            trial_ends_at = str(state.get("shopping_trial_ends_at") or "").strip()
            offer_price = int(state.get("offer_price_krw") or 59_000)
            offer_cycles = int(state.get("offer_cycles") or 6)
            if resolved_plan and resolved_plan.is_shopping_pro:
                offer_text = "현재 쇼핑 프로 이용 중 · 쿠팡·네이버·토스·Ali 상품 링크 지원"
            elif str(state.get("commerce_scope") or "").lower() == "multi" and trial_ends_at:
                trial_date = trial_ends_at[:10]
                offer_text = f"기존 고객 · {trial_date} 전까지 쇼핑 프로 무료"
                if offer_eligible:
                    offer_text += f" · 이후 월 {offer_price:,}원×최대 {offer_cycles}회 · 월간권 해지 후 전환"
            elif offer_eligible:
                offer_text = (
                    f"기존 고객 · 월 {offer_price:,}원×최대 {offer_cycles}회 · "
                    "이후 월 69,000원 · 월간권 해지 후 전환"
                )
            else:
                offer_text = "무료 계정도 첫 작업 1회는 모든 쇼핑몰 링크를 체험할 수 있습니다."
            self._shopping_offer_label.setText(offer_text)

        if hasattr(self, "_pay_shopping_monthly_btn"):
            pro_month_price = int(state.get("offer_price_krw") or 59_000) if state.get("offer_eligible") else 69_000
            self._pay_shopping_monthly_btn.setText(
                f"월간 쇼핑 프로  {pro_month_price:,}원\n10개 Threads 계정 · 정기결제"
            )

        if hasattr(self, "_pay_cancel_btn"):
            self._pay_cancel_btn.setVisible(bool(paid_account and state.get("is_recurring")))

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

    def _shopping_pro_month_plan_id(self):
        from src import auth_client
        from src.subscription_plans import (
            SHOPPING_PRO_FOUNDER_MONTHLY_PLAN_ID,
            SHOPPING_PRO_MONTHLY_PLAN_ID,
        )

        state = auth_client.get_auth_state()
        if state.get("offer_eligible"):
            return str(state.get("offer_plan_id") or SHOPPING_PRO_FOUNDER_MONTHLY_PLAN_ID)
        return SHOPPING_PRO_MONTHLY_PLAN_ID

    def _set_payment_busy(self, busy, status=""):
        for widget_name in (
            "_pay_weekly_btn",
            "_pay_monthly_btn",
            "_pay_shopping_weekly_btn",
            "_pay_shopping_monthly_btn",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(not busy)
        if status and hasattr(self, "_pay_status_label"):
            self._pay_status_label.setText(status)

    def _request_payapp_checkout(self, plan_id="stmaker_pro_week"):
        phone = re.sub(r"[^0-9]", "", self._pay_phone_edit.text().strip())
        phone_masked = phone
        if len(phone) >= 7:
            phone_masked = f"{phone[:3]}****{phone[-4:]}"
        self._log_user_activity(
            "payment_checkout_requested",
            f"phone={phone_masked}; plan_id={plan_id}",
        )
        if not phone:
            self._log_user_activity(
                "payment_checkout_validation_failed",
                "reason=empty_phone",
                level="WARNING",
            )
            show_warning(self, "결제 요청", "휴대폰 번호를 입력해주세요. (예: 01012345678)")
            self._set_payment_busy(False, "휴대폰 번호를 확인해주세요.")
            return

        self._set_payment_busy(True, "안전한 결제 페이지를 준비하고 있습니다…")
        try:
            from src import auth_client
            from src.subscription_plans import RECURRING_PLAN_IDS

            if plan_id in RECURRING_PLAN_IDS:
                result = auth_client.create_payapp_subscription(phone, plan_id=plan_id)
            else:
                result = auth_client.create_payapp_checkout(phone, plan_id=plan_id)
        except Exception:
            self._log_user_activity("payment_checkout_request_failed", "reason=api_exception", level="ERROR")
            logger.exception("PayApp 결제 요청 중 예외가 발생했습니다.")
            show_error(self, "결제 요청 실패", "결제 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            self._set_payment_busy(False, "결제 요청에 실패했습니다. 잠시 후 다시 시도해주세요.")
            return

        self._set_payment_busy(False)

        if not isinstance(result, dict):
            self._log_user_activity("payment_checkout_request_failed", "reason=invalid_response", level="ERROR")
            show_error(self, "결제 요청 실패", "결제 서버 응답 형식이 올바르지 않습니다.")
            self._set_payment_busy(False, "결제 서버 응답을 확인하지 못했습니다.")
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
            self._set_payment_busy(False, message)
            return

        server_plan_id = str(result.get("plan_id") or "").strip()
        expected_plan_id = plan_id
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
            self._set_payment_busy(False, "결제 요금제 확인에 실패했습니다.")
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
            self._set_payment_busy(False, "결제 페이지 주소를 받지 못했습니다.")
            return

        if not auth_client.is_trusted_payment_url(pay_url):
            safe_url = auth_client.safe_url_for_log(pay_url)
            self._log_user_activity(
                "payment_checkout_request_failed",
                f"reason=untrusted_payment_url; url={safe_url}",
                level="ERROR",
            )
            show_error(
                self,
                "결제 요청 실패",
                "신뢰할 수 없는 결제 URL이 감지되어 결제창을 열지 않았습니다.",
            )
            self._set_payment_busy(False, "안전하지 않은 결제 주소가 차단되었습니다.")
            return

        safe_pay_url = auth_client.safe_url_for_log(pay_url)
        self._log_user_activity("payment_checkout_url_ready", f"url={safe_pay_url}")
        opened = self._open_external_link(pay_url, "settings_payapp_checkout")
        if not opened:
            self._log_user_activity("payment_checkout_open_failed", f"url={safe_pay_url}", level="WARNING")
            show_error(self, "결제 요청 실패", f"결제 페이지를 열지 못했습니다.\n{safe_pay_url}")
            self._set_payment_busy(False, "결제 페이지를 열지 못했습니다.")
            return

        self._log_user_activity("payment_checkout_opened", f"url={safe_pay_url}")
        self.signals.log.emit(f"PayApp 결제 페이지가 열렸습니다: {safe_pay_url}")
        self._set_payment_busy(False, "결제 페이지가 열렸습니다. 결제 후 ‘상태 새로고침’을 눌러주세요.")
        # Refresh entitlement shortly after PayApp approval instead of waiting
        # for the normal one-minute heartbeat interval.
        for delay_ms in (5_000, 15_000, 30_000, 60_000, 120_000):
            QTimer.singleShot(delay_ms, self._send_heartbeat)

    def _cancel_payapp_subscription(self):
        choice = QMessageBox.question(
            self,
            "월 정기결제 해지",
            "다음 자동결제를 중단하시겠습니까?\n현재 승인된 이용 기간은 만료일까지 유지됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            from src import auth_client

            status = auth_client.get_payapp_subscriptions()
            if not isinstance(status, dict) or not status.get("success"):
                message = str((status or {}).get("message") or "정기결제 상태를 확인하지 못했습니다.")
                show_error(self, "정기결제 해지", message)
                return
            candidates = status.get("subscriptions") or status.get("items") or status.get("data") or []
            if isinstance(candidates, dict):
                candidates = candidates.get("subscriptions") or candidates.get("items") or [candidates]
            if not isinstance(candidates, list):
                candidates = []
            active = next(
                (
                    item for item in candidates
                    if isinstance(item, dict)
                    and str(item.get("status") or item.get("rebill_status") or "active").lower()
                    not in {"cancelled", "canceled", "expired", "failed"}
                    and (item.get("rebill_no") or item.get("rebillNo"))
                ),
                None,
            )
            if not active:
                show_info(self, "정기결제 해지", "해지할 활성 월 정기결제가 없습니다.")
                return
            rebill_no = str(active.get("rebill_no") or active.get("rebillNo") or "").strip()
            result = auth_client.cancel_payapp_subscription(rebill_no)
            if not isinstance(result, dict) or not result.get("success"):
                message = str((result or {}).get("message") or "정기결제를 해지하지 못했습니다.")
                show_error(self, "정기결제 해지", message)
                return
            self._log_user_activity("payment_subscription_cancelled", "status=success")
            show_info(self, "정기결제 해지", "다음 자동결제가 중단되었습니다. 현재 이용 기간은 만료일까지 유지됩니다.")
            self._send_heartbeat()
        except Exception:
            logger.exception("PayApp 정기결제 해지 중 오류가 발생했습니다.")
            show_error(self, "정기결제 해지", "정기결제 해지 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

    def open_settings(self, tab_index=None):
        """Switch to the unified Settings workspace."""
        logger.info("설정 화면 열기 호출")
        self._switch_page(1, source="open_settings")
        if tab_index is not None and hasattr(self, "_settings_tab_bar"):
            self._settings_tab_bar.setCurrentIndex(max(0, min(int(tab_index), 3)))

    # ────────────────────────────────────────────────────────
    #  THREADS LOGIN LOGIC
    # ────────────────────────────────────────────────────────

    def _open_threads_login(self):
        raw_username = self.username_edit.text().strip()
        username = self._normalize_threads_username(raw_username)

        if raw_username and username and raw_username != username:
            self.username_edit.setText(username)
            self._log_user_activity(
                "threads_username_normalized",
                f"raw={raw_username[:80]}; normalized={username}",
            )

        if username:
            config.instagram_username = username
            account_id = self.selected_threads_account_id()
            if account_id:
                try:
                    config.update_threads_account(account_id, expected_username=username)
                except (KeyError, ValueError):
                    pass
            config.save()

        if getattr(self, "_threads_login_browser_open", False):
            self._log_user_activity(
                "threads_login_launch_skipped",
                "reason=browser_already_open",
            )
            self._update_login_status(
                "pending",
                "이미 로그인 브라우저가 열려 있습니다. 로그인 후 창을 닫아주세요.",
            )
            self.signals.log.emit("로그인 브라우저가 이미 열려 있습니다. 로그인 후 창을 닫아주세요.")
            return

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
        # Threads browser login itself does not require an AI key. The dummy
        # value keeps the browser/session wrapper available in Grok mode.
        if not runtime_api_key or len(runtime_api_key.strip()) < 10:
            runtime_api_key = "dummy-key-for-session-setup"
        logger.info(
            "Threads 로그인 브라우저 실행 요청: profile=%s username_provided=%s",
            profile_dir,
            bool(username),
        )
        self._threads_login_browser_open = True

        def open_browser():
            launch_notified = False
            try:
                from src.computer_use_agent import ComputerUseAgent

                agent = ComputerUseAgent(
                    api_key=runtime_api_key,
                    headless=False,
                    profile_dir=profile_dir
                )
                # Some accounts fall into redirect loops when stale session/cookie
                # state is reused. Start from a clean saved-state file for login flow.
                try:
                    agent.clear_saved_session()
                    logger.info("Threads 로그인 시작 전 저장 세션을 초기화했습니다.")
                except Exception:
                    logger.exception("Threads 로그인 시작 전 저장 세션 초기화에 실패했습니다.")
                agent.start_browser()
                # 로그인 플로우는 반드시 로그인 페이지(/login)로 먼저 이동한다.
                # 로그아웃 상태에서 프로필(/@username)로 가면 페이지는 열리지만(200)
                # 로그인 UI가 무한 로딩되어 실제 로그인이 되지 않는 문제가 있었다.
                path_candidates = ["/login"]
                if username:
                    path_candidates.append(f"/@{username}")
                path_candidates.append("/")

                opened_url = ""
                last_nav_error = None
                for path_candidate in path_candidates:
                    try:
                        opened_url = goto_threads_with_fallback(
                            agent.page,
                            path=path_candidate,
                            timeout=30000,
                            retries_per_url=1,
                            logger=logger,
                        )
                        break
                    except Exception as nav_exc:
                        last_nav_error = nav_exc
                        logger.warning(
                            "Threads 로그인 경로 시도 실패(path=%s): %s",
                            path_candidate,
                            nav_exc,
                        )

                if not opened_url:
                    raise RuntimeError(
                        f"Threads 로그인 페이지 접속 실패: {last_nav_error}"
                        if last_nav_error
                        else "Threads 로그인 페이지 접속 실패"
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

        if success:
            self._threads_login_browser_open = True
            self.threads_login_btn.setEnabled(False)
            self.threads_login_btn.setText("로그인 창 열림")
            self._update_login_status("pending", "브라우저가 열렸습니다. 로그인 완료 후 창을 닫아주세요.")
            opened_url = str(detail or "").strip()
            self._log_user_activity("threads_login_browser_opened", f"url={opened_url or '(unknown)'}")
            if opened_url:
                self.signals.log.emit(f"Threads 로그인 브라우저가 열렸습니다. 로그인 후 창을 닫아주세요: {opened_url}")
            else:
                self.signals.log.emit("Threads 로그인 브라우저가 열렸습니다. 로그인 후 창을 닫아주세요.")
            return

        self._threads_login_browser_open = False
        self._restore_login_btn()
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
        self._threads_login_browser_open = False
        self._restore_login_btn()
        self._log_user_activity("threads_login_browser_closed", "session_saved=True")
        self._update_login_status("pending", "저장된 로그인 계정을 확인하는 중...")
        self.signals.log.emit("Threads 브라우저가 닫혀 세션을 저장했습니다. 계정을 확인합니다.")
        self._check_login_status()

    def _check_login_status(self):
        account = self.selected_threads_account()
        if account is None:
            show_warning(self, "Threads 계정", "먼저 확인할 계정을 선택해 주세요.")
            return
        self.check_login_btn.setEnabled(False)
        self.check_login_btn.setText("확인 중...")
        self._update_login_status("pending", "저장된 로그인 계정을 확인하는 중...")
        account_id = account.account_id
        expected_username = account.expected_username
        profile_id = account.profile_id

        def run_check():
            agent = None
            result = (False, None, account_id, expected_username)
            try:
                from src.computer_use_agent import ComputerUseAgent
                from src.threads_playwright_helper import ThreadsPlaywrightHelper

                agent = ComputerUseAgent(
                    api_key="dummy-key-for-session-check",
                    headless=True,
                    profile_dir=profile_id,
                )
                agent.start_browser()
                goto_threads_with_fallback(
                    agent.page,
                    path="/",
                    timeout=15000,
                    retries_per_url=1,
                )
                helper = ThreadsPlaywrightHelper(agent.page)
                logged_in = helper.check_login_status()
                username = helper.get_logged_in_username() if logged_in else None
                verified = bool(
                    logged_in and helper.verify_account(expected_username)
                )
                result = (verified, username, account_id, expected_username)
            except Exception:
                logger.exception("Threads 로그인 계정 확인에 실패했습니다.")
            finally:
                if agent is not None:
                    try:
                        agent.close()
                    except Exception:
                        pass
            if self._closed:
                return
            app = QApplication.instance()
            if app is not None:
                app.postEvent(self, LoginStatusEvent(result))

        threading.Thread(target=run_check, daemon=True).start()

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
            result = tuple(evt.result)
            is_logged_in, username = result[:2]
            account_id = result[2] if len(result) > 2 else ""
            expected_username = result[3] if len(result) > 3 else ""
            self._log_user_activity(
                "threads_login_check_result",
                f"is_logged_in={bool(is_logged_in)}; username={username or ''}",
            )
            self.check_login_btn.setEnabled(True)
            self.check_login_btn.setText("로그인 상태 확인")

            if is_logged_in:
                name = f"@{username}" if username else "연결됨"
                self._update_login_status("success", name)
                if account_id:
                    try:
                        config.update_threads_account(
                            account_id,
                            last_verified_username=username or expected_username,
                            last_verified_at=datetime.now().astimezone().isoformat(),
                        )
                        config.save()
                        self._refresh_threads_account_ui(account_id)
                    except (KeyError, ValueError):
                        logger.exception("Threads 계정 검증 결과 저장에 실패했습니다.")
            else:
                self._update_login_status("error", "로그인 또는 계정 일치 확인 실패")
            return True
        return super().event(evt)

    # ────────────────────────────────────────────────────────
    #  UPLOAD LOGIC
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _is_dev_quota_bypass_enabled():
        value = str(os.getenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "") or "").strip().lower()
        return value in {"1", "true", "yes", "y", "on"}

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

    def _configure_multi_account_pipeline(self, selected_provider, api_key):
        if hasattr(self.pipeline, "set_google_api_key"):
            self.pipeline.set_google_api_key(api_key)
        if hasattr(self.pipeline, "set_ai_provider"):
            self.pipeline.set_ai_provider(selected_provider)
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None and not runtime.is_running:
            runtime.set_pipeline(self.pipeline)

    def _start_selected_account_batch(
        self,
        link_data,
        *,
        interval,
        selected_provider,
        api_key,
        next_allowed_at=None,
    ):
        account = self.selected_threads_account()
        if account is None:
            show_warning(self, "Threads 계정", "설정에서 먼저 Threads 계정을 추가해 주세요.")
            return False
        if not self._ensure_threads_account_allowed(account.account_id):
            return False
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is None:
            self._init_multi_account_runtime()
            runtime = self._multi_account_runtime
        runtime.refresh_accounts()
        if next_allowed_at:
            runtime.queue_store(account.account_id).set_phase(
                "waiting",
                next_allowed_at=next_allowed_at,
            )
            runtime.refresh_accounts()
        self._configure_multi_account_pipeline(selected_provider, api_key)
        added = runtime.enqueue(account.account_id, link_data)
        if added <= 0:
            show_info(self, "대기열", "모든 링크가 이미 이 계정의 대기열 또는 업로드 이력에 있습니다.")
            self._render_account_queue(account.account_id)
            return False

        self._account_drafts[account.account_id] = "\n".join(item[0] for item in link_data)
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.stop_all_btn.setEnabled(True)
        self.status_badge.update_style(Colors.WARNING, "실행중")
        self._sidebar_status_label.setText("실행중")
        self._reset_steps()
        self._render_account_queue(account.account_id)
        self.signals.run_state.emit(
            {
                "phase": "running",
                "message": f"@{account.expected_username} 대기열에 {added}개 추가",
                "pending": len(runtime.snapshot(account.account_id).get("pending_items") or []),
                "total": len(runtime.snapshot(account.account_id).get("pending_items") or []),
            }
        )
        runtime.start_account(account.account_id)
        self._log_user_activity(
            "multi_account_batch_started",
            f"account_id={account.account_id}; added={added}; interval={interval}",
        )
        return True

    def start_all_accounts(self):
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is None:
            self._init_multi_account_runtime()
            runtime = self._multi_account_runtime
        runtime.refresh_accounts()
        allowed_ids = {
            account.account_id
            for account in self._threads_accounts()[: self._threads_account_limit()]
        }
        pending_total = sum(
            len(state.get("pending_items") or []) + (1 if state.get("current_item") else 0)
            for account_id, state in runtime.snapshots().items()
            if account_id in allowed_ids
        )
        if pending_total <= 0:
            show_info(self, "전체 대기열", "실행할 계정별 대기열이 없습니다.")
            return
        selected_provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
        api_key = (
            self._resolve_runtime_gemini_api_key(validate=True)
            if selected_provider == AI_PROVIDER_GEMINI
            else ""
        )
        self._configure_multi_account_pipeline(selected_provider, api_key)
        self.is_running = True
        self.start_all_btn.setEnabled(False)
        self.stop_all_btn.setEnabled(True)
        for account in self._threads_accounts()[: self._threads_account_limit()]:
            state = runtime.snapshot(account.account_id)
            if state.get("current_item") or state.get("pending_items"):
                runtime.start_account(account.account_id)
        self.signals.log.emit(f"전체 계정 대기열 {pending_total}개 실행을 시작했습니다.")

    def stop_all_accounts(self):
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is None:
            return
        runtime.stop_all()
        if runtime.is_running:
            self.pipeline.cancel()
        self.is_running = False
        self.start_all_btn.setEnabled(True)
        self.stop_all_btn.setEnabled(False)
        self.signals.log.emit("전체 계정 대기열 중지를 요청했습니다.")

    def _start_existing_selected_queue(self) -> bool:
        account = self.selected_threads_account()
        runtime = getattr(self, "_multi_account_runtime", None)
        if account is None or runtime is None:
            return False
        if not self._ensure_threads_account_allowed(account.account_id):
            return False
        state = runtime.snapshot(account.account_id)
        pending = len(state.get("pending_items") or []) + (
            1 if state.get("current_item") else 0
        )
        if pending <= 0:
            return False
        selected_provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
        api_key = (
            self._resolve_runtime_gemini_api_key(validate=True)
            if selected_provider == AI_PROVIDER_GEMINI
            else ""
        )
        self._configure_multi_account_pipeline(selected_provider, api_key)
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.stop_all_btn.setEnabled(True)
        runtime.start_account(account.account_id)
        self.signals.log.emit(
            f"@{account.expected_username}의 저장된 대기열 {pending}개를 시작했습니다."
        )
        return True

    def start_upload(self):
        logger.info("업로드 시작 호출")
        self._log_user_activity("batch_start_requested", "source=start_button")
        if not self._ensure_threads_account_allowed():
            return
        content = self.links_text.toPlainText().strip()
        if not content:
            if self._start_existing_selected_queue():
                return
            self._log_user_activity("batch_start_blocked", "reason=empty_links_input", level="WARNING")
            logger.warning("업로드 시작 차단: 내용이 비어 있습니다")
            show_warning(self, "알림", "상품 링크를 입력하세요.")
            return

        config.load()
        selected_provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
        api_key = (
            self._resolve_runtime_gemini_api_key(validate=True)
            if selected_provider == AI_PROVIDER_GEMINI
            else ""
        )
        if selected_provider == AI_PROVIDER_GEMINI and (
            not api_key or len(api_key.strip()) < 10
        ):
            self._log_user_activity("batch_start_key_fallback", "reason=invalid_runtime_api_key", level="WARNING")
            logger.warning("Gemini API 키 검증 실패: 제목 기반 fallback 문구로 계속 진행합니다.")
            api_key = ""

        link_data = self._extract_links(content)
        if not link_data:
            self._log_user_activity("batch_start_blocked", "reason=no_valid_links", level="WARNING")
            logger.warning("업로드 시작 차단: 유효한 링크가 없습니다")
            show_warning(self, "알림", "지원하는 상품 링크를 찾을 수 없습니다.")
            return
        if not self._ensure_marketplace_links_allowed(link_data):
            return

        selected_account = self.selected_threads_account()
        interval = max(
            int(selected_account.upload_interval if selected_account is not None else config.upload_interval),
            30,
        )
        logger.info("업로드 준비 완료: links=%d interval=%d", len(link_data), interval)

        quota_bypass = self._is_dev_quota_bypass_enabled()
        if quota_bypass:
            logger.info("개발자 모드: 작업량 사전 점검을 건너뜁니다.")
            self._log_user_activity("batch_start_quota_bypass", "mode=developer_unlimited")
        else:
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

        self._start_selected_account_batch(
            link_data,
            interval=interval,
            selected_provider=selected_provider,
            api_key=api_key,
        )
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
        if hasattr(self.pipeline, "set_google_api_key"):
            self.pipeline.set_google_api_key(api_key)
        if hasattr(self.pipeline, "set_ai_provider"):
            self.pipeline.set_ai_provider(selected_provider)
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
        if not self._ensure_threads_account_allowed():
            return
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
            show_warning(self, "알림", "지원하는 상품 링크를 찾을 수 없습니다.")
            return
        if not self._ensure_marketplace_links_allowed(link_data):
            return

        runtime = getattr(self, "_multi_account_runtime", None)
        account = self.selected_threads_account()
        if runtime is not None and account is not None:
            added = runtime.enqueue(account.account_id, link_data)
            self._account_drafts[account.account_id] = "\n".join(item[0] for item in link_data)
            self._render_account_queue(account.account_id)
            if added:
                runtime.start_account(account.account_id)
                self.is_running = True
                self.start_btn.setEnabled(False)
                self.add_btn.setEnabled(True)
                self.stop_btn.setEnabled(True)
                self.stop_all_btn.setEnabled(True)
                self.signals.log.emit(
                    f"@{account.expected_username} 대기열에 {added}개 링크를 추가했습니다."
                )
            else:
                show_info(self, "대기열", "새로 추가할 링크가 없습니다.")
            return

        added = 0
        added_items = []
        with self._urls_lock:
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)
                    added += 1
                    added_items.append(item)

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
            if added_items:
                now_text = datetime.now().astimezone().isoformat()
                with self._resume_state_lock:
                    known_urls = {entry.get("url") for entry in self._resume_items}
                    for url, keyword in self._normalize_link_data(added_items):
                        if url in known_urls:
                            continue
                        self._resume_items.append(
                            {
                                "url": url,
                                "keyword": keyword or "",
                                "status": "pending",
                                "product_title": "",
                                "updated_at": now_text,
                                "source": "manual_add",
                            }
                        )
                self._save_resume_state("queue_add")
            self._log_user_activity(
                "queue_add_links_success",
                f"added={added}; queue_size={self.link_queue.qsize()}",
            )
            logger.info("링크 큐 추가 결과: added=%d queue=%d", added, self.link_queue.qsize())
            self._progress_queue_label.setText(f"대기열: {self.link_queue.qsize()}개 준비됨")
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
            "skipped": 0,
            "cancelled": False,
            "details": [],
        }

        total_links = self.link_queue.qsize()
        quota_bypass = self._is_dev_quota_bypass_enabled()

        def log(msg):
            message_text = str(msg or "").strip()
            if not message_text:
                return
            self.signals.log.emit(message_text)
            self.signals.progress.emit(message_text)
            self._log_user_activity("batch_runtime_log", message_text)

        agent = None
        helper = None
        try:
            log(f"업로드 시작 (대기열: {self.link_queue.qsize()})")
            if quota_bypass:
                log("개발자 모드: 작업량 제한 및 차감 동기화를 건너뜁니다.")
            self.signals.status.emit("처리중")

            api_key = str((worker_config or {}).get("api_key") or "")
            profile_dir = str((worker_config or {}).get("profile_dir") or ".threads_profile")

            def close_agent_for_wait():
                nonlocal agent, helper
                if agent is None:
                    return
                try:
                    agent.save_session()
                except Exception:
                    logger.debug("대기 전 Threads 세션 저장 실패", exc_info=True)
                try:
                    agent.close()
                except Exception:
                    logger.debug("대기 전 Threads 브라우저 종료 실패", exc_info=True)
                agent = None
                helper = None

            def ensure_threads_ready() -> bool:
                nonlocal agent, helper
                if agent is not None and helper is not None:
                    return True

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
                    try:
                        login_wait_seconds = int(os.getenv("THREAD_AUTO_LOGIN_WAIT_SECONDS", "60") or "60")
                    except ValueError:
                        login_wait_seconds = 60
                    login_wait_seconds = max(login_wait_seconds, 60)
                    login_wait_steps = max(1, login_wait_seconds // 3)
                    log(f"로그인 대기 시간 설정: {login_wait_seconds}초")
                    log(f"로그인이 필요합니다. {login_wait_seconds}초 안에 로그인해주세요.")
                    for wait_sec in range(login_wait_steps):
                        time.sleep(3)
                        remaining = max(0, login_wait_seconds - (wait_sec * 3))
                        if wait_sec % 3 == 0:
                            log(f"로그인 대기 중... {remaining}초 남음")
                        if helper.check_login_status():
                            log("로그인 확인됨")
                            break
                    else:
                        log(f"{login_wait_seconds}초 내 로그인되지 않아 업로드를 취소합니다.")
                        log(f"로그인 대기 시간 초과: {login_wait_seconds}초")
                        close_agent_for_wait()
                        return False

                log("Threads 로그인 상태 확인 완료")
                return True

            processed_count = 0
            empty_count = 0

            def emit_run_state(
                phase: str,
                message: str = "",
                current_item: str = "",
                *,
                pending: int | None = None,
                completed: int | None = None,
                next_allowed_at=None,
                remaining: int = 0,
            ) -> None:
                pending_count = self.link_queue.qsize() if pending is None else max(0, int(pending))
                total_count = max(total_links, pending_count + max(processed_count - 1, 0))
                completed_count = (
                    max(0, int(completed))
                    if completed is not None
                    else max(0, total_count - pending_count)
                )
                self.signals.run_state.emit(
                    {
                        "phase": phase,
                        "message": message,
                        "current_item": current_item,
                        "pending": pending_count,
                        "total": total_count,
                        "completed": completed_count,
                        "failed": results["failed"] + results["parse_failed"],
                        "next_allowed_at": next_allowed_at,
                        "remaining": remaining,
                    }
                )

            emit_run_state(
                "running",
                f"대기열 {self.link_queue.qsize()}개 실행 중 · {_format_interval(interval)} 간격",
                pending=self.link_queue.qsize(),
                completed=0,
            )
            self._wait_for_resume_interval_if_needed(log, total_links=total_links)

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

                processed_count += 1
                url, keyword = item if isinstance(item, tuple) else (item, None)
                results["total"] += 1
                self._mark_resume_item(url, "running")

                log(f"{processed_count}번째 항목 처리 중 (대기열: {self.link_queue.qsize()})")

                # Update progress
                self.signals.queue_progress.emit(f"전체: {processed_count} / {total_links}")
                current_label = str(keyword or url or "").strip()
                emit_run_state(
                    "processing",
                    "상품 정보 분석 중입니다.",
                    current_label,
                    pending=self.link_queue.qsize() + 1,
                    completed=max(processed_count - 1, 0),
                )

                try:
                    already_uploaded = pipeline_ref.link_history.is_uploaded(url)
                except Exception:
                    logger.exception("업로드 이력 확인에 실패했습니다.")
                    already_uploaded = False
                if already_uploaded:
                    results["skipped"] += 1
                    self._mark_resume_item(url, "skipped", "(중복)")
                    log(f"중복 링크라 건너뜁니다: {str(url)[:40]}...")
                    self.signals.link_status.emit(url, "중복", "이미 업로드됨")
                    results["details"].append(
                        {
                            "product_title": "(중복)",
                            "url": url,
                            "success": False,
                            "skipped": True,
                        }
                    )
                    self.signals.reset_steps.emit()
                    continue

                if not quota_bypass:
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
                            emit_run_state(
                                "blocked",
                                f"작업량 확인 필요: {quota_message}",
                                current_label,
                                pending=self.link_queue.qsize() + 1,
                                completed=max(processed_count - 1, 0),
                            )
                            results["cancelled"] = True
                            break
                    except Exception:
                        logger.exception("업로드 루프에서 작업량 확인 실패")
                        log("작업량 확인 실패로 업로드를 중단합니다.")
                        emit_run_state(
                            "blocked",
                            "작업량 확인 실패로 업로드를 중단했습니다.",
                            current_label,
                            pending=self.link_queue.qsize() + 1,
                            completed=max(processed_count - 1, 0),
                        )
                        results["cancelled"] = True
                        break

                # Step 0: Link analysis
                self.signals.step_update.emit(0, "active")
                self.signals.link_status.emit(url, "진행중", "")

                log("상품 정보 분석 중...")

                external_post_attempted = False
                try:
                    # Step 1: Content generation (parse + AI)
                    self.signals.step_update.emit(0, "done")
                    self.signals.step_update.emit(1, "active")

                    post_data = pipeline_ref.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results["parse_failed"] += 1
                        self._mark_resume_item(url, "parse_failed", error="parse_failed")
                        log("분석 실패로 이 항목을 건너뜁니다.")
                        self.signals.step_update.emit(1, "error")
                        self.signals.link_status.emit(url, "실패", "분석 실패")
                        self.signals.reset_steps.emit()
                        continue

                    results["processed"] += 1
                    product_name = post_data.get("product_title", "")[:30]
                    log(f"분석 완료: {product_name}")
                    self.signals.step_update.emit(1, "done")
                except CancelledException:
                    results["cancelled"] = True
                    log("사용자 요청으로 작업을 중단합니다.")
                    self.signals.reset_steps.emit()
                    break
                except Exception as exc:
                    results["parse_failed"] += 1
                    self._mark_resume_item(url, "parse_failed", error=str(exc))
                    log(f"분석 오류: {str(exc)[:80]}")
                    self.signals.step_update.emit(1, "error")
                    self.signals.link_status.emit(url, "실패", "오류")
                    self.signals.reset_steps.emit()
                    continue

                # Step 2: Upload to Threads
                self.signals.step_update.emit(2, "active")
                log("Threads 게시글 업로드 중...")
                emit_run_state(
                    "uploading",
                    "Threads 게시글 업로드 중입니다.",
                    str(keyword or url or "").strip(),
                    pending=self.link_queue.qsize() + 1,
                    completed=max(processed_count - 1, 0),
                )
                reserved_work_id = str(
                    post_data.get("managed_ai_reservation_id") or ""
                ).strip()
                managed_quota_mode = str(
                    post_data.get("managed_ai_quota_mode") or "reservation"
                ).strip().lower()
                reservation_supported = bool(reserved_work_id) and managed_quota_mode != "legacy"

                try:
                    if not ensure_threads_ready():
                        if reservation_supported and reserved_work_id:
                            try:
                                from src import auth_client
                                auth_client.release_reserved_work(reserved_work_id)
                            except Exception:
                                logger.exception("Threads 확인 실패 후 관리형 AI 예약 해제 실패")
                        results["cancelled"] = True
                        self._mark_resume_item(url, "pending", product_name, "threads_login_required")
                        emit_run_state(
                            "blocked",
                            "Threads 로그인 확인이 필요합니다. 현재 항목은 저장했습니다.",
                            product_name or current_label,
                            pending=self.link_queue.qsize() + 1,
                            completed=max(processed_count - 1, 0),
                        )
                        self.signals.step_update.emit(2, "error")
                        self.signals.link_status.emit(url, "대기", "Threads 확인 필요")
                        break

                    goto_threads_with_fallback(
                        agent.page,
                        path="/",
                        timeout=15000,
                        retries_per_url=1,
                        logger=logger,
                    )
                    time.sleep(2)

                    posts_data = build_product_thread_payload(post_data)

                    # Reserve work token when backend supports atomic quota flow.
                    if not quota_bypass and not reserved_work_id:
                        reservation_request_id = str(
                            getattr(self, "_resume_recovered_idempotency_keys", {}).get(url)
                            or post_data.get("managed_ai_job_id")
                            or hashlib.sha256(
                                f"{url}|{time.time_ns()}".encode("utf-8")
                            ).hexdigest()
                        )
                        self._mark_resume_item(
                            url,
                            "running",
                            product_name,
                            idempotency_key=reservation_request_id,
                        )
                        try:
                            from src import auth_client
                            reserve_result = auth_client.reserve_work(reservation_request_id)
                            if (
                                isinstance(reserve_result, dict)
                                and reserve_result.get("code") == "IDEMPOTENCY_REPLAY"
                                and str(reserve_result.get("reservation_status") or "").lower()
                                in {"released", "expired"}
                            ):
                                # The old attempt is conclusively known not to
                                # have posted. Rotate once before the external
                                # side effect and start a genuinely new attempt.
                                reservation_request_id = hashlib.sha256(
                                    f"{url}|{time.time_ns()}|retry".encode("utf-8")
                                ).hexdigest()
                                self._mark_resume_item(
                                    url,
                                    "running",
                                    product_name,
                                    idempotency_key=reservation_request_id,
                                )
                                reserve_result = auth_client.reserve_work(
                                    reservation_request_id
                                )
                            if isinstance(reserve_result, dict) and reserve_result.get("unsupported"):
                                log("안전한 작업 예약 기능을 사용할 수 없어 업로드를 중단합니다.")
                                emit_run_state(
                                    "blocked",
                                    "안전한 작업 예약 기능을 사용할 수 없습니다.",
                                    product_name or current_label,
                                    pending=self.link_queue.qsize() + 1,
                                    completed=max(processed_count - 1, 0),
                                )
                                results["cancelled"] = True
                                break
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
                                    emit_run_state(
                                        "blocked",
                                        "작업 예약 ID가 없어 안전상 중단했습니다.",
                                        product_name or current_label,
                                        pending=self.link_queue.qsize() + 1,
                                        completed=max(processed_count - 1, 0),
                                    )
                                    results["cancelled"] = True
                                    break
                                self._mark_resume_item(
                                    url,
                                    "running",
                                    product_name,
                                    reservation_id=reserved_work_id,
                                    idempotency_key=reservation_request_id,
                                )
                        except Exception:
                            logger.exception("업로드 루프에서 작업량 예약 실패")
                            log("작업 예약 실패로 업로드를 중단합니다.")
                            emit_run_state(
                                "blocked",
                                "작업 예약 실패로 업로드를 중단했습니다.",
                                product_name or current_label,
                                pending=self.link_queue.qsize() + 1,
                                completed=max(processed_count - 1, 0),
                            )
                            results["cancelled"] = True
                            break

                    # Persist the ambiguous external side-effect boundary before
                    # asking Threads to publish. A crash from this point onward
                    # must never cause an automatic duplicate upload.
                    self._mark_resume_item(
                        url,
                        "posting",
                        product_name,
                        reservation_id=reserved_work_id,
                        idempotency_key=reservation_request_id,
                    )
                    external_post_attempted = True
                    success = helper.create_thread_direct(posts_data)
                    recorded_success = bool(success)
                    stop_for_billing_sync = False
                    pause_for_threads_ui = False
                    helper_error = str(getattr(helper, "last_error", "") or "")
                    if success:
                        if quota_bypass:
                            self._mark_resume_item(url, "completed", product_name)
                            results["uploaded"] += 1
                            log(f"업로드 성공: {product_name}")
                            self.signals.step_update.emit(2, "done")
                            self.signals.step_update.emit(3, "done")
                            self.signals.link_status.emit(url, "완료", product_name)
                        else:
                            if reservation_supported and reserved_work_id:
                                self._mark_resume_item(
                                    url,
                                    "posted_commit_pending",
                                    product_name,
                                    reservation_id=reserved_work_id,
                                )
                            try:
                                from src import auth_client
                                if reservation_supported and reserved_work_id:
                                    use_result = auth_client.commit_reserved_work(reserved_work_id)
                                else:
                                    use_result = auth_client.use_work()
                                if not isinstance(use_result, dict) or not self._is_work_allowed(use_result):
                                    billing_msg = (
                                        use_result.get("message", "알 수 없음")
                                        if isinstance(use_result, dict)
                                        else "알 수 없음"
                                    )
                                    recorded_success = False
                                    stop_for_billing_sync = True
                                    results["failed"] += 1
                                    log(f"작업량 동기화 실패: {billing_msg}. 안전상 업로드를 중단합니다.")
                                    emit_run_state(
                                        "blocked",
                                        f"작업량 동기화 실패: {billing_msg}",
                                        product_name or current_label,
                                        pending=self.link_queue.qsize() + 1,
                                        completed=max(processed_count - 1, 0),
                                    )
                                    self.signals.step_update.emit(3, "error")
                                    self.signals.link_status.emit(url, "실패", f"과금 동기화 실패: {billing_msg}")
                                else:
                                    self._mark_resume_item(url, "completed", product_name)
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
                                emit_run_state(
                                    "blocked",
                                    "작업량 동기화 실패로 안전상 중단했습니다.",
                                    product_name or current_label,
                                    pending=self.link_queue.qsize() + 1,
                                    completed=max(processed_count - 1, 0),
                                )
                                self.signals.step_update.emit(3, "error")
                                self.signals.link_status.emit(url, "실패", "과금 동기화 실패")
                    else:
                        self._mark_resume_item(
                            url,
                            "posting_unknown",
                            product_name,
                            helper_error or "upload_result_unknown",
                            reservation_id=reserved_work_id,
                            idempotency_key=reservation_request_id,
                        )
                        ui_blocker_tokens = (
                            "login_prompt",
                            "login_popup",
                            "compose_button_not_found",
                            "textarea_missing",
                        )
                        if any(token in helper_error for token in ui_blocker_tokens):
                            pause_for_threads_ui = True
                            results["cancelled"] = True
                            blocker = helper_error or "threads_ui_unavailable"
                            self._mark_resume_item(url, "posting_unknown", product_name, blocker)
                            log(f"Threads 로그인/작성창 확인 필요: {blocker}. 현재 항목을 보존하고 중단합니다.")
                            emit_run_state(
                                "blocked",
                                f"Threads 로그인/작성창 확인 필요: {blocker}",
                                product_name or current_label,
                                pending=self.link_queue.qsize() + 1,
                                completed=max(processed_count - 1, 0),
                            )
                            self.signals.step_update.emit(2, "error")
                            self.signals.link_status.emit(url, "대기", "Threads 확인 필요")
                        else:
                            results["failed"] += 1
                            self._mark_resume_item(url, "posting_unknown", product_name, helper_error or "upload_failed")
                            log(f"업로드 실패: {product_name}")
                            self.signals.step_update.emit(2, "error")
                            self.signals.link_status.emit(url, "실패", product_name)

                    try:
                        if success or not pause_for_threads_ui:
                            pipeline_ref.link_history.add_link(url, product_name, success=bool(success))
                    except Exception:
                        logger.exception("업로드 이력 저장에 실패했습니다.")

                    results["details"].append(
                        {
                            "product_title": product_name,
                            "url": url,
                            "success": recorded_success,
                        }
                    )
                    if stop_for_billing_sync or pause_for_threads_ui:
                        results["cancelled"] = True
                        break
                except Exception as exc:
                    if (
                        reservation_supported
                        and reserved_work_id
                        and not external_post_attempted
                    ):
                        try:
                            from src import auth_client
                            auth_client.release_reserved_work(reserved_work_id)
                        except Exception:
                            logger.exception("업로드 예외 처리 중 예약 작업량 해제 실패")
                    exc_text = str(exc)
                    browser_blocker_tokens = (
                        "Target page, context or browser has been closed",
                        "Threads 접속 실패",
                        "browser has been closed",
                        "context has been closed",
                    )
                    if any(token in exc_text for token in browser_blocker_tokens):
                        results["cancelled"] = True
                        self._mark_resume_item(url, "pending", product_name, exc_text)
                        log(f"Threads 브라우저 상태 확인 필요: {exc_text[:120]}. 현재 항목을 보존하고 중단합니다.")
                        emit_run_state(
                            "blocked",
                            f"Threads 브라우저 상태 확인 필요: {exc_text[:120]}",
                            product_name or current_label,
                            pending=self.link_queue.qsize() + 1,
                            completed=max(processed_count - 1, 0),
                        )
                        self.signals.step_update.emit(2, "error")
                        self.signals.link_status.emit(url, "대기", "Threads 확인 필요")
                        break
                    results["failed"] += 1
                    self._mark_resume_item(url, "failed", product_name, exc_text)
                    log(f"업로드 오류: {exc_text[:80]}")
                    self.signals.step_update.emit(2, "error")
                    self.signals.link_status.emit(url, "실패", product_name)

                self.signals.results.emit(results["uploaded"], results["failed"])
                self.signals.reset_steps.emit()

                if not self._stop_event.is_set() and not self.link_queue.empty():
                    next_allowed_at = time.time() + interval
                    self._set_resume_next_allowed_at(next_allowed_at)
                    close_agent_for_wait()
                    log(f"다음 항목까지 {_format_interval(interval)} 대기")
                    for sec in range(interval):
                        if self._stop_event.is_set():
                            results["cancelled"] = True
                            break
                        remaining = interval - sec
                        emit_run_state(
                            "waiting",
                            "다음 예약 업로드까지 대기 중입니다.",
                            "",
                            pending=self.link_queue.qsize(),
                            completed=max(total_links - self.link_queue.qsize(), 0),
                            next_allowed_at=next_allowed_at,
                            remaining=remaining,
                        )
                        if remaining % 60 == 0 and remaining > 0:
                            log(f"대기 중... {_format_interval(remaining)} 남음")
                        time.sleep(1)
                if not self._stop_event.is_set():
                    self._set_resume_next_allowed_at(None)

            log("=" * 40)
            log(
                "작업 종료 - "
                f"성공: {results['uploaded']} / "
                f"실패: {results['failed']} / "
                f"분석 실패: {results['parse_failed']} / "
                f"중복 스킵: {results['skipped']}"
            )

            # 서버에 배치 완료 로그 전송
            try:
                from src import auth_client
                summary = (
                    f"성공: {results['uploaded']}, "
                    f"실패: {results['failed']}, "
                    f"파싱실패: {results['parse_failed']}, "
                    f"중복스킵: {results['skipped']}"
                )
                if results["cancelled"]:
                    auth_client.log_action("batch_cancelled", summary)
                else:
                    auth_client.log_action("batch_complete", summary)
            except Exception:
                pass

            if results["cancelled"]:
                self.signals.status.emit("취소됨")
                emit_run_state(
                    "blocked" if self.link_queue.qsize() else "finished",
                    "작업이 중단되었습니다. 남은 작업은 저장되어 다음 실행 때 이어갈 수 있습니다."
                    if self.link_queue.qsize()
                    else "작업이 취소되었습니다.",
                    pending=self.link_queue.qsize(),
                    completed=max(total_links - self.link_queue.qsize(), 0),
                )
            else:
                self.signals.status.emit("완료")
                emit_run_state(
                    "finished",
                    "대기열 작업이 완료되었습니다.",
                    pending=0,
                    completed=total_links,
                )

            self.signals.finished.emit(results)

        except Exception as exc:
            logger.exception("_run_upload_queue에서 치명적 오류 발생")
            log(f"치명적 오류: {exc}")
            self.signals.status.emit("오류")
            self.signals.run_state.emit(
                {
                    "phase": "error",
                    "message": f"치명적 오류: {str(exc)[:120]}",
                    "pending": self.link_queue.qsize(),
                    "total": total_links,
                    "completed": max(total_links - self.link_queue.qsize(), 0),
                    "failed": results["failed"] + results["parse_failed"],
                }
            )
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
        runtime = getattr(self, "_multi_account_runtime", None)
        account_id = self.selected_threads_account_id()
        if runtime is not None and account_id:
            try:
                schedule = runtime.snapshot(account_id).get("schedule")
            except KeyError:
                schedule = None
            if schedule is not None and (
                getattr(schedule, "running", False)
                or getattr(schedule, "enabled", False)
            ):
                runtime.stop_account(account_id)
                if getattr(schedule, "running", False):
                    self.pipeline.cancel()
                self.signals.log.emit("선택한 계정의 대기열 중지를 요청했습니다.")
                self.signals.status.emit("중지중...")
                self.stop_btn.setEnabled(False)
                return
        if self.is_running:
            self.signals.log.emit("중지 요청됨. 현재 항목 처리 후 중단합니다.")
            self.signals.status.emit("중지중...")
            self.status_badge.update_style(Colors.WARNING, "중지중")
            self._relayout_header_account_card()
            self._sidebar_status_label.setText("중지중...")
            self._save_resume_state("user_stop")
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
        """Start a server heartbeat without blocking Qt's event loop."""
        if self._redirecting_to_login or self._closed:
            return
        if os.getenv("THREAD_AUTO_DISABLE_HEARTBEAT", "").strip() == "1":
            self._apply_heartbeat_result({"state": "disabled"})
            return

        # A slow request here used to make typing and button clicks freeze.
        if self._heartbeat_in_flight:
            return
        self._heartbeat_in_flight = True
        task = "uploading" if self.is_running else "idle"
        threading.Thread(
            target=self._heartbeat_worker,
            args=(task,),
            daemon=True,
            name="server-heartbeat-worker",
        ).start()

    def _heartbeat_worker(self, task: str) -> None:
        """Run the blocking server heartbeat away from the Qt event loop."""
        try:
            from src import auth_client

            if not auth_client.is_logged_in():
                payload = {"state": "logged_out"}
            else:
                payload = {
                    "state": "complete",
                    "result": auth_client.refresh_account_state(
                        current_task=task,
                        app_version=self._app_version,
                    ),
                }
        except Exception as exc:
            logger.exception("Heartbeat worker failed")
            payload = {"state": "error", "error": str(exc)}

        try:
            self.signals.heartbeat_complete.emit(payload)
        except RuntimeError:
            # The window may have been destroyed while the request was running.
            pass

    def _apply_heartbeat_result(self, payload: object) -> None:
        """Apply heartbeat state on the Qt thread after the worker completes."""
        self._heartbeat_in_flight = False
        if self._closed or self._redirecting_to_login:
            return

        data = payload if isinstance(payload, dict) else {}
        state = data.get("state")
        if state == "disabled":
            self._online_dot.setStyleSheet(
                f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
            )
            self._connection_label.setText("로컬 실행")
            self._connection_label.setStyleSheet(
                f"color: {Colors.SUCCESS}; font-size: 8pt; font-weight: 700; background: transparent;"
            )
            self._server_label.setText("서버 연결: 로컬 모드")
            if not self.is_running:
                self.status_label.setText("로컬 실행")
            return

        if state == "logged_out":
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
                # Set the guard before any window transition. Queued heartbeat
                # results can otherwise enter a nested modal loop repeatedly.
                self._session_expiry_notified = True
                self._redirect_to_login_window("로그인 세션이 만료되었습니다. 다시 로그인해 주세요.")
            return

        result = data.get("result") if state == "complete" else None
        if isinstance(result, dict):
            self._update_account_display()
            self._refresh_threads_account_ui(self.selected_threads_account_id())

        if isinstance(result, dict) and result.get("status") is True:
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
            return

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
            # The server already reported this session as invalid. Clear the
            # local token immediately instead of blocking the UI on logout I/O.
            auth_client.clear_local_session()
        except Exception:
            logger.debug("세션 만료 복귀 중 로컬 세션 정리에 실패했습니다.", exc_info=True)

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
        """Open the update center and use the same safe installation path."""
        if isinstance(self._pending_update_info, dict):
            self._activate_pending_update()
            return
        logger.info("Manual update check requested")
        self._show_update_dialog(None)

    def _check_for_updates_silent(self):
        """Check for updates without blocking text entry or paint events."""
        if os.getenv("THREAD_AUTO_DISABLE_AUTO_UPDATE", "").strip() == "1":
            logger.info("Automatic update check disabled by environment")
            return
        if self._update_check_in_flight:
            return

        self._update_check_in_flight = True
        threading.Thread(
            target=self._update_check_worker,
            daemon=True,
            name="update-check-worker",
        ).start()


    def _update_check_worker(self) -> None:
        """Check for updates without blocking text entry or paint events."""
        try:
            from src.auto_updater import AutoUpdater

            update_info = AutoUpdater(self._app_version).check_for_updates()
            payload = {"update_info": update_info}
        except Exception as exc:
            logger.exception("Background update check failed")
            payload = {"error": str(exc)}

        try:
            self.signals.update_check_complete.emit(payload)
        except RuntimeError:
            pass

    def _apply_update_check_result(self, payload: object) -> None:
        self._update_check_in_flight = False
        if self._closed:
            return

        data = payload if isinstance(payload, dict) else {}
        update_info = data.get("update_info")
        if not isinstance(update_info, dict) or not update_info:
            return

        version_text = str(update_info.get("version", "") or "").strip()
        self._pending_update_info = dict(update_info)
        self.update_btn.setText(f"업데이트 {version_text}" if version_text else "업데이트")
        self.update_btn.setVisible(True)
        self.update_btn.setEnabled(not self._update_installing)
        self._relayout_header_account_card()
        logger.info("Update available (version=%s)", version_text)
        self._maybe_show_update_notice()

    def _has_active_update_work(self) -> bool:
        runtime = getattr(self, "_multi_account_runtime", None)
        return bool(self.is_running or (runtime is not None and runtime.is_running))

    def _activate_pending_update(self) -> None:
        update_info = self._pending_update_info
        if not isinstance(update_info, dict):
            self._show_update_dialog(None)
            return
        self._show_update_dialog(update_info)

    def _maybe_show_update_notice(self) -> None:
        """Offer each new version once, after active uploads become idle."""
        update_info = self._pending_update_info
        if not isinstance(update_info, dict) or self._has_active_update_work():
            return
        version = str(update_info.get("version", "") or "").strip()
        if version and version == self._update_notice_version:
            return
        self._update_notice_version = version or "unknown"
        self._show_update_dialog(update_info)

    def _show_update_dialog(self, update_info=None) -> None:
        existing = getattr(self, "_update_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        dialog = UpdateDialog(
            self._app_version,
            self,
            update_info=update_info if isinstance(update_info, dict) else None,
        )
        dialog.install_requested.connect(self._start_update_from_dialog)
        dialog.finished.connect(
            lambda _result, current=dialog: self._release_update_dialog(current)
        )
        self._update_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _release_update_dialog(self, dialog) -> None:
        if getattr(self, "_update_dialog", None) is dialog:
            self._update_dialog = None

    def _start_update_from_dialog(self, update_info: object) -> None:
        if not isinstance(update_info, dict):
            return
        active = self._has_active_update_work()
        if active and not ask_yes_no(
            self,
            "작업을 저장하고 업데이트",
            (
                "현재 작업을 안전하게 저장하고 중단한 뒤 업데이트합니다.\n"
                "프로그램이 다시 실행되면 남은 작업도 자동으로 이어집니다.\n\n"
                "지금 업데이트할까요?"
            ),
        ):
            dialog = getattr(self, "_update_dialog", None)
            if dialog is not None:
                dialog.set_install_error(
                    "현재 작업이 끝난 뒤 상단 업데이트 버튼에서 다시 시작할 수 있습니다."
                )
            return
        self._run_auto_update_flow(update_info, resume_after=active)

    def _prepare_update_resume(self, update_info: dict) -> dict:
        runtime = getattr(self, "_multi_account_runtime", None)
        account_ids = active_account_ids(runtime.snapshots()) if runtime is not None else []
        marker = self._update_resume_store.save(
            str(update_info.get("version") or ""),
            account_ids,
            legacy_running=bool(self.is_running and not account_ids),
        )
        self._save_resume_state("app_update")
        if runtime is not None:
            runtime.stop_all()
        try:
            self.pipeline.cancel()
        except Exception:
            logger.debug("Pipeline cancellation during update failed", exc_info=True)
        self.is_running = False
        self.signals.status.emit("업데이트를 위해 작업을 안전하게 중지하는 중")
        self.signals.log.emit("업데이트 후 자동 재개를 위해 현재 대기열을 저장했습니다.")
        return marker

    def _run_auto_update_flow(self, update_info: dict, *, resume_after: bool):
        """Download and launch a verified update, preserving active queue state."""
        if not isinstance(update_info, dict) or not update_info or self._update_installing:
            return
        self._update_installing = True
        self.update_btn.setEnabled(False)
        try:
            marker = self._prepare_update_resume(update_info) if resume_after else None
        except Exception as exc:
            logger.exception("Failed to preserve work before update")
            self._update_installing = False
            self.update_btn.setEnabled(True)
            saved_marker = self._update_resume_store.load()
            if saved_marker:
                self._resume_update_work(saved_marker)
            message = f"현재 작업을 안전하게 저장하지 못해 업데이트를 시작하지 않았습니다.\n{exc}"
            dialog = getattr(self, "_update_dialog", None)
            if dialog is not None:
                dialog.set_install_error(message)
            else:
                show_error(self, "업데이트 준비 실패", message)
            return

        def worker():
            result = {"success": False, "resume_marker": marker, "message": "업데이트에 실패했습니다."}
            try:
                from src.auto_updater import AutoUpdater

                runtime = getattr(self, "_multi_account_runtime", None)
                if runtime is not None and not runtime.stop_and_join(30):
                    raise RuntimeError("작업 중단이 완료되지 않아 업데이트를 취소했습니다.")

                updater = AutoUpdater(self._app_version)
                update_file = updater.download_update(
                    update_info,
                    progress_callback=lambda percent: self.signals.update_install_progress.emit(
                        {"stage": "downloading", "percent": percent}
                    ),
                )
                if not update_file:
                    raise RuntimeError("검증된 업데이트 파일을 내려받지 못했습니다.")
                self.signals.update_install_progress.emit({"stage": "installing"})
                if not updater.install_update(
                    update_file,
                    expected_sha256=str(update_info.get("expected_sha256", "") or ""),
                    asset_name=str(update_info.get("asset_name", "") or ""),
                ):
                    raise RuntimeError("업데이트 설치 프로그램을 시작하지 못했습니다.")
                result = {"success": True, "resume_marker": marker}
            except Exception as exc:
                logger.exception("Automatic update flow failed")
                result["message"] = str(exc) or result["message"]
            try:
                self.signals.update_install_complete.emit(result)
            except RuntimeError:
                pass

        threading.Thread(target=worker, daemon=True, name="auto-update-worker").start()

    def _apply_update_install_progress(self, payload: object) -> None:
        dialog = getattr(self, "_update_dialog", None)
        if dialog is None:
            return
        data = payload if isinstance(payload, dict) else {}
        if data.get("stage") == "installing":
            dialog.set_installing()
        else:
            dialog.set_download_progress(data.get("percent", 0))

    def _apply_update_install_result(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        if data.get("success"):
            logger.info("Verified update runner started; exiting without logout")
            self._force_close_for_update = True
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        self._update_installing = False
        self.update_btn.setEnabled(True)
        if data.get("resume_marker"):
            self._resume_update_work_when_ready(data.get("resume_marker"))
        message = str(data.get("message") or "잠시 후 다시 시도해 주세요.")
        dialog = getattr(self, "_update_dialog", None)
        if dialog is not None:
            dialog.set_install_error(message)
        else:
            show_error(self, "업데이트 실패", message)

    def _resume_update_work_when_ready(self, marker: dict, retries: int = 120) -> bool:
        """Resume only after the previous upload worker has fully exited."""
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None and bool(getattr(runtime, "is_running", False)):
            if retries <= 0:
                show_warning(
                    self,
                    "작업 재개 대기",
                    "기존 작업의 종료가 지연되어 재개 정보를 보존했습니다. 프로그램을 다시 실행하면 자동으로 이어집니다.",
                )
                return False
            QTimer.singleShot(
                1000,
                lambda: self._resume_update_work_when_ready(marker, retries - 1),
            )
            return False
        return self._resume_update_work(marker)

    def _resume_after_completed_update(self) -> None:
        marker = self._update_resume_store.load()
        if not marker:
            return
        completed = update_completed(self._app_version, marker.get("target_version"))
        self._resume_update_work(marker)
        if not completed:
            show_warning(
                self,
                "업데이트 재시도 필요",
                "업데이트가 완료되지 않아 기존 버전으로 작업을 이어갑니다. 상단 업데이트 버튼이 표시되면 다시 시도해 주세요.",
            )

    def _resume_update_work(self, marker: dict) -> bool:
        if not isinstance(marker, dict):
            return False
        started = []
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None and bool(getattr(runtime, "is_running", False)):
            return False
        try:
            if runtime is not None:
                runtime.refresh_accounts()
                selected_provider = normalize_ai_provider(getattr(config, "ai_provider", ""))
                api_key = self._resolve_runtime_gemini_api_key(validate=True) if selected_provider == AI_PROVIDER_GEMINI else ""
                self._configure_multi_account_pipeline(selected_provider, api_key)
                allowed_ids = {
                    account.account_id
                    for account in self._threads_accounts()[: self._threads_account_limit()]
                }
                for account_id in marker.get("account_ids") or []:
                    if account_id not in allowed_ids:
                        continue
                    snapshot = runtime.snapshot(account_id)
                    if snapshot.get("current_item") or snapshot.get("pending_items"):
                        runtime.start_account(account_id)
                        started.append(account_id)
            if marker.get("legacy_running") and not started:
                state = self._load_resume_state_file()
                pending = self._resume_pending_link_data(state)
                if pending and self.start_link_data_batch(
                    pending,
                    interval=max(int(state.get("interval") or config.upload_interval or 60), 30),
                    source="update_resume",
                    next_allowed_at=state.get("next_allowed_at"),
                ):
                    self._archive_legacy_resume_state()
                    started.append("legacy")
            if started:
                self.is_running = True
                self.signals.log.emit("업데이트가 완료되어 남은 작업을 자동으로 이어갑니다.")
                self.signals.status.emit("업데이트 완료 · 작업 자동 재개")
        except Exception:
            logger.exception("Failed to resume work after update")
            show_warning(
                self,
                "작업 재개 확인",
                "저장된 작업의 자동 재개에 실패했습니다. 재개 정보는 보존했으니 프로그램을 다시 실행하거나 대기열에서 시작해 주세요.",
            )
            return False
        self._update_resume_store.clear()
        return True

    def open_tutorial(self):
        """Show help beside the controls instead of opening a new window."""
        logger.info("인라인 도움말 열기 호출")
        self.toggle_inline_help(True)

    # ────────────────────────────────────────────────────────
    #  EVENTS
    # ────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not config.tutorial_shown:
            config.tutorial_shown = True
            config.save()
            QTimer.singleShot(0, lambda: self.toggle_inline_help(True))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_pages"):
            self._relayout_main_window()

    def paintEvent(self, event):
        """메인 윈도우 하단 강조 라인."""
        super().paintEvent(event)
        painter = QPainter(self)
        w, h = self.width(), self.height()
        bot_grad = QLinearGradient(0, 0, w, 0)
        bot_grad.setColorAt(0, QColor(45, 212, 191, 0))
        bot_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        bot_grad.setColorAt(0.7, QColor(Colors.ACCENT))
        bot_grad.setColorAt(1, QColor(45, 212, 191, 0))
        painter.fillRect(0, h - 2, w, 2, bot_grad)

    def closeEvent(self, event):
        """윈도우 종료 시 로그아웃 처리."""
        logger.info("종료 이벤트 호출; is_running=%s", self.is_running)
        forced_relogin = bool(getattr(self, "_force_close_for_relogin", False))
        forced_update = bool(getattr(self, "_force_close_for_update", False))
        self._log_user_activity(
            "ui_window_closing",
            f"forced_relogin={forced_relogin}; forced_update={forced_update}; is_running={self.is_running}",
        )

        if self.is_running and not (forced_relogin or forced_update):
            if not ask_yes_no(
                self,
                "종료 확인",
                "작업이 진행 중입니다. 정말 종료하시겠습니까?",
            ):
                event.ignore()
                return
            self.stop_upload()
        elif self.is_running and (forced_relogin or forced_update):
            self.stop_upload()
        runtime = getattr(self, "_multi_account_runtime", None)
        if runtime is not None:
            runtime.stop_all()
        self._save_resume_state("window_close")
        self._closed = True
        self._browser_cancel.set()
        try:
            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer is not None:
                self._heartbeat_timer.stop()
        except Exception:
            logger.exception("하트비트 타이머 중지 실패")

        if not (forced_relogin or forced_update):
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
        if not (forced_relogin or forced_update):
            # The hidden login window is still a top-level Qt window. Closing
            # only the main window therefore leaves pythonw.exe alive forever
            # unless the application event loop is ended explicitly.
            app = QApplication.instance()
            if app is not None:
                app.quit()
