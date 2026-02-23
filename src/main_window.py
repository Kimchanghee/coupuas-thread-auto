# -*- coding: utf-8 -*-
"""
쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (PyQt6)
Stitch Blue 디자인 - 사이드바 + 스택 페이지 레이아웃
좌표 기반 배치 (setGeometry), 레이아웃 매니저 없음
"""
import re
import html
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
from src.theme import (Colors, Typography, Radius, Gradients,
                       global_stylesheet, badge_style, stat_card_style,
                       terminal_text_style,
                       muted_text_style,
                       hint_text_style, section_title_style)
from src.ui_messages import ask_yes_no, show_error, show_info, show_warning
from src.events import LoginStatusEvent

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
        ("◈", "링크 입력"),
        ("⬆", "업로드 설정"),
        ("⚙", "설정"),
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
        title_label = QLabel("쿠팡 파트너스", header)
        title_label.setGeometry(62, 10, 220, 30)
        title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 15pt; font-weight: 800;"
            " letter-spacing: -0.5px; background: transparent;"
        )

        # Subtitle
        sub_label = QLabel("THREAD AUTOMATION", header)
        sub_label.setGeometry(62, 38, 200, 20)
        sub_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 700;"
            " letter-spacing: 2px; background: transparent;"
        )

        # Right-side elements (positioned from right edge)
        _nav_pill_style = (
            f"QPushButton {{ background: rgba(13, 89, 242, 0.08);"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid rgba(13, 89, 242, 0.15);"
            f" border-radius: 14px; font-size: 9pt; font-weight: 600;"
            f" padding: 4px 12px; }}"
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

        # Update button
        self.update_btn = QPushButton("업데이트", header)
        self.update_btn.setGeometry(WIN_W - 80 - 12 - 56 - 10 - 60, 20, 60, 28)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet(_nav_pill_style)
        self.update_btn.clicked.connect(self.check_for_updates)

        # Re-place header pills by sizeHint to avoid text clipping across fonts
        nav_y = 20
        nav_h = 28
        nav_gap = 10
        nav_right = WIN_W - 16
        for btn in (self.logout_btn, self.tutorial_btn, self.update_btn):
            btn.ensurePolished()
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(nav_h)
            # Add a bit of slack to avoid left/right clipping when font rendering differs.
            text_w = btn.fontMetrics().horizontalAdvance(btn.text())
            w = max(btn.sizeHint().width() + 16, text_w + 30, 68)
            nav_right -= w
            btn.setGeometry(nav_right, nav_y, w, nav_h)
            nav_right -= nav_gap


        # ── Account info card (compact horizontal bar) ──
        acct_card = QWidget(header)
        acct_card.setObjectName("acctInfoCard")
        acct_card.setStyleSheet(f"""
            QWidget#acctInfoCard {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 14px;
            }}
        """)

        # Card inner elements
        cx = 12  # left padding inside card

        # Online dot
        self._online_dot = QLabel("", acct_card)
        self._online_dot.setGeometry(cx, 9, 10, 10)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px;"
        )
        cx += 16

        # Status badge (compact text inside card)
        self.status_badge = Badge("대기중", Colors.SUCCESS, acct_card)
        self.status_badge.setGeometry(cx, 2, 70, 24)
        cx += 74

        # Separator 1
        sep1 = QFrame(acct_card)
        sep1.setGeometry(cx, 6, 1, 16)
        sep1.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self._acct_sep1 = sep1
        cx += 10

        # Plan badge (FREE / PRO)
        self._plan_badge = QLabel("FREE", acct_card)
        self._plan_badge.setGeometry(cx, 3, 52, 22)
        self._plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._plan_badge.setStyleSheet(
            f"QLabel {{ background-color: rgba(34, 197, 94, 0.12);"
            f" color: {Colors.SUCCESS}; border: 1px solid rgba(34, 197, 94, 0.3);"
            f" border-radius: 11px; font-size: 8pt; font-weight: 700;"
            f" letter-spacing: 1px; }}"
        )
        cx += 58

        # Separator 2
        sep2 = QFrame(acct_card)
        sep2.setGeometry(cx, 6, 1, 16)
        sep2.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self._acct_sep2 = sep2
        cx += 10

        # Work count label
        self._work_label = QLabel("0 / 0 회", acct_card)
        self._work_label.setGeometry(cx, 0, 90, 28)
        self._work_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._work_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent; border: none;"
        )
        cx += 90 + 10  # right padding

        # Position the card to the left of nav buttons
        card_w = cx
        card_x = nav_right - 4 - card_w
        acct_card.setGeometry(card_x, 20, card_w, 28)
        self._acct_info_card = acct_card
        self._header_nav_buttons = (self.logout_btn, self.tutorial_btn, self.update_btn)
        self._relayout_header_account_card()

        self._header = header
        self._brand_icon = brand_icon

    def _relayout_header_account_card(self):
        """Resize/reposition account card to prevent right-top clipping."""
        if not hasattr(self, "_acct_info_card"):
            return

        nav_buttons = getattr(self, "_header_nav_buttons", ())
        nav_left = min((btn.x() for btn in nav_buttons), default=WIN_W - 16)
        min_card_x = 340  # keep safe distance from brand title zone

        card = self._acct_info_card
        cx = 12

        if hasattr(self, "_online_dot"):
            self._online_dot.setGeometry(cx, 9, 10, 10)
        cx += 16

        status_w = max(self.status_badge.sizeHint().width() + 10, 70)
        self.status_badge.setGeometry(cx, 2, status_w, 24)
        cx += status_w + 4

        self._acct_sep1.setGeometry(cx, 6, 1, 16)
        cx += 10

        plan_w = max(
            self._plan_badge.fontMetrics().horizontalAdvance(self._plan_badge.text()) + 20,
            52
        )
        self._plan_badge.setGeometry(cx, 3, plan_w, 22)
        cx += plan_w + 6

        self._acct_sep2.setGeometry(cx, 6, 1, 16)
        cx += 10

        work_text = self._work_label.text() or "0 / 0 회"
        work_w = max(self._work_label.fontMetrics().horizontalAdvance(work_text) + 16, 90)
        status_min_w = 58
        plan_min_w = 46
        work_min_w = 64

        fixed_w = 12 + 16 + 4 + 10 + 6 + 10 + 10  # paddings + separators + gaps
        dynamic_w = status_w + plan_w + work_w
        desired_card_w = fixed_w + dynamic_w
        max_card_w = max(nav_left - 12 - min_card_x, fixed_w + status_min_w + plan_min_w + work_min_w)

        if desired_card_w > max_card_w:
            overflow = desired_card_w - max_card_w

            reduce_work = min(max(work_w - work_min_w, 0), overflow)
            work_w -= reduce_work
            overflow -= reduce_work

            if overflow > 0:
                reduce_status = min(max(status_w - status_min_w, 0), overflow)
                status_w -= reduce_status
                overflow -= reduce_status
                self.status_badge.setGeometry(28, 2, status_w, 24)

            if overflow > 0:
                reduce_plan = min(max(plan_w - plan_min_w, 0), overflow)
                plan_w -= reduce_plan
                overflow -= reduce_plan
                self._plan_badge.setGeometry(0, 3, plan_w, 22)

        # Rebuild positions after any width compression.
        cx = 12
        if hasattr(self, "_online_dot"):
            self._online_dot.setGeometry(cx, 9, 10, 10)
        cx += 16

        self.status_badge.setGeometry(cx, 2, status_w, 24)
        cx += status_w + 4

        self._acct_sep1.setGeometry(cx, 6, 1, 16)
        cx += 10

        self._plan_badge.setGeometry(cx, 3, plan_w, 22)
        cx += plan_w + 6

        self._acct_sep2.setGeometry(cx, 6, 1, 16)
        cx += 10

        self._work_label.setGeometry(cx, 0, work_w, 28)
        self._work_label.setToolTip(work_text)
        cx += work_w + 10

        card_w = cx
        card_x = max(min_card_x, nav_left - 12 - card_w)
        card.setGeometry(card_x, 20, card_w, 28)

    # ── Sidebar ─────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sidebar = SidebarPanel(parent)
        sidebar.setGeometry(0, HEADER_H, SIDEBAR_W, WIN_H - HEADER_H)
        self._sidebar = sidebar

        # Button group for exclusive selection
        self._sidebar_group = QButtonGroup(self)
        self._sidebar_group.setExclusive(True)
        self._sidebar_buttons = []

        for i, (icon, label) in enumerate(self._SIDEBAR_ITEMS):
            btn = QPushButton(f"  {icon}   {label}", sidebar)
            btn.setGeometry(0, 20 + i * 48, SIDEBAR_W, 44)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_style())
            self._sidebar_group.addButton(btn, i)
            self._sidebar_buttons.append(btn)

        self._sidebar_buttons[0].setChecked(True)
        self._sidebar_group.idClicked.connect(self._switch_page)

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
        coupang_link = QLabel(
            '<a href="https://partners.coupang.com/" '
            'style="color: #3B7BFF; text-decoration: none; font-weight: 600;">'
            '쿠팡 파트너스 바로가기 →</a>',
            page
        )
        coupang_link.setGeometry(CONTENT_W - 28 - 220, 28, 220, 24)
        coupang_link.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        coupang_link.setOpenExternalLinks(True)
        coupang_link.setStyleSheet("background: transparent;")

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

        _field_lbl_style = (
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Scroll area for settings content
        scroll = QScrollArea(page)
        scroll.setGeometry(0, cy, CONTENT_W, CONTENT_H - cy)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
        )

        content = QWidget()
        content.setFixedWidth(CONTENT_W)
        scroll.setWidget(content)

        sy = 8  # y offset within scroll content

        # ── Section 1: 계정 정보 ───────────────────────────
        acct = SectionFrame(content)
        acct.setGeometry(28, sy, 944, 80)

        # User icon circle
        acct_icon = QLabel("U", acct)
        acct_icon.setGeometry(20, 20, 40, 40)
        acct_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acct_icon.setStyleSheet(
            f"QLabel {{ background: {Gradients.ACCENT_BTN}; color: #FFFFFF;"
            f" border-radius: 20px; font-size: 14pt; font-weight: 700; }}"
        )

        self._acct_username_label = QLabel("사용자", acct)
        self._acct_username_label.setGeometry(72, 16, 300, 22)
        self._acct_username_label.setStyleSheet(
            "color: #FFFFFF; font-size: 11pt; font-weight: 700; background: transparent;"
        )

        self._acct_status_label = QLabel("활성 계정", acct)
        self._acct_status_label.setGeometry(72, 40, 300, 18)
        self._acct_status_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        # Plan badge (right side)
        self._acct_plan_badge = QLabel("무료 체험", acct)
        self._acct_plan_badge.setGeometry(780, 16, 140, 26)
        self._acct_plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_plan_badge.setStyleSheet(
            f"QLabel {{ background-color: rgba(34, 197, 94, 0.12);"
            f" color: {Colors.SUCCESS}; border: 1px solid rgba(34, 197, 94, 0.3);"
            f" border-radius: 13px; font-size: 9pt; font-weight: 700; }}"
        )

        self._acct_work_label = QLabel("0 / 0 회 사용", acct)
        self._acct_work_label.setGeometry(780, 46, 140, 18)
        self._acct_work_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_work_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        sy += 92

        # ── Section 2: Threads 계정 ────────────────────────
        threads_sec = SectionFrame(content)
        threads_sec.setGeometry(28, sy, 944, 200)

        threads_title = QLabel("Threads 계정", threads_sec)
        threads_title.setGeometry(24, 12, 200, 22)
        threads_title.setStyleSheet(section_title_style())

        name_label = QLabel("계정 이름", threads_sec)
        name_label.setGeometry(24, 40, 100, 20)
        name_label.setStyleSheet(_field_lbl_style)

        name_hint = QLabel("프로필 식별용", threads_sec)
        name_hint.setGeometry(130, 40, 200, 20)
        name_hint.setStyleSheet(hint_text_style())

        self.username_edit = QLineEdit(threads_sec)
        self.username_edit.setGeometry(24, 64, 896, 34)
        self.username_edit.setPlaceholderText("예: myaccount")

        # Status dot + label
        self._threads_status_dot = QLabel("", threads_sec)
        self._threads_status_dot.setGeometry(24, 112, 10, 10)
        self._threads_status_dot.setStyleSheet(
            f"background-color: {Colors.TEXT_MUTED}; border-radius: 5px;"
        )

        self.login_status_label = QLabel("연결 안됨", threads_sec)
        self.login_status_label.setGeometry(42, 108, 300, 20)
        self.login_status_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Threads login button
        self.threads_login_btn = QPushButton("Threads 로그인", threads_sec)
        self.threads_login_btn.setGeometry(24, 140, 200, 38)
        self.threads_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)

        # Check login button
        self.check_login_btn = QPushButton("상태 확인", threads_sec)
        self.check_login_btn.setGeometry(234, 140, 160, 38)
        self.check_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_login_btn.setProperty("class", "ghost")
        self.check_login_btn.clicked.connect(self._check_login_status)

        hint_label = QLabel("로그인 후 브라우저를 닫으면 세션이 자동 저장됩니다.", threads_sec)
        hint_label.setGeometry(24, 180, 600, 16)
        hint_label.setStyleSheet(hint_text_style())

        sy += 212

        # ── Section 3: API 설정 ────────────────────────────
        api_sec = SectionFrame(content)
        api_sec.setGeometry(28, sy, 944, 100)

        api_title = QLabel("API 설정", api_sec)
        api_title.setGeometry(24, 12, 200, 22)
        api_title.setStyleSheet(section_title_style())

        api_label = QLabel("마스터 API 키", api_sec)
        api_label.setGeometry(24, 38, 200, 16)
        api_label.setStyleSheet(_field_lbl_style)

        api_hint = QLabel("Google AI Studio에서 발급", api_sec)
        api_hint.setGeometry(150, 38, 300, 16)
        api_hint.setStyleSheet(hint_text_style())

        self.gemini_key_edit = QLineEdit(api_sec)
        self.gemini_key_edit.setGeometry(24, 58, 896, 34)
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("Gemini API 키를 입력하세요")

        sy += 112

        # ── Section 4: 보안 설정 ───────────────────────────
        security_sec = SectionFrame(content)
        security_sec.setGeometry(28, sy, 944, 110)

        security_title = QLabel("보안 설정", security_sec)
        security_title.setGeometry(24, 12, 200, 22)
        security_title.setStyleSheet(section_title_style())

        self.allow_ai_fallback_check = QCheckBox("업로드 실패 시 AI 대체 업로드 허용", security_sec)
        self.allow_ai_fallback_check.setGeometry(24, 44, 360, 22)

        security_hint = QLabel(
            "비활성화 시 직접 업로드 실패를 즉시 실패로 처리합니다.",
            security_sec,
        )
        security_hint.setGeometry(24, 72, 520, 16)
        security_hint.setStyleSheet(hint_text_style())

        sy += 122

        # ── Section 5: 앱 정보 ─────────────────────────────
        info_sec = SectionFrame(content)
        info_sec.setGeometry(28, sy, 944, 80)

        info_title = QLabel("앱 정보", info_sec)
        info_title.setGeometry(24, 12, 200, 22)
        info_title.setStyleSheet(section_title_style())

        self._version_label = QLabel("", info_sec)
        self._version_label.setGeometry(24, 40, 300, 18)
        self._version_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        dev_label = QLabel("개발: 쿠팡 파트너스 자동화 팀", info_sec)
        dev_label.setGeometry(24, 58, 400, 16)
        dev_label.setStyleSheet(hint_text_style())

        sy += 92

        # ── Section 6: 튜토리얼 ────────────────────────────
        tutorial_sec = SectionFrame(content)
        tutorial_sec.setGeometry(28, sy, 944, 82)

        tutorial_title = QLabel("튜토리얼", tutorial_sec)
        tutorial_title.setGeometry(24, 12, 200, 22)
        tutorial_title.setStyleSheet(section_title_style())

        self._tutorial_settings_btn = QPushButton("튜토리얼 재실행", tutorial_sec)
        self._tutorial_settings_btn.setGeometry(24, 40, 180, 34)
        self._tutorial_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutorial_settings_btn.setProperty("class", "ghost")
        self._tutorial_settings_btn.clicked.connect(self.open_tutorial)

        sy += 82

        # ── Section 7: 문의하기 ────────────────────────────
        contact_sec = SectionFrame(content)
        contact_sec.setGeometry(28, sy, 944, 82)

        contact_title = QLabel("문의하기", contact_sec)
        contact_title.setGeometry(24, 12, 200, 22)
        contact_title.setStyleSheet(section_title_style())

        self._contact_btn = QPushButton("문의하기", contact_sec)
        self._contact_btn.setGeometry(24, 40, 140, 34)
        self._contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._contact_btn.setProperty("class", "ghost")
        self._contact_btn.clicked.connect(self._open_contact)

        contact_desc = QLabel("이용 중 문의사항은 아래 버튼을 통해 연락주세요.", contact_sec)
        contact_desc.setGeometry(180, 40, 500, 16)
        contact_desc.setStyleSheet(hint_text_style())

        sy += 82

        # ── Action Buttons Row ─────────────────────────────
        self._update_settings_btn = QPushButton("업데이트 확인", content)
        self._update_settings_btn.setGeometry(28, sy, 150, 42)
        self._update_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_settings_btn.setProperty("class", "ghost")
        self._update_settings_btn.clicked.connect(self.check_for_updates)

        # Save button (accent, right-aligned)
        self._settings_save_btn = QPushButton("저장", content)
        self._settings_save_btn.setGeometry(832, sy, 140, 42)
        self._settings_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_save_btn.clicked.connect(self._save_settings)

        sy += 60

        # Set scroll content height
        content.setFixedHeight(sy + 20)

    # ── StatusBar ───────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = QFrame(parent)
        bar.setGeometry(0, WIN_H - STATUSBAR_H, WIN_W, STATUSBAR_H)
        bar.setStyleSheet(
            f"QFrame {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 #12203A, stop:0.5 #162847, stop:1 #12203A);"
            f"  border-top: 2px solid rgba(13, 89, 242, 0.3);"
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

    def _switch_page(self, index):
        """Show selected page, hide others. Also sync sidebar button."""
        for i, page in enumerate(self._pages):
            page.setVisible(i == index)
        self._current_page = index
        if hasattr(self, '_sidebar_buttons') and 0 <= index < len(self._sidebar_buttons):
            self._sidebar_buttons[index].setChecked(True)

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

    def _update_link_table_status(self, url, status, product_name):
        """Update status and product name for a specific URL in the table."""
        row = self._link_url_row_map.get(url)
        if row is None:
            return

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

        lower_message = str(message).lower()
        if any(kw in lower_message for kw in ("error", "fail", "cancel", "오류", "취소", "실패", "중단")):
            self.status_badge.update_style(Colors.ERROR, str(message)[:14])
        elif any(kw in lower_message for kw in ("done", "ready", "complete", "success", "완료", "대기", "연결")):
            self.status_badge.update_style(Colors.SUCCESS, str(message)[:14])
        else:
            self.status_badge.update_style(Colors.WARNING, str(message)[:14])

    def _set_progress(self, message):
        self.progress_label.setText(message)
        self.progress_label.setVisible(bool(message.strip()))

    def _set_results(self, success, failed):
        total = success + failed
        # Update sidebar progress labels
        self._sidebar_success_label.setText(f"성공: {success}")
        self._sidebar_failed_label.setText(f"실패: {failed}")
        self._sidebar_total_label.setText(f"전체: {total}")
        # Update queue progress
        self._set_queue_progress(f"전체: {total} 처리됨")

    def _set_queue_progress(self, message: str):
        self._progress_queue_label.setText(str(message or ""))

    def _add_product(self, title, success):
        # No separate product list; table is updated via link_status signal
        pass

    def _on_finished(self, results):
        logger.info("업로드 완료: %s", results)
        self._active_pipeline = None
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "준비")
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

    def _load_settings(self):
        """Load config values into widgets."""
        self.gemini_key_edit.setText(config.gemini_api_key)

        total = config.upload_interval
        self.hour_spin.setValue(total // 3600)
        self.min_spin.setValue((total % 3600) // 60)
        self.sec_spin.setValue(total % 60)

        self.video_check.setChecked(config.prefer_video)
        self.allow_ai_fallback_check.setChecked(bool(config.allow_ai_fallback))
        self.username_edit.setText(config.instagram_username)

    def _save_settings(self):
        """Save widget values to config."""
        interval = (
            self.hour_spin.value() * 3600 +
            self.min_spin.value() * 60 +
            self.sec_spin.value()
        )
        if interval < 30:
            interval = 30
            show_info(self, "알림", "최소 업로드 간격은 30초입니다.")

        config.gemini_api_key = self.gemini_key_edit.text().strip()
        config.upload_interval = interval
        config.prefer_video = self.video_check.isChecked()
        config.allow_ai_fallback = self.allow_ai_fallback_check.isChecked()
        config.instagram_username = self.username_edit.text().strip()

        config.save()

        if self.is_running:
            logger.info("실행 중 설정 저장됨; 파이프라인 재초기화는 보류합니다")
        else:
            self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)

        show_info(self, "저장 완료", "설정이 저장되었습니다.")
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

        # Header plan badge (inside account info card)
        if paid_account:
            self._plan_badge.setText("PRO")
            self._plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(13, 89, 242, 0.15);"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid rgba(13, 89, 242, 0.3);"
                f" border-radius: 11px; font-size: 8pt; font-weight: 700;"
                f" letter-spacing: 1px; }}"
            )
        else:
            self._plan_badge.setText("FREE")
            self._plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(34, 197, 94, 0.12);"
                f" color: {Colors.SUCCESS}; border: 1px solid rgba(34, 197, 94, 0.3);"
                f" border-radius: 11px; font-size: 8pt; font-weight: 700;"
                f" letter-spacing: 1px; }}"
            )

        if isinstance(remaining_count, (int, float)) and work_count <= 0:
            work_count = int(work_used) + int(remaining_count)

        self._work_label.setText(f"{work_used} / {work_count} 회")

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
        show_info(
            self,
            "문의하기",
            "문의사항이 있으시면 아래로 연락해주세요.\n\n"
            "이메일: support@paropartners.com\n"
            "텔레그램: @support_bot\n\n"
            "영업시간: 평일 10:00 - 18:00"
        )

    def open_settings(self):
        """Switch to settings page (page 2) instead of opening dialog."""
        logger.info("설정 화면 열기 호출")
        self._switch_page(2)

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
                    api_key=config.gemini_api_key,
                    headless=False,
                    profile_dir=profile_dir
                )
                agent.start_browser()
                agent.page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=30000)
                self.signals.threads_login_launch.emit(True, "")
                launch_notified = True

                import time
                for _ in range(300):
                    if cancel_event.is_set():
                        break
                    time.sleep(1)
                    try:
                        agent.page.url
                    except Exception:
                        break

                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    pass

            except Exception as e:
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
            self._update_login_status("pending", "브라우저가 열렸습니다. 로그인 후 닫아주세요.")
            self.signals.log.emit("Threads 로그인 브라우저가 열렸습니다.")
            return

        reason = str(detail or "").strip() or "원인을 확인할 수 없습니다."
        self._update_login_status("error", "브라우저 실행 실패")
        self.signals.log.emit(f"Threads 로그인 브라우저 실행 실패: {reason}")
        show_warning(
            self,
            "로그인 브라우저 오류",
            "Threads 로그인 브라우저를 열지 못했습니다.\n"
            "Google Chrome이 설치되어 있는지 확인한 뒤 다시 시도해주세요.\n\n"
            f"원인: {reason}",
        )

    def _check_login_status(self):
        self.check_login_btn.setEnabled(False)
        self.check_login_btn.setText("확인 중...")
        self._update_login_status("pending", "확인 중...")

        def check_status():
            try:
                from src.computer_use_agent import ComputerUseAgent
                from src.threads_playwright_helper import ThreadsPlaywrightHelper

                profile_dir = self._get_profile_dir()
                agent = ComputerUseAgent(
                    api_key=config.gemini_api_key,
                    headless=True,
                    profile_dir=profile_dir
                )
                agent.start_browser()

                try:
                    agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                    import time
                    time.sleep(2)

                    helper = ThreadsPlaywrightHelper(agent.page)
                    is_logged_in = helper.check_login_status()
                    logged_user = helper.get_logged_in_username() if is_logged_in else None

                    return is_logged_in, logged_user
                finally:
                    try:
                        agent.close()
                    except Exception:
                        pass

            except Exception as e:
                logger.exception("로그인 상태 확인 실패")
                return False, None

        def run_check():
            result = check_status()
            if self._closed:
                return
            app = QApplication.instance()
            if app:
                app.postEvent(self, LoginStatusEvent(result))

        thread = threading.Thread(target=run_check, daemon=True)
        thread.start()

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

    def event(self, evt):
        if evt.type() == LoginStatusEvent.EventType:
            if self._closed:
                return True
            is_logged_in, username = evt.result
            self.check_login_btn.setEnabled(True)
            self.check_login_btn.setText("상태 확인")

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
        content = self.links_text.toPlainText().strip()
        if not content:
            logger.warning("업로드 시작 차단: 내용이 비어 있습니다")
            show_warning(self, "알림", "쿠팡 파트너스 링크를 입력하세요.")
            return

        api_key = config.gemini_api_key
        if not api_key or len(api_key.strip()) < 10:
            logger.warning("업로드 시작 차단: API 키가 유효하지 않습니다")
            show_error(self, "설정 필요", "설정에서 유효한 Gemini API 키를 설정하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
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

        if not ask_yes_no(
            self,
            "확인",
            f"{len(link_data)}개 링크를 처리하고 업로드할까요?\n"
            f"업로드 간격: {_format_interval(interval)}\n\n"
            "(실행 중에 링크를 추가할 수 있습니다)",
        ):
            logger.info("업로드 시작이 사용자에 의해 취소되었습니다")
            return

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
            "api_key": config.gemini_api_key,
            "profile_dir": profile_dir,
        }
        self._active_pipeline = self.pipeline
        thread = threading.Thread(
            target=self._run_upload_queue,
            args=(interval, worker_config, self._active_pipeline),
            daemon=True,
        )
        thread.start()
        logger.info("업로드 작업 스레드 시작")

    def add_links_to_queue(self):
        logger.info("링크 큐 추가 호출")
        content = self.links_text.toPlainText().strip()
        if not content:
            logger.warning("링크 큐 추가 차단: 내용이 비어 있습니다")
            show_warning(self, "알림", "추가할 링크를 입력하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
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
            logger.info("링크 큐 추가 결과: added=%d queue=%d", added, self.link_queue.qsize())
            self.signals.log.emit(f"{added}개 새 링크 추가됨 (대기열: {self.link_queue.qsize()})")
            clean_links = "\n".join([item[0] for item in link_data])
            self.links_text.setPlainText(clean_links)
        else:
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
            self.signals.log.emit(msg)
            self.signals.progress.emit(msg)

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
                agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
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
                    agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
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
                self._server_label.setText("서버 연결: 정상")
                if not self.is_running:
                    self.status_label.setText("연결됨")
            else:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.ERROR}; border-radius: 4px;"
                )
                self._server_label.setText("서버 연결: 끊김")
                self.status_label.setText("연결 끊김")
        except Exception:
            logger.exception("하트비트 전송 실패")
            self._online_dot.setStyleSheet(
                f"background-color: {Colors.ERROR}; border-radius: 4px;"
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
        event.accept()

