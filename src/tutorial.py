"""
사용법 안내 - 튜토리얼 다이얼로그 & 오버레이
쇼핑 상품 스레드 자동화의 모든 기능을 단계별로 설명합니다.

오버레이 모드: 메인 윈도우의 실제 버튼/입력창 위치를 직접 하이라이트하여 안내합니다.
다이얼로그 모드: [사용법] 버튼으로 열리는 독립 안내 창입니다.
"""
from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.app_icon import apply_window_icon
from src.theme import (
    Colors,
    Gradients,
    Radius,
    close_btn_style,
    ghost_btn_style,
    header_title_style,
    muted_text_style,
)

# ─── Tutorial Dialog Pages ─────────────────────────────────

TUTORIAL_PAGES = [
    {
        "icon": "C",
        "title": "환영합니다!",
        "subtitle": "여러 쇼핑몰의 Threads 자동화",
        "content": (
            "이 프로그램은 국내 7개 제휴 프로그램과\n"
            "AliExpress 호환 상품 링크를\n"
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
        "title": "1단계: AI 이용 준비",
        "subtitle": "별도 API 키 없이 바로 사용",
        "content": (
            "로그인과 이용권만으로 AI 게시글을 생성합니다.\n"
            "\n"
            "  설정 방법\n"
            "\n"
            "  1. 프로그램 회원가입 후 로그인합니다\n"
            "  2. 무료 월 5회 또는 구매한 이용권을 확인합니다\n"
            "  3. 상품 링크를 입력하면 Grok 4.3이 문안을 작성합니다\n"
            "\n"
            "  * xAI나 Google API 키를 직접 설정할 필요가 없습니다"
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
        "subtitle": "이미 발급받은 제휴 URL 붙여넣기",
        "content": (
            "각 제휴 프로그램에서 발급받은 링크를 그대로 입력합니다.\n"
            "앱이 제휴 링크를 새로 만들거나 바꾸지는 않습니다.\n"
            "\n"
            "  지원 프로그램\n"
            "\n"
            "  \u2022 쿠팡 파트너스 · 네이버 쇼핑 커넥트\n"
            "  \u2022 토스 쇼핑 쉐어링크 · 오늘의집 큐레이터\n"
            "  \u2022 무신사 큐레이터 · 컬리 큐레이터\n"
            "  \u2022 올리브영 쇼핑 큐레이터 · AliExpress(호환)\n"
            "\n"
            "  한 줄에 하나씩 붙여넣으면 원본 제휴 URL을 유지합니다.\n"
            "  쿠팡 외 링크는 쇼핑 프로가 필요합니다.\n"
            "  공개 페이지의 정보만 읽으므로 로그인·앱 전용 페이지나\n"
            "  허용된 경로 밖의 리다이렉트는 분석이 제한될 수 있습니다."
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
            "  1. 프로그램 로그인 및 이용량 확인\n"
            "  2. [Threads 계정]에서 로그인\n"
            "  3. [링크 입력]에서 상품 링크 붙여넣기\n"
            "  4. [자동화 시작] 버튼 클릭\n"
            "\n"
            "  문제 해결\n"
            "\n"
            "  \u2022 업로드 실패: [작업 로그]에서 오류 메시지 확인\n"
            "  \u2022 로그인 만료: [Threads 계정]에서 다시 로그인\n"
            "  \u2022 AI 오류: 남은 이용량과 인터넷 연결 확인"
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
        apply_window_icon(self)

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

        self.prev_btn = QPushButton("이전", self)
        prev_w = max(104, self.prev_btn.fontMetrics().horizontalAdvance(self.prev_btn.text()) + 36)
        self.prev_btn.setGeometry(24, 580, prev_w, 36)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(
            ghost_btn_style() + "\nQPushButton { font-size: 13pt; }"
        )
        self.prev_btn.clicked.connect(self._prev_page)

        self.skip_btn = QPushButton("건너뛰기", self)
        skip_w = max(110, self.skip_btn.fontMetrics().horizontalAdvance(self.skip_btn.text()) + 30)
        self.skip_btn.setGeometry((W - skip_w) // 2, 580, skip_w, 36)
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
        next_w = max(104, self.next_btn.fontMetrics().horizontalAdvance(self.next_btn.text()) + 32)
        self.next_btn.setGeometry(W - 24 - next_w, 580, next_w, 36)
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
        top_grad.setColorAt(0, QColor(13, 89, 242, 0))
        top_grad.setColorAt(0.3, QColor(Colors.ACCENT))
        top_grad.setColorAt(0.7, QColor(Colors.ACCENT_LIGHT))
        top_grad.setColorAt(1, QColor(59, 123, 255, 0))
        painter.fillRect(0, 0, W, 3, top_grad)

        bot_grad = QLinearGradient(0, 0, W, 0)
        bot_grad.setColorAt(0, QColor(13, 89, 242, 0))
        bot_grad.setColorAt(0.5, QColor(Colors.ACCENT_DARK))
        bot_grad.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, H - 2, W, 2, bot_grad)


# ─── Overlay Tutorial Steps (위젯 하이라이트 기반) ──────────

# 각 단계는 메인 윈도우의 실제 위젯을 하이라이트하며 설명합니다.
# "widget": MainWindow 속성 이름 (예: "_sidebar")
# "title": 단계 제목
# "desc": 설명 텍스트
# "tooltip_pos": 설명 카드 위치 ("right", "left", "bottom", "top")
# "padding": 하이라이트 영역 패딩 (기본 6px)

OVERLAY_STEPS = [
    {
        "widget": "_sidebar",
        "title": "운영 흐름을 둘러보세요",
        "desc": "운영 홈, 자동화, 작업 기록, Threads 계정과 설정을 한 곳에서 이동합니다.",
        "tooltip_pos": "right",
    },
    {
        "widget": "_run_state_frame",
        "title": "실행 준비를 확인하세요",
        "desc": "연결 계정, 남은 작업량과 업로드 단계를 자동화 시작 전에 한 번에 확인할 수 있습니다.",
        "tooltip_pos": "left",
        "padding": 8,
    },
    {
        "widget": "links_text",
        "title": "상품 링크를 붙여넣으세요",
        "desc": "제휴 프로그램에서 발급한 URL을 한 줄에 하나씩 입력하면 채널과 오류를 즉시 검사합니다.",
        "tooltip_pos": "right",
        "padding": 6,
    },
    {
        "widget": "start_btn",
        "title": "확인 후 자동화를 시작하세요",
        "desc": "실행 전 요약에서 링크 수와 간격을 확인한 뒤 분석, 글 생성, 업로드를 진행합니다.",
        "tooltip_pos": "top",
    },
    {
        "widget": "_settings_tab_bar",
        "title": "언제든 설정을 조정할 수 있어요",
        "desc": "계정 연결, 글쓰기 방식, AI와 앱 설정은 저장된 상태로 유지되며 화면 도움말은 F1로 다시 열 수 있습니다.",
        "tooltip_pos": "bottom",
    },
]


# ─── Tutorial Overlay Widget (위젯 하이라이트 방식) ──────────

class _LegacyTutorialOverlay(QWidget):
    """메인 윈도우의 실제 위젯을 하이라이트하는 튜토리얼 오버레이"""

    TOOLTIP_W = 340
    TOOLTIP_H_MAX = 340
    HIGHLIGHT_PAD = 6
    GLOW_WIDTH = 2

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

        # Dim everything except the current highlighted widget (70% opacity).
        dim = QColor(0, 0, 0, 179)
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
            glow2_pen = QPen(QColor(13, 89, 242, 90), 1)
            painter.setPen(glow2_pen)
            painter.drawRoundedRect(outer, 12, 12)

    def _build_ui(self):
        # 설명 카드 (tooltip) - 모든 요소를 카드 안에 배치
        self.tooltip_card = QWidget(self)
        self.tooltip_card.setStyleSheet(f"""
            QWidget#tooltipCard {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        self.tooltip_card.setObjectName("tooltipCard")

        # 단계 표시
        self.step_label = QLabel(self.tooltip_card)
        self.step_label.setStyleSheet(
            muted_text_style("11pt") + " font-weight: 600; border: none;"
        )

        # 제목
        self.title_label = QLabel(self.tooltip_card)
        self.title_label.setStyleSheet(
            header_title_style("16pt") + " border: none;"
        )

        # 설명
        self.desc_label = QLabel(self.tooltip_card)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12pt; "
            f"background: transparent; border: none; line-height: 1.5;"
        )

        # 구분선 (설명과 버튼 사이)
        self.separator = QFrame(self.tooltip_card)
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setStyleSheet(f"background-color: {Colors.BORDER}; border: none; max-height: 1px;")

        # 건너뛰기 버튼 (카드 안)
        self.skip_btn = QPushButton("건너뛰기", self.tooltip_card)
        self.skip_btn.setFixedHeight(34)
        self.skip_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_MUTED};
                border: none; border-radius: {Radius.MD};
                padding: 0 10px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; }}
        """)
        self.skip_btn.clicked.connect(self._close_overlay)

        # 이전 버튼 (카드 안)
        self.prev_btn = QPushButton("이전", self.tooltip_card)
        self.prev_btn.setFixedHeight(34)
        self.prev_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_ELEVATED};
                border-color: {Colors.BORDER_LIGHT};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.prev_btn.clicked.connect(self._prev_step)

        # 다음 버튼 (카드 안)
        self.next_btn = QPushButton("다음", self.tooltip_card)
        self.next_btn.setFixedHeight(34)
        self.next_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN}; color: #FFFFFF;
                border: none; border-radius: {Radius.MD};
                padding: 0 12px;
            }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
        """)
        self.next_btn.clicked.connect(self._next_step)

        # 다시 보지 않기 체크박스 (카드 안)
        self.dont_show_check = QCheckBox("다시 보지 않기", self.tooltip_card)
        self.dont_show_check.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY}; font-size: 11pt; spacing: 6px;
                background: transparent; border: none;
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

        # 페이지 표시 점은 제거 (카드 내부에서는 step_label로 충분)

    def _position_tooltip(self):
        """하이라이트 영역에 따라 설명 카드를 배치합니다. 모든 요소가 카드 내부."""
        W, H = self.width(), self.height()
        step = self._steps[self._step_index]
        pos = step.get("tooltip_pos", "right")
        hl = self._highlight_rect

        # ── 카드 내부 레이아웃 ──
        pad = 20
        inner_w = self.TOOLTIP_W - pad * 2

        self.step_label.setGeometry(pad, pad, inner_w, 18)
        self.title_label.setGeometry(pad, pad + 26, inner_w, 28)

        # desc 높이
        desc_text = step.get("desc", "")
        line_count = desc_text.count('\n') + 1
        desc_h = max(line_count * 22, 44)
        desc_y = pad + 60
        self.desc_label.setGeometry(pad, desc_y, inner_w, desc_h)

        # 구분선
        sep_y = desc_y + desc_h + 14
        self.separator.setGeometry(pad, sep_y, inner_w, 1)

        # 버튼 영역 (구분선 아래)
        btn_y = sep_y + 14
        btn_gap = 10

        skip_w = max(92, self.skip_btn.fontMetrics().horizontalAdvance(self.skip_btn.text()) + 24)
        prev_w = max(92, self.prev_btn.fontMetrics().horizontalAdvance(self.prev_btn.text()) + 24)
        next_w = max(92, self.next_btn.fontMetrics().horizontalAdvance(self.next_btn.text()) + 24)

        total_w = skip_w + prev_w + next_w + (btn_gap * 2)
        if total_w > inner_w:
            fit_w = max(82, (inner_w - (btn_gap * 2)) // 3)
            skip_w = prev_w = next_w = fit_w

        # 건너뛰기: 좌측
        self.skip_btn.setGeometry(pad, btn_y, skip_w, 34)

        # 이전: 중앙
        prev_x = pad + (inner_w - prev_w) // 2
        self.prev_btn.setGeometry(prev_x, btn_y, prev_w, 34)

        # 다음: 우측
        self.next_btn.setGeometry(pad + inner_w - next_w, btn_y, next_w, 34)

        # 체크박스 (마지막 단계에서만 표시, 버튼 아래)
        check_y = btn_y + 42
        self.dont_show_check.setGeometry(pad, check_y, inner_w, 20)

        # 카드 높이 계산
        is_last = self._step_index == len(self._steps) - 1
        if is_last:
            card_h = check_y + 20 + pad
        else:
            card_h = btn_y + 34 + pad

        card_h = min(card_h, self.TOOLTIP_H_MAX)

        # ── 위치 결정 ──
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

        self.tooltip_card.setGeometry(tx, ty, self.TOOLTIP_W, card_h)

    def _update_step(self):
        """현재 단계의 정보를 업데이트합니다."""
        step = self._steps[self._step_index]
        total = len(self._steps)
        idx = self._step_index

        # 하이라이트 영역 계산
        self._highlight_rect = self._get_highlight_rect()

        # 텍스트 업데이트
        self.step_label.setText(f"{idx + 1} / {total}")
        self.title_label.setText(step["title"])
        self.desc_label.setText(step["desc"])

        # 버튼 상태
        self.prev_btn.setVisible(idx > 0)
        is_last = idx == total - 1
        if is_last:
            self.next_btn.setText("시작하기")
            self.skip_btn.setVisible(False)
            self.dont_show_check.setVisible(True)
        else:
            self.next_btn.setText("다음")
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
            if not config.save():
                config.load()
        self.hide()

    def mousePressEvent(self, event):
        event.accept()


class TutorialOverlay(QWidget):
    """Canonical five-step contextual help overlay.

    The card is layout-driven and clamped to the visible viewport, so Korean
    copy and controls remain readable at the supported 760 x 560 minimum.
    """

    TOOLTIP_W = 340
    TOOLTIP_H_MAX = 360
    HIGHLIGHT_PAD = 6
    EDGE_MARGIN = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step_index = 0
        self._steps = OVERLAY_STEPS
        self._dont_show_again = False
        self._highlight_rect = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("현재 화면 도움말")
        self._build_ui()
        self._update_step()

    def show_overlay(self):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _get_main_window(self):
        widget = self.parent()
        while widget:
            if hasattr(widget, "_sidebar"):
                return widget
            widget = widget.parent() if hasattr(widget, "parent") else None
        return None

    def _get_highlight_rect(self):
        step = self._steps[self._step_index]
        widget_name = step.get("widget")
        main_win = self._get_main_window()
        if main_win is not None and hasattr(main_win, "_switch_page"):
            settings_targets = {"_settings_tab_bar"}
            automation_targets = {
                "_run_state_frame",
                "links_text",
                "start_btn",
            }
            if widget_name in settings_targets:
                main_win._switch_page(1, source="tutorial")
            elif widget_name in automation_targets:
                main_win._switch_page(0, source="tutorial")
        target = getattr(main_win, widget_name, None) if main_win and widget_name else None
        if target is None or not target.isVisible():
            return None
        if widget_name in {"_run_state_frame", "links_text"}:
            scroll = getattr(main_win, "_link_scroll", None)
            if scroll is not None:
                scroll.ensureWidgetVisible(target, 12, 12)
        pad = int(step.get("padding", self.HIGHLIGHT_PAD))
        global_pos = target.mapToGlobal(QPoint(0, 0))
        local_pos = self.mapFromGlobal(global_pos)
        highlight = QRect(
            local_pos.x() - pad,
            local_pos.y() - pad,
            target.width() + pad * 2,
            target.height() + pad * 2,
        )
        return highlight.intersected(self.rect().adjusted(4, 4, -4, -4))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        full = QPainterPath()
        full.addRect(QRectF(self.rect()))
        dim = QColor(16, 28, 36, 205)
        if self._highlight_rect and not self._highlight_rect.isEmpty():
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(self._highlight_rect), 12, 12)
            painter.fillPath(full.subtracted(hole), dim)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(37, 185, 188), 3))
            painter.drawRoundedRect(QRectF(self._highlight_rect), 12, 12)

            # A short connector keeps the relationship obvious without
            # obscuring the highlighted control.
            card = self.tooltip_card.geometry()
            target = self._highlight_rect.center()
            if card.center().x() <= target.x():
                origin = QPoint(card.right(), card.center().y())
            else:
                origin = QPoint(card.left(), card.center().y())
            painter.drawLine(origin, target)
        else:
            painter.fillPath(full, dim)

    def _build_ui(self):
        self.tooltip_card = QFrame(self)
        self.tooltip_card.setObjectName("contextHelpCard")
        self.tooltip_card.setStyleSheet(f"""
            QFrame#contextHelpCard {{ background: {Colors.BG_CARD}; border: 2px solid {Colors.ACCENT};
                border-radius: 14px; }}
            QLabel {{ background: transparent; border: none; }}
        """)
        card_layout = QVBoxLayout(self.tooltip_card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(8)
        self._tooltip_layout = card_layout

        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setFixedSize(64, 28)
        self.step_label.setFont(QFont("Pretendard", 9, QFont.Weight.Bold))
        self.step_label.setStyleSheet(
            f"background: {Colors.INFO_BG}; color: {Colors.ACCENT_LIGHT}; border-radius: 14px;"
        )
        card_layout.addWidget(self.step_label, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont("Pretendard", 14, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        card_layout.addWidget(self.title_label)

        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.desc_label.setFont(QFont("Pretendard", 10))
        self.desc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; line-height: 1.45;")
        card_layout.addWidget(self.desc_label)

        self.shortcut_label = QLabel("Esc로 언제든 닫을 수 있습니다.")
        self.shortcut_label.setFont(QFont("Pretendard", 8))
        self.shortcut_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        card_layout.addWidget(self.shortcut_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.prev_btn = QPushButton("이전")
        self.prev_btn.setMinimumSize(88, 44)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setAccessibleName("이전 도움말 단계")
        self.prev_btn.setStyleSheet(ghost_btn_style())
        self.prev_btn.clicked.connect(self._prev_step)
        button_row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("다음")
        self.next_btn.setMinimumHeight(44)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setAccessibleName("다음 도움말 단계")
        self.next_btn.setStyleSheet(f"""
            QPushButton {{ background: {Gradients.ACCENT_BTN}; color: #FFFFFF; border: none;
                border-radius: 8px; min-height: 44px; padding: 0 20px; font-weight: 700; }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:focus {{ border: 2px solid {Colors.INK}; }}
        """)
        self.next_btn.clicked.connect(self._next_step)
        button_row.addWidget(self.next_btn, 1)
        card_layout.addLayout(button_row)

        self.dont_show_check = QCheckBox("다시 보지 않기")
        self.dont_show_check.setMinimumHeight(30)
        self.dont_show_check.setStyleSheet(f"""
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; font-size: 9.5pt; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 5px; background: {Colors.BG_INPUT}; }}
            QCheckBox::indicator:checked {{ background: {Colors.ACCENT}; border-color: {Colors.ACCENT}; }}
        """)
        self.dont_show_check.toggled.connect(self._on_dont_show_toggled)
        card_layout.addWidget(self.dont_show_check)

        self.skip_btn = QPushButton("도움말 닫기", self)
        self.skip_btn.setAccessibleName("도움말 닫기")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setFixedSize(112, 40)
        self.skip_btn.setStyleSheet(
            "QPushButton { background: rgba(16, 28, 36, 0.88); color: white; border: 1px solid #52636D;"
            " border-radius: 8px; padding: 0; min-height: 40px; }"
            "QPushButton:hover { background: #0D7C84; }"
        )
        self.skip_btn.clicked.connect(self._close_overlay)

    def _position_tooltip(self):
        width = max(1, self.width())
        height = max(1, self.height())
        card_w = max(280, min(self.TOOLTIP_W, width - self.EDGE_MARGIN * 2))
        inner_w = max(220, card_w - 44)
        self.title_label.setFixedWidth(inner_w)
        self.desc_label.setFixedWidth(inner_w)
        desc_bounds = self.desc_label.fontMetrics().boundingRect(
            QRect(0, 0, inner_w, 1000),
            int(Qt.TextFlag.TextWordWrap),
            self.desc_label.text(),
        )
        self.desc_label.setFixedHeight(max(46, desc_bounds.height() + 4))
        title_bounds = self.title_label.fontMetrics().boundingRect(
            QRect(0, 0, inner_w, 200),
            int(Qt.TextFlag.TextWordWrap),
            self.title_label.text(),
        )
        self.title_label.setFixedHeight(max(28, title_bounds.height() + 2))
        self._tooltip_layout.activate()
        card_h = min(self.TOOLTIP_H_MAX, self.tooltip_card.sizeHint().height())

        highlight = self._highlight_rect
        position = self._steps[self._step_index].get("tooltip_pos", "right")
        margin = 16
        if highlight and not highlight.isEmpty():
            if position == "right":
                x, y = highlight.right() + margin, highlight.top()
                if x + card_w > width - self.EDGE_MARGIN:
                    x = highlight.left() - card_w - margin
            elif position == "left":
                x, y = highlight.left() - card_w - margin, highlight.top()
                if x < self.EDGE_MARGIN:
                    x = highlight.right() + margin
            elif position == "top":
                x, y = highlight.center().x() - card_w // 2, highlight.top() - card_h - margin
                if y < self.EDGE_MARGIN:
                    y = highlight.bottom() + margin
            else:
                x, y = highlight.center().x() - card_w // 2, highlight.bottom() + margin
                if y + card_h > height - self.EDGE_MARGIN:
                    y = highlight.top() - card_h - margin
        else:
            x, y = (width - card_w) // 2, (height - card_h) // 2

        x = max(self.EDGE_MARGIN, min(int(x), width - card_w - self.EDGE_MARGIN))
        y = max(self.EDGE_MARGIN, min(int(y), height - card_h - self.EDGE_MARGIN))
        self.tooltip_card.setGeometry(x, y, card_w, card_h)
        self.skip_btn.move(width - self.skip_btn.width() - 16, 16)

    def _update_step(self):
        step = self._steps[self._step_index]
        is_last = self._step_index == len(self._steps) - 1
        self._highlight_rect = self._get_highlight_rect()
        self.step_label.setText(f"{self._step_index + 1} / {len(self._steps)}")
        self.title_label.setText(step["title"])
        self.desc_label.setText(step["desc"])
        self.prev_btn.setEnabled(self._step_index > 0)
        self.next_btn.setText("완료" if is_last else "다음")
        self.dont_show_check.setVisible(is_last)
        self._position_tooltip()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._highlight_rect = self._get_highlight_rect()
        self._position_tooltip()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close_overlay()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace, Qt.Key.Key_P):
            self._prev_step()
        elif key in (
            Qt.Key.Key_Right,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
            Qt.Key.Key_N,
        ):
            self._next_step()
        elif key == Qt.Key.Key_Home:
            self._step_index = 0
            self._update_step()
        elif key == Qt.Key.Key_End:
            self._step_index = len(self._steps) - 1
            self._update_step()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

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
        self._dont_show_again = bool(checked)

    def _close_overlay(self):
        from src.config import config

        if self._dont_show_again:
            config.tutorial_shown = True
            if not config.save():
                config.load()
        self.hide()

    def mousePressEvent(self, event):
        event.accept()
