"""
쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (PyQt5)
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
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QListWidget, QFrame,
    QLineEdit, QSpinBox, QCheckBox, QButtonGroup,
    QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QColor, QPainter, QLinearGradient, QPen

from src.config import config
from src.coupang_uploader import CoupangPartnersPipeline
from src.theme import (Colors, Typography, Radius, Gradients,
                       global_stylesheet, badge_style, stat_card_style,
                       terminal_text_style,
                       muted_text_style,
                       hint_text_style, section_title_style)
from src.ui_messages import ask_yes_no, show_error, show_info, show_warning

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


# ─── LoginStatusEvent ──────────────────────────────────────

class LoginStatusEvent(QEvent):
    EventType = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result):
        super().__init__(LoginStatusEvent.EventType)
        self.result = result


# ─── Badge ──────────────────────────────────────────────────

class Badge(QLabel):
    """작은 알약형 상태 배지."""
    def __init__(self, text="", color=Colors.ACCENT, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
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
        painter.setRenderHint(QPainter.Antialiasing)
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
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # 배경
        painter.setPen(Qt.NoPen)
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
        painter.setRenderHint(QPainter.Antialiasing)
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
        ("≡", "작업 로그"),
        ("◎", "결과 확인"),
        ("○", "Threads 계정"),
        ("⚙", "설정"),
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
        logger.info("MainWindow initialized")

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)

        self._current_page = 0
        self._build_ui()
        self.setStyleSheet(global_stylesheet())
        self._switch_page(0)
        self._tutorial_overlay = None
        self._tutorial_widgets = {}
        self._app_version = self._resolve_app_version()

        # Heartbeat timer
        from PyQt5.QtCore import QTimer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(60_000)
        QTimer.singleShot(1000, self._send_heartbeat)

        # Auto update check
        QTimer.singleShot(3000, self._check_for_updates_silent)

        # Load settings into page 4 widgets
        self._load_settings()

        logger.info("MainWindow UI setup complete")

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
        brand_icon.setAlignment(Qt.AlignCenter)
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
            f"color: {Colors.ACCENT_LIGHT}; font-size: 7pt; font-weight: 700;"
            " letter-spacing: 2px; background: transparent;"
        )

        # Right-side buttons (positioned from right edge)
        _nav_pill_style = (
            f"QPushButton {{ background: rgba(13, 89, 242, 0.08);"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid rgba(13, 89, 242, 0.15);"
            f" border-radius: 14px; font-size: 9pt; font-weight: 600;"
            f" padding: 4px 12px; }}"
            f" QPushButton:hover {{ background: rgba(13, 89, 242, 0.20);"
            f" color: #FFFFFF; border-color: rgba(13, 89, 242, 0.40); }}"
        )

        # Logout button
        self.logout_btn = QPushButton("로그아웃", header)
        self.logout_btn.setGeometry(WIN_W - 80, 20, 64, 28)
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(239, 68, 68, 0.08);"
            f" color: {Colors.TEXT_MUTED};"
            f" border: 1px solid rgba(239, 68, 68, 0.15);"
            f" border-radius: 14px; font-size: 9pt; font-weight: 600;"
            f" padding: 4px 12px; }}"
            f" QPushButton:hover {{ background: rgba(239, 68, 68, 0.25);"
            f" color: {Colors.ERROR}; border-color: {Colors.ERROR}; }}"
        )
        self.logout_btn.clicked.connect(self._do_logout)

        # Tutorial button
        self.tutorial_btn = QPushButton("Tutorial", header)
        self.tutorial_btn.setGeometry(WIN_W - 80 - 16 - 50, 20, 50, 28)
        self.tutorial_btn.setCursor(Qt.PointingHandCursor)
        self.tutorial_btn.setStyleSheet(_nav_pill_style)
        self.tutorial_btn.clicked.connect(self.open_tutorial)

        # Update button
        self.update_btn = QPushButton("업데이트", header)
        self.update_btn.setGeometry(WIN_W - 80 - 16 - 50 - 12 - 60, 20, 60, 28)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setStyleSheet(_nav_pill_style)
        self.update_btn.clicked.connect(self.check_for_updates)

        # Status badge
        badge_x = WIN_W - 80 - 16 - 50 - 12 - 60 - 12 - 90
        self.status_badge = Badge("대기중", Colors.SUCCESS, header)
        self.status_badge.setGeometry(badge_x, 22, 90, 24)

        # Online dot
        self._online_dot = QLabel("", header)
        self._online_dot.setGeometry(badge_x - 18, 27, 10, 10)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px;"
            f" border: 2px solid rgba(34, 197, 94, 0.3);"
        )

        self._header = header
        self._brand_icon = brand_icon

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
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_style())
            self._sidebar_group.addButton(btn, i)
            self._sidebar_buttons.append(btn)

        self._sidebar_buttons[0].setChecked(True)
        self._sidebar_group.buttonClicked[int].connect(self._switch_page)

        # Divider line below buttons
        divider_y = 20 + len(self._SIDEBAR_ITEMS) * 48 + 12
        divider = QFrame(sidebar)
        divider.setGeometry(20, divider_y, SIDEBAR_W - 40, 1)
        divider.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")

        # Progress section below divider
        prog_y = divider_y + 16

        prog_title = QLabel("작업 현황", sidebar)
        prog_title.setGeometry(24, prog_y, 200, 20)
        prog_title.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 700;"
            " letter-spacing: 1.5px; background: transparent;"
        )

        prog_y += 28

        # Success count
        self._sidebar_success_dot = QLabel("", sidebar)
        self._sidebar_success_dot.setGeometry(24, prog_y + 4, 8, 8)
        self._sidebar_success_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
        )
        self._sidebar_success_label = QLabel("성공: 0", sidebar)
        self._sidebar_success_label.setGeometry(40, prog_y, 200, 20)
        self._sidebar_success_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        prog_y += 26

        # Failed count
        self._sidebar_failed_dot = QLabel("", sidebar)
        self._sidebar_failed_dot.setGeometry(24, prog_y + 4, 8, 8)
        self._sidebar_failed_dot.setStyleSheet(
            f"background-color: {Colors.ERROR}; border-radius: 4px;"
        )
        self._sidebar_failed_label = QLabel("실패: 0", sidebar)
        self._sidebar_failed_label.setGeometry(40, prog_y, 200, 20)
        self._sidebar_failed_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        prog_y += 26

        # Total count
        self._sidebar_total_dot = QLabel("", sidebar)
        self._sidebar_total_dot.setGeometry(24, prog_y + 4, 8, 8)
        self._sidebar_total_dot.setStyleSheet(
            f"background-color: {Colors.INFO}; border-radius: 4px;"
        )
        self._sidebar_total_label = QLabel("전체: 0", sidebar)
        self._sidebar_total_label.setGeometry(40, prog_y, 200, 20)
        self._sidebar_total_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        prog_y += 32

        # Status label
        self._sidebar_status_label = QLabel("대기중", sidebar)
        self._sidebar_status_label.setGeometry(24, prog_y, 240, 20)
        self._sidebar_status_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
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
        """Build 5 pages as QWidgets positioned to the right of the sidebar."""
        page_x = SIDEBAR_W
        page_y = HEADER_H
        page_w = CONTENT_W
        page_h = CONTENT_H

        self._pages = []
        for i in range(5):
            page = QWidget(parent)
            page.setGeometry(page_x, page_y, page_w, page_h)
            page.setVisible(False)
            self._pages.append(page)

        self._build_page0_links(self._pages[0])
        self._build_page1_log(self._pages[1])
        self._build_page2_results(self._pages[2])
        self._build_page3_threads(self._pages[3])
        self._build_page4_settings(self._pages[4])

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
        icon_label.setAlignment(Qt.AlignCenter)
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

        # Link count badge (top right)
        self.link_count_badge = Badge("0개 링크", Colors.TEXT_MUTED, page)
        self.link_count_badge.setGeometry(CONTENT_W - 28 - 90, 28, 90, 24)

        # Hint text
        hint = QLabel("아래에 쿠팡 파트너스 URL을 붙여넣기 하세요 (한 줄에 하나씩)", page)
        hint.setGeometry(28, cy, 700, 20)
        hint.setStyleSheet(muted_text_style("9pt"))

        # Links text area
        self.links_text = QPlainTextEdit(page)
        self.links_text.setGeometry(28, cy + 24, 944, 520)
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://link.coupang.com/a/yyy"
        )
        self.links_text.textChanged.connect(self._update_link_count)

        # Buttons row
        btn_y = cy + 24 + 520 + 12  # = 638

        # Start button
        self.start_btn = QPushButton("\u25B6  자동화 시작", page)
        self.start_btn.setGeometry(28, btn_y, 300, 48)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {Gradients.ACCENT_BTN};"
            f"  color: #FFFFFF;"
            f"  border: 2px solid rgba(59, 123, 255, 0.5);"
            f"  border-radius: {Radius.LG};"
            f"  font-size: 12pt; font-weight: 800; letter-spacing: 0.5px;"
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
        self.add_btn.setGeometry(338, btn_y, 200, 48)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setEnabled(False)
        self.add_btn.setProperty("class", "outline-success")
        self.add_btn.clicked.connect(self.add_links_to_queue)

        # Stop button
        self.stop_btn = QPushButton("중지", page)
        self.stop_btn.setGeometry(548, btn_y, 140, 48)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "outline-danger")
        self.stop_btn.clicked.connect(self.stop_upload)

    # ── Page 1: 작업 로그 ───────────────────────────────────

    def _build_page1_log(self, page):
        cy = self._make_page_header(page, "≡", "작업 로그")

        self.log_text = QTextEdit(page)
        self.log_text.setGeometry(28, cy, 944, 590)
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(self.MAX_LOG_LINES)
        self.log_text.setStyleSheet(terminal_text_style())

    # ── Page 2: 결과 확인 ───────────────────────────────────

    def _build_page2_results(self, page):
        cy = self._make_page_header(page, "◎", "결과 확인")

        # 3 stat cards
        self._stat_success_card, self._stat_success_val = self._build_stat_card_widget(
            page, 28, cy, 304, 120, "✔", "0", "SUCCESS", Colors.SUCCESS
        )
        self._stat_failed_card, self._stat_failed_val = self._build_stat_card_widget(
            page, 348, cy, 304, 120, "✘", "0", "FAIL", Colors.ERROR
        )
        self._stat_total_card, self._stat_total_val = self._build_stat_card_widget(
            page, 668, cy, 304, 120, "Σ", "0", "TOTAL", Colors.INFO
        )

        # "처리된 항목" label
        items_label = QLabel("처리된 항목", page)
        items_label.setGeometry(28, cy + 130, 300, 20)
        items_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " letter-spacing: 1px; background: transparent;"
        )

        # Products list
        list_y = cy + 156
        list_h = CONTENT_H - list_y - 16
        self.products_list = QListWidget(page)
        self.products_list.setGeometry(28, list_y, 944, list_h)
        self.products_list.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {Colors.BG_INPUT};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: {Radius.LG};"
            f"  padding: 6px; font-size: 10pt;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 10px 12px;"
            f"  border-radius: {Radius.SM};"
            f"  border-bottom: 1px solid {Colors.BORDER};"
            f"}}"
            f"QListWidget::item:last-child {{ border-bottom: none; }}"
        )

    def _build_stat_card_widget(self, parent, x, y, w, h, icon_char, value, eng_label, color):
        """Build a stat card at absolute position. Returns (card, value_label)."""
        card = QFrame(parent)
        card.setGeometry(x, y, w, h)
        card.setStyleSheet(stat_card_style(color))

        # Icon
        icon_lbl = QLabel(icon_char, card)
        icon_lbl.setGeometry(0, 10, w, 28)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 18pt; font-weight: 800;"
            " background: transparent; border: none;"
        )

        # Value
        val_lbl = QLabel(value, card)
        val_lbl.setGeometry(0, 38, w, 40)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(
            f"color: {color}; font-size: 26pt; font-weight: 800;"
            " background: transparent; border: none;"
        )

        # Eng label
        eng_lbl = QLabel(eng_label, card)
        eng_lbl.setGeometry(0, 80, w, 20)
        eng_lbl.setAlignment(Qt.AlignCenter)
        eng_lbl.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 7pt; font-weight: 700;"
            " letter-spacing: 2px; background: transparent; border: none;"
        )

        return card, val_lbl

    # ── Page 3: Threads 계정 ────────────────────────────────

    def _build_page3_threads(self, page):
        cy = self._make_page_header(page, "○", "Threads 계정")

        section = SectionFrame(page)
        section.setGeometry(28, cy, 944, 300)

        # "계정 이름" label
        name_label = QLabel("계정 이름", section)
        name_label.setGeometry(24, 20, 100, 20)
        name_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10pt; font-weight: 600;"
            " background: transparent;"
        )

        name_hint = QLabel("프로필 식별용", section)
        name_hint.setGeometry(130, 20, 200, 20)
        name_hint.setStyleSheet(hint_text_style())

        # Username input
        self.username_edit = QLineEdit(section)
        self.username_edit.setGeometry(24, 44, 896, 38)
        self.username_edit.setPlaceholderText("예: myaccount")

        # Status dot + login_status_label
        self._threads_status_dot = QLabel("", section)
        self._threads_status_dot.setGeometry(24, 100, 10, 10)
        self._threads_status_dot.setStyleSheet(
            f"background-color: {Colors.TEXT_MUTED}; border-radius: 5px;"
        )

        self.login_status_label = QLabel("연결 안됨", section)
        self.login_status_label.setGeometry(42, 96, 300, 20)
        self.login_status_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Threads login button
        self.threads_login_btn = QPushButton("Threads 로그인", section)
        self.threads_login_btn.setGeometry(24, 132, 200, 42)
        self.threads_login_btn.setCursor(Qt.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)

        # Check login button (ghost style)
        self.check_login_btn = QPushButton("상태 확인", section)
        self.check_login_btn.setGeometry(234, 132, 160, 42)
        self.check_login_btn.setCursor(Qt.PointingHandCursor)
        self.check_login_btn.setProperty("class", "ghost")
        self.check_login_btn.clicked.connect(self._check_login_status)

        # Hint text
        hint_label = QLabel("로그인 후 브라우저를 닫으면 세션이 자동 저장됩니다.", section)
        hint_label.setGeometry(24, 190, 600, 20)
        hint_label.setStyleSheet(hint_text_style())

    # ── Page 4: 설정 ────────────────────────────────────────

    def _build_page4_settings(self, page):
        cy = self._make_page_header(page, "⚙", "설정")

        # Section 1: API 설정
        sec1 = SectionFrame(page)
        sec1.setGeometry(28, cy, 944, 114)

        sec1_title = QLabel("API 설정", sec1)
        sec1_title.setGeometry(24, 14, 200, 22)
        sec1_title.setStyleSheet(section_title_style())

        api_label = QLabel("마스터 API 키", sec1)
        api_label.setGeometry(24, 42, 200, 18)
        api_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        api_hint = QLabel("Google AI Studio에서 발급", sec1)
        api_hint.setGeometry(150, 42, 300, 18)
        api_hint.setStyleSheet(hint_text_style())

        self.gemini_key_edit = QLineEdit(sec1)
        self.gemini_key_edit.setGeometry(24, 66, 896, 36)
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_key_edit.setPlaceholderText("Gemini API 키를 입력하세요")

        # Section 2: 업로드 설정
        sec2 = SectionFrame(page)
        sec2.setGeometry(28, 210, 944, 150)

        sec2_title = QLabel("업로드 설정", sec2)
        sec2_title.setGeometry(24, 14, 200, 22)
        sec2_title.setStyleSheet(section_title_style())

        interval_label = QLabel("업로드 간격", sec2)
        interval_label.setGeometry(24, 44, 100, 18)
        interval_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        interval_hint = QLabel("최소 30초", sec2)
        interval_hint.setGeometry(130, 44, 100, 18)
        interval_hint.setStyleSheet(hint_text_style())

        self.hour_spin = QSpinBox(sec2)
        self.hour_spin.setGeometry(24, 68, 90, 36)
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" 시간")

        self.min_spin = QSpinBox(sec2)
        self.min_spin.setGeometry(124, 68, 80, 36)
        self.min_spin.setRange(0, 59)
        self.min_spin.setSuffix(" 분")

        self.sec_spin = QSpinBox(sec2)
        self.sec_spin.setGeometry(214, 68, 80, 36)
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setSuffix(" 초")

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선", sec2)
        self.video_check.setGeometry(24, 114, 300, 24)

        # Section 3: 텔레그램 알림
        sec3 = SectionFrame(page)
        sec3.setGeometry(28, 374, 944, 210)

        sec3_title = QLabel("텔레그램 알림", sec3)
        sec3_title.setGeometry(24, 14, 200, 22)
        sec3_title.setStyleSheet(section_title_style())

        self.telegram_check = QCheckBox("텔레그램 알림 활성화", sec3)
        self.telegram_check.setGeometry(24, 44, 300, 24)

        bot_label = QLabel("봇 토큰", sec3)
        bot_label.setGeometry(24, 78, 100, 18)
        bot_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        self.bot_token_edit = QLineEdit(sec3)
        self.bot_token_edit.setGeometry(24, 100, 896, 36)
        self.bot_token_edit.setEchoMode(QLineEdit.Password)
        self.bot_token_edit.setPlaceholderText("BotFather 토큰")

        chat_label = QLabel("채팅 ID", sec3)
        chat_label.setGeometry(24, 144, 100, 18)
        chat_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        self.chat_id_edit = QLineEdit(sec3)
        self.chat_id_edit.setGeometry(24, 166, 896, 36)
        self.chat_id_edit.setPlaceholderText("채팅 ID")

        # Save button
        self._settings_save_btn = QPushButton("저장", page)
        self._settings_save_btn.setGeometry(832, 640, 140, 48)
        self._settings_save_btn.setCursor(Qt.PointingHandCursor)
        self._settings_save_btn.clicked.connect(self._save_settings)

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
        self.status_label = QLabel("Ready", bar)
        self.status_label.setGeometry(34, 6, 600, 20)
        self.status_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # Server label (right side)
        self._server_label = QLabel("서버 연결: --", bar)
        self._server_label.setGeometry(WIN_W - 400, 6, 200, 20)
        self._server_label.setAlignment(Qt.AlignRight)
        self._server_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 600;"
            " background: transparent;"
        )

        # Progress label (far right)
        self.progress_label = QLabel("", bar)
        self.progress_label.setGeometry(WIN_W - 190, 6, 180, 20)
        self.progress_label.setAlignment(Qt.AlignRight)
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
    #  BUSINESS LOGIC (preserved from existing)
    # ────────────────────────────────────────────────────────

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        clean_msg = str(message).strip()
        if not clean_msg:
            return

        logger.info("UI_LOG %s", clean_msg)

        safe_msg = html.escape(clean_msg)
        lower_msg = clean_msg.lower()
        color = Colors.TEXT_SECONDARY
        tag = "INFO"
        tag_color = Colors.INFO
        if any(kw in lower_msg for kw in ("error", "fail", "exception", "cancel")):
            color = Colors.ERROR
            tag = "ERROR"
            tag_color = Colors.ERROR
        elif any(kw in lower_msg for kw in ("success", "done", "complete")):
            color = Colors.SUCCESS
            tag = "SUCCESS"
            tag_color = Colors.SUCCESS
        elif any(kw in lower_msg for kw in ("warn", "wait", "running", "start")):
            color = Colors.WARNING
            tag = "WARN"
            tag_color = Colors.WARNING

        self.log_text.append(
            f'<span style="color:{Colors.TEXT_MUTED}">[{timestamp}]</span> '
            f'<span style="color:{tag_color};font-weight:700">{tag}</span> '
            f'<span style="color:{color}">{safe_msg}</span>'
        )

    def _set_status(self, message):
        logger.info("Status updated: %s", message)
        self.status_label.setText(message)

        lower_message = str(message).lower()
        if any(kw in lower_message for kw in ("error", "fail", "cancel")):
            self.status_badge.update_style(Colors.ERROR, str(message)[:14])
        elif any(kw in lower_message for kw in ("done", "ready", "complete", "success")):
            self.status_badge.update_style(Colors.SUCCESS, str(message)[:14])
        else:
            self.status_badge.update_style(Colors.WARNING, str(message)[:14])

    def _set_progress(self, message):
        self.progress_label.setText(message)

    def _set_results(self, success, failed):
        total = success + failed
        self._stat_success_val.setText(str(success))
        self._stat_failed_val.setText(str(failed))
        self._stat_total_val.setText(str(total))
        # Also update sidebar progress labels
        self._sidebar_success_label.setText(f"성공: {success}")
        self._sidebar_failed_label.setText(f"실패: {failed}")
        self._sidebar_total_label.setText(f"전체: {total}")

    def _add_product(self, title, success):
        icon = "\u2714" if success else "\u2718"
        color = Colors.SUCCESS if success else Colors.ERROR
        item_text = f"  {icon}  {title[:55]}"
        self.products_list.addItem(item_text)
        item = self.products_list.item(self.products_list.count() - 1)
        item.setForeground(QColor(color))

    def _on_finished(self, results):
        logger.info("Upload finished: %s", results)
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "Ready")
        self._sidebar_status_label.setText("완료")

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get("parse_failed", 0)
        uploaded = results.get("uploaded", 0)
        failed = results.get("failed", 0)

        # Auto-switch to results page
        self._switch_page(2)
        self._sidebar_buttons[2].setChecked(True)

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
    #  SETTINGS LOGIC (embedded from settings_dialog.py)
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리."""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def _get_profile_dir(self):
        username = self.username_edit.text().strip()
        if username:
            profile_name = self._sanitize_profile_name(username)
            return f".threads_profile_{profile_name}"
        return ".threads_profile"

    def _load_settings(self):
        """Load config values into page 4 widgets."""
        self.gemini_key_edit.setText(config.gemini_api_key)

        total = config.upload_interval
        self.hour_spin.setValue(total // 3600)
        self.min_spin.setValue((total % 3600) // 60)
        self.sec_spin.setValue(total % 60)

        self.video_check.setChecked(config.prefer_video)
        self.telegram_check.setChecked(config.telegram_enabled)
        self.bot_token_edit.setText(config.telegram_bot_token)
        self.chat_id_edit.setText(config.telegram_chat_id)
        self.username_edit.setText(config.instagram_username)

    def _save_settings(self):
        """Save page 4 widget values to config, reinitialize pipeline."""
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
        config.telegram_enabled = self.telegram_check.isChecked()
        config.telegram_bot_token = self.bot_token_edit.text().strip()
        config.telegram_chat_id = self.chat_id_edit.text().strip()
        config.instagram_username = self.username_edit.text().strip()

        config.save()

        # Reinitialize pipeline with new API key
        self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)

        show_info(self, "저장 완료", "설정이 저장되었습니다.")
        logger.info("settings saved; pipeline reinitialized")

    def open_settings(self):
        """Switch to settings page (page 4) instead of opening dialog."""
        logger.info("open_settings invoked")
        self._switch_page(4)

    # ────────────────────────────────────────────────────────
    #  THREADS LOGIN LOGIC (embedded from settings_dialog.py)
    # ────────────────────────────────────────────────────────

    def _open_threads_login(self):
        username = self.username_edit.text().strip()
        if not username:
            show_warning(self, "알림", "먼저 계정 이름을 입력하세요.")
            return

        config.instagram_username = username
        config.save()

        self.threads_login_btn.setEnabled(False)
        self.threads_login_btn.setText("여는 중...")
        self._update_login_status("pending", "브라우저 여는 중...")

        self._browser_cancel.clear()
        cancel_event = self._browser_cancel

        def open_browser():
            try:
                from src.computer_use_agent import ComputerUseAgent

                profile_dir = self._get_profile_dir()
                agent = ComputerUseAgent(
                    api_key=config.gemini_api_key,
                    headless=False,
                    profile_dir=profile_dir
                )
                agent.start_browser()
                agent.page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=30000)

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
                print(f"브라우저 오류: {e}")

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, self._restore_login_btn)

    def _restore_login_btn(self):
        if self._closed:
            return
        self.threads_login_btn.setEnabled(True)
        self.threads_login_btn.setText("Threads 로그인")

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
                print(f"로그인 확인 오류: {e}")
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
    #  UPLOAD LOGIC (preserved exactly from existing)
    # ────────────────────────────────────────────────────────

    def start_upload(self):
        logger.info("start_upload invoked")
        content = self.links_text.toPlainText().strip()
        if not content:
            logger.warning("start_upload blocked: empty content")
            show_warning(self, "알림", "쿠팡 파트너스 링크를 입력하세요.")
            return

        api_key = config.gemini_api_key
        if not api_key or len(api_key.strip()) < 10:
            logger.warning("start_upload blocked: invalid API key")
            show_error(self, "설정 필요", "설정에서 유효한 Gemini API 키를 설정하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            logger.warning("start_upload blocked: no valid links found")
            show_warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
            return

        config.load()
        interval = max(config.upload_interval, 30)
        logger.info("start_upload prepared: links=%d interval=%d", len(link_data), interval)

        if not ask_yes_no(
            self,
            "확인",
            f"{len(link_data)}개 링크를 처리하고 업로드할까요?\n"
            f"업로드 간격: {_format_interval(interval)}\n\n"
            "(실행 중에 링크를 추가할 수 있습니다)",
        ):
            logger.info("start_upload cancelled by user")
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.products_list.clear()
        self.status_badge.update_style(Colors.WARNING, "실행중")
        self._sidebar_status_label.setText("실행중")

        self._stat_success_val.setText("0")
        self._stat_failed_val.setText("0")
        self._stat_total_val.setText("0")
        self._sidebar_success_label.setText("성공: 0")
        self._sidebar_failed_label.setText("실패: 0")
        self._sidebar_total_label.setText("전체: 0")

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

        # Auto-switch to log page
        self._switch_page(1)
        self._sidebar_buttons[1].setChecked(True)

        thread = threading.Thread(
            target=self._run_upload_queue,
            args=(interval,),
            daemon=True,
        )
        thread.start()
        logger.info("upload worker thread started")

    def add_links_to_queue(self):
        logger.info("add_links_to_queue invoked")
        content = self.links_text.toPlainText().strip()
        if not content:
            logger.warning("add_links_to_queue blocked: empty content")
            show_warning(self, "알림", "추가할 링크를 입력하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            logger.warning("add_links_to_queue blocked: no valid links found")
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

        if added > 0:
            logger.info("add_links_to_queue: added=%d queue=%d", added, self.link_queue.qsize())
            self.signals.log.emit(f"{added}개 새 링크 추가됨 (대기열: {self.link_queue.qsize()})")
            clean_links = "\n".join([item[0] for item in link_data])
            self.links_text.setPlainText(clean_links)
        else:
            logger.info("add_links_to_queue: no new links added")
            show_info(self, "알림", "모든 링크가 이미 대기열에 있거나 처리되었습니다.")

    def _run_upload_queue(self, interval):
        logger.info("upload queue worker started: interval=%s", interval)
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

        def log(msg):
            self.signals.log.emit(msg)
            self.signals.progress.emit(msg)

        try:
            log(f"Upload started (queue: {self.link_queue.qsize()})")
            self.signals.status.emit("Processing")

            ig_username = config.instagram_username
            if ig_username:
                profile_name = self._sanitize_profile_name(ig_username)
                profile_dir = f".threads_profile_{profile_name}"
            else:
                profile_dir = ".threads_profile"

            log("Starting browser...")
            agent = ComputerUseAgent(
                api_key=config.gemini_api_key,
                headless=False,
                profile_dir=profile_dir,
            )
            agent.start_browser()

            try:
                agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
            except Exception:
                logger.exception("Initial navigation to Threads failed")

            helper = ThreadsPlaywrightHelper(agent.page)

            if not helper.check_login_status():
                log("Login required. Please sign in within 60 seconds.")
                for wait_sec in range(20):
                    time.sleep(3)
                    remaining = 60 - (wait_sec * 3)
                    if wait_sec % 3 == 0:
                        log(f"Waiting for login... {remaining}s remaining")
                    if helper.check_login_status():
                        log("Login confirmed")
                        break
                else:
                    log("Login timeout after 60 seconds. Upload cancelled.")
                    results["cancelled"] = True
                    self.signals.finished.emit(results)
                    return

            log("Threads login status verified")

            processed_count = 0
            empty_count = 0

            while not self._stop_event.is_set():
                try:
                    item = self.link_queue.get(timeout=5)
                    empty_count = 0
                except queue.Empty:
                    empty_count += 1
                    if empty_count >= 6:
                        log("Queue empty. Worker stopped.")
                        break
                    log("Waiting for new links...")
                    continue

                if self._stop_event.is_set():
                    results["cancelled"] = True
                    break

                processed_count += 1
                url, keyword = item if isinstance(item, tuple) else (item, None)
                results["total"] += 1

                log(f"Processing item {processed_count} (queue: {self.link_queue.qsize()})")
                log("Parsing product data...")

                try:
                    post_data = self.pipeline.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results["parse_failed"] += 1
                        log("Parse failed. Skipping this item.")
                        continue

                    results["processed"] += 1
                    product_name = post_data.get("product_title", "")[:30]
                    log(f"Parse completed: {product_name}")
                except Exception as exc:
                    results["parse_failed"] += 1
                    log(f"Parse error: {str(exc)[:80]}")
                    continue

                log("Uploading thread post...")
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

                    success = helper.create_thread_direct(posts_data)
                    if success:
                        results["uploaded"] += 1
                        log(f"Upload success: {product_name}")
                        self.signals.product.emit(product_name, True)
                    else:
                        results["failed"] += 1
                        log(f"Upload failed: {product_name}")
                        self.signals.product.emit(product_name, False)

                    results["details"].append(
                        {
                            "product_title": product_name,
                            "url": url,
                            "success": success,
                        }
                    )
                except Exception as exc:
                    results["failed"] += 1
                    log(f"Upload error: {str(exc)[:80]}")
                    self.signals.product.emit(product_name, False)

                self.signals.results.emit(results["uploaded"], results["failed"])

                if not self._stop_event.is_set():
                    log(f"Waiting {_format_interval(interval)} until next item")
                    for sec in range(interval):
                        if self._stop_event.is_set():
                            results["cancelled"] = True
                            break
                        remaining = interval - sec
                        if remaining % 60 == 0 and remaining > 0:
                            log(f"Waiting... {_format_interval(remaining)} left")
                        time.sleep(1)

            try:
                agent.save_session()
                agent.close()
            except Exception:
                logger.exception("Failed to close browser cleanly")

            log("=" * 40)
            log(
                "Finished - "
                f"Uploaded: {results['uploaded']} / "
                f"Failed: {results['failed']} / "
                f"Parse failed: {results['parse_failed']}"
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
                self.signals.status.emit("Cancelled")
            else:
                self.signals.status.emit("Completed")

            self.signals.finished.emit(results)

        except Exception as exc:
            logger.exception("Fatal error in _run_upload_queue")
            log(f"Fatal error: {exc}")
            self.signals.status.emit("Error")
            self.signals.finished.emit(results)
            try:
                from src import auth_client
                auth_client.log_action("batch_error", str(exc)[:200], level="ERROR")
            except Exception:
                pass

    def stop_upload(self):
        logger.info("stop_upload invoked; is_running=%s", self.is_running)
        if self.is_running:
            self.signals.log.emit("Stop requested. The current item will finish first.")
            self.signals.status.emit("Stopping...")
            self.status_badge.update_style(Colors.WARNING, "Stopping")
            self._sidebar_status_label.setText("중지중...")
            self.is_running = False
            self.pipeline.cancel()
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
        logger.debug("heartbeat tick; is_running=%s", self.is_running)
        try:
            from src import auth_client

            if not auth_client.is_logged_in():
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.TEXT_MUTED}; border-radius: 4px;"
                )
                self.status_label.setText("Logged out")
                self._server_label.setText("서버 연결: 로그아웃")
                return

            task = "uploading" if self.is_running else "idle"
            result = auth_client.heartbeat(
                current_task=task,
                app_version=self._app_version
            )
            if result.get("status") is True:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
                )
                self._server_label.setText("서버 연결: 정상")
                if not self.is_running:
                    self.status_label.setText("Connected")
            else:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.ERROR}; border-radius: 4px;"
                )
                self._server_label.setText("서버 연결: 끊김")
                self.status_label.setText("Connection lost")
        except Exception:
            logger.exception("heartbeat failed")
            self._online_dot.setStyleSheet(
                f"background-color: {Colors.ERROR}; border-radius: 4px;"
            )
            self._server_label.setText("서버 연결: 오류")
            self.status_label.setText("Connection error")

    def _do_logout(self):
        """로그아웃 처리 후 앱 종료."""
        logger.info("logout requested")
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
            QApplication.quit()

    def check_for_updates(self):
        """업데이트 확인 (사용자 버튼 클릭)."""
        logger.info("manual update check opened")
        from src.update_dialog import UpdateDialog

        dialog = UpdateDialog(self._app_version, self)
        dialog.exec_()

    def _check_for_updates_silent(self):
        """백그라운드 자동 업데이트 체크 (알림만 표시)."""
        logger.info("silent update check started")
        try:
            from src.auto_updater import AutoUpdater

            updater = AutoUpdater(self._app_version)
            update_info = updater.check_for_updates()

            if update_info:
                if ask_yes_no(
                    self,
                    "업데이트 알림",
                    f"새 버전이 출시되었습니다. (v{update_info['version']})\n\n"
                    f"지금 업데이트하시겠습니까?",
                ):
                    self.check_for_updates()
        except Exception as e:
            logger.exception("silent update check failed")
            print(f"자동 업데이트 체크 실패: {e}")

    def open_tutorial(self):
        logger.info("open_tutorial invoked")
        from src.tutorial import TutorialDialog
        dialog = TutorialDialog(self)
        dialog.exec_()

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
        logger.info("closeEvent invoked; is_running=%s", self.is_running)
        self._closed = True
        self._browser_cancel.set()
        if self.is_running:
            if not ask_yes_no(
                self,
                "종료 확인",
                "작업이 진행 중입니다. 정말 종료하시겠습니까?",
            ):
                self._closed = False
                event.ignore()
                return
            self.stop_upload()

        try:
            from src import auth_client
            auth_client.logout()
        except Exception:
            pass
        event.accept()
