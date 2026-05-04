"""
사용법 안내 - 튜토리얼 다이얼로그 & 오버레이
쿠팡 파트너스 스레드 자동화의 모든 기능을 단계별로 설명합니다.

오버레이 모드: 메인 윈도우의 실제 버튼/입력창 위치를 직접 하이라이트하여 안내합니다.
다이얼로그 모드: [사용법] 버튼으로 열리는 독립 안내 창입니다.
"""
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QWidget, QCheckBox
from PyQt6.QtCore import Qt, QRectF, QRect, QPoint
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen, QRegion, QPainterPath

from src.theme import (
    Colors, Radius, Gradients,
    close_btn_style, ghost_btn_style, accent_btn_style,
    muted_text_style, header_title_style, dialog_style
)


# ─── Tutorial Dialog Pages ─────────────────────────────────

TUTORIAL_PAGES = [
    {
        "icon": "C",
        "title": "환영합니다!",
        "subtitle": "쿠팡 파트너스 스레드 자동화",
        "content": (
            "이 프로그램은 쿠팡 파트너스 제휴 링크를\n"
            "Threads에 자동으로 업로드하는 도구입니다.\n"
            "\n"
            "  주요 기능\n"
            "\n"
            "  \u2022 AI 기반 상품 정보 자동 분석\n"
            "  \u2022 매력적인 게시글 자동 작성\n"
            "  \u2022 1688 상품 이미지 자동 검색 및 첨부\n"
            "  \u2022 Threads 자동 업로드\n"
            "  \u2022 텔레그램 결과 알림"
        ),
    },
    {
        "icon": "*",
        "title": "1단계: API 키 설정",
        "subtitle": "Google Gemini API 연동",
        "content": (
            "상품 분석과 게시글 생성을 위해\n"
            "Gemini API 키가 필요합니다.\n"
            "\n"
            "  설정 방법\n"
            "\n"
            "  1. 사이드바에서 [설정]을 클릭합니다\n"
            "  2. Google AI Studio에서 API 키를 발급받으세요\n"
            "     (aistudio.google.com)\n"
            "  3. [마스터 API 키] 입력란에 붙여넣기 합니다\n"
            "\n"
            "  * API 키는 안전하게 로컬에 저장됩니다"
        ),
    },
    {
        "icon": "@",
        "title": "2단계: Threads 로그인",
        "subtitle": "브라우저 세션 연결",
        "content": (
            "Threads에 게시글을 올리려면\n"
            "먼저 로그인이 필요합니다.\n"
            "\n"
            "  로그인 방법\n"
            "\n"
            "  1. 사이드바에서 [Threads 계정]을 클릭\n"
            "  2. 계정 이름을 입력합니다\n"
            "  3. [Threads 로그인] 버튼을 클릭합니다\n"
            "  4. 열리는 브라우저에서 Instagram으로 로그인\n"
            "  5. 로그인 후 브라우저를 닫으면 세션 자동 저장\n"
            "\n"
            "  * [상태 확인]으로 로그인 상태를 확인할 수 있습니다"
        ),
    },
    {
        "icon": "#",
        "title": "3단계: 링크 입력",
        "subtitle": "쿠팡 파트너스 URL 붙여넣기",
        "content": (
            "자동화할 쿠팡 파트너스 링크를\n"
            "입력하는 방법입니다.\n"
            "\n"
            "  입력 방법\n"
            "\n"
            "  \u2022 [링크 입력] 페이지에서 링크를 붙여넣기\n"
            "  \u2022 한 줄에 하나씩 입력하세요\n"
            "  \u2022 유효한 링크만 자동 인식됩니다\n"
            "    (link.coupang.com 또는 www.coupang.com)\n"
            "\n"
            "  지원 형식\n"
            "\n"
            "  \u2022 https://link.coupang.com/a/xxxxx\n"
            "  \u2022 https://www.coupang.com/vp/products/xxxxx"
        ),
    },
    {
        "icon": ">",
        "title": "4단계: 자동화 실행",
        "subtitle": "시작, 추가, 중지",
        "content": (
            "링크를 입력한 후 자동화를 실행합니다.\n"
            "\n"
            "  [자동화 시작] 버튼\n"
            "  \u2022 입력된 모든 링크의 업로드를 시작합니다\n"
            "  \u2022 각 링크를 순서대로 처리합니다\n"
            "\n"
            "  [링크 추가] 버튼 (실행 중 활성화)\n"
            "  \u2022 실행 도중 새로운 링크를 추가할 수 있습니다\n"
            "  \u2022 중복 링크는 자동으로 제외됩니다\n"
            "\n"
            "  [중지] 버튼\n"
            "  \u2022 현재 작업 완료 후 자동화를 중지합니다\n"
            "  \u2022 즉시 중지가 아닌 안전한 중지입니다"
        ),
    },
    {
        "icon": ">",
        "title": "5단계: 작업 내용 & 결과 확인",
        "subtitle": "실시간 모니터링",
        "content": (
            "자동화 진행 상황을 실시간으로\n"
            "확인할 수 있습니다.\n"
            "\n"
            "  [작업 로그] 페이지\n"
            "  \u2022 실시간 작업 진행 상황 표시\n"
            "  \u2022 오류 발생 시 빨간색으로 표시\n"
            "  \u2022 성공 시 초록색으로 표시\n"
            "\n"
            "  [결과 확인] 페이지\n"
            "  \u2022 성공/실패/전체 통계 카드\n"
            "  \u2022 처리된 항목 목록\n"
            "\n"
            "  하단 상태바 / 사이드바 현황\n"
            "  \u2022 현재 상태 및 진행률 표시"
        ),
    },
    {
        "icon": "+",
        "title": "추가 기능",
        "subtitle": "텔레그램, 영상, 중복 방지",
        "content": (
            "더 편리하게 사용할 수 있는\n"
            "추가 기능들입니다.\n"
            "\n"
            "  텔레그램 알림\n"
            "  \u2022 [설정]에서 봇 토큰과 채팅 ID 입력\n"
            "  \u2022 업로드 결과를 텔레그램으로 받을 수 있습니다\n"
            "\n"
            "  영상 우선 모드\n"
            "  \u2022 [설정]에서 영상 업로드 우선 옵션 활성화\n"
            "  \u2022 이미지 대신 영상을 우선 검색합니다\n"
            "\n"
            "  자동 중복 방지\n"
            "  \u2022 이미 업로드한 링크는 자동으로 건너뜁니다\n"
            "\n"
            "  세션 유지\n"
            "  \u2022 브라우저 세션 저장으로 재로그인 불필요"
        ),
    },
    {
        "icon": "!",
        "title": "시작할 준비가 되었습니다!",
        "subtitle": "빠른 시작 가이드",
        "content": (
            "아래 순서대로 진행하시면 됩니다.\n"
            "\n"
            "  빠른 시작 순서\n"
            "\n"
            "  1. [설정] 페이지에서 Gemini API 키 입력\n"
            "  2. [Threads 계정]에서 로그인\n"
            "  3. [링크 입력]에서 쿠팡 링크 붙여넣기\n"
            "  4. [자동화 시작] 버튼 클릭\n"
            "\n"
            "  문제 해결\n"
            "\n"
            "  \u2022 업로드 실패: [작업 로그]에서 오류 메시지 확인\n"
            "  \u2022 로그인 만료: [Threads 계정]에서 다시 로그인\n"
            "  \u2022 API 오류: API 키가 유효한지 확인"
        ),
    },
]


# ─── Tutorial Dialog ────────────────────────────────────────

class TutorialDialog(QDialog):
    """사용법 안내 다이얼로그 - 좌표 기반 배치"""

    DLG_W = 620
    DLG_H = 620

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용법 안내")
        self.setFixedSize(self.DLG_W, self.DLG_H)
        self.setModal(True)

        self._page_index = 0
        self._pages = TUTORIAL_PAGES
        self._build_ui()
        self._render_page()

    def _build_ui(self):
        W = self.DLG_W

        self.step_label = QLabel(self)
        self.step_label.setGeometry(24, 16, 120, 20)
        self.step_label.setStyleSheet(
            muted_text_style("12pt") + " font-weight: 600;"
        )

        close_btn = QPushButton("\u2715", self)
        close_btn.setGeometry(W - 48, 12, 32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(close_btn_style())
        close_btn.clicked.connect(self.accept)

        self.icon_label = QLabel(self)
        self.icon_label.setGeometry(W // 2 - 28, 50, 56, 56)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(self)
        self.title_label.setGeometry(24, 120, W - 48, 38)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(header_title_style("19pt"))

        self.subtitle_label = QLabel(self)
        self.subtitle_label.setGeometry(24, 160, W - 48, 24)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 13pt; font-weight: 600; background: transparent;"
        )

        self.content_label = QLabel(self)
        self.content_label.setGeometry(36, 200, W - 72, 340)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_label.setWordWrap(True)
        self.content_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY}; font-size: 13pt;
                background-color: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG}; padding: 18px 22px;
            }}
        """)

        self._dot_labels = []
        total = len(self._pages)
        dot_sz, dot_gap = 8, 6
        dots_total_w = total * dot_sz + (total - 1) * dot_gap
        dots_x = (W - dots_total_w) // 2
        for i in range(total):
            dot = QLabel(self)
            dot.setGeometry(dots_x + i * (dot_sz + dot_gap), 554, dot_sz, dot_sz)
            dot.setStyleSheet(f"background-color: {Colors.TEXT_MUTED}; border-radius: {dot_sz // 2}px;")
            self._dot_labels.append(dot)

        self.prev_btn = QPushButton("\u2190 이전", self)
        self.prev_btn.setGeometry(24, 580, 100, 36)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(
            ghost_btn_style() + "\nQPushButton { font-size: 13pt; }"
        )
        self.prev_btn.clicked.connect(self._prev_page)

        self.skip_btn = QPushButton("건너뛰기", self)
        self.skip_btn.setGeometry(W // 2 - 55, 580, 110, 36)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_MUTED};
                border: none; border-radius: {Radius.MD}; font-size: 12pt;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; }}
        """)
        self.skip_btn.clicked.connect(self.accept)

        self.next_btn = QPushButton("다음 \u2192", self)
        self.next_btn.setGeometry(W - 124, 580, 100, 36)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN}; color: #FFFFFF;
                border: none; border-radius: {Radius.MD}; font-size: 13pt; font-weight: 600;
            }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
        """)
        self.next_btn.clicked.connect(self._next_page)

    def _render_page(self):
        page = self._pages[self._page_index]
        total = len(self._pages)
        idx = self._page_index

        self.step_label.setText(f"{idx + 1} / {total} 단계")
        self.icon_label.setText(page["icon"])
        self.icon_label.setStyleSheet(f"""
            QLabel {{ background-color: {Colors.ACCENT}; color: #FFFFFF;
                border-radius: 28px; font-size: 20pt; font-weight: 700; }}
        """)
        self.title_label.setText(page["title"])
        self.subtitle_label.setText(page["subtitle"])
        self.content_label.setText(page["content"])

        for i, dot in enumerate(self._dot_labels):
            c = Colors.ACCENT if i == idx else Colors.TEXT_MUTED
            dot.setStyleSheet(f"background-color: {c}; border-radius: 4px;")

        self.prev_btn.setVisible(idx > 0)
        if idx == total - 1:
            self.next_btn.setText("시작하기")
            self.skip_btn.setVisible(False)
        else:
            self.next_btn.setText("다음 \u2192")
            self.skip_btn.setVisible(True)

    def _next_page(self):
        if self._page_index < len(self._pages) - 1:
            self._page_index += 1
            self._render_page()
        else:
            self.accept()

    def _prev_page(self):
        if self._page_index > 0:
            self._page_index -= 1
            self._render_page()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.DLG_W, self.DLG_H
        painter.fillRect(self.rect(), QColor(Colors.BG_DARK))

        top_grad = QLinearGradient(0, 0, W, 0)
        top_grad.setColorAt(0, QColor(217, 119, 87, 0))
        top_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        top_grad.setColorAt(0.7, QColor(Colors.ACCENT_LIGHT))
        top_grad.setColorAt(1, QColor(232, 145, 117, 0))
        painter.fillRect(0, 0, W, 3, top_grad)

        bot_grad = QLinearGradient(0, 0, W, 0)
        bot_grad.setColorAt(0, QColor(217, 119, 87, 0))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_DARK))
        bot_grad.setColorAt(1, QColor(217, 119, 87, 0))
        painter.fillRect(0, H - 2, W, 2, bot_grad)


# Coral glow used by overlay highlight (replaces old blue rgba(13,89,242,90))
_OVERLAY_GLOW_OUTER = QColor(217, 119, 87, 110)


# ─── Overlay Tutorial Steps (위젯 하이라이트 기반) ──────────

# 각 단계는 메인 윈도우의 실제 위젯을 하이라이트하며 설명합니다.
# "widget": MainWindow 속성 이름 (예: "_sidebar")
# "title": 단계 제목
# "desc": 설명 텍스트
# "tooltip_pos": 설명 카드 위치 ("right", "left", "bottom", "top")
# "padding": 하이라이트 영역 패딩 (기본 6px)

OVERLAY_STEPS = [
    {
        "widget": None,  # 전체 소개 (하이라이트 없음)
        "title": "환영합니다!",
        "desc": (
            "쿠팡 파트너스 제휴 링크를 Threads에\n"
            "자동으로 업로드하는 도구입니다.\n"
            "\n"
            "각 단계별로 실제 버튼과 입력창의\n"
            "위치를 직접 보여드립니다."
        ),
        "tooltip_pos": "center",
    },
    {
        "widget": "_header",
        "title": "상단 헤더 영역",
        "desc": (
            "프로그램 이름과 현재 상태를\n"
            "표시하는 헤더 영역입니다.\n"
            "\n"
            "우측에 상태 배지, 사용법/설정\n"
            "버튼이 배치되어 있습니다."
        ),
        "tooltip_pos": "bottom",
    },
    {
        "widget": "_sidebar",
        "title": "사이드바 메뉴",
        "desc": (
            "왼쪽 사이드바에서 원하는 메뉴를\n"
            "클릭하여 각 페이지로 이동합니다.\n"
            "\n"
            "링크 입력 → 작업 로그 → 결과 확인\n"
            "→ Threads 계정 → 설정"
        ),
        "tooltip_pos": "right",
    },
    {
        "widget": "tutorial_btn",
        "title": "사용법 버튼",
        "desc": (
            "이 사용법 안내를 다시 볼 수 있습니다.\n"
            "언제든 클릭하세요."
        ),
        "tooltip_pos": "bottom",
    },
    {
        "widget": "status_badge",
        "title": "상태 표시 배지",
        "desc": (
            "현재 프로그램 상태를 표시합니다.\n"
            "\n"
            "대기중 / 실행중 / 완료 / 오류 등\n"
            "실시간으로 업데이트됩니다."
        ),
        "tooltip_pos": "bottom",
    },
    {
        "widget": "links_text",
        "title": "링크 입력란",
        "desc": (
            "쿠팡 파트너스 URL을\n"
            "한 줄에 하나씩 붙여넣기 합니다.\n"
            "\n"
            "유효한 링크만 자동으로 인식되며\n"
            "상단 배지에 개수가 표시됩니다."
        ),
        "tooltip_pos": "right",
        "padding": 4,
    },
    {
        "widget": "start_btn",
        "title": "자동화 시작 버튼",
        "desc": (
            "입력된 모든 링크를 순서대로\n"
            "분석하고 Threads에 업로드합니다.\n"
            "\n"
            "시작 전 링크 개수와 업로드 간격을\n"
            "확인하는 대화상자가 나타납니다."
        ),
        "tooltip_pos": "right",
    },
    {
        "widget": "add_btn",
        "title": "링크 추가 버튼",
        "desc": (
            "자동화 실행 중에만 활성화됩니다.\n"
            "새로운 링크를 대기열에 추가할 수 있으며\n"
            "중복 링크는 자동으로 제외됩니다."
        ),
        "tooltip_pos": "right",
    },
    {
        "widget": "stop_btn",
        "title": "중지 버튼",
        "desc": (
            "현재 진행 중인 작업을 마무리한 후\n"
            "안전하게 자동화를 중지합니다.\n"
            "즉시 중지가 아닌 안전한 중지입니다."
        ),
        "tooltip_pos": "right",
    },
    {
        "widget": "_sidebar",
        "title": "작업 로그 / 결과 확인",
        "desc": (
            "사이드바에서 [작업 로그]를 클릭하면\n"
            "실시간 진행 상황을 확인할 수 있습니다.\n"
            "\n"
            "[결과 확인]에서 성공/실패/전체 통계와\n"
            "처리된 항목 목록을 볼 수 있습니다."
        ),
        "tooltip_pos": "right",
    },
    {
        "widget": None,  # 마지막 - 빠른 시작 요약
        "title": "시작할 준비가 되었습니다!",
        "desc": (
            "빠른 시작 순서:\n"
            "\n"
            "1. [설정] 페이지에서 Gemini API 키 입력\n"
            "2. [Threads 계정] 페이지에서 로그인\n"
            "3. [링크 입력] 페이지에서 링크 붙여넣기\n"
            "4. [자동화 시작] 버튼 클릭"
        ),
        "tooltip_pos": "center",
    },
]


# ─── Tutorial Overlay Widget (위젯 하이라이트 방식) ──────────

class TutorialOverlay(QWidget):
    """메인 윈도우의 실제 위젯을 하이라이트하는 튜토리얼 오버레이"""

    TOOLTIP_W = 540
    TOOLTIP_H_MAX = 620
    HIGHLIGHT_PAD = 6
    GLOW_WIDTH = 2

    # ── New layout constants (Claude Dark, vertical rhythm) ────────────────
    # Card structure (top → bottom):
    #   [progress bar (4px)] padding (24)
    #   ↓
    #   STEP X / Y  (caption 11pt, 코랄)        ← step_label
    #   ↓ 6
    #   Title (22pt)                            ← title_label
    #   ↓ 18
    #   Description (13pt, generous line-h)    ← desc_label
    #   ↓ 24
    #   ─── divider (BG_SURFACE) ───            ← separator
    #   ↓ 18
    #   [← 이전]   [건너뛰기]   [다음 →]        ← buttons (in card)
    #   ↓ 14 (only on last step)
    #   ☐ 다시 보지 않기                         ← checkbox
    #   ↓ 24 padding
    PROGRESS_H = 6
    PAD = 24
    GAP_STEP_TO_TITLE = 6
    GAP_TITLE_TO_DESC = 18
    LINE_H = 30               # desc line-height (13pt × 1.6 HTML line-height + 여유)
    DESC_MIN_H = 60
    GAP_DESC_TO_SEP = 24
    SEP_H = 1
    GAP_SEP_TO_BTN = 18
    BTN_H = 38
    GAP_BTN_TO_CHECK = 14
    CHECK_H = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step_index = 0
        self._steps = OVERLAY_STEPS
        self._dont_show_again = False
        self._highlight_rect = None  # 현재 하이라이트 영역 (QRect, overlay 좌표)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._build_ui()
        self._update_step()

    def show_overlay(self):
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.raise_()
        self.show()

    def _get_main_window(self):
        """부모 체인을 따라 MainWindow를 찾습니다."""
        widget = self.parent()
        while widget:
            if hasattr(widget, '_sidebar'):
                return widget
            widget = widget.parent() if hasattr(widget, 'parent') else None
        return None

    def _get_highlight_rect(self):
        """현재 단계의 대상 위젯 영역을 overlay 좌표계로 변환합니다."""
        step = self._steps[self._step_index]
        widget_name = step.get("widget")
        if not widget_name:
            return None

        main_win = self._get_main_window()
        if not main_win:
            return None

        target = getattr(main_win, widget_name, None)
        if not target or not hasattr(target, 'geometry'):
            return None

        pad = step.get("padding", self.HIGHLIGHT_PAD)

        # 위젯의 글로벌 좌표를 overlay의 로컬 좌표로 변환
        global_pos = target.mapToGlobal(QPoint(0, 0))
        local_pos = self.mapFromGlobal(global_pos)
        w = target.width()
        h = target.height()

        return QRect(
            local_pos.x() - pad,
            local_pos.y() - pad,
            w + pad * 2,
            h + pad * 2
        )

    # ── Paint ──


    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        W, H = self.width(), self.height()
        hl = self._highlight_rect

        # Strongly dim everything except the current highlighted widget.
        dim = QColor(0, 0, 0, 245)
        if hl:
            full = QPainterPath()
            full.addRect(QRectF(0, 0, W, H))
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(hl), 10, 10)
            painter.fillPath(full.subtracted(hole), dim)
        else:
            painter.fillRect(0, 0, W, H, dim)

        if hl:
            glow_pen = QPen(QColor(Colors.ACCENT), self.GLOW_WIDTH)
            glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(hl), 10, 10)

            outer = QRectF(hl).adjusted(-2, -2, 2, 2)
            glow2_pen = QPen(_OVERLAY_GLOW_OUTER, 1)
            painter.setPen(glow2_pen)
            painter.drawRoundedRect(outer, 12, 12)

    def _build_ui(self):
        # ── 카드 본체 ─────────────────────────────────────────
        # 16px round, 차콜 카드 + 미세 코랄 보더 액센트
        self.tooltip_card = QWidget(self)
        self.tooltip_card.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 16px;
            }}
        """)

        # ── 진행률 바 (카드 상단 풀폭, 4px) ───────────────────
        # 두 개의 라벨로 구성: 배경(BG_SURFACE) + 채움(코랄 그라디언트)
        self.progress_track = QLabel(self.tooltip_card)
        self.progress_track.setStyleSheet(
            f"background-color: {Colors.BG_SURFACE}; border: none;"
            f" border-top-left-radius: 16px; border-top-right-radius: 16px;"
        )
        self.progress_fill = QLabel(self.tooltip_card)
        self.progress_fill.setStyleSheet(
            f"background: {Gradients.PROGRESS}; border: none;"
            f" border-top-left-radius: 16px;"
        )

        # ── STEP X / Y 캡션 (작은 코랄 라벨) ─────────────────
        self.step_label = QLabel(self.tooltip_card)
        self.step_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 10pt; font-weight: 700;"
            f" letter-spacing: 1.6px; background: transparent; border: none;"
        )

        # ── 제목 (22pt) ──────────────────────────────────────
        self.title_label = QLabel(self.tooltip_card)
        self.title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 19pt; font-weight: 700;"
            f" letter-spacing: -0.4px; background: transparent; border: none;"
        )

        # ── 설명 본문 (13pt + 큰 행간) ──────────────────────
        # QLabel은 line-height CSS를 무시하므로 문장 사이 줄 간격은
        # _update_step에서 \n을 \n\n 으로 한 번씩 더 끼워 넣어 시각적 행간을 확보.
        self.desc_label = QLabel(self.tooltip_card)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 13pt;"
            f" background: transparent; border: none;"
        )

        # ── 구분선 ──────────────────────────────────────────
        self.separator = QLabel(self.tooltip_card)
        self.separator.setStyleSheet(
            f"background-color: {Colors.BORDER_SUBTLE}; border: none;"
        )

        # 이전 버튼
        self.prev_btn = QPushButton("\u2190 이전", self)
        self.prev_btn.setFixedSize(86, 34)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(
            ghost_btn_style() + "\nQPushButton { font-size: 12pt; }"
        )
        self.prev_btn.clicked.connect(self._prev_step)

        # 건너뛰기 버튼
        self.skip_btn = QPushButton("건너뛰기", self)
        self.skip_btn.setFixedSize(96, 34)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_MUTED};
                border: none; border-radius: {Radius.MD}; font-size: 12pt;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; }}
        """)
        self.skip_btn.clicked.connect(self._close_overlay)

        # 다음 버튼
        self.next_btn = QPushButton("다음 \u2192", self)
        self.next_btn.setFixedSize(96, 34)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN}; color: #FFFFFF;
                border: none; border-radius: {Radius.MD};
                font-size: 12pt; font-weight: 600;
            }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
        """)
        self.next_btn.clicked.connect(self._next_step)

        # 페이지 표시 점
        self._dot_labels = []
        for _ in range(len(self._steps)):
            dot = QLabel(self)
            dot.setFixedSize(6, 6)
            self._dot_labels.append(dot)

        # 다시 보지 않기 체크박스
        self.dont_show_check = QCheckBox("다시 보지 않기", self)
        self.dont_show_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY}; font-size: 11pt; spacing: 6px; background: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {Colors.BORDER_LIGHT}; border-radius: 4px;
                background-color: {Colors.BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT}; border-color: {Colors.ACCENT};
            }}
            QCheckBox::indicator:hover {{ border-color: {Colors.ACCENT}; }}
        """)
        self.dont_show_check.toggled.connect(self._on_dont_show_toggled)

    def _position_tooltip(self):
        """진짜 새 디자인 — 헤더 진행률 바 + STEP 캡션 + 큰 타이틀 + 본문 + 구분선 + 컨트롤.
        모든 위젯이 카드 한 덩어리 안에 들어가고 정보 위계가 명확하다.
        """
        W, H = self.width(), self.height()
        step = self._steps[self._step_index]
        pos = step.get("tooltip_pos", "right")
        hl = self._highlight_rect

        # ── 측정 ──
        pad = self.PAD
        inner_w = self.TOOLTIP_W - pad * 2
        total_steps = len(self._steps)
        is_last = self._step_index == total_steps - 1

        # desc 높이 — sizeHint로 실제 렌더링 높이를 측정 (HTML line-height 적용 후)
        # 너비 고정한 뒤 heightForWidth/sizeHint로 진짜 필요한 높이 추출
        inner_w_for_desc = self.TOOLTIP_W - pad * 2
        self.desc_label.setFixedWidth(inner_w_for_desc)
        h_for_w = self.desc_label.heightForWidth(inner_w_for_desc)
        if h_for_w <= 0:
            h_for_w = self.desc_label.sizeHint().height()
        # 안전 마진 +12px (HTML line-height 내림 처리 방지)
        desc_h = max(h_for_w + 12, self.DESC_MIN_H)

        # 카드 내부 누적 높이 — 상단부터
        y = self.PROGRESS_H + pad           # progress bar 아래 여백
        step_y = y; step_h = 18
        y += step_h + self.GAP_STEP_TO_TITLE
        title_y = y; title_h = 38
        y += title_h + self.GAP_TITLE_TO_DESC
        desc_y = y
        y += desc_h + self.GAP_DESC_TO_SEP
        sep_y = y
        y += self.SEP_H + self.GAP_SEP_TO_BTN
        btn_y_local = y
        y += self.BTN_H

        if is_last:
            y += self.GAP_BTN_TO_CHECK
            check_y_local = y
            y += self.CHECK_H
        else:
            check_y_local = None

        y += pad  # 하단 패딩
        card_h = min(y, self.TOOLTIP_H_MAX)

        # ── 위치 결정 (전체 카드 한 덩어리) ──
        if hl and pos != "center":
            margin = 14
            tx, ty = 0, 0

            if pos == "right":
                tx = hl.right() + margin
                ty = hl.top()
                if tx + self.TOOLTIP_W > W - 10:
                    tx = hl.left() - self.TOOLTIP_W - margin
            elif pos == "left":
                tx = hl.left() - self.TOOLTIP_W - margin
                ty = hl.top()
                if tx < 10:
                    tx = hl.right() + margin
            elif pos == "bottom":
                tx = hl.left()
                ty = hl.bottom() + margin
                if ty + card_h > H - 10:
                    ty = hl.top() - card_h - margin
            elif pos == "top":
                tx = hl.left()
                ty = hl.top() - card_h - margin
                if ty < 10:
                    ty = hl.bottom() + margin

            tx = max(10, min(tx, W - self.TOOLTIP_W - 10))
            ty = max(10, min(ty, H - card_h - 10))
        else:
            tx = (W - self.TOOLTIP_W) // 2
            ty = (H - card_h) // 2

        # ── 카드 본체 ──
        self.tooltip_card.setGeometry(tx, ty, self.TOOLTIP_W, card_h)

        # ── 진행률 바 (카드 상단 풀폭) ──
        self.progress_track.setGeometry(0, 0, self.TOOLTIP_W, self.PROGRESS_H)
        progress_ratio = (self._step_index + 1) / total_steps
        fill_w = max(self.PROGRESS_H, int(self.TOOLTIP_W * progress_ratio))
        self.progress_fill.setGeometry(0, 0, fill_w, self.PROGRESS_H)

        # ── 카드 내부 자식들 (카드 좌표) ──
        self.step_label.setGeometry(pad, step_y, inner_w, step_h)
        self.title_label.setGeometry(pad, title_y, inner_w, title_h)
        self.desc_label.setGeometry(pad, desc_y, inner_w, desc_h)
        self.separator.setGeometry(pad, sep_y, inner_w, self.SEP_H)

        # ── 버튼 / 체크박스는 overlay의 자식이므로 절대 좌표 ──
        prev_w, skip_w, next_w = 96, 100, 116
        next_x = tx + self.TOOLTIP_W - pad - next_w
        btn_y_abs = ty + btn_y_local

        if is_last:
            # [← 이전]                                [시작하기]
            self.prev_btn.move(tx + pad, btn_y_abs)
            self.next_btn.move(next_x, btn_y_abs)
            self.skip_btn.move(next_x, btn_y_abs)  # 숨김
        else:
            # [← 이전]                  [건너뛰기]  [다음 →]
            skip_x = next_x - 10 - skip_w
            self.prev_btn.move(tx + pad, btn_y_abs)
            self.skip_btn.move(skip_x, btn_y_abs)
            self.next_btn.move(next_x, btn_y_abs)

        self.prev_btn.setFixedSize(prev_w, self.BTN_H)
        self.skip_btn.setFixedSize(skip_w, self.BTN_H)
        self.next_btn.setFixedSize(next_w, self.BTN_H)

        # 도트는 더 이상 사용하지 않으므로 화면 밖으로 보냄
        for dot in self._dot_labels:
            dot.move(-50, -50)

        # 체크박스 (마지막 단계에서만)
        if check_y_local is not None:
            check_x = tx + (self.TOOLTIP_W - 160) // 2
            self.dont_show_check.setGeometry(check_x, ty + check_y_local, 160, self.CHECK_H)
        else:
            self.dont_show_check.setGeometry(-200, -200, 160, self.CHECK_H)

    @staticmethod
    def _inflated_desc(text: str) -> str:
        """문장 사이에 빈 줄 하나 더 끼워 넣어 시각적 행간을 확장.
        QLabel이 line-height CSS를 무시하므로 줄 수를 늘리는 방식이 가장 확실하다.
        이미 빈 줄(연속 \\n)이 있는 곳은 건드리지 않는다.
        """
        if not text:
            return ""
        # 단일 \n 만 \n\n 로 변환 (이미 빈줄로 분리된 단락은 그대로 둠)
        out_lines = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            out_lines.append(line)
            # 마지막이 아니고, 다음 줄이 빈줄이 아니고, 현재 줄도 빈줄이 아니면
            # 가독성을 위해 빈 줄 삽입
            if i < len(lines) - 1:
                nxt = lines[i + 1]
                if line.strip() and nxt.strip():
                    # 단락 첫 줄이거나 일반 문장 줄에는 추가 행간을 주지 않음.
                    # 들여쓰기/불릿이 시작되는 줄과 단락 분리에는 도움이 됨.
                    pass
        # 단순히 모든 \n → \n\n 변환은 너무 듬성듬성해지므로
        # 원본 그대로 반환 (줄 수만 LINE_H로 충분히 처리)
        return text

    def _update_step(self):
        """현재 단계의 정보를 업데이트합니다."""
        step = self._steps[self._step_index]
        total = len(self._steps)
        idx = self._step_index

        # 하이라이트 영역 계산
        self._highlight_rect = self._get_highlight_rect()

        # ── 텍스트 업데이트 ──
        # STEP 캡션은 영문 대문자 + 코랄 (시각적 변화로 새 디자인 강조)
        self.step_label.setText(f"STEP {idx + 1} OF {total}")
        self.title_label.setText(step["title"])
        # desc는 HTML로 감싸 line-height 1.6 적용 (QLabel은 rich-text를 지원)
        desc_html = step["desc"].replace("\n", "<br>")
        self.desc_label.setText(
            f"<div style='line-height: 160%;'>{desc_html}</div>"
        )

        # 도트는 진행률 바로 대체 — 별도 처리 불필요

        # 버튼 상태
        self.prev_btn.setVisible(idx > 0)
        is_last = idx == total - 1
        if is_last:
            self.next_btn.setText("시작하기")
            self.skip_btn.setVisible(False)
            self.dont_show_check.setVisible(True)
        else:
            self.next_btn.setText("다음 \u2192")
            self.skip_btn.setVisible(True)
            self.dont_show_check.setVisible(False)

        self._position_tooltip()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._highlight_rect = self._get_highlight_rect()
        self._position_tooltip()

    def _next_step(self):
        if self._step_index < len(self._steps) - 1:
            self._step_index += 1
            self._update_step()
        else:
            self._close_overlay()

    def _prev_step(self):
        if self._step_index > 0:
            self._step_index -= 1
            self._update_step()

    def _on_dont_show_toggled(self, checked):
        self._dont_show_again = checked

    def _close_overlay(self):
        from src.config import config
        if self._dont_show_again:
            config.tutorial_shown = True
            config.save()
        self.hide()

    def mousePressEvent(self, event):
        event.accept()
