"""Responsive first-run onboarding for Thread Auto.

The dialog is deliberately presentation-only.  It never checks a plan,
launches a browser, saves settings, or claims that an external task succeeded.
Instead, each contextual action emits an intent signal for the application
controller and the controller reports real state through ``set_step_status``.
"""

from __future__ import annotations

from typing import ClassVar

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.app_icon import apply_window_icon
from src.theme import (
    Colors,
    ControlHeight,
    Radius,
    Spacing,
    accent_btn_style,
    ghost_btn_style,
    input_style,
    outline_btn_style,
)
from src.ui_components import BrandMark, SectionCard, StatusPill


class OnboardingDialog(QDialog):
    """Four-step, controller-driven first-run guide.

    Step indexes are zero-based in the public API.  Navigation changes only
    the visible guide page; it does not mark external work as complete.
    """

    skipped = pyqtSignal()
    finished = pyqtSignal()
    open_subscription_requested = pyqtSignal()
    open_accounts_requested = pyqtSignal()
    open_settings_requested = pyqtSignal()
    sample_link_requested = pyqtSignal(str)

    RECOMMENDED_WIDTH = 1040
    RECOMMENDED_HEIGHT = 720
    MINIMUM_WIDTH = 640
    MINIMUM_HEIGHT = 500
    COMPACT_BREAKPOINT = 820

    STEPS: ClassVar[tuple[dict[str, object], ...]] = (
        {
            "short": "이용권",
            "title": "이용권 확인",
            "eyebrow": "ACCESS",
            "description": "자동화를 시작하기 전에 실제 남은 이용량과 적용 중인 이용권을 확인합니다.",
            "status_detail": "아직 이용권 상태를 확인하지 않았습니다.",
            "bullets": (
                "무료 사용량 또는 구매한 이용권이 서버에서 확인되어야 합니다.",
                "이 화면은 남은 횟수나 결제 상태를 임의로 표시하지 않습니다.",
                "구독 · 지원 화면에서 현재 계정에 적용된 정보를 확인하세요.",
            ),
        },
        {
            "short": "Threads",
            "title": "Threads 연결",
            "eyebrow": "ACCOUNT",
            "description": "게시할 Threads 계정을 브라우저 세션으로 안전하게 연결합니다.",
            "status_detail": "아직 Threads 연결 상태를 확인하지 않았습니다.",
            "bullets": (
                "로그인 정보는 온보딩 화면에 입력하지 않습니다.",
                "Threads 계정 화면에서 외부 브라우저로 로그인합니다.",
                "연결 후에는 계정 이름과 세션 상태가 일치하는지 확인하세요.",
            ),
        },
        {
            "short": "기본값",
            "title": "업로드 기본값",
            "eyebrow": "DEFAULTS",
            "description": "반복 작업에 사용할 간격, 콘텐츠 방식, 미디어 옵션을 점검합니다.",
            "status_detail": "아직 업로드 기본값을 확인하지 않았습니다.",
            "bullets": (
                "업로드 간격은 계정 운영 정책에 맞게 설정하세요.",
                "글쓰기 콘셉트와 영상 우선 여부를 실제 작업 전에 검토하세요.",
                "변경 사항은 설정 화면에서 저장한 뒤 적용됩니다.",
            ),
        },
        {
            "short": "테스트 링크",
            "title": "테스트 링크",
            "eyebrow": "DRY RUN",
            "description": "직접 발급받은 제휴 링크 하나로 입력과 채널 분류 흐름을 확인합니다.",
            "status_detail": "아직 테스트 링크를 자동화 화면으로 보내지 않았습니다.",
            "bullets": (
                "본인이 제휴 프로그램에서 발급받은 URL만 사용하세요.",
                "Thread Auto는 입력한 원본 제휴 URL을 임의로 바꾸지 않습니다.",
                "요청 버튼은 자동화 화면으로 링크를 전달할 뿐 업로드를 시작하지 않습니다.",
            ),
        },
    )

    VALID_STEP_STATUSES: ClassVar[set[str]] = {
        "pending",
        "current",
        "complete",
        "needs_attention",
        "error",
    }
    _STATUS_ALIASES: ClassVar[dict[str, str]] = {
        "idle": "pending",
        "waiting": "pending",
        "active": "current",
        "running": "current",
        "done": "complete",
        "completed": "complete",
        "success": "complete",
        "warning": "needs_attention",
        "blocked": "needs_attention",
        "failed": "error",
        "failure": "error",
    }
    _STATUS_PRESENTATION: ClassVar[dict[str, tuple[str, str]]] = {
        "pending": ("대기", "neutral"),
        "current": ("현재 단계", "running"),
        "complete": ("완료", "success"),
        "needs_attention": ("확인 필요", "warning"),
        "error": ("오류", "error"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_step = 0
        self._compact: bool | None = None
        self._terminal_outcome: str | None = None
        self._step_statuses = ["pending"] * len(self.STEPS)
        self._step_details = [str(step["status_detail"]) for step in self.STEPS]

        self.setWindowTitle("Thread Auto 빠른 시작")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT)
        self._apply_parent_relative_size(parent)
        self.setAccessibleName("Thread Auto 첫 실행 안내")
        self.setAccessibleDescription(
            "이용권, Threads 연결, 업로드 기본값, 테스트 링크를 순서대로 확인합니다."
        )
        apply_window_icon(self)

        self._build_ui()
        self._refresh_step_ui()
        self._apply_responsive_layout(force=True)

    @property
    def current_step(self) -> int:
        """Zero-based index of the guide page currently shown."""

        return self._current_step

    @property
    def is_compact(self) -> bool:
        """Whether the top-stepper layout is currently active."""

        return bool(self._compact)

    def set_current_step(self, index: int) -> None:
        """Navigate to one of the four presentation steps."""

        step_index = self._validated_index(index)
        self._current_step = step_index
        self.step_stack.setCurrentIndex(step_index)
        self._refresh_step_ui()

    def set_step_status(self, index: int, status: str, detail: str = "") -> None:
        """Render real controller state without performing the underlying work."""

        step_index = self._validated_index(index)
        normalized = str(status or "").strip().lower().replace("-", "_")
        normalized = self._STATUS_ALIASES.get(normalized, normalized)
        if normalized not in self.VALID_STEP_STATUSES:
            raise ValueError(f"unsupported onboarding step status: {status}")
        self._step_statuses[step_index] = normalized
        self._step_details[step_index] = str(detail or "").strip()
        self._refresh_step_ui()

    def accept(self) -> None:
        """Finish onboarding once and preserve QDialog accepted semantics."""

        if self._terminal_outcome is None:
            self._terminal_outcome = "finished"
            self.finished.emit()
        QDialog.accept(self)

    def reject(self) -> None:
        """Skip onboarding once for Escape, window close, and the skip action."""

        if self._terminal_outcome is None:
            self._terminal_outcome = "skipped"
            self.skipped.emit()
        QDialog.reject(self)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Back or (
            event.key() == Qt.Key.Key_Left
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self._go_back()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Forward or (
            event.key() == Qt.Key.Key_Right
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self._go_next()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_parent_relative_size(self, parent: QWidget | None) -> None:
        if parent is not None and parent.width() > 0 and parent.height() > 0:
            reference_width = parent.width()
            reference_height = parent.height()
        else:
            screen = self.screen() or QApplication.primaryScreen()
            available = screen.availableGeometry() if screen is not None else None
            reference_width = available.width() if available is not None else 1280
            reference_height = available.height() if available is not None else 800

        maximum_width = max(self.MINIMUM_WIDTH, int(reference_width * 0.9))
        maximum_height = max(self.MINIMUM_HEIGHT, int(reference_height * 0.9))
        self.setMaximumSize(maximum_width, maximum_height)
        self.resize(
            min(self.RECOMMENDED_WIDTH, maximum_width),
            min(self.RECOMMENDED_HEIGHT, maximum_height),
        )

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {Colors.PORCELAIN}; color: {Colors.INK}; }}
            QLabel {{ background: transparent; }}
            QFrame#onboardingHeader, QFrame#onboardingFooter {{
                background-color: {Colors.PAPER};
                border: 1px solid {Colors.LINE};
                border-radius: {Radius.CARD};
            }}
            QFrame#onboardingStepNavigation {{
                background-color: {Colors.INK};
                border: 1px solid {Colors.INK};
                border-radius: {Radius.HERO};
            }}
            QFrame#onboardingContent {{
                background-color: {Colors.PAPER};
                border: 1px solid {Colors.LINE};
                border-radius: {Radius.HERO};
            }}
            """
        )
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(
            Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL
        )
        self.root_layout.setSpacing(Spacing.LG)

        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        self.header = QFrame(self)
        self.header.setObjectName("onboardingHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        header_layout.setSpacing(Spacing.MD)

        mark = BrandMark(self.header, background=Colors.INK, foreground=Colors.PAPER)
        mark.setFixedSize(44, 44)
        header_layout.addWidget(mark)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("처음 4가지만 확인하면 바로 시작할 수 있어요", self.header)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {Colors.INK}; font-size: 14pt; font-weight: 800;")
        subtitle = QLabel(
            "실제 계정 상태는 각 관리 화면에서 확인하며, 온보딩이 성공 상태를 대신 만들지 않습니다.",
            self.header,
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {Colors.SLATE}; font-size: 9.5pt; font-weight: 500;"
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box, 1)

        self.skip_btn = QPushButton("나중에 설정", self.header)
        self.skip_btn.setFixedHeight(ControlHeight.INPUT)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setAccessibleName("온보딩 건너뛰기")
        self.skip_btn.setAccessibleDescription(
            "온보딩을 닫습니다. 필요한 설정은 나중에 각 관리 화면에서 할 수 있습니다."
        )
        self.skip_btn.setStyleSheet(ghost_btn_style())
        self.skip_btn.clicked.connect(self.reject)
        header_layout.addWidget(self.skip_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.root_layout.addWidget(self.header)

    def _build_body(self) -> None:
        self.body_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(Spacing.LG)

        self.step_navigation = QFrame(self)
        self.step_navigation.setObjectName("onboardingStepNavigation")
        self.step_navigation.setAccessibleName("온보딩 단계")
        self.step_layout = QBoxLayout(
            QBoxLayout.Direction.TopToBottom, self.step_navigation
        )
        self.step_layout.setContentsMargins(
            Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD
        )
        self.step_layout.setSpacing(Spacing.SM)
        self.step_group = QButtonGroup(self)
        self.step_group.setExclusive(True)
        self.step_buttons: list[QPushButton] = []
        for index, step in enumerate(self.STEPS):
            button = QPushButton(self.step_navigation)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(60)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            button.setAccessibleName(f"{index + 1}단계 {step['title']}")
            button.clicked.connect(
                lambda _checked=False, value=index: self.set_current_step(value)
            )
            self.step_group.addButton(button, index)
            self.step_layout.addWidget(button, 1)
            self.step_buttons.append(button)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("onboardingContent")
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.step_stack = QStackedWidget(self.content_frame)
        self.step_stack.setAccessibleName("온보딩 단계 내용")
        content_layout.addWidget(self.step_stack)

        self.step_scroll_areas: list[QScrollArea] = []
        self.step_status_pills: list[StatusPill] = []
        self.step_detail_labels: list[QLabel] = []
        self._page_layouts: list[QVBoxLayout] = []
        for index in range(len(self.STEPS)):
            self._build_step_page(index)

        self.body_layout.addWidget(self.step_navigation)
        self.body_layout.addWidget(self.content_frame, 1)
        self.root_layout.addLayout(self.body_layout, 1)

    def _build_step_page(self, index: int) -> None:
        step = self.STEPS[index]
        scroll_area = QScrollArea(self.step_stack)
        scroll_area.setObjectName(f"onboardingStep{index + 1}Scroll")
        scroll_area.setAccessibleName(f"{index + 1}단계 {step['title']} 내용")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        page = QWidget(scroll_area)
        page.setObjectName(f"onboardingStep{index + 1}Page")
        page.setMinimumWidth(0)
        page.setStyleSheet("background: transparent; border: none;")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        page_layout.setSpacing(Spacing.LG)

        eyebrow = QLabel(f"STEP {index + 1:02d}  /  {step['eyebrow']}", page)
        eyebrow.setStyleSheet(
            f"color: {Colors.SIGNAL_TEAL}; font-size: 9pt; font-weight: 800;"
            " letter-spacing: 1.2px;"
        )
        title = QLabel(str(step["title"]), page)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {Colors.INK}; font-size: 20pt; font-weight: 800;")
        description = QLabel(str(step["description"]), page)
        description.setWordWrap(True)
        description.setStyleSheet(
            f"color: {Colors.SLATE}; font-size: 10.5pt; line-height: 1.45;"
        )
        page_layout.addWidget(eyebrow)
        page_layout.addWidget(title)
        page_layout.addWidget(description)

        card = SectionCard(
            "이 단계에서 확인할 내용",
            "연결된 관리 화면에서 실제 값을 확인한 뒤 상태가 업데이트됩니다.",
            page,
        )
        status_row = QHBoxLayout()
        status_row.setSpacing(Spacing.MD)
        pill = StatusPill("대기", "neutral", card.body)
        detail = QLabel(self._step_details[index], card.body)
        detail.setWordWrap(True)
        detail.setStyleSheet(
            f"color: {Colors.SLATE}; font-size: 9.5pt; font-weight: 500;"
        )
        status_row.addWidget(pill, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(detail, 1)
        card.body_layout.addLayout(status_row)

        for bullet_text in step["bullets"]:
            bullet = QLabel(f"•  {bullet_text}", card.body)
            bullet.setWordWrap(True)
            bullet.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10pt;")
            card.body_layout.addWidget(bullet)

        action = self._build_step_action(index, card.body)
        card.body_layout.addWidget(action, 0, Qt.AlignmentFlag.AlignLeft)
        page_layout.addWidget(card)
        page_layout.addStretch(1)

        scroll_area.setWidget(page)
        self.step_stack.addWidget(scroll_area)
        self.step_scroll_areas.append(scroll_area)
        self.step_status_pills.append(pill)
        self.step_detail_labels.append(detail)
        self._page_layouts.append(page_layout)

    def _build_step_action(self, index: int, parent: QWidget) -> QWidget:
        if index == 0:
            self.subscription_btn = self._action_button(
                "구독 · 이용권 열기", "구독 및 이용권 화면 열기", parent
            )
            self.subscription_btn.clicked.connect(self.open_subscription_requested.emit)
            return self.subscription_btn
        if index == 1:
            self.accounts_btn = self._action_button(
                "Threads 계정 열기", "Threads 계정 연결 화면 열기", parent
            )
            self.accounts_btn.clicked.connect(self.open_accounts_requested.emit)
            return self.accounts_btn
        if index == 2:
            self.settings_btn = self._action_button(
                "업로드 설정 열기", "업로드 기본값 설정 화면 열기", parent
            )
            self.settings_btn.clicked.connect(self.open_settings_requested.emit)
            return self.settings_btn

        sample_box = QWidget(parent)
        sample_box.setMinimumWidth(0)
        sample_layout = QVBoxLayout(sample_box)
        sample_layout.setContentsMargins(0, Spacing.XS, 0, 0)
        sample_layout.setSpacing(Spacing.SM)
        sample_label = QLabel("테스트할 제휴 링크", sample_box)
        sample_label.setStyleSheet(
            f"color: {Colors.INK}; font-size: 9.5pt; font-weight: 700;"
        )
        sample_layout.addWidget(sample_label)
        self.sample_link_edit = QLineEdit(sample_box)
        self.sample_link_edit.setMinimumHeight(ControlHeight.INPUT)
        self.sample_link_edit.setPlaceholderText("https://link.coupang.com/a/...")
        self.sample_link_edit.setAccessibleName("테스트 제휴 링크")
        self.sample_link_edit.setAccessibleDescription(
            "직접 발급받은 http 또는 https 제휴 링크 하나를 입력합니다."
        )
        self.sample_link_edit.setStyleSheet(input_style())
        self.sample_link_edit.textChanged.connect(self._clear_sample_link_error)
        sample_layout.addWidget(self.sample_link_edit)
        self.sample_link_error = QLabel("", sample_box)
        self.sample_link_error.setWordWrap(True)
        self.sample_link_error.setAccessibleName("테스트 링크 입력 오류")
        self.sample_link_error.setStyleSheet(
            f"color: {Colors.CORAL}; font-size: 9pt; font-weight: 600;"
        )
        self.sample_link_error.setVisible(False)
        sample_layout.addWidget(self.sample_link_error)
        self.sample_link_btn = self._action_button(
            "이 링크로 자동화 화면 열기",
            "입력한 링크를 자동화 화면으로 전달",
            sample_box,
        )
        self.sample_link_btn.clicked.connect(self._request_sample_link)
        sample_layout.addWidget(self.sample_link_btn, 0, Qt.AlignmentFlag.AlignLeft)
        return sample_box

    @staticmethod
    def _action_button(text: str, accessible_name: str, parent: QWidget) -> QPushButton:
        button = QPushButton(text, parent)
        button.setMinimumHeight(ControlHeight.INPUT)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAccessibleName(accessible_name)
        button.setAccessibleDescription(
            "외부 작업을 직접 실행하지 않고 애플리케이션에 화면 이동을 요청합니다."
        )
        button.setStyleSheet(outline_btn_style(Colors.SIGNAL_TEAL))
        return button

    def _build_footer(self) -> None:
        self.footer = QFrame(self)
        self.footer.setObjectName("onboardingFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        footer_layout.setSpacing(Spacing.MD)

        self.step_counter = QLabel("1 / 4", self.footer)
        self.step_counter.setMinimumWidth(64)
        self.step_counter.setAccessibleName("현재 온보딩 단계")
        self.step_counter.setStyleSheet(
            f"color: {Colors.DEEP_TEAL}; font-size: 10pt; font-weight: 800;"
        )
        footer_layout.addWidget(self.step_counter)
        footer_layout.addStretch(1)

        self.back_btn = QPushButton("이전", self.footer)
        self.back_btn.setFixedHeight(ControlHeight.PRIMARY)
        self.back_btn.setMinimumWidth(112)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setAccessibleName("이전 온보딩 단계")
        self.back_btn.setAccessibleDescription("Alt+왼쪽 화살표")
        self.back_btn.setStyleSheet(ghost_btn_style())
        self.back_btn.clicked.connect(self._go_back)
        footer_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("다음", self.footer)
        self.next_btn.setFixedHeight(ControlHeight.PRIMARY)
        self.next_btn.setMinimumWidth(156)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setAccessibleName("다음 온보딩 단계")
        self.next_btn.setAccessibleDescription(
            "Alt+오른쪽 화살표. 마지막 단계에서는 온보딩을 완료합니다."
        )
        self.next_btn.setStyleSheet(accent_btn_style(use_gradient=False))
        self.next_btn.setDefault(True)
        self.next_btn.clicked.connect(self._go_next)
        footer_layout.addWidget(self.next_btn)
        self.root_layout.addWidget(self.footer)

        self._back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        self._back_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._back_shortcut.activated.connect(self._go_back)
        self._next_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        self._next_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._next_shortcut.activated.connect(self._go_next)

    def _go_back(self) -> None:
        if self._current_step > 0:
            self.set_current_step(self._current_step - 1)

    def _go_next(self) -> None:
        if self._current_step < len(self.STEPS) - 1:
            self.set_current_step(self._current_step + 1)
        else:
            self.accept()

    def _request_sample_link(self) -> None:
        value = self.sample_link_edit.text().strip()
        parsed = QUrl(value)
        if (
            not value
            or not parsed.isValid()
            or parsed.scheme().lower() not in {"http", "https"}
            or not parsed.host()
        ):
            self.sample_link_error.setText(
                "http:// 또는 https://로 시작하는 유효한 제휴 링크를 입력해 주세요."
            )
            self.sample_link_error.setVisible(True)
            self.sample_link_edit.setStyleSheet(
                input_style() + f"QLineEdit {{ border: 2px solid {Colors.CORAL}; }}"
            )
            self.sample_link_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._clear_sample_link_error()
        self.sample_link_requested.emit(value)

    def _clear_sample_link_error(self, *_args) -> None:
        if not hasattr(self, "sample_link_error"):
            return
        self.sample_link_error.clear()
        self.sample_link_error.setVisible(False)
        self.sample_link_edit.setStyleSheet(input_style())

    def _refresh_step_ui(self) -> None:
        if not hasattr(self, "step_buttons"):
            return
        total = len(self.STEPS)
        self.step_counter.setText(f"{self._current_step + 1} / {total}")
        self.step_counter.setAccessibleDescription(
            f"전체 {total}단계 중 {self._current_step + 1}단계"
        )
        self.back_btn.setEnabled(self._current_step > 0)
        self.next_btn.setText(
            "온보딩 완료" if self._current_step == total - 1 else "다음"
        )
        for index, button in enumerate(self.step_buttons):
            button.setChecked(index == self._current_step)
            status = self._effective_status(index)
            status_text, pill_status = self._STATUS_PRESENTATION[status]
            detail = self._step_details[index]
            self.step_status_pills[index].set_status(pill_status, status_text)
            self.step_detail_labels[index].setText(detail)
            self.step_detail_labels[index].setVisible(bool(detail))
            button.setAccessibleDescription(
                f"{status_text}. {detail}" if detail else status_text
            )
            self._style_step_button(button, status, index == self._current_step)
        self._update_step_button_texts()

    def _effective_status(self, index: int) -> str:
        stored = self._step_statuses[index]
        if stored == "pending" and index == self._current_step:
            return "current"
        return stored

    def _style_step_button(
        self, button: QPushButton, status: str, selected: bool
    ) -> None:
        if status == "complete":
            accent = Colors.EMERALD
        elif status in {"needs_attention", "error"}:
            accent = Colors.AMBER if status == "needs_attention" else Colors.CORAL
        elif selected or status == "current":
            accent = Colors.SIGNAL_TEAL
        else:
            accent = Colors.TEXT_ON_INK_MUTED
        background = "rgba(255, 255, 255, 0.10)" if selected else "transparent"
        border = accent if selected else "rgba(255, 255, 255, 0.12)"
        button.setStyleSheet(
            f"QPushButton {{ background-color: {background}; color: {Colors.PAPER};"
            f" border: 1px solid {border}; border-radius: {Radius.INPUT};"
            " padding: 8px 12px; text-align: left; font-size: 9.5pt;"
            " font-weight: 700; }}"
            f"QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.12);"
            f" border-color: {accent}; }}"
            f"QPushButton:focus {{ border: 2px solid {Colors.PAPER}; }}"
            f"QPushButton:checked {{ background-color: rgba(13, 124, 132, 0.28);"
            f" border-color: {accent}; }}"
        )

    def _update_step_button_texts(self) -> None:
        if not hasattr(self, "step_buttons"):
            return
        compact = bool(self._compact)
        for index, (step, button) in enumerate(zip(self.STEPS, self.step_buttons)):
            if compact:
                button.setText(f"{index + 1:02d}\n{step['short']}")
                button.setMinimumHeight(56)
            else:
                button.setText(f"{index + 1:02d}  {step['title']}\n{step['short']}")
                button.setMinimumHeight(64)

    def _apply_responsive_layout(self, *, force: bool = False) -> None:
        if not hasattr(self, "body_layout"):
            return
        compact = self.width() < self.COMPACT_BREAKPOINT
        if not force and compact == self._compact:
            return
        self._compact = compact
        if compact:
            self.root_layout.setContentsMargins(
                Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD
            )
            self.root_layout.setSpacing(Spacing.MD)
            self.body_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.body_layout.setSpacing(Spacing.MD)
            self.step_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.step_navigation.setMinimumWidth(0)
            self.step_navigation.setMaximumWidth(16777215)
            self.step_navigation.setMinimumHeight(76)
            self.step_navigation.setMaximumHeight(88)
            self.skip_btn.setText("건너뛰기")
            self.back_btn.setMinimumWidth(96)
            self.next_btn.setMinimumWidth(132)
            page_inset = Spacing.LG
        else:
            self.root_layout.setContentsMargins(
                Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL
            )
            self.root_layout.setSpacing(Spacing.LG)
            self.body_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.body_layout.setSpacing(Spacing.LG)
            self.step_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.step_navigation.setMinimumWidth(240)
            self.step_navigation.setMaximumWidth(270)
            self.step_navigation.setMinimumHeight(0)
            self.step_navigation.setMaximumHeight(16777215)
            self.skip_btn.setText("나중에 설정")
            self.back_btn.setMinimumWidth(112)
            self.next_btn.setMinimumWidth(156)
            page_inset = Spacing.XL

        for page_layout in self._page_layouts:
            page_layout.setContentsMargins(
                page_inset, page_inset, page_inset, page_inset
            )
        self._update_step_button_texts()

    def _validated_index(self, index: int) -> int:
        try:
            value = int(index)
        except (TypeError, ValueError) as exc:
            raise IndexError(f"onboarding step index out of range: {index}") from exc
        if not 0 <= value < len(self.STEPS):
            raise IndexError(f"onboarding step index out of range: {index}")
        return value
