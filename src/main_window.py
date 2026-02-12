"""
쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (PyQt5)
Stitch Blue 디자인 - 좌표 기반 배치
"""
import re
import html
import time
import logging
import threading
import queue
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QListWidget, QFrame,
    QMessageBox, QStatusBar, QTabWidget, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPainter, QLinearGradient

from src.config import config
from src.coupang_uploader import CoupangPartnersPipeline
from src.theme import (Colors, Typography, Radius, Gradients, Spacing,
                       global_stylesheet, hex_alpha, badge_style, stat_card_style,
                       tab_widget_style, terminal_text_style, header_title_style,
                       muted_text_style, section_icon_style, accent_btn_style,
                       outline_btn_style)

logger = logging.getLogger(__name__)


#

def _format_interval(seconds):
    """Return a human-readable interval."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"




#

class Signals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(str)
    results = pyqtSignal(int, int)
    product = pyqtSignal(str, bool)
    finished = pyqtSignal(dict)


#

class Card(QFrame):
    """둥근 글로우 카드 위젯 (Stitch 스타일)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

    def paintEvent(self, _event):
        from PyQt5.QtGui import QPen, QPainterPath
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)

        #
        glow_pen = QPen(QColor(13, 89, 242, 65), 3)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 14, 14)

        #
        painter.setPen(QPen(QColor("#3A4C65"), 1.5))
        painter.setBrush(QColor("#1C2840"))
        painter.drawRoundedRect(rect, 12, 12)

        #
        accent = QLinearGradient(rect.x(), 0, rect.right(), 0)
        accent.setColorAt(0, QColor(13, 89, 242, 0))
        accent.setColorAt(0.2, QColor(13, 89, 242, 140))
        accent.setColorAt(0.5, QColor(59, 123, 255, 180))
        accent.setColorAt(0.8, QColor(13, 89, 242, 140))
        accent.setColorAt(1, QColor(59, 123, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        clip = QPainterPath()
        clip.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), 4.0, 12, 12)
        painter.drawPath(clip)

        #
        left_grad = QLinearGradient(0, rect.y(), 0, rect.bottom())
        left_grad.setColorAt(0, QColor(Colors.ACCENT_LIGHT))
        left_grad.setColorAt(0.5, QColor(Colors.ACCENT))
        left_grad.setColorAt(1, QColor(Colors.ACCENT_DARK))
        painter.setBrush(left_grad)
        left_bar = QPainterPath()
        left_bar.addRoundedRect(float(rect.x()), float(rect.y() + 12), 3.0, float(rect.height() - 24), 1.5, 1.5)
        painter.drawPath(left_bar)


#

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


#

class HeaderBar(QFrame):
    """그라디언트 헤더 바."""
    ACCENT_LINE_H = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        #
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#12203A"))
        grad.setColorAt(0.5, QColor("#162847"))
        grad.setColorAt(1, QColor("#12203A"))
        painter.fillRect(self.rect(), grad)

        #
        accent = QLinearGradient(0, 0, w, 0)
        accent.setColorAt(0, QColor(13, 89, 242, 0))
        accent.setColorAt(0.2, QColor(Colors.ACCENT))
        accent.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        accent.setColorAt(0.8, QColor(Colors.ACCENT))
        accent.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, 0, w, self.ACCENT_LINE_H, accent)

        #
        from PyQt5.QtGui import QPen
        painter.setPen(QPen(QColor(13, 89, 242, 80), 1))
        painter.drawLine(0, h - 1, w, h - 1)


#

class MainWindow(QMainWindow):
    """쿠팡 파트너스 스레드 자동화 메인 윈도우."""

    MAX_LOG_LINES = 2000

    #
    WIN_W = 1120
    WIN_H = 760
    HEADER_H = 72
    MARGIN = 16
    GAP = 12
    LEFT_W = 440

    COUPANG_LINK_PATTERN = re.compile(
        r'https?://(?:link\.coupang\.com|www\.coupang\.com)[^\s<>"\']*',
        re.IGNORECASE
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coupang Partners Thread Automation")
        self.setFixedSize(self.WIN_W, self.WIN_H)

        self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._urls_lock = threading.Lock()
        self.link_queue = queue.Queue()
        self.processed_urls = set()
        logger.info("MainWindow initialized")

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)

        self._build_ui()
        self.setStyleSheet(global_stylesheet())
        self._tutorial_overlay = None

        #
        self._tutorial_widgets = {}

        #
        from PyQt5.QtCore import QTimer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(60_000)
        #
        QTimer.singleShot(1000, self._send_heartbeat)

        #
        QTimer.singleShot(3000, self._check_for_updates_silent)
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

    #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        #
        self._build_header(central)

        #
        content_y = self.HEADER_H + 14
        content_h = self.WIN_H - self.HEADER_H - 14 - 40
        right_x = self.MARGIN + self.LEFT_W + self.GAP
        right_w = self.WIN_W - right_x - self.MARGIN

        #
        self._build_input_panel(central, self.MARGIN, content_y, self.LEFT_W, content_h)

        #
        self._build_output_panel(central, right_x, content_y, right_w, content_h)

        #
        self._build_statusbar()

    def _build_header(self, parent):
        header = HeaderBar(parent)
        header.setGeometry(0, 0, self.WIN_W, self.HEADER_H)

        #
        brand_glow = QLabel("", header)
        brand_glow.setGeometry(14, 12, 48, 48)
        brand_glow.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(13, 89, 242, 0.25);
                border: 2px solid rgba(13, 89, 242, 0.4);
                border-radius: 24px;
            }}
        """)
        brand_icon = QLabel("C", header)
        brand_icon.setGeometry(18, 16, 40, 40)
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setStyleSheet(f"""
            QLabel {{
                background: {Gradients.ACCENT_BTN};
                color: #FFFFFF;
                border-radius: 20px;
                font-size: 17pt;
                font-weight: 800;
            }}
        """)

        #
        title_label = QLabel("쿠팡 파트너스", header)
        title_label.setGeometry(72, 12, 250, 32)
        title_label.setStyleSheet(
            f"color: #FFFFFF; font-size: 16pt; font-weight: 800; "
            f"letter-spacing: -0.5px; background: transparent;"
        )

        #
        sub_label = QLabel("THREAD AUTOMATION", header)
        sub_label.setGeometry(72, 42, 200, 20)
        sub_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 700; "
            f"letter-spacing: 2px; background: transparent;"
        )

        #
        rx = self.WIN_W - 20

        #
        _nav_pill_style = f"""
            QPushButton {{
                background: rgba(13, 89, 242, 0.08);
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid rgba(13, 89, 242, 0.15);
                border-radius: 14px;
                font-size: 9pt;
                font-weight: 600;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: rgba(13, 89, 242, 0.20);
                color: #FFFFFF;
                border-color: rgba(13, 89, 242, 0.40);
            }}
        """

        #
        rx -= 68
        self.logout_btn = QPushButton("로그아웃", header)
        self.logout_btn.setGeometry(rx, 22, 64, 28)
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239, 68, 68, 0.08);
                color: {Colors.TEXT_MUTED};
                border: 1px solid rgba(239, 68, 68, 0.15);
                border-radius: 14px;
                font-size: 9pt;
                font-weight: 600;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.25);
                color: {Colors.ERROR};
                border-color: {Colors.ERROR};
            }}
        """)
        self.logout_btn.clicked.connect(self._do_logout)

        #
        rx -= 56
        self.settings_btn = QPushButton("설정", header)
        self.settings_btn.setGeometry(rx, 22, 48, 28)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(_nav_pill_style)
        self.settings_btn.clicked.connect(self.open_settings)

        #
        rx -= 68
        self.update_btn = QPushButton("업데이트", header)
        self.update_btn.setGeometry(rx, 22, 60, 28)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setStyleSheet(_nav_pill_style)
        self.update_btn.clicked.connect(self.check_for_updates)

        #
        rx -= 58
        self.tutorial_btn = QPushButton("Tutorial", header)
        self.tutorial_btn.setGeometry(rx, 22, 50, 28)
        self.tutorial_btn.setCursor(Qt.PointingHandCursor)
        self.tutorial_btn.setStyleSheet(_nav_pill_style)
        self.tutorial_btn.clicked.connect(self.open_tutorial)

        #
        rx -= 100
        self.status_badge = Badge("대기중", Colors.SUCCESS, header)
        self.status_badge.setGeometry(rx, 24, 90, 24)

        #
        rx -= 18
        self._online_dot = QLabel("", header)
        self._online_dot.setGeometry(rx, 32, 10, 10)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px; "
            f"border: 2px solid rgba(34, 197, 94, 0.3);"
        )

        #
        self._header = header
        self._brand_icon = brand_icon

    def _build_input_panel(self, parent, x, y, w, h):
        panel = Card(parent)
        panel.setGeometry(x, y, w, h)

        px, py = 18, 16
        inner_w = w - 36  # 18 * 2

        #
        icon_bg = QLabel("", panel)
        icon_bg.setGeometry(px, py, 32, 32)
        icon_bg.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(13, 89, 242, 0.15);
                border: 1px solid rgba(13, 89, 242, 0.3);
                border-radius: 16px;
            }}
        """)
        icon_label = QLabel("\u26A1", panel)
        icon_label.setGeometry(px, py, 32, 32)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 14pt; background: transparent;"
        )

        #
        sec_label = QLabel("새 자동화 시작", panel)
        sec_label.setGeometry(px + 40, py, 250, 32)
        sec_label.setStyleSheet(
            f"font-size: 13pt; font-weight: 800; color: #FFFFFF; "
            f"letter-spacing: -0.3px; background: transparent;"
        )

        #
        self.link_count_badge = Badge("0개 링크", Colors.TEXT_MUTED, panel)
        self.link_count_badge.setGeometry(w - 18 - 90, py + 2, 90, 24)

        #
        hint = QLabel("아래에 쿠팡 파트너스 URL을 붙여넣기 하세요 (한 줄에 하나씩)", panel)
        hint.setGeometry(px, py + 40, inner_w, 18)
        hint.setStyleSheet(muted_text_style("9pt"))

        #
        text_y = py + 66
        text_h = (h - 16 - 48) - text_y - 12  # 48 = btn_h

        self.links_text = QPlainTextEdit(panel)
        self.links_text.setGeometry(px, text_y, inner_w, text_h)
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://link.coupang.com/a/yyy"
        )
        self.links_text.textChanged.connect(self._update_link_count)

        #
        btn_h = 48
        btn_y = h - 16 - btn_h
        btn_gap = 10
        total_btn_w = inner_w - btn_gap * 2
        start_w = int(total_btn_w * 0.50)
        add_w = int(total_btn_w * 0.28)
        stop_w = total_btn_w - start_w - add_w

        self.start_btn = QPushButton("\u25B6  자동화 시작", panel)
        self.start_btn.setGeometry(px, btn_y, start_w, btn_h)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN};
                color: #FFFFFF;
                border: 2px solid rgba(59, 123, 255, 0.5);
                border-radius: {Radius.LG};
                font-size: 12pt;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: {Gradients.ACCENT_BTN_HOVER};
                border-color: rgba(59, 123, 255, 0.8);
            }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
            QPushButton:disabled {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_MUTED};
                border-color: {Colors.BORDER};
            }}
        """)
        self.start_btn.clicked.connect(self.start_upload)

        self.add_btn = QPushButton("링크 추가", panel)
        self.add_btn.setGeometry(px + start_w + btn_gap, btn_y, add_w, btn_h)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setEnabled(False)
        self.add_btn.setProperty("class", "outline-success")
        self.add_btn.clicked.connect(self.add_links_to_queue)

        self.stop_btn = QPushButton("중지", panel)
        self.stop_btn.setGeometry(px + start_w + btn_gap + add_w + btn_gap, btn_y, stop_w, btn_h)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "outline-danger")
        self.stop_btn.clicked.connect(self.stop_upload)

        #
        self._input_panel = panel

    def _build_output_panel(self, parent, x, y, w, h):
        panel = Card(parent)
        panel.setGeometry(x, y, w, h)

        #
        self.tabs = QTabWidget(panel)
        self.tabs.setGeometry(0, 0, w, h)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(tab_widget_style())

        #
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(16, 10, 16, 16)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_icon = QLabel(">")
        log_icon.setStyleSheet(
            f"color: {Colors.ACCENT}; font-family: {Typography.FAMILY_MONO}; "
            f"font-size: 11pt; font-weight: 700;"
        )
        log_icon.setFixedWidth(18)
        log_header.addWidget(log_icon)
        log_title = QLabel("작업 내용")
        log_title.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; letter-spacing: 1px;"
        )
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(self.MAX_LOG_LINES)
        self.log_text.setStyleSheet(terminal_text_style())
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "작업 내용")

        #
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(16, 10, 16, 16)
        result_layout.setSpacing(12)

        #
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self.stat_success, self._stat_success_val = self._build_stat_card("성공", "0", Colors.SUCCESS)
        self.stat_failed, self._stat_failed_val = self._build_stat_card("실패", "0", Colors.ERROR)
        self.stat_total, self._stat_total_val = self._build_stat_card("전체", "0", Colors.INFO)
        stats_row.addWidget(self.stat_success)
        stats_row.addWidget(self.stat_failed)
        stats_row.addWidget(self.stat_total)
        result_layout.addLayout(stats_row)

        #
        list_header = QHBoxLayout()
        list_label = QLabel("처리된 항목")
        list_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; letter-spacing: 1px;"
        )
        list_header.addWidget(list_label)
        list_header.addStretch()
        result_layout.addLayout(list_header)

        self.products_list = QListWidget()
        self.products_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG};
                padding: 6px;
                font-size: 9pt;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: {Radius.SM};
                border-bottom: 1px solid {Colors.BORDER};
            }}
            QListWidget::item:last-child {{
                border-bottom: none;
            }}
        """)
        result_layout.addWidget(self.products_list, 1)
        self.tabs.addTab(result_tab, "결과")

        #
        self._output_panel = panel

    _STAT_ICONS = {"성공": "\u2714", "실패": "\u2718", "전체": "\u03A3"}
    _STAT_ENG = {"성공": "SUCCESS", "실패": "FAIL", "전체": "TOTAL"}

    def _build_stat_card(self, label, value, color):
        card = QFrame()
        card.setStyleSheet(stat_card_style(color))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        #
        icon_label = QLabel(self._STAT_ICONS.get(label, ""))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            f"color: {color}; font-size: 20pt; font-weight: 800; background: transparent; border: none;"
        )
        layout.addWidget(icon_label)

        #
        val_label = QLabel(value)
        val_label.setAlignment(Qt.AlignCenter)
        val_label.setStyleSheet(
            f"color: {color}; font-size: 28pt; font-weight: 800; background: transparent; border: none;"
        )
        layout.addWidget(val_label)

        #
        eng_label = QLabel(self._STAT_ENG.get(label, label))
        eng_label.setAlignment(Qt.AlignCenter)
        eng_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 7pt; font-weight: 700; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )
        layout.addWidget(eng_label)

        return card, val_label

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.setStyleSheet(f"""
            QStatusBar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #12203A, stop:0.5 #162847, stop:1 #12203A);
                color: {Colors.TEXT_SECONDARY};
                border-top: 2px solid rgba(13, 89, 242, 0.3);
                padding: 6px 16px;
                font-size: 9pt;
            }}
        """)

        #
        self._statusbar_dot = QLabel("")
        self._statusbar_dot.setFixedSize(10, 10)
        self._statusbar_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 5px; "
            f"border: 2px solid rgba(34, 197, 94, 0.3);"
        )
        self.statusbar.addWidget(self._statusbar_dot)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600;")
        self.statusbar.addWidget(self.status_label, 1)

        #
        self._server_label = QLabel("서버 연결: --")
        self._server_label.setStyleSheet(f"color: {Colors.ACCENT_LIGHT}; font-size: 8pt; font-weight: 600;")
        self.statusbar.addPermanentWidget(self._server_label)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt;")
        self.statusbar.addPermanentWidget(self.progress_label)

    #

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

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get("parse_failed", 0)
        uploaded = results.get("uploaded", 0)
        failed = results.get("failed", 0)

        if results.get("cancelled"):
            msg = (
                "업로드가 취소되었습니다.\n\n"
                f"  완료: {uploaded}\n"
                f"  실패: {failed}"
            )
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            QMessageBox.information(self, "취소됨", msg)
        else:
            msg = (
                "업로드가 완료되었습니다.\n\n"
                f"  성공: {uploaded}\n"
                f"  실패: {failed}"
            )
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            QMessageBox.information(self, "완료", msg)

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

    #

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리."""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def open_settings(self):
        logger.info("open_settings invoked")
        from src.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)
            logger.info("settings saved; pipeline reinitialized")

    def open_tutorial(self):
        logger.info("open_tutorial invoked")
        from src.tutorial import TutorialDialog
        dialog = TutorialDialog(self)
        dialog.exec_()

    def start_upload(self):
        logger.info("start_upload invoked")
        content = self.links_text.toPlainText().strip()
        if not content:
            logger.warning("start_upload blocked: empty content")
            QMessageBox.warning(self, "알림", "쿠팡 파트너스 링크를 입력하세요.")
            return

        api_key = config.gemini_api_key
        if not api_key or len(api_key.strip()) < 10:
            logger.warning("start_upload blocked: invalid API key")
            QMessageBox.critical(self, "설정 필요", "설정에서 유효한 Gemini API 키를 설정하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            logger.warning("start_upload blocked: no valid links found")
            QMessageBox.warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
            return

        config.load()
        interval = max(config.upload_interval, 30)
        logger.info("start_upload prepared: links=%d interval=%d", len(link_data), interval)

        reply = QMessageBox.question(
            self,
            "확인",
            f"{len(link_data)}개 링크를 처리하고 업로드할까요?\n"
            f"업로드 간격: {_format_interval(interval)}\n\n"
            "(실행 중에 링크를 추가할 수 있습니다)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            logger.info("start_upload cancelled by user")
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.products_list.clear()
        self.status_badge.update_style(Colors.WARNING, "실행중")

        self._stat_success_val.setText("0")
        self._stat_failed_val.setText("0")
        self._stat_total_val.setText("0")

        with self._urls_lock:
            self.processed_urls.clear()
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)

        clean_links = "\n".join([item[0] for item in link_data])
        self.links_text.setPlainText(clean_links)

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
            QMessageBox.warning(self, "알림", "추가할 링크를 입력하세요.")
            return

        link_data = self._extract_links(content)
        if not link_data:
            logger.warning("add_links_to_queue blocked: no valid links found")
            QMessageBox.warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
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
            QMessageBox.information(self, "알림", "모든 링크가 이미 대기열에 있거나 처리되었습니다.")

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

    def stop_upload(self):
        logger.info("stop_upload invoked; is_running=%s", self.is_running)
        if self.is_running:
            self.signals.log.emit("Stop requested. The current item will finish first.")
            self.signals.status.emit("Stopping...")
            self.status_badge.update_style(Colors.WARNING, "Stopping")
            self.is_running = False
            self.pipeline.cancel()

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
                return

            task = "uploading" if self.is_running else "idle"
            result = auth_client.heartbeat(current_task=task, app_version="v2.2.0")
            if result.get("status") is True:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
                )
                if not self.is_running:
                    self.status_label.setText("Connected")
            else:
                self._online_dot.setStyleSheet(
                    f"background-color: {Colors.ERROR}; border-radius: 4px;"
                )
                self.status_label.setText("Connection lost")
        except Exception:
            logger.exception("heartbeat failed")
            self._online_dot.setStyleSheet(
                f"background-color: {Colors.ERROR}; border-radius: 4px;"
            )
            self.status_label.setText("Connection error")

    def _do_logout(self):
        """로그아웃 처리 후 앱 종료."""
        logger.info("logout requested")
        if self.is_running:
            QMessageBox.warning(self, "알림", "작업 중에는 로그아웃할 수 없습니다.\n먼저 작업을 중지해주세요.")
            return
        reply = QMessageBox.question(
            self, "로그아웃",
            "로그아웃하고 프로그램을 종료하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                from src import auth_client
                auth_client.logout()
            except Exception:
                pass
            QApplication.quit()

    def check_for_updates(self):
        """업데이트 확인 (사용자 버튼 클릭)."""
        logger.info("manual update check opened")
        from main import VERSION
        from src.update_dialog import UpdateDialog

        dialog = UpdateDialog(VERSION, self)
        dialog.exec_()

    def _check_for_updates_silent(self):
        """백그라운드 자동 업데이트 체크 (알림만 표시)."""
        logger.info("silent update check started")
        try:
            from main import VERSION
            from src.auto_updater import AutoUpdater

            updater = AutoUpdater(VERSION)
            update_info = updater.check_for_updates()

            if update_info:
                #
                reply = QMessageBox.information(
                    self,
                    "업데이트 알림",
                    f"새 버전이 출시되었습니다. (v{update_info['version']})\n\n"
                    f"지금 업데이트하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    self.check_for_updates()
        except Exception as e:
            #
            logger.exception("silent update check failed")
            print(f"자동 업데이트 체크 실패: {e}")

    def closeEvent(self, event):
        """윈도우 종료 시 로그아웃 처리."""
        logger.info("closeEvent invoked; is_running=%s", self.is_running)
        if self.is_running:
            reply = QMessageBox.question(
                self, "종료 확인",
                "작업이 진행 중입니다. 정말 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.stop_upload()

        try:
            from src import auth_client
            auth_client.logout()
        except Exception:
            pass
        event.accept()
