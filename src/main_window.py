"""
쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (PyQt5)
Stitch Blue 디자인 - 좌표 기반 배치
"""
import re
import html
import time
import threading
import queue
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QListWidget, QFrame,
    QMessageBox, QStatusBar, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPainter, QLinearGradient

from src.config import config
from src.coupang_uploader import CoupangPartnersPipeline
from src.theme import Colors, Typography, Radius, global_stylesheet


# ─── Helpers ─────────────────────────────────────────────────

def _format_interval(seconds):
    """초 단위를 사람이 읽기 쉬운 시간 문자열로 변환"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}시간 {m}분 {s}초"
    elif m > 0:
        return f"{m}분 {s}초"
    return f"{s}초"


def _hex_alpha(color, alpha_hex):
    """#RRGGBB 색상에 알파 hex 접미사 추가. hex가 아니면 그대로 반환."""
    if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        return f"{color}{alpha_hex}"
    return color


# ─── Signals ────────────────────────────────────────────────

class Signals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(str)
    results = pyqtSignal(int, int)
    product = pyqtSignal(str, bool)
    finished = pyqtSignal(dict)


# ─── Card Widget ────────────────────────────────────────────

class Card(QFrame):
    """둥근 모서리 카드 컨테이너"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(Colors.BORDER))
        painter.setBrush(QColor(Colors.BG_CARD))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


# ─── Badge Widget ───────────────────────────────────────────

class Badge(QLabel):
    """작은 알약형 상태 배지"""
    def __init__(self, text="", color=Colors.ACCENT, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(52)
        self._apply(color)

    def _apply(self, color):
        bg = _hex_alpha(color, "18")
        border = _hex_alpha(color, "35")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 0 12px;
                font-size: 8pt;
                font-weight: 600;
            }}
        """)

    def update_style(self, color, text=None):
        if text:
            self.setText(text)
        self._apply(color)


# ─── Header Bar ─────────────────────────────────────────────

class HeaderBar(QFrame):
    """그라디언트 배경의 상단 바"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(Colors.BG_CARD))
        grad.setColorAt(0.5, QColor("#131A2A"))
        grad.setColorAt(1, QColor(Colors.BG_CARD))
        painter.fillRect(self.rect(), grad)
        painter.setPen(QColor(Colors.BORDER))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Main Window ────────────────────────────────────────────

class MainWindow(QMainWindow):
    """쿠팡 파트너스 스레드 자동화 - 메인 윈도우 (좌표 기반 배치)"""

    MAX_LOG_LINES = 2000

    # 윈도우 크기 상수
    WIN_W = 1120
    WIN_H = 760
    HEADER_H = 58
    MARGIN = 16
    GAP = 12
    LEFT_W = 440

    COUPANG_LINK_PATTERN = re.compile(
        r'https?://(?:link\.coupang\.com|www\.coupang\.com)[^\s<>"\']*',
        re.IGNORECASE
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("쿠팡 파트너스 스레드 자동화")
        self.setFixedSize(self.WIN_W, self.WIN_H)

        self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)
        self._stop_event = threading.Event()
        self._stop_event.set()  # 초기 상태: 실행 안 함
        self._urls_lock = threading.Lock()
        self.link_queue = queue.Queue()
        self.processed_urls = set()

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

        # 튜토리얼에서 하이라이트할 위젯 참조 (tutorial.py에서 사용)
        self._tutorial_widgets = {}

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

    # ━━━━━━━━━━━━━━━━━━━━━ UI BUILD (좌표 기반) ━━━━━━━━━━━━━━━━━━━━━

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # 헤더 바
        self._build_header(central)

        # 콘텐츠 영역 좌표 계산
        content_y = self.HEADER_H + 14
        content_h = self.WIN_H - self.HEADER_H - 14 - 40  # 40 = 상태바(28) + 하단 여백(12)
        right_x = self.MARGIN + self.LEFT_W + self.GAP
        right_w = self.WIN_W - right_x - self.MARGIN

        # 왼쪽 패널 (입력)
        self._build_input_panel(central, self.MARGIN, content_y, self.LEFT_W, content_h)

        # 오른쪽 패널 (출력)
        self._build_output_panel(central, right_x, content_y, right_w, content_h)

        # 상태바
        self._build_statusbar()

    def _build_header(self, parent):
        header = HeaderBar(parent)
        header.setGeometry(0, 0, self.WIN_W, self.HEADER_H)

        # 브랜드 아이콘
        brand_icon = QLabel("C", header)
        brand_icon.setGeometry(20, 12, 34, 34)
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.ACCENT};
                color: #FFFFFF;
                border-radius: 8px;
                font-size: 15pt;
                font-weight: 700;
            }}
        """)

        # 타이틀
        title_label = QLabel("쿠팡 파트너스", header)
        title_label.setGeometry(66, 6, 250, 28)
        title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14pt; font-weight: 700; "
            f"letter-spacing: -0.3px; background: transparent;"
        )

        # 서브타이틀
        sub_label = QLabel("스레드 자동화", header)
        sub_label.setGeometry(66, 32, 150, 20)
        sub_label.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 9pt; font-weight: 600; background: transparent;"
        )

        # 우측 버튼 영역 (오른쪽부터 배치)
        rx = self.WIN_W - 20  # 우측 마진

        # 설정 버튼
        rx -= 80
        self.settings_btn = QPushButton("설정", header)
        self.settings_btn.setGeometry(rx, 12, 80, 34)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setProperty("class", "ghost")
        self.settings_btn.clicked.connect(self.open_settings)

        # 사용법 버튼
        rx -= 88  # 80 + 8 간격
        self.tutorial_btn = QPushButton("사용법", header)
        self.tutorial_btn.setGeometry(rx, 12, 80, 34)
        self.tutorial_btn.setCursor(Qt.PointingHandCursor)
        self.tutorial_btn.setProperty("class", "ghost")
        self.tutorial_btn.clicked.connect(self.open_tutorial)

        # 상태 배지
        rx -= 98  # 90 + 8 간격
        self.status_badge = Badge("대기중", Colors.SUCCESS, header)
        self.status_badge.setGeometry(rx, 17, 90, 24)

        # 온라인 표시 점
        rx -= 16
        self._online_dot = QLabel("", header)
        self._online_dot.setGeometry(rx, 25, 8, 8)
        self._online_dot.setStyleSheet(
            f"background-color: {Colors.SUCCESS}; border-radius: 4px;"
        )

        # 튜토리얼 위젯 참조 저장
        self._header = header
        self._brand_icon = brand_icon

    def _build_input_panel(self, parent, x, y, w, h):
        panel = Card(parent)
        panel.setGeometry(x, y, w, h)

        px, py = 18, 16  # 내부 패딩
        inner_w = w - 36  # 18 * 2

        # 섹션 아이콘
        icon_label = QLabel("*", panel)
        icon_label.setGeometry(px, py, 20, 28)
        icon_label.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 14pt; font-weight: 700; background: transparent;"
        )

        # 섹션 제목
        sec_label = QLabel("새 자동화 시작", panel)
        sec_label.setGeometry(px + 28, py, 250, 28)
        sec_label.setStyleSheet(
            f"font-size: 12pt; font-weight: 700; color: {Colors.TEXT_PRIMARY}; "
            f"letter-spacing: -0.2px; background: transparent;"
        )

        # 링크 개수 배지
        self.link_count_badge = Badge("0개 링크", Colors.TEXT_MUTED, panel)
        self.link_count_badge.setGeometry(w - 18 - 90, py + 2, 90, 24)

        # 안내 문구
        hint = QLabel("아래에 쿠팡 파트너스 URL을 붙여넣기 하세요 (한 줄에 하나씩)", panel)
        hint.setGeometry(px, py + 40, inner_w, 18)
        hint.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; background: transparent;"
        )

        # 텍스트 입력 영역
        text_y = py + 66
        btn_h = 44
        btn_y = h - 16 - btn_h
        text_h = btn_y - text_y - 12

        self.links_text = QPlainTextEdit(panel)
        self.links_text.setGeometry(px, text_y, inner_w, text_h)
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://link.coupang.com/a/yyy"
        )
        self.links_text.textChanged.connect(self._update_link_count)

        # 액션 버튼들 (비율 5:3:2)
        btn_gap = 10
        total_btn_w = inner_w - btn_gap * 2
        start_w = int(total_btn_w * 0.50)
        add_w = int(total_btn_w * 0.28)
        stop_w = total_btn_w - start_w - add_w

        self.start_btn = QPushButton("자동화 시작", panel)
        self.start_btn.setGeometry(px, btn_y, start_w, btn_h)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: {Radius.MD};
                font-size: 11pt;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_LIGHT}; }}
            QPushButton:pressed {{ background-color: {Colors.ACCENT_DARK}; }}
            QPushButton:disabled {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_MUTED}; }}
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

        # 튜토리얼 위젯 참조
        self._input_panel = panel

    def _build_output_panel(self, parent, x, y, w, h):
        panel = Card(parent)
        panel.setGeometry(x, y, w, h)

        # 탭 위젯 (카드 내부를 채움)
        self.tabs = QTabWidget(panel)
        self.tabs.setGeometry(0, 0, w, h)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                padding: 12px 22px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 10pt;
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                color: {Colors.TEXT_SECONDARY};
            }}
            QTabBar::tab:selected {{
                color: {Colors.ACCENT};
                border-bottom-color: {Colors.ACCENT};
            }}
        """)

        # 탭 1: 작업 내용
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
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_TERMINAL};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG};
                padding: 14px;
                color: {Colors.TEXT_SECONDARY};
                font-family: {Typography.FAMILY_MONO};
                font-size: 9pt;
            }}
        """)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "작업 내용")

        # 탭 2: 결과
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(16, 10, 16, 16)
        result_layout.setSpacing(12)

        # 통계 카드 행
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self.stat_success, self._stat_success_val = self._build_stat_card("성공", "0", Colors.SUCCESS)
        self.stat_failed, self._stat_failed_val = self._build_stat_card("실패", "0", Colors.ERROR)
        self.stat_total, self._stat_total_val = self._build_stat_card("전체", "0", Colors.INFO)
        stats_row.addWidget(self.stat_success)
        stats_row.addWidget(self.stat_failed)
        stats_row.addWidget(self.stat_total)
        result_layout.addLayout(stats_row)

        # 처리된 항목 목록
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

        # 튜토리얼 위젯 참조
        self._output_panel = panel

    def _build_stat_card(self, label, value, color):
        card = QFrame()
        bg_color = _hex_alpha(color, "0D")
        border_color = _hex_alpha(color, "25")
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {Radius.LG};
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        val_label = QLabel(value)
        val_label.setAlignment(Qt.AlignCenter)
        val_label.setStyleSheet(
            f"color: {color}; font-size: 22pt; font-weight: 700; background: transparent; border: none;"
        )
        layout.addWidget(val_label)

        name_label = QLabel(label)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600; "
            f"letter-spacing: 1px; background: transparent; border: none;"
        )
        layout.addWidget(name_label)

        return card, val_label

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QLabel("시스템 온라인")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt;")
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt;")
        self.statusbar.addWidget(self.status_label, 1)
        self.statusbar.addPermanentWidget(self.progress_label)

    # ━━━━━━━━━━━━━━━━━━━━━ SLOTS ━━━━━━━━━━━━━━━━━━━━━

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        # 이모지 및 영문 로그 마커를 한글로 정리
        clean_msg = message
        _emoji_map = {
            "\u2705": "", "\u274c": "", "\u26a0\ufe0f": "", "\ud83d\udcce": "",
            "\ud83d\udd10": "", "\ud83d\udcbe": "", "\u2139\ufe0f": "",
            "\ud83d\udcca": "", "\ud83d\udcf8": "", "\ud83d\udd0d": "",
            "\ud83d\udcdd": "", "\ud83d\udce4": "", "\ud83d\udc4d": "",
            "\ud83d\udee1\ufe0f": "", "\u23f3": "", "\u2328\ufe0f": "",
            "\ud83c\udfaf": "", "\ud83d\udcf0": "", "\ud83d\udd25": "",
            "\ud83d\udcf1": "", "\ud83d\udc40": "", "\ud83d\udca1": "",
            "1\ufe0f\u20e3": "[1]", "2\ufe0f\u20e3": "[2]",
            "\ud83d\uddbc\ufe0f": "", "\ud83d\udd18": "",
        }
        for emoji, replacement in _emoji_map.items():
            clean_msg = clean_msg.replace(emoji, replacement)
        clean_msg = clean_msg.strip()
        if not clean_msg:
            return

        safe_msg = html.escape(clean_msg)
        color = Colors.TEXT_SECONDARY
        if any(kw in clean_msg for kw in ("오류", "실패", "치명적", "중단")):
            color = Colors.ERROR
        elif any(kw in clean_msg for kw in ("성공", "완료", "확인됨", "확보")):
            color = Colors.SUCCESS
        elif "===" in clean_msg or "━" in clean_msg:
            color = Colors.ACCENT
        elif any(kw in clean_msg for kw in ("대기", "진행", "시작", "중지")):
            color = Colors.WARNING
        self.log_text.append(
            f'<span style="color:{Colors.TEXT_MUTED}">[{timestamp}]</span> '
            f'<span style="color:{color}">{safe_msg}</span>'
        )

    def _set_status(self, message):
        self.status_label.setText(message)
        if any(kw in message for kw in ("오류", "취소", "실패", "중단")):
            self.status_badge.update_style(Colors.ERROR, message[:14])
        elif any(kw in message for kw in ("완료", "대기")):
            self.status_badge.update_style(Colors.SUCCESS, message[:14])
        else:
            self.status_badge.update_style(Colors.WARNING, message[:14])

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
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "대기중")

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get('parse_failed', 0)
        if results.get('cancelled'):
            msg = (f"업로드가 취소되었습니다.\n\n"
                   f"  완료: {results.get('uploaded', 0)}\n"
                   f"  실패: {results.get('failed', 0)}")
            if parse_failed > 0:
                msg += f"\n  분석 오류: {parse_failed}"
            QMessageBox.information(self, "취소됨", msg)
        else:
            msg = (f"업로드가 완료되었습니다.\n\n"
                   f"  성공: {results.get('uploaded', 0)}\n"
                   f"  실패: {results.get('failed', 0)}")
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

    # ━━━━━━━━━━━━━━━━━━━━━ ACTIONS ━━━━━━━━━━━━━━━━━━━━━

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리"""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def open_settings(self):
        from src.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)

    def open_tutorial(self):
        from src.tutorial import TutorialDialog
        dialog = TutorialDialog(self)
        dialog.exec_()

    def start_upload(self):
        content = self.links_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "알림", "쿠팡 파트너스 링크를 입력하세요.")
            return

        api_key = config.gemini_api_key
        if not api_key or len(api_key.strip()) < 10:
            QMessageBox.critical(self, "설정 필요", "설정에서 유효한 Gemini API 키를 설정하세요.")
            return

        link_data = self._extract_links(content)

        if not link_data:
            QMessageBox.warning(self, "알림", "유효한 쿠팡 링크를 찾을 수 없습니다.")
            return

        config.load()
        interval = max(config.upload_interval, 30)

        reply = QMessageBox.question(
            self, "확인",
            f"{len(link_data)}개 링크를 처리하고 업로드할까요?\n"
            f"업로드 간격: {_format_interval(interval)}\n\n"
            f"(실행 중에 링크를 추가할 수 있습니다)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.products_list.clear()
        self.status_badge.update_style(Colors.WARNING, "실행중")

        # 통계 초기화
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
            daemon=True
        )
        thread.start()

    def add_links_to_queue(self):
        content = self.links_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "알림", "추가할 링크를 입력하세요.")
            return

        link_data = self._extract_links(content)

        if not link_data:
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
            self.signals.log.emit(f"{added}개 새 링크 추가됨 (대기열: {self.link_queue.qsize()})")
            clean_links = "\n".join([item[0] for item in link_data])
            self.links_text.setPlainText(clean_links)
        else:
            QMessageBox.information(self, "알림", "모든 링크가 이미 대기열에 있거나 처리되었습니다.")

    def _run_upload_queue(self, interval):
        from src.computer_use_agent import ComputerUseAgent
        from src.threads_playwright_helper import ThreadsPlaywrightHelper

        results = {
            'total': 0,
            'processed': 0,
            'parse_failed': 0,
            'uploaded': 0,
            'failed': 0,
            'cancelled': False,
            'details': []
        }

        def log(msg):
            self.signals.log.emit(msg)
            self.signals.progress.emit(msg)

        try:
            log(f"자동화 시작 (대기열: {self.link_queue.qsize()}개)")
            self.signals.status.emit("처리 중")

            ig_username = config.instagram_username
            if ig_username:
                profile_name = self._sanitize_profile_name(ig_username)
                profile_dir = f".threads_profile_{profile_name}"
            else:
                profile_dir = ".threads_profile"

            log("브라우저를 시작하는 중...")
            agent = ComputerUseAgent(
                api_key=config.gemini_api_key,
                headless=False,
                profile_dir=profile_dir
            )
            agent.start_browser()

            try:
                agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
            except Exception:
                pass

            helper = ThreadsPlaywrightHelper(agent.page)

            if not helper.check_login_status():
                log("로그인이 필요합니다 - 브라우저에서 로그인해 주세요 (60초 제한)")
                for wait_sec in range(20):
                    time.sleep(3)
                    remaining = 60 - (wait_sec * 3)
                    if wait_sec % 3 == 0:
                        log(f"로그인 대기 중... 약 {remaining}초 남음")
                    if helper.check_login_status():
                        log("로그인 확인됨")
                        break
                else:
                    log("로그인 실패 - 60초 시간 초과로 중단합니다")
                    results['cancelled'] = True
                    self.signals.finished.emit(results)
                    return

            log("Threads 로그인 상태 확인됨")

            processed_count = 0
            empty_count = 0

            while not self._stop_event.is_set():
                try:
                    item = self.link_queue.get(timeout=5)
                    empty_count = 0
                except queue.Empty:
                    empty_count += 1
                    if empty_count >= 6:
                        log("대기열이 비어있어 종료합니다")
                        break
                    log("새 링크를 대기하는 중...")
                    continue

                if self._stop_event.is_set():
                    results['cancelled'] = True
                    break

                processed_count += 1
                url, keyword = item if isinstance(item, tuple) else (item, None)
                results['total'] += 1

                log(f"━━━ 항목 {processed_count} (남은 대기열: {self.link_queue.qsize()}개) ━━━")

                log("상품 정보 분석 중...")
                try:
                    post_data = self.pipeline.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results['parse_failed'] += 1
                        log("상품 분석 실패 - 다음 항목으로 건너뜁니다")
                        continue

                    results['processed'] += 1
                    product_name = post_data.get('product_title', '')[:30]
                    log(f"상품 분석 완료: {product_name}")

                except Exception as e:
                    results['parse_failed'] += 1
                    log(f"상품 분석 오류: {str(e)[:50]}")
                    continue

                log("Threads에 게시글 업로드 중...")
                try:
                    agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2)

                    posts_data = [
                        {'text': post_data['first_post']['text'], 'image_path': post_data['first_post'].get('media_path')},
                        {'text': post_data['second_post']['text'], 'image_path': None}
                    ]

                    success = helper.create_thread_direct(posts_data)

                    if success:
                        results['uploaded'] += 1
                        log(f"업로드 성공: {product_name}")
                        self.signals.product.emit(product_name, True)
                    else:
                        results['failed'] += 1
                        log(f"업로드 실패: {product_name}")
                        self.signals.product.emit(product_name, False)

                    results['details'].append({
                        'product_title': product_name,
                        'url': url,
                        'success': success
                    })

                except Exception as e:
                    results['failed'] += 1
                    log(f"업로드 오류: {str(e)[:50]}")
                    self.signals.product.emit(product_name, False)

                self.signals.results.emit(results['uploaded'], results['failed'])

                if not self._stop_event.is_set():
                    log(f"다음 항목까지 {_format_interval(interval)} 대기합니다")

                    for sec in range(interval):
                        if self._stop_event.is_set():
                            results['cancelled'] = True
                            break
                        remaining = interval - sec
                        if remaining % 60 == 0 and remaining > 0:
                            log(f"대기 중... {_format_interval(remaining)} 남음")
                        time.sleep(1)

            try:
                agent.save_session()
                agent.close()
            except Exception:
                pass

            log("━" * 40)
            log(f"작업 완료 - 성공: {results['uploaded']} / 실패: {results['failed']} / 분석 오류: {results['parse_failed']}")

            if results['cancelled']:
                self.signals.status.emit("취소됨")
            else:
                self.signals.status.emit("완료")

            self.signals.finished.emit(results)

        except Exception as e:
            log(f"치명적 오류 발생: {e}")
            self.signals.status.emit("오류 발생")
            self.signals.finished.emit(results)

    def stop_upload(self):
        if self.is_running:
            self.signals.log.emit("중지를 요청했습니다. 현재 작업을 마무리한 후 중지됩니다.")
            self.signals.status.emit("중지 중...")
            self.status_badge.update_style(Colors.WARNING, "중지 중")
            self.is_running = False
            self.pipeline.cancel()
