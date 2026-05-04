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

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────

WIN_W = 1360
WIN_H = 960       # 설정 페이지 모든 카드 + 안전 여유
HEADER_H = 84
SIDEBAR_W = 320
CONTENT_W = 1040  # WIN_W - SIDEBAR_W
CONTENT_H = 836   # WIN_H - HEADER_H - STATUSBAR_H
STATUSBAR_H = 40


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

        # 배경 — 웜 차콜 (Claude Dark)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(Colors.BG_HEADER))
        grad.setColorAt(1, QColor(Colors.BG_DARK))
        painter.fillRect(self.rect(), grad)

        # 상단 accent 라인 — 코랄
        accent = QLinearGradient(0, 0, w, 0)
        accent.setColorAt(0, QColor(217, 119, 87, 0))
        accent.setColorAt(0.2, QColor(Colors.ACCENT))
        accent.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        accent.setColorAt(0.8, QColor(Colors.ACCENT))
        accent.setColorAt(1, QColor(217, 119, 87, 0))
        painter.fillRect(0, 0, w, self.ACCENT_LINE_H, accent)

        # 하단 border — 미묘한 톤
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
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

        # 사이드바 배경 — 한 단계 더 어두운 차콜
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.BG_SIDEBAR))
        painter.drawRect(0, 0, w, h)

        # 오른쪽 border 라인
        painter.setPen(QPen(QColor(Colors.BORDER_SUBTLE), 1))
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
        logger.info("MainWindow initialized")

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)
        self.signals.step_update.connect(self._update_step)
        self.signals.link_status.connect(self._update_link_table_status)

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
        """새 헤더 — 큰 브랜드(좌) + 우측 액션 그룹.
        세로 중앙 정렬, 충분한 패딩, 알약 버튼 충돌 없음.
        """
        header = HeaderBar(parent)
        header.setGeometry(0, 0, WIN_W, HEADER_H)

        cy = HEADER_H // 2  # vertical center

        # ── 브랜드 (좌): 큰 코랄 칩 + 2줄 타이틀 ──
        brand_size = 48
        bx = 24
        brand_icon = QLabel("C", header)
        brand_icon.setGeometry(bx, cy - brand_size // 2, brand_size, brand_size)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setStyleSheet(
            f"QLabel {{ background: {Gradients.ACCENT_BTN};"
            f" color: #FFFFFF; border-radius: {brand_size // 2}px;"
            f" font-size: 18pt; font-weight: 800;"
            f" border: 2px solid rgba(217, 119, 87, 0.35); }}"
        )

        title_label = QLabel("쿠팡 파트너스", header)
        title_label.setGeometry(bx + brand_size + 14, cy - 24, 240, 28)
        title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 16pt; font-weight: 700;"
            f" letter-spacing: -0.4px; background: transparent;"
        )

        sub_label = QLabel("THREAD AUTOMATION", header)
        sub_label.setGeometry(bx + brand_size + 14, cy + 4, 240, 18)
        sub_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 700;"
            f" letter-spacing: 2.5px; background: transparent;"
        )

        # ── 우측 액션 알약 스타일 ──
        nav_pill = (
            f"QPushButton {{ background: {Colors.BG_ELEVATED};"
            f" color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER};"
            f" border-radius: 16px; font-size: 9pt; font-weight: 600;"
            f" padding: 6px 16px; }}"
            f" QPushButton:hover {{ background: {Colors.BG_HOVER};"
            f" color: {Colors.TEXT_PRIMARY}; border-color: {Colors.ACCENT}; }}"
        )

        self.logout_btn = QPushButton("로그아웃", header)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet(
            f"QPushButton {{ background: transparent;"
            f" color: {Colors.TEXT_MUTED};"
            f" border: 1px solid {Colors.BORDER};"
            f" border-radius: 16px; font-size: 9pt; font-weight: 600;"
            f" padding: 6px 16px; }}"
            f" QPushButton:hover {{ background: {Colors.ERROR};"
            f" color: #FFFFFF; border-color: {Colors.ERROR}; }}"
        )
        self.logout_btn.clicked.connect(self._do_logout)

        self.tutorial_btn = QPushButton("Tutorial", header)
        self.tutorial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tutorial_btn.setStyleSheet(nav_pill)
        self.tutorial_btn.clicked.connect(self.open_tutorial)

        self.update_btn = QPushButton("업데이트", header)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet(nav_pill)
        self.update_btn.clicked.connect(self.check_for_updates)

        # 우측에서 좌측으로 배치 — sizeHint 기반 (+30 충분 마진으로 한국어 텍스트 잘림 방지)
        nav_h = 32
        nav_gap = 8
        nav_right = WIN_W - 24
        nav_y = cy - nav_h // 2
        for btn in (self.logout_btn, self.tutorial_btn, self.update_btn):
            btn.ensurePolished()
            btn.setFixedHeight(nav_h)
            w = max(btn.sizeHint().width() + 30, 80)
            nav_right -= w
            btn.setGeometry(nav_right, nav_y, w, nav_h)
            nav_right -= nav_gap

        # 세로 구분선
        sep_x = nav_right - 6
        sep = QFrame(header)
        sep.setGeometry(sep_x, cy - 14, 1, 28)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")

        # 사용 횟수 + 플랜 배지 — 칩 형태
        self._plan_badge = QLabel("FREE", header)
        plan_w = 60
        plan_x = sep_x - 10 - plan_w
        self._plan_badge.setGeometry(plan_x, cy - 14, plan_w, 28)
        self._plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._plan_badge.setStyleSheet(
            f"QLabel {{ background-color: rgba(122, 184, 122, 0.16);"
            f" color: {Colors.SUCCESS}; border: 1px solid rgba(122, 184, 122, 0.4);"
            f" border-radius: 14px; font-size: 9pt; font-weight: 700;"
            f" letter-spacing: 1.2px; }}"
        )

        self._work_label = QLabel("0 / 0 회", header)
        work_w = 80
        work_x = plan_x - 10 - work_w
        self._work_label.setGeometry(work_x, cy - 12, work_w, 24)
        self._work_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._work_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10pt; font-weight: 600;"
            f" background: transparent;"
        )

        # 상태 배지 (대기중/진행중) + 좌측 코랄 닷
        self.status_badge = Badge("대기중", Colors.SUCCESS, header)
        status_w = 90
        status_x = work_x - 14 - status_w
        self.status_badge.setGeometry(status_x, cy - 12, status_w, 24)

        self._online_dot = QLabel("", header)
        self._online_dot.setGeometry(status_x - 18, cy - 5, 10, 10)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px;"
            f" border: 2px solid rgba(122, 184, 122, 0.35);"
        )

        self._header = header
        self._brand_icon = brand_icon

    # ── Sidebar ─────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sidebar = SidebarPanel(parent)
        # statusbar(WIN_H-STATUSBAR_H ~ WIN_H)와 겹치지 않도록 높이를 STATUSBAR_H 만큼 줄임
        sidebar.setGeometry(0, HEADER_H, SIDEBAR_W, WIN_H - HEADER_H - STATUSBAR_H)
        self._sidebar = sidebar

        # Button group for exclusive selection
        self._sidebar_group = QButtonGroup(self)
        self._sidebar_group.setExclusive(True)
        self._sidebar_buttons = []

        # ── 메뉴 (큰 아이템, 좌측 코랄 인디케이터) ──
        menu_top = 24
        item_h = 56
        for i, (icon, label) in enumerate(self._SIDEBAR_ITEMS):
            btn = QPushButton(f"   {icon}     {label}", sidebar)
            btn.setGeometry(0, menu_top + i * (item_h + 4), SIDEBAR_W, item_h)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_style())
            self._sidebar_group.addButton(btn, i)
            self._sidebar_buttons.append(btn)

        self._sidebar_buttons[0].setChecked(True)
        self._sidebar_group.idClicked.connect(self._switch_page)

        section_y = menu_top + len(self._SIDEBAR_ITEMS) * (item_h + 4) + 18

        # ── 카드 #1: 진행 상황 ──
        card_pad_x = 16
        card_w = SIDEBAR_W - card_pad_x * 2
        prog_card_h = 28 + 24 * len(self._PROCESS_STEPS) + 26
        prog_card = QFrame(sidebar)
        prog_card.setGeometry(card_pad_x, section_y, card_w, prog_card_h)
        prog_card.setStyleSheet(
            f"QFrame {{ background-color: {Colors.BG_SURFACE};"
            f" border: 1px solid {Colors.BORDER_SUBTLE};"
            f" border-radius: 14px; }}"
        )

        prog_title = QLabel("진행 상황", prog_card)
        prog_title.setGeometry(16, 12, card_w - 100, 18)
        prog_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 700;"
            f" letter-spacing: 1.4px; background: transparent; border: none;"
        )
        self._progress_queue_label = QLabel("0 / 0", prog_card)
        self._progress_queue_label.setGeometry(card_w - 80, 10, 64, 22)
        self._progress_queue_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._progress_queue_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 11pt; font-weight: 700;"
            f" background: transparent; border: none;"
        )

        # Step indicators (안에 도트 + 라벨) — 라벨 색을 TEXT_SECONDARY로 끌어올려 가독성 확보
        self._step_dots = []
        self._step_labels = []
        sy = 38
        for step_name in self._PROCESS_STEPS:
            dot = QLabel("●", prog_card)
            dot.setGeometry(14, sy, 24, 20)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(
                f"color: {Colors.BORDER_LIGHT}; font-size: 11pt; background: transparent; border: none;"
            )
            label = QLabel(step_name, prog_card)
            label.setGeometry(38, sy, card_w - 50, 20)
            label.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; font-size: 10pt; font-weight: 500;"
                f" background: transparent; border: none;"
            )
            self._step_dots.append(dot)
            self._step_labels.append(label)
            sy += 24

        section_y += prog_card_h + 12

        # ── 카드 #2: 통계 (가로 3분할) ──
        stat_card_h = 76
        stat_card = QFrame(sidebar)
        stat_card.setGeometry(card_pad_x, section_y, card_w, stat_card_h)
        stat_card.setStyleSheet(
            f"QFrame {{ background-color: {Colors.BG_SURFACE};"
            f" border: 1px solid {Colors.BORDER_SUBTLE};"
            f" border-radius: 14px; }}"
        )
        col_w = (card_w - 32) // 3

        def _stat_col(idx, label, color):
            x = 16 + col_w * idx
            cap = QLabel(label, stat_card)
            cap.setGeometry(x, 14, col_w, 14)
            cap.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 700;"
                f" letter-spacing: 1px; background: transparent; border: none;"
            )
            value = QLabel("0", stat_card)
            value.setGeometry(x, 32, col_w, 30)
            value.setStyleSheet(
                f"color: {color}; font-size: 18pt; font-weight: 800;"
                f" background: transparent; border: none;"
            )
            return value

        self._sidebar_success_label = _stat_col(0, "성공", Colors.SUCCESS)
        self._sidebar_failed_label = _stat_col(1, "실패", Colors.ERROR)
        self._sidebar_total_label = _stat_col(2, "전체", Colors.ACCENT_LIGHT)
        # legacy dot widgets — 더 이상 사용하지 않지만 참조 호환을 위해 더미 라벨로
        self._sidebar_success_dot = QLabel("", sidebar)
        self._sidebar_failed_dot = QLabel("", sidebar)
        self._sidebar_total_dot = QLabel("", sidebar)
        self._sidebar_success_dot.hide(); self._sidebar_failed_dot.hide(); self._sidebar_total_dot.hide()
        # 상태 라벨 (이전 버전 호환)
        self._sidebar_status_label = QLabel("대기중", sidebar)
        self._sidebar_status_label.hide()

        section_y += stat_card_h + 12

        # ── 카드 #3: 작업 로그 (남은 공간 모두) ──
        log_y = section_y
        log_avail_h = WIN_H - HEADER_H - log_y - STATUSBAR_H - 12
        log_card = QFrame(sidebar)
        log_card.setGeometry(card_pad_x, log_y, card_w, max(log_avail_h, 120))
        log_card.setStyleSheet(
            f"QFrame {{ background-color: {Colors.BG_SURFACE};"
            f" border: 1px solid {Colors.BORDER_SUBTLE};"
            f" border-radius: 14px; }}"
        )
        log_title = QLabel("작업 로그", log_card)
        log_title.setGeometry(16, 12, card_w - 32, 18)
        log_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 700;"
            f" letter-spacing: 1.4px; background: transparent; border: none;"
        )
        self.log_text = QTextEdit(log_card)
        self.log_text.setGeometry(12, 36, card_w - 24, max(log_avail_h - 48, 60))
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(self.MAX_LOG_LINES)
        self.log_text.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: {Colors.BG_TERMINAL};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 10px;"
            f"  padding: 10px;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"  font-family: {Typography.FAMILY_MONO};"
            f"  font-size: 9pt;"
            f"}}"
        )

    @staticmethod
    def _sidebar_btn_style():
        """Sidebar menu item — 큰 알약, 좌측 코랄 인디케이터."""
        return (
            f"QPushButton {{"
            f"  background: transparent;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"  border: none;"
            f"  border-left: 3px solid transparent;"
            f"  text-align: left;"
            f"  padding-left: 18px;"
            f"  font-size: 11pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(217, 119, 87, 0.08);"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: rgba(217, 119, 87, 0.14);"
            f"  color: {Colors.TEXT_BRIGHT};"
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
        """페이지 헤더 — 큰 코랄 칩 + 큰 타이틀(22pt). next y 반환."""
        chip_size = 44
        chip_x, chip_y = 32, 28
        # 코랄 칩
        chip = QLabel(icon_char, page)
        chip.setGeometry(chip_x, chip_y, chip_size, chip_size)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setStyleSheet(
            f"QLabel {{ background: {Gradients.ACCENT_BTN};"
            f" color: #FFFFFF; border-radius: {chip_size // 2}px;"
            f" font-size: 16pt; font-weight: 700;"
            f" border: 2px solid rgba(217, 119, 87, 0.30); }}"
        )
        # 큰 타이틀
        title = QLabel(title_text, page)
        title.setGeometry(chip_x + chip_size + 16, chip_y + 4, 460, 36)
        title.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 20pt; font-weight: 700;"
            f" letter-spacing: -0.5px; background: transparent;"
        )
        # 미세한 구분선 (칩 아래)
        sep = QFrame(page)
        sep.setGeometry(28, chip_y + chip_size + 18, CONTENT_W - 56, 1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER_SUBTLE}; border: none;")

        return chip_y + chip_size + 32  # 다음 가용 y

    # ── Page 0: 링크 입력 ───────────────────────────────────

    def _build_page0_links(self, page):
        cy = self._make_page_header(page, "◈", "링크 입력")

        # Coupang Partners hyperlink (top right)
        coupang_link = QLabel(
            '<a href="https://partners.coupang.com/" '
            'style="color: #E89175; text-decoration: none; font-weight: 600;">'
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
        self.links_text.setGeometry(28, cy + 24, 984, 160)
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
            f"  border: 2px solid rgba(232, 145, 117, 0.5);"
            f"  border-radius: {Radius.LG};"
            f"  font-size: 11pt; font-weight: 800; letter-spacing: 0.5px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Gradients.ACCENT_BTN_HOVER};"
            f"  border-color: rgba(232, 145, 117, 0.8);"
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
        self.link_table.setGeometry(28, table_y, 984, table_h)
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
        sec1.setGeometry(28, cy, 984, 140)

        sec1_title = QLabel("업로드 간격", sec1)
        sec1_title.setGeometry(24, 16, 200, 22)
        sec1_title.setStyleSheet(section_title_style())

        interval_hint = QLabel("최소 30초 - 업로드 사이 대기 시간을 설정합니다", sec1)
        interval_hint.setGeometry(24, 42, 500, 16)
        interval_hint.setStyleSheet(hint_text_style())

        # spinbox — text는 우측 화살표 옆까지, 우측 끝에 up/down 한 덩어리
        # 너비는 padding(우 30 + 좌 12) + suffix("0 시간")까지 충분히
        self.hour_spin = QSpinBox(sec1)
        self.hour_spin.setGeometry(24, 68, 140, 40)
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" 시간")

        self.min_spin = QSpinBox(sec1)
        self.min_spin.setGeometry(176, 68, 120, 40)
        self.min_spin.setRange(0, 59)
        self.min_spin.setSuffix(" 분")

        self.sec_spin = QSpinBox(sec1)
        self.sec_spin.setGeometry(308, 68, 120, 40)
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setSuffix(" 초")

        # ── Upload Options Section ─────────────────────────
        sec2 = SectionFrame(page)
        sec2.setGeometry(28, cy + 156, 984, 90)

        sec2_title = QLabel("업로드 옵션", sec2)
        sec2_title.setGeometry(24, 16, 200, 22)
        sec2_title.setStyleSheet(section_title_style())

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선", sec2)
        self.video_check.setGeometry(24, 48, 400, 24)

        # ── Save Button ────────────────────────────────────
        # 카드 우측 끝과 정렬 (28 + 984 - 140 = 872)
        self._upload_save_btn = QPushButton("저장", page)
        self._upload_save_btn.setGeometry(872, cy + 268, 140, 42)
        self._upload_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_save_btn.clicked.connect(self._save_settings)

    # ── Page 2: 설정 ────────────────────────────────────────

    def _build_page2_settings(self, page):
        cy = self._make_page_header(page, "⚙", "설정")

        # ── 페이지 헤더 우측 액션 버튼 (저장 / 업데이트 확인) ──
        # ScrollArea 안에 들어가지 않고 페이지에 직접 부착해 항상 보임
        action_y = 32
        save_w = 110
        upd_w = 168     # "업데이트 확인" 한글 5자 + 영문 + 패딩 충분히
        save_x = CONTENT_W - 28 - save_w
        upd_x = save_x - 12 - upd_w

        self._update_settings_btn = QPushButton("업데이트 확인", page)
        self._update_settings_btn.setGeometry(upd_x, action_y, upd_w, 36)
        self._update_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_settings_btn.setProperty("class", "ghost")
        self._update_settings_btn.clicked.connect(self.check_for_updates)

        self._settings_save_btn = QPushButton("저장", page)
        self._settings_save_btn.setGeometry(save_x, action_y, save_w, 36)
        self._settings_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_save_btn.clicked.connect(self._save_settings)

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
        # ScrollArea viewport는 세로 스크롤바 자리 8px 만큼 좁아짐 — 그만큼 빼서 가로 스크롤 차단
        content.setFixedWidth(CONTENT_W - 16)
        scroll.setWidget(content)

        sy = 8  # y offset within scroll content

        # ── Section 1: 계정 정보 ───────────────────────────
        acct = SectionFrame(content)
        acct.setGeometry(28, sy, 984, 80)

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
        # 카드 너비 984 기준 — 우측 끝(984-24-140=820)에 정렬
        self._acct_plan_badge = QLabel("무료 체험", acct)
        self._acct_plan_badge.setGeometry(820, 16, 140, 26)
        self._acct_plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_plan_badge.setStyleSheet(
            f"QLabel {{ background-color: rgba(122, 184, 122, 0.12);"
            f" color: {Colors.SUCCESS}; border: 1px solid rgba(122, 184, 122, 0.3);"
            f" border-radius: 13px; font-size: 9pt; font-weight: 700; }}"
        )

        self._acct_work_label = QLabel("0 / 0 회 사용", acct)
        self._acct_work_label.setGeometry(820, 46, 140, 18)
        self._acct_work_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._acct_work_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )

        sy += 92

        # ── Section 2: Threads 계정 ────────────────────────
        threads_sec = SectionFrame(content)
        threads_sec.setGeometry(28, sy, 984, 184)

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
        self.username_edit.setGeometry(24, 64, 936, 34)
        self.username_edit.setPlaceholderText("예: myaccount")

        # Status dot + label (한 줄)
        self._threads_status_dot = QLabel("", threads_sec)
        self._threads_status_dot.setGeometry(24, 112, 10, 10)
        self._threads_status_dot.setStyleSheet(
            f"background-color: {Colors.TEXT_MUTED}; border-radius: 5px;"
        )

        self.login_status_label = QLabel("연결 안됨", threads_sec)
        self.login_status_label.setGeometry(42, 108, 200, 20)
        self.login_status_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
            " background: transparent;"
        )

        # 안내문 — status 라벨 우측에 같은 줄로 배치 (버튼과 겹침 방지)
        hint_label = QLabel("로그인 후 브라우저를 닫으면 세션이 자동 저장됩니다.", threads_sec)
        hint_label.setGeometry(260, 108, 660, 20)
        hint_label.setStyleSheet(hint_text_style())

        # Threads login button — status 라벨(y=108~128)과 12px 간격 두고 배치
        self.threads_login_btn = QPushButton("Threads 로그인", threads_sec)
        self.threads_login_btn.setGeometry(24, 140, 200, 36)
        self.threads_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)

        # Check login button
        self.check_login_btn = QPushButton("상태 확인", threads_sec)
        self.check_login_btn.setGeometry(234, 140, 160, 36)
        self.check_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_login_btn.setProperty("class", "ghost")
        self.check_login_btn.clicked.connect(self._check_login_status)

        sy += 196

        # ── Section 3: API 설정 ────────────────────────────
        api_sec = SectionFrame(content)
        api_sec.setGeometry(28, sy, 984, 100)

        api_title = QLabel("API 설정", api_sec)
        api_title.setGeometry(24, 12, 200, 22)
        api_title.setStyleSheet(section_title_style())

        api_label = QLabel("마스터 API 키", api_sec)
        api_label.setGeometry(24, 38, 110, 16)
        api_label.setStyleSheet(_field_lbl_style)

        api_hint = QLabel("Google AI Studio에서 발급", api_sec)
        api_hint.setGeometry(140, 38, 300, 16)
        api_hint.setStyleSheet(hint_text_style())

        self.gemini_key_edit = QLineEdit(api_sec)
        self.gemini_key_edit.setGeometry(24, 58, 936, 34)
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("Gemini API 키를 입력하세요")

        sy += 112

        # ── Section 4: 텔레그램 알림 ───────────────────────
        # 채팅 ID 입력란(y=148, h=34, 끝=182)이 카드 안에 들어오도록 높이 192
        tg_sec = SectionFrame(content)
        tg_sec.setGeometry(28, sy, 984, 192)

        tg_title = QLabel("텔레그램 알림", tg_sec)
        tg_title.setGeometry(24, 12, 200, 22)
        tg_title.setStyleSheet(section_title_style())

        self.telegram_check = QCheckBox("텔레그램 알림 활성화", tg_sec)
        self.telegram_check.setGeometry(24, 40, 300, 22)

        bot_label = QLabel("봇 토큰", tg_sec)
        bot_label.setGeometry(24, 68, 100, 16)
        bot_label.setStyleSheet(_field_lbl_style)

        self.bot_token_edit = QLineEdit(tg_sec)
        self.bot_token_edit.setGeometry(24, 88, 936, 34)
        self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bot_token_edit.setPlaceholderText("BotFather 토큰")

        chat_label = QLabel("채팅 ID", tg_sec)
        chat_label.setGeometry(24, 128, 100, 16)
        chat_label.setStyleSheet(_field_lbl_style)

        self.chat_id_edit = QLineEdit(tg_sec)
        self.chat_id_edit.setGeometry(24, 148, 896, 34)
        self.chat_id_edit.setPlaceholderText("채팅 ID")

        sy += 204

        # ── Sections 5–7 통합: 앱 정보 / 튜토리얼 / 문의하기를 한 줄 가로 3분할 카드 ──
        bottom_sec = SectionFrame(content)
        bottom_sec.setGeometry(28, sy, 984, 92)

        # 셀 너비 = (984 - 24*2 padding - 16*2 gap) / 3 = (984-80) / 3 = 301
        cell_w = (984 - 24 * 2 - 16 * 2) // 3
        cell_y = 12
        cell_h = 64

        # 5-1) 앱 정보
        info_x = 24
        info_title = QLabel("앱 정보", bottom_sec)
        info_title.setGeometry(info_x, cell_y, cell_w, 18)
        info_title.setStyleSheet(section_title_style())
        self._version_label = QLabel("", bottom_sec)
        self._version_label.setGeometry(info_x, cell_y + 24, cell_w, 18)
        self._version_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
        )
        dev_label = QLabel("개발: 쿠팡 파트너스 자동화 팀", bottom_sec)
        dev_label.setGeometry(info_x, cell_y + 44, cell_w, 16)
        dev_label.setStyleSheet(hint_text_style())

        # 5-2) 튜토리얼
        tut_x = info_x + cell_w + 16
        tut_title = QLabel("튜토리얼", bottom_sec)
        tut_title.setGeometry(tut_x, cell_y, cell_w, 18)
        tut_title.setStyleSheet(section_title_style())
        self._tutorial_settings_btn = QPushButton("튜토리얼 재실행", bottom_sec)
        self._tutorial_settings_btn.setGeometry(tut_x, cell_y + 26, min(cell_w, 180), 34)
        self._tutorial_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tutorial_settings_btn.setProperty("class", "ghost")
        self._tutorial_settings_btn.clicked.connect(self.open_tutorial)

        # 5-3) 문의하기
        ct_x = tut_x + cell_w + 16
        ct_title = QLabel("문의하기", bottom_sec)
        ct_title.setGeometry(ct_x, cell_y, cell_w, 18)
        ct_title.setStyleSheet(section_title_style())
        self._contact_btn = QPushButton("문의하기", bottom_sec)
        self._contact_btn.setGeometry(ct_x, cell_y + 26, min(cell_w, 140), 34)
        self._contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._contact_btn.setProperty("class", "ghost")
        self._contact_btn.clicked.connect(self._open_contact)

        sy += 104

        # 액션 버튼은 페이지 헤더 우측으로 옮겼으므로 ScrollArea 안에서는 제거됨

        # Set scroll content height — viewport(=CONTENT_H-cy-스크롤바)에 정확히 맞춤
        content.setFixedHeight(sy + 4)

    # ── StatusBar ───────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = QFrame(parent)
        bar.setGeometry(0, WIN_H - STATUSBAR_H, WIN_W, STATUSBAR_H)
        bar.setStyleSheet(
            f"QFrame {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            f"    stop:0 {Colors.BG_HEADER}, stop:1 {Colors.BG_DARK});"
            f"  border-top: 1px solid {Colors.BORDER_SUBTLE};"
            f"}}"
        )
        self._status_bar_frame = bar

        # Dot
        self._statusbar_dot = QLabel("", bar)
        self._statusbar_dot.setGeometry(16, 11, 10, 10)
        self._statusbar_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px;"
            f" border: 2px solid rgba(122, 184, 122, 0.3);"
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
        # Update sidebar progress labels
        self._sidebar_success_label.setText(str(success))
        self._sidebar_failed_label.setText(str(failed))
        self._sidebar_total_label.setText(str(total))
        # Update queue progress
        self._progress_queue_label.setText(f"전체: {total} 처리됨")

    def _add_product(self, title, success):
        # No separate product list; table is updated via link_status signal
        pass

    def _on_finished(self, results):
        logger.info("Upload finished: %s", results)
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "Ready")
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
        self.telegram_check.setChecked(config.telegram_enabled)
        self.bot_token_edit.setText(config.telegram_bot_token)
        self.chat_id_edit.setText(config.telegram_chat_id)
        self.username_edit.setText(config.instagram_username)

    def _save_settings(self):
        """Save widget values to config, reinitialize pipeline."""
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

    def _update_account_display(self):
        """Update header and settings page with auth data."""
        auth = getattr(self, '_auth_data', None) or {}
        username = auth.get("username") or getattr(self, '_auth_data', {}).get("id", "")

        # Resolve from auth_client state if not in auth_data
        try:
            from src import auth_client
            state = auth_client.get_auth_state()
            if not username:
                username = state.get("username", "")
            work_count = state.get("work_count", 0)
            work_used = state.get("work_used", 0)
        except Exception:
            work_count = auth.get("work_count", 0)
            work_used = auth.get("work_used", 0)

        display_name = username or "사용자"

        # Header plan badge
        if work_count > 10:
            self._plan_badge.setText("PRO")
            self._plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(217, 119, 87, 0.15);"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid rgba(217, 119, 87, 0.3);"
                f" border-radius: 14px; font-size: 9pt; font-weight: 700;"
                f" letter-spacing: 1px; }}"
            )
        else:
            self._plan_badge.setText("FREE")
            self._plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(122, 184, 122, 0.12);"
                f" color: {Colors.SUCCESS}; border: 1px solid rgba(122, 184, 122, 0.3);"
                f" border-radius: 14px; font-size: 9pt; font-weight: 700;"
                f" letter-spacing: 1px; }}"
            )

        self._work_label.setText(f"{work_used} / {work_count} 회")

        # Settings page account card
        self._acct_username_label.setText(display_name)
        self._acct_work_label.setText(f"{work_used} / {work_count} 회 사용")

        if work_count > 10:
            self._acct_plan_badge.setText("프로 구독")
            self._acct_plan_badge.setStyleSheet(
                f"QLabel {{ background-color: rgba(217, 119, 87, 0.15);"
                f" color: {Colors.ACCENT_LIGHT}; border: 1px solid rgba(217, 119, 87, 0.3);"
                f" border-radius: 13px; font-size: 9pt; font-weight: 700; }}"
            )
        else:
            self._acct_plan_badge.setText("무료 체험")

        # Version label
        self._version_label.setText(f"현재 버전: {self._app_version}")

    def _open_contact(self):
        """Open contact/support dialog."""
        show_info(
            self,
            "문의하기",
            "문의사항이 있으시면 아래로 연락해주세요.\n\n"
            "이메일: support@example.com\n"
            "텔레그램: @support_bot\n\n"
            "영업시간: 평일 10:00 - 18:00"
        )

    def open_settings(self):
        """Switch to settings page (page 2) instead of opening dialog."""
        logger.info("open_settings invoked")
        self._switch_page(2)

    # ────────────────────────────────────────────────────────
    #  THREADS LOGIN LOGIC
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
                logger.exception("browser error during Threads login flow")

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

        from PyQt6.QtCore import QTimer
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
                logger.exception("login status check failed")
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
        self.status_badge.update_style(Colors.WARNING, "실행중")
        self._sidebar_status_label.setText("실행중")

        self._sidebar_success_label.setText("0")
        self._sidebar_failed_label.setText("0")
        self._sidebar_total_label.setText("0")
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

        total_links = self.link_queue.qsize()

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

                # Update progress
                self._progress_queue_label.setText(
                    f"전체: {processed_count} / {total_links}"
                )

                # Step 0: Link analysis
                self.signals.step_update.emit(0, "active")
                self.signals.link_status.emit(url, "진행중", "")

                log("Parsing product data...")

                try:
                    # Step 1: Content generation (parse + AI)
                    self.signals.step_update.emit(0, "done")
                    self.signals.step_update.emit(1, "active")

                    post_data = self.pipeline.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results["parse_failed"] += 1
                        log("Parse failed. Skipping this item.")
                        self.signals.step_update.emit(1, "error")
                        self.signals.link_status.emit(url, "실패", "분석 실패")
                        self._reset_steps()
                        continue

                    results["processed"] += 1
                    product_name = post_data.get("product_title", "")[:30]
                    log(f"Parse completed: {product_name}")
                    self.signals.step_update.emit(1, "done")
                except Exception as exc:
                    results["parse_failed"] += 1
                    log(f"Parse error: {str(exc)[:80]}")
                    self.signals.step_update.emit(1, "error")
                    self.signals.link_status.emit(url, "실패", "오류")
                    self._reset_steps()
                    continue

                # Step 2: Upload to Threads
                self.signals.step_update.emit(2, "active")
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
                        self.signals.step_update.emit(2, "done")
                        self.signals.step_update.emit(3, "done")
                        self.signals.link_status.emit(url, "완료", product_name)
                    else:
                        results["failed"] += 1
                        log(f"Upload failed: {product_name}")
                        self.signals.step_update.emit(2, "error")
                        self.signals.link_status.emit(url, "실패", product_name)

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
                    self.signals.step_update.emit(2, "error")
                    self.signals.link_status.emit(url, "실패", product_name)

                self.signals.results.emit(results["uploaded"], results["failed"])
                self._reset_steps()

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
        dialog.exec()

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
            # Silent check: keep UI quiet; details are already in logs.
            return

    def open_tutorial(self):
        logger.info("open_tutorial invoked")
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
        bot_grad.setColorAt(0, QColor(217, 119, 87, 0))
        bot_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        bot_grad.setColorAt(0.7, QColor(Colors.ACCENT))
        bot_grad.setColorAt(1, QColor(217, 119, 87, 0))
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
