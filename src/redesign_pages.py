"""Layout-based pages for the Thread Auto *Editorial Control Room* redesign.

These widgets deliberately contain presentation state only.  Callers inject
domain data through the ``render_*`` methods and subscribe to the intent
signals exposed by each page.  This keeps the pages safe to embed in
``MainWindow`` without coupling them to authentication, persistence or upload
services.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.theme import (
    Colors,
    ControlHeight,
    Radius,
    Spacing,
    Typography,
    accent_btn_style,
    ghost_btn_style,
    outline_btn_style,
)

_COMPACT_BREAKPOINT = 1020


def _read(item: Any, key: str, default: Any = "") -> Any:
    """Read a field from a mapping or a simple data object."""
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _identifier(item: Any, fallback: str = "") -> str:
    for key in ("id", "account_id", "job_id", "record_id", "plan_id", "username"):
        value = _read(item, key, "")
        if value not in (None, ""):
            return str(value)
    return fallback


def _status_color(item: Any) -> str:
    kind = _text(_read(item, "status_kind", _read(item, "kind", ""))).lower()
    status = _text(_read(item, "status", _read(item, "result", ""))).lower()
    value = f"{kind} {status}"
    if any(word in value for word in ("error", "fail", "실패", "만료", "오류")):
        return Colors.ERROR
    if any(
        word in value
        for word in ("warning", "pending", "재확인", "확인 필요", "중복", "대기")
    ):
        return Colors.WARNING
    if any(word in value for word in ("success", "healthy", "완료", "성공", "정상")):
        return Colors.SUCCESS
    return Colors.ACCENT


def _clear_layout(layout: QBoxLayout | QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)  # type: ignore[arg-type]


def _set_accessible(widget: QWidget, object_name: str, accessible_name: str) -> QWidget:
    widget.setObjectName(object_name)
    widget.setAccessibleName(accessible_name)
    return widget


def _button(
    text: str,
    object_name: str,
    accessible_name: str,
    *,
    kind: str = "primary",
) -> QPushButton:
    button = QPushButton(text)
    _set_accessible(button, object_name, accessible_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    if kind == "primary":
        button.setStyleSheet(
            accent_btn_style(use_gradient=False)
            + f"QPushButton#{object_name} {{ min-height: {ControlHeight.PRIMARY}px; }}"
        )
        button.setMinimumHeight(ControlHeight.PRIMARY)
    elif kind == "danger":
        button.setStyleSheet(
            outline_btn_style(Colors.ERROR)
            + f"QPushButton#{object_name} {{ min-height: {ControlHeight.INPUT}px; }}"
        )
        button.setMinimumHeight(ControlHeight.INPUT)
    else:
        button.setStyleSheet(
            ghost_btn_style()
            + f"QPushButton#{object_name} {{ min-height: {ControlHeight.INPUT}px; }}"
        )
        button.setMinimumHeight(ControlHeight.INPUT)
    return button


class _Card(QFrame):
    def __init__(
        self, object_name: str, accessible_name: str, *, dark: bool = False
    ) -> None:
        super().__init__()
        _set_accessible(self, object_name, accessible_name)
        self.setProperty("uiRole", "darkCard" if dark else "card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class _EmptyState(QFrame):
    def __init__(self, object_name: str, title: str, description: str) -> None:
        super().__init__()
        _set_accessible(self, object_name, title)
        self.setProperty("uiRole", "emptyState")
        self.setMinimumHeight(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.XS)
        title_label = QLabel(title)
        title_label.setProperty("uiRole", "sectionTitle")
        description_label = QLabel(description)
        description_label.setProperty("uiRole", "muted")
        description_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(description_label)


class _MetricCard(_Card):
    def __init__(self, item: Any, index: int, prefix: str) -> None:
        label = _text(_read(item, "label", _read(item, "title", "지표")), "지표")
        super().__init__(f"{prefix}MetricCard{index}", f"{label} 지표")
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.XS)
        label_widget = QLabel(label)
        label_widget.setProperty("uiRole", "metricLabel")
        value_widget = QLabel(_text(_read(item, "value", "—"), "—"))
        value_widget.setProperty("uiRole", "metricValue")
        value_widget.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_widget = QLabel(_text(_read(item, "detail", _read(item, "caption", ""))))
        detail_widget.setProperty("uiRole", "metricDetail")
        detail_widget.setWordWrap(True)
        detail_widget.setStyleSheet(f"color: {_status_color(item)};")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        layout.addWidget(detail_widget)


class _PageBase(QWidget):
    """Shared scroll shell, styling and breakpoint support."""

    def __init__(self, object_name: str, accessible_name: str) -> None:
        super().__init__()
        _set_accessible(self, object_name, accessible_name)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._compact = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea()
        _set_accessible(
            self.scroll_area,
            f"{object_name}ScrollArea",
            f"{accessible_name} 스크롤 영역",
        )
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.content = QWidget()
        _set_accessible(
            self.content, f"{object_name}Content", f"{accessible_name} 콘텐츠"
        )
        self.content.setMinimumWidth(0)
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        self.body.setSpacing(Spacing.LG)
        self.scroll_area.setWidget(self.content)
        outer.addWidget(self.scroll_area)

        self.setStyleSheet(self._page_stylesheet())

    @staticmethod
    def _page_stylesheet() -> str:
        return f"""
            QScrollArea {{ background: {Colors.BG_DARK}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {Colors.BG_DARK}; }}
            QFrame[uiRole="card"] {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.HERO};
            }}
            QFrame[uiRole="darkCard"] {{
                background: {Colors.INK};
                border: 1px solid {Colors.INK};
                border-radius: {Radius.HERO};
            }}
            QFrame[uiRole="emptyState"] {{
                background: {Colors.BG_INPUT};
                border: 1px dashed {Colors.BORDER_LIGHT};
                border-radius: {Radius.CARD};
            }}
            QLabel[uiRole="eyebrow"] {{
                color: {Colors.ACCENT};
                {Typography.CAPTION}
            }}
            QLabel[uiRole="pageTitle"] {{
                color: {Colors.TEXT_PRIMARY};
                {Typography.TITLE_XL}
            }}
            QLabel[uiRole="sectionTitle"] {{
                color: {Colors.TEXT_PRIMARY};
                {Typography.TITLE_SM}
            }}
            QLabel[uiRole="muted"], QLabel[uiRole="metricLabel"], QLabel[uiRole="metricDetail"] {{
                color: {Colors.TEXT_MUTED};
                {Typography.CAPTION}
            }}
            QLabel[uiRole="metricValue"] {{
                color: {Colors.TEXT_PRIMARY};
                {Typography.TITLE_MD}
            }}
            QLabel[uiRole="inverseTitle"] {{
                color: {Colors.TEXT_ON_INK};
                {Typography.TITLE_LG}
            }}
            QLabel[uiRole="inverseBody"] {{
                color: {Colors.SKY};
                {Typography.BODY_SM}
            }}
            QLabel[uiRole="status"] {{
                background: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.PILL};
                padding: 4px 10px;
                {Typography.CAPTION}
            }}
            QTableWidget {{
                background: {Colors.BG_CARD};
                alternate-background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD};
                gridline-color: {Colors.BORDER_SUBTLE};
                selection-background-color: {Colors.SKY};
                selection-color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background: {Colors.BG_INPUT};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
                padding: 8px;
                {Typography.CAPTION}
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid transparent;
                border-radius: {Radius.CARD};
                padding: 12px;
                margin: 3px 0;
            }}
            QListWidget::item:hover {{ background: {Colors.BG_HOVER}; }}
            QListWidget::item:selected {{
                background: {Colors.SKY};
                border-color: {Colors.ACCENT};
                color: {Colors.TEXT_PRIMARY};
            }}
            QLineEdit, QComboBox {{
                min-height: {ControlHeight.INPUT}px;
                background: {Colors.BG_INPUT};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.INPUT};
                padding: 0 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border: 2px solid {Colors.ACCENT}; }}
        """

    def _add_page_header(
        self,
        eyebrow: str,
        title: str,
        description: str,
        action: QPushButton | None = None,
    ) -> None:
        self.header = QWidget()
        _set_accessible(self.header, f"{self.objectName()}Header", f"{title} 머리말")
        self.header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(Spacing.LG)
        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(Spacing.XS)
        eyebrow_label = QLabel(eyebrow)
        eyebrow_label.setProperty("uiRole", "eyebrow")
        title_label = QLabel(title)
        _set_accessible(title_label, f"{self.objectName()}Title", title)
        title_label.setProperty("uiRole", "pageTitle")
        description_label = QLabel(description)
        description_label.setProperty("uiRole", "muted")
        description_label.setWordWrap(True)
        title_layout.addWidget(eyebrow_label)
        title_layout.addWidget(title_label)
        title_layout.addWidget(description_label)
        self.header_layout.addWidget(title_box, 1)
        if action is not None:
            self.header_layout.addWidget(action, 0, Qt.AlignmentFlag.AlignBottom)
        self.body.addWidget(self.header)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        compact = event.size().width() < _COMPACT_BREAKPOINT
        if compact != self._compact:
            self._compact = compact
            self._apply_responsive_layout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        compact = self.width() < _COMPACT_BREAKPOINT
        if compact != self._compact:
            self._compact = compact
            self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        if hasattr(self, "header_layout"):
            self.header_layout.setDirection(
                QBoxLayout.Direction.TopToBottom
                if self._compact
                else QBoxLayout.Direction.LeftToRight
            )


class DashboardPage(_PageBase):
    """Operational overview using only data supplied by ``render_dashboard``."""

    new_automation_requested = pyqtSignal()
    history_open_requested = pyqtSignal()
    account_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("dashboardPage", "운영 홈")
        if parent is not None:
            self.setParent(parent)

        self.new_automation_button = _button(
            "새 자동화 만들기",
            "dashboardNewAutomationButton",
            "새 자동화 만들기",
        )
        self.new_automation_button.clicked.connect(self.new_automation_requested.emit)
        self._add_page_header(
            "CONTROL ROOM",
            "운영 홈",
            "오늘 상태와 계정 건강, 최근 결과를 한곳에서 확인합니다.",
            self.new_automation_button,
        )

        self.metrics_host = QWidget()
        _set_accessible(self.metrics_host, "dashboardMetrics", "오늘의 운영 지표")
        self.metrics_layout = QGridLayout(self.metrics_host)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setHorizontalSpacing(Spacing.MD)
        self.metrics_layout.setVerticalSpacing(Spacing.MD)
        self._metric_widgets: list[QWidget] = []
        self.body.addWidget(self.metrics_host)

        self.dashboard_pair = QWidget()
        self.dashboard_pair_layout = QBoxLayout(
            QBoxLayout.Direction.LeftToRight, self.dashboard_pair
        )
        self.dashboard_pair_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_pair_layout.setSpacing(Spacing.LG)

        self.next_action_card = _Card(
            "dashboardNextActionCard", "다음 자동화 안내", dark=True
        )
        hero_layout = QVBoxLayout(self.next_action_card)
        hero_layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        hero_layout.setSpacing(Spacing.MD)
        hero_title = QLabel("다음 자동화를 준비하세요")
        hero_title.setProperty("uiRole", "inverseTitle")
        hero_body = QLabel(
            "제휴 링크를 검사한 뒤 연결된 Threads 계정으로 안전하게 배포할 수 있습니다."
        )
        hero_body.setProperty("uiRole", "inverseBody")
        hero_body.setWordWrap(True)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_body)
        hero_layout.addStretch(1)
        hero_action = _button(
            "새 자동화 시작",
            "dashboardHeroAutomationButton",
            "새 자동화 시작",
        )
        hero_action.clicked.connect(self.new_automation_requested.emit)
        hero_layout.addWidget(hero_action, 0, Qt.AlignmentFlag.AlignLeft)

        self.accounts_card = _Card("dashboardAccountHealthCard", "Threads 계정 상태")
        accounts_layout = QVBoxLayout(self.accounts_card)
        accounts_layout.setContentsMargins(
            Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG
        )
        accounts_layout.setSpacing(Spacing.MD)
        accounts_title = QLabel("계정 상태")
        accounts_title.setProperty("uiRole", "sectionTitle")
        accounts_layout.addWidget(accounts_title)
        self.account_health_host = QWidget()
        self.account_health_layout = QVBoxLayout(self.account_health_host)
        self.account_health_layout.setContentsMargins(0, 0, 0, 0)
        self.account_health_layout.setSpacing(Spacing.SM)
        accounts_layout.addWidget(self.account_health_host, 1)

        self.dashboard_pair_layout.addWidget(self.next_action_card, 2)
        self.dashboard_pair_layout.addWidget(self.accounts_card, 1)
        self.body.addWidget(self.dashboard_pair)

        self.recent_card = _Card("dashboardRecentJobsCard", "최근 작업")
        recent_layout = QVBoxLayout(self.recent_card)
        recent_layout.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.XL)
        recent_layout.setSpacing(Spacing.MD)
        recent_header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        recent_title = QLabel("최근 작업")
        recent_title.setProperty("uiRole", "sectionTitle")
        self.history_button = _button(
            "전체 기록 보기",
            "dashboardOpenHistoryButton",
            "전체 작업 기록 보기",
            kind="secondary",
        )
        self.history_button.clicked.connect(self.history_open_requested.emit)
        recent_header.addWidget(recent_title)
        recent_header.addStretch(1)
        recent_header.addWidget(self.history_button)
        recent_layout.addLayout(recent_header)
        self.recent_table = _make_table(
            "dashboardRecentJobsTable",
            "최근 작업 목록",
            ["시작 시간", "계정", "결과", "소요 시간", "상태"],
        )
        self.recent_table.setMinimumHeight(178)
        recent_layout.addWidget(self.recent_table)
        self.recent_empty = _EmptyState(
            "dashboardRecentJobsEmpty",
            "아직 작업 기록이 없습니다",
            "새 자동화를 실행하면 최근 결과가 여기에 표시됩니다.",
        )
        recent_layout.addWidget(self.recent_empty)
        self.body.addWidget(self.recent_card)
        self.body.addStretch(1)

        self.render_dashboard()

    def render_dashboard(
        self,
        metrics: Mapping[str, Any] | Sequence[Any] | None = None,
        accounts: Sequence[Any] | None = None,
        recent_jobs: Sequence[Any] | None = None,
    ) -> None:
        metric_items = _normalise_metrics(metrics)
        _clear_layout(self.metrics_layout)
        self._metric_widgets = []
        if metric_items:
            self._metric_widgets = [
                _MetricCard(item, index, "dashboard")
                for index, item in enumerate(metric_items)
            ]
        else:
            self._metric_widgets = [
                _EmptyState(
                    "dashboardMetricsEmpty",
                    "표시할 운영 지표가 없습니다",
                    "첫 작업이 시작되면 오늘의 상태가 자동으로 채워집니다.",
                )
            ]
        self._reflow_metrics()

        _clear_layout(self.account_health_layout)
        account_rows = list(accounts or [])
        if not account_rows:
            self.account_health_layout.addWidget(
                _EmptyState(
                    "dashboardAccountsEmpty",
                    "연결된 계정이 없습니다",
                    "Threads 계정을 연결하면 상태를 확인할 수 있습니다.",
                )
            )
        else:
            for index, account in enumerate(account_rows):
                account_id = _identifier(account, str(index))
                name = _text(
                    _read(account, "name", _read(account, "username", account_id)),
                    account_id,
                )
                status = _text(_read(account, "status", "상태 미확인"), "상태 미확인")
                row = QPushButton(f"{name}\n{status}")
                _set_accessible(row, f"dashboardAccountRow{index}", f"{name}, {status}")
                row.setProperty("class", "ghost")
                row.setMinimumHeight(52)
                row.setStyleSheet(
                    ghost_btn_style()
                    + f"QPushButton#{row.objectName()} {{ min-height: 52px; }}"
                )
                row.setToolTip(name)
                row.clicked.connect(
                    lambda _checked=False, value=account_id: self.account_selected.emit(
                        value
                    )
                )
                self.account_health_layout.addWidget(row)
            self.account_health_layout.addStretch(1)

        _set_table_data(
            self.recent_table,
            list(recent_jobs or []),
            ["started_at", "account", "result", "duration", "status"],
        )
        has_jobs = bool(recent_jobs)
        self.recent_table.setVisible(has_jobs)
        self.recent_empty.setVisible(not has_jobs)

    def _reflow_metrics(self) -> None:
        for widget in self._metric_widgets:
            self.metrics_layout.removeWidget(widget)
        columns = 2 if self._compact else min(4, max(1, len(self._metric_widgets)))
        for index, widget in enumerate(self._metric_widgets):
            self.metrics_layout.addWidget(widget, index // columns, index % columns)
        for column in range(4):
            self.metrics_layout.setColumnStretch(column, 1 if column < columns else 0)

    def _apply_responsive_layout(self) -> None:
        super()._apply_responsive_layout()
        self.dashboard_pair_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self._compact
            else QBoxLayout.Direction.LeftToRight
        )
        self._reflow_metrics()


class HistoryPage(_PageBase):
    """Searchable work-history presentation surface."""

    export_requested = pyqtSignal()
    filters_changed = pyqtSignal(object)
    retry_requested = pyqtSignal(str)
    record_open_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("historyPage", "작업 기록")
        if parent is not None:
            self.setParent(parent)

        self.export_button = _button(
            "CSV 내보내기",
            "historyExportButton",
            "작업 기록 CSV 내보내기",
            kind="secondary",
        )
        self.export_button.clicked.connect(self.export_requested.emit)
        self._add_page_header(
            "OPERATIONS LOG",
            "작업 기록",
            "검색과 필터로 결과를 찾고 실패한 작업을 다시 확인합니다.",
            self.export_button,
        )

        self.filters_card = _Card("historyFiltersCard", "작업 기록 검색과 필터")
        self.filters_layout = QGridLayout(self.filters_card)
        self.filters_layout.setContentsMargins(
            Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG
        )
        self.filters_layout.setSpacing(Spacing.SM)
        self.search_input = QLineEdit()
        _set_accessible(
            self.search_input, "historySearchInput", "상품명, 링크 또는 계정 검색"
        )
        self.search_input.setPlaceholderText("상품명, 링크, 계정으로 검색")
        self.search_input.setMinimumHeight(ControlHeight.INPUT)
        self.period_filter = _filter_combo("historyPeriodFilter", "조회 기간 필터")
        self.account_filter = _filter_combo("historyAccountFilter", "계정 필터")
        self.status_filter = _filter_combo("historyStatusFilter", "작업 상태 필터")
        self._filter_widgets: list[QWidget] = [
            self.search_input,
            self.period_filter,
            self.account_filter,
            self.status_filter,
        ]
        self.search_input.textChanged.connect(self._emit_filters)
        self.period_filter.currentTextChanged.connect(self._emit_filters)
        self.account_filter.currentTextChanged.connect(self._emit_filters)
        self.status_filter.currentTextChanged.connect(self._emit_filters)
        self.body.addWidget(self.filters_card)

        self.metrics_host = QWidget()
        self.metrics_layout = QGridLayout(self.metrics_host)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setSpacing(Spacing.MD)
        self._metric_widgets: list[QWidget] = []
        self.body.addWidget(self.metrics_host)

        table_card = _Card("historyResultsCard", "게시 이력")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.XL)
        table_layout.setSpacing(Spacing.MD)
        table_title = QLabel("게시 이력")
        table_title.setProperty("uiRole", "sectionTitle")
        table_layout.addWidget(table_title)
        self.history_table = _make_table(
            "historyResultsTable",
            "게시 이력 목록",
            ["시간", "채널", "상품 / 링크", "계정", "결과", "작업"],
        )
        self.history_table.setMinimumHeight(330)
        self.history_table.cellActivated.connect(self._handle_cell_action)
        self.history_table.cellClicked.connect(self._handle_cell_action)
        table_layout.addWidget(self.history_table)
        self.history_empty = _EmptyState(
            "historyResultsEmpty",
            "조건에 맞는 작업 기록이 없습니다",
            "자동화를 실행하거나 검색 조건을 변경해 보세요.",
        )
        table_layout.addWidget(self.history_empty)
        self.body.addWidget(table_card)
        self.body.addStretch(1)
        self._rows: list[Any] = []

        self.render_history()
        self._apply_responsive_layout()

    def set_filter_options(
        self,
        *,
        periods: Sequence[str] | None = None,
        accounts: Sequence[str] | None = None,
        statuses: Sequence[str] | None = None,
    ) -> None:
        _set_combo_items(self.period_filter, periods)
        _set_combo_items(self.account_filter, accounts)
        _set_combo_items(self.status_filter, statuses)

    def render_history(
        self,
        rows: Sequence[Any] | None = None,
        metrics: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> None:
        self._rows = list(rows or [])
        _set_table_data(
            self.history_table,
            self._rows,
            ["time", "channel", "product", "account", "result", "action"],
        )
        has_rows = bool(self._rows)
        self.history_table.setVisible(has_rows)
        self.history_empty.setVisible(not has_rows)

        _clear_layout(self.metrics_layout)
        metric_items = _normalise_metrics(metrics)
        self._metric_widgets = (
            [
                _MetricCard(item, index, "history")
                for index, item in enumerate(metric_items)
            ]
            if metric_items
            else [
                _EmptyState(
                    "historyMetricsEmpty",
                    "집계할 작업 기록이 없습니다",
                    "기록 데이터가 전달되면 기간별 지표가 표시됩니다.",
                )
            ]
        )
        self._reflow_metrics()

    def _emit_filters(self, *_args) -> None:
        self.filters_changed.emit(self.current_filters())

    def current_filters(self) -> dict[str, str]:
        """Return the currently visible filter state for controller refreshes."""
        return {
            "query": self.search_input.text(),
            "period": self.period_filter.currentData()
            or self.period_filter.currentText(),
            "account": self.account_filter.currentData()
            or self.account_filter.currentText(),
            "status": self.status_filter.currentData()
            or self.status_filter.currentText(),
        }

    def _handle_cell_action(self, row: int, column: int) -> None:
        if (
            not (0 <= row < len(self._rows))
            or column != self.history_table.columnCount() - 1
        ):
            return
        item = self._rows[row]
        record_id = _identifier(item, str(row))
        action = _text(_read(item, "action", "")).lower()
        if "재시도" in action or "retry" in action:
            self.retry_requested.emit(record_id)
        else:
            self.record_open_requested.emit(record_id)

    def _reflow_filters(self) -> None:
        for widget in self._filter_widgets:
            self.filters_layout.removeWidget(widget)
        if self._compact:
            self.filters_layout.addWidget(self.search_input, 0, 0, 1, 2)
            self.filters_layout.addWidget(self.period_filter, 1, 0)
            self.filters_layout.addWidget(self.account_filter, 1, 1)
            self.filters_layout.addWidget(self.status_filter, 2, 0, 1, 2)
        else:
            self.filters_layout.addWidget(self.search_input, 0, 0)
            self.filters_layout.addWidget(self.period_filter, 0, 1)
            self.filters_layout.addWidget(self.account_filter, 0, 2)
            self.filters_layout.addWidget(self.status_filter, 0, 3)
        self.filters_layout.setColumnStretch(0, 3 if not self._compact else 1)
        for column in range(1, 4):
            self.filters_layout.setColumnStretch(column, 1 if not self._compact else 0)

    def _reflow_metrics(self) -> None:
        for widget in self._metric_widgets:
            self.metrics_layout.removeWidget(widget)
        columns = 2 if self._compact else min(4, max(1, len(self._metric_widgets)))
        for index, widget in enumerate(self._metric_widgets):
            self.metrics_layout.addWidget(widget, index // columns, index % columns)
        for column in range(4):
            self.metrics_layout.setColumnStretch(column, 1 if column < columns else 0)

    def _apply_responsive_layout(self) -> None:
        super()._apply_responsive_layout()
        self._reflow_filters()
        self._reflow_metrics()


class AccountsPage(_PageBase):
    """Threads account master-detail page with compact drill-in behaviour."""

    account_selected = pyqtSignal(str)
    add_account_requested = pyqtSignal()
    remove_account_requested = pyqtSignal(str)
    reconnect_account_requested = pyqtSignal(str)
    test_account_requested = pyqtSignal(str)
    manage_subscription_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("accountsPage", "Threads 계정")
        if parent is not None:
            self.setParent(parent)

        self.add_account_button = _button(
            "계정 추가",
            "accountsAddButton",
            "Threads 계정 추가",
        )
        self.add_account_button.setAccessibleDescription(
            "외부 브라우저에서 Threads 로그인 후 연결 상태를 확인합니다."
        )
        self.add_account_button.clicked.connect(self.add_account_requested.emit)
        self._add_page_header(
            "ACCOUNT HEALTH",
            "Threads 계정",
            "연결 상태와 세션 건강, 계정 한도를 관리합니다.",
            self.add_account_button,
        )

        self.master_detail = QWidget()
        self.master_detail_layout = QBoxLayout(
            QBoxLayout.Direction.LeftToRight, self.master_detail
        )
        self.master_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.master_detail_layout.setSpacing(Spacing.LG)

        self.master_card = _Card("accountsMasterCard", "연결된 Threads 계정 목록")
        self.master_card.setMinimumWidth(0)
        master_layout = QVBoxLayout(self.master_card)
        master_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        master_layout.setSpacing(Spacing.MD)
        master_header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        master_title = QLabel("연결 계정")
        master_title.setProperty("uiRole", "sectionTitle")
        self.limit_badge = QLabel("한도 정보 없음")
        _set_accessible(
            self.limit_badge, "accountsLimitBadge", "Threads 계정 한도 정보 없음"
        )
        self.limit_badge.setProperty("uiRole", "status")
        master_header.addWidget(master_title)
        master_header.addStretch(1)
        master_header.addWidget(self.limit_badge)
        master_layout.addLayout(master_header)
        self.account_list = QListWidget()
        _set_accessible(self.account_list, "accountsList", "연결된 Threads 계정")
        self.account_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.account_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.account_list.setMinimumHeight(220)
        self.account_list.currentItemChanged.connect(self._select_list_item)
        master_layout.addWidget(self.account_list, 1)
        self.accounts_empty = _EmptyState(
            "accountsListEmpty",
            "연결된 계정이 없습니다",
            "계정 추가를 선택하면 외부 브라우저에서 안전하게 연결합니다.",
        )
        master_layout.addWidget(self.accounts_empty)
        self.plan_label = QLabel("요금제 및 계정 한도 데이터가 없습니다.")
        _set_accessible(self.plan_label, "accountsPlanLabel", "요금제와 계정 한도")
        self.plan_label.setProperty("uiRole", "muted")
        self.plan_label.setWordWrap(True)
        master_layout.addWidget(self.plan_label)
        self.plan_button = _button(
            "요금제 보기",
            "accountsPlanButton",
            "계정 한도 요금제 보기",
            kind="secondary",
        )
        self.plan_button.clicked.connect(self.manage_subscription_requested.emit)
        master_layout.addWidget(self.plan_button)

        self.detail_card = _Card("accountsDetailCard", "선택한 Threads 계정 상세")
        self.detail_card.setMinimumWidth(0)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.XL)
        detail_layout.setSpacing(Spacing.MD)
        self.back_button = _button(
            "계정 목록으로",
            "accountsBackButton",
            "Threads 계정 목록으로 돌아가기",
            kind="secondary",
        )
        self.back_button.clicked.connect(self._show_master)
        detail_layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.detail_title = QLabel("계정을 선택하세요")
        _set_accessible(self.detail_title, "accountsDetailTitle", "선택한 계정")
        self.detail_title.setProperty("uiRole", "pageTitle")
        self.detail_title.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)
        self.detail_status = QLabel("상태 정보 없음")
        _set_accessible(self.detail_status, "accountsDetailStatus", "선택한 계정 상태")
        self.detail_status.setProperty("uiRole", "status")
        detail_layout.addWidget(self.detail_status, 0, Qt.AlignmentFlag.AlignLeft)
        self.detail_description = QLabel(
            "목록에서 계정을 선택하면 사용자 이름과 세션 상태를 확인할 수 있습니다."
        )
        _set_accessible(
            self.detail_description, "accountsDetailDescription", "계정 상세 안내"
        )
        self.detail_description.setProperty("uiRole", "muted")
        self.detail_description.setWordWrap(True)
        detail_layout.addWidget(self.detail_description)

        self.detail_fields = QWidget()
        fields_layout = QGridLayout(self.detail_fields)
        fields_layout.setContentsMargins(0, Spacing.SM, 0, Spacing.SM)
        fields_layout.setHorizontalSpacing(Spacing.XL)
        fields_layout.setVerticalSpacing(Spacing.MD)
        field_specs = [
            ("display_name", "계정 이름"),
            ("username", "Threads 사용자 이름"),
            ("last_checked", "마지막 확인"),
            ("session_status", "로그인 세션"),
            ("next_check", "다음 자동 확인"),
        ]
        self.detail_values: dict[str, QLabel] = {}
        for row, (key, label) in enumerate(field_specs):
            label_widget = QLabel(label)
            label_widget.setProperty("uiRole", "muted")
            value_widget = QLabel("—")
            _set_accessible(
                value_widget, f"accountsDetail{key.title().replace('_', '')}", label
            )
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            fields_layout.addWidget(label_widget, row, 0)
            fields_layout.addWidget(value_widget, row, 1)
            self.detail_values[key] = value_widget
        fields_layout.setColumnStretch(1, 1)
        detail_layout.addWidget(self.detail_fields)

        self.account_action_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.account_action_layout.setSpacing(Spacing.SM)
        self.reconnect_button = _button(
            "브라우저에서 다시 로그인",
            "accountsReconnectButton",
            "선택한 Threads 계정 다시 로그인",
        )
        self.test_button = _button(
            "연결 테스트",
            "accountsTestButton",
            "선택한 Threads 계정 연결 테스트",
            kind="secondary",
        )
        self.reconnect_button.clicked.connect(self._request_reconnect)
        self.test_button.clicked.connect(self._request_test)
        self.account_action_layout.addWidget(self.reconnect_button)
        self.account_action_layout.addWidget(self.test_button)
        detail_layout.addLayout(self.account_action_layout)
        detail_layout.addStretch(1)
        danger_title = QLabel("위험 구역")
        danger_title.setStyleSheet(f"color: {Colors.ERROR}; {Typography.TITLE_SM}")
        detail_layout.addWidget(danger_title)
        danger_description = QLabel(
            "계정을 삭제하면 저장된 세션 연결이 해제됩니다. 삭제 영향은 실행 전에 다시 확인해야 합니다."
        )
        danger_description.setProperty("uiRole", "muted")
        danger_description.setWordWrap(True)
        detail_layout.addWidget(danger_description)
        self.remove_button = _button(
            "계정 삭제",
            "accountsRemoveButton",
            "선택한 Threads 계정 삭제",
            kind="danger",
        )
        self.remove_button.clicked.connect(self._request_remove)
        detail_layout.addWidget(self.remove_button, 0, Qt.AlignmentFlag.AlignRight)

        self.master_detail_layout.addWidget(self.master_card, 1)
        self.master_detail_layout.addWidget(self.detail_card, 2)
        self.body.addWidget(self.master_detail, 1)
        self.body.addStretch(1)

        self._accounts: dict[str, Any] = {}
        self._selected_id: str | None = None
        self.render_accounts()

    def render_accounts(
        self,
        accounts: Sequence[Any] | None = None,
        selected_id: str | None = None,
        limit: Any | None = None,
        plan_name: str | None = None,
    ) -> None:
        rows = list(accounts or [])
        self._accounts = {
            _identifier(account, str(index)): account
            for index, account in enumerate(rows)
        }
        self.account_list.blockSignals(True)
        self.account_list.clear()
        for index, account in enumerate(rows):
            account_id = _identifier(account, str(index))
            name = _text(
                _read(account, "display_name", _read(account, "name", account_id)),
                account_id,
            )
            username = _text(_read(account, "username", ""))
            status = _text(_read(account, "status", "상태 미확인"), "상태 미확인")
            line = f"{name}\n{username} · {status}" if username else f"{name}\n{status}"
            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, account_id)
            item.setToolTip(f"{name}\n{username}\n{status}".strip())
            item.setForeground(QColor(_status_color(account)))
            item.setSizeHint(QSize(0, 64))
            self.account_list.addItem(item)
            if selected_id is not None and account_id == str(selected_id):
                self.account_list.setCurrentItem(item)
        self.account_list.blockSignals(False)

        self.accounts_empty.setVisible(not rows)
        self.account_list.setVisible(bool(rows))
        used = len(rows)
        if limit not in (None, ""):
            self.limit_badge.setText(f"{used} / {limit}개")
            self.limit_badge.setAccessibleName(f"Threads 계정 {used}개, 한도 {limit}개")
        else:
            self.limit_badge.setText(f"{used}개 연결" if rows else "한도 정보 없음")
        self.plan_label.setText(
            f"현재 요금제: {plan_name}"
            if plan_name
            else "요금제 및 계정 한도 데이터가 없습니다."
        )

        chosen = str(selected_id) if selected_id is not None else None
        if chosen in self._accounts:
            self._render_detail(chosen)
        elif self._selected_id in self._accounts:
            self._render_detail(self._selected_id or "")
        else:
            self._clear_detail()
        self._apply_account_visibility()

    def _select_list_item(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        account_id = _text(current.data(Qt.ItemDataRole.UserRole))
        if account_id not in self._accounts:
            return
        self._render_detail(account_id)
        self.account_selected.emit(account_id)
        self._apply_account_visibility()

    def _render_detail(self, account_id: str) -> None:
        account = self._accounts.get(account_id)
        if account is None:
            self._clear_detail()
            return
        self._selected_id = account_id
        display_name = _text(
            _read(account, "display_name", _read(account, "name", account_id)),
            account_id,
        )
        status = _text(_read(account, "status", "상태 미확인"), "상태 미확인")
        self.detail_title.setText(display_name)
        self.detail_title.setAccessibleName(f"선택한 계정 {display_name}")
        self.detail_status.setText(status)
        self.detail_status.setStyleSheet(f"color: {_status_color(account)};")
        self.detail_description.setText(
            _text(
                _read(
                    account,
                    "description",
                    "Threads 게시 연결과 브라우저 세션 상태를 확인합니다.",
                )
            )
        )
        values = {
            "display_name": display_name,
            "username": _text(_read(account, "username", "—"), "—"),
            "last_checked": _text(_read(account, "last_checked", "—"), "—"),
            "session_status": _text(_read(account, "session_status", "—"), "—"),
            "next_check": _text(_read(account, "next_check", "—"), "—"),
        }
        for key, value in values.items():
            self.detail_values[key].setText(value)
            self.detail_values[key].setToolTip(value)
        for button in (self.remove_button, self.reconnect_button, self.test_button):
            button.setEnabled(True)

    def _clear_detail(self) -> None:
        self._selected_id = None
        self.detail_title.setText("계정을 선택하세요")
        self.detail_status.setText("상태 정보 없음")
        self.detail_status.setStyleSheet("")
        self.detail_description.setText(
            "목록에서 계정을 선택하면 사용자 이름과 세션 상태를 확인할 수 있습니다."
        )
        for value in self.detail_values.values():
            value.setText("—")
        for button in (self.remove_button, self.reconnect_button, self.test_button):
            button.setEnabled(False)

    def _request_remove(self) -> None:
        if self._selected_id:
            self.remove_account_requested.emit(self._selected_id)

    def _request_reconnect(self) -> None:
        if self._selected_id:
            self.reconnect_account_requested.emit(self._selected_id)

    def _request_test(self) -> None:
        if self._selected_id:
            self.test_account_requested.emit(self._selected_id)

    def _show_master(self) -> None:
        if self._compact:
            self.master_card.show()
            self.detail_card.hide()

    def _apply_account_visibility(self) -> None:
        if not self._compact:
            self.master_card.show()
            self.detail_card.show()
            return
        if self._selected_id:
            self.master_card.hide()
            self.detail_card.show()
        else:
            self.master_card.show()
            self.detail_card.hide()

    def _apply_responsive_layout(self) -> None:
        super()._apply_responsive_layout()
        self.master_detail_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self._compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.account_action_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self._compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.back_button.setVisible(self._compact)
        self._apply_account_visibility()


class SubscriptionPage(_PageBase):
    """Current plan, comparison and support surface."""

    manage_subscription_requested = pyqtSignal()
    support_requested = pyqtSignal()
    plan_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("subscriptionPage", "구독 및 지원")
        if parent is not None:
            self.setParent(parent)

        self.manage_button = _button(
            "구독 관리",
            "subscriptionManageButton",
            "현재 구독 관리",
            kind="secondary",
        )
        self.manage_button.clicked.connect(self.manage_subscription_requested.emit)
        self._add_page_header(
            "PLAN & SUPPORT",
            "구독 · 지원",
            "현재 요금제와 작업량을 확인하고 결제 또는 지원으로 이동합니다.",
            self.manage_button,
        )

        self.current_plan_card = _Card(
            "subscriptionCurrentPlanCard", "현재 요금제", dark=True
        )
        current_layout = QGridLayout(self.current_plan_card)
        current_layout.setContentsMargins(
            Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL
        )
        current_layout.setHorizontalSpacing(Spacing.XL)
        current_layout.setVerticalSpacing(Spacing.SM)
        self.current_plan_label = QLabel("현재 요금제")
        self.current_plan_label.setProperty("uiRole", "inverseBody")
        self.current_plan_name = QLabel("구독 정보가 없습니다")
        _set_accessible(
            self.current_plan_name, "subscriptionCurrentPlanName", "현재 요금제"
        )
        self.current_plan_name.setProperty("uiRole", "inverseTitle")
        self.current_plan_name.setWordWrap(True)
        self.current_plan_detail = QLabel(
            "구독 데이터가 연결되면 이용 범위가 표시됩니다."
        )
        self.current_plan_detail.setProperty("uiRole", "inverseBody")
        self.current_plan_detail.setWordWrap(True)
        self.usage_value = QLabel("작업량 정보 없음")
        _set_accessible(
            self.usage_value, "subscriptionUsageValue", "남은 작업량 정보 없음"
        )
        self.usage_value.setProperty("uiRole", "inverseTitle")
        self.renewal_value = QLabel("갱신일 정보 없음")
        _set_accessible(
            self.renewal_value, "subscriptionRenewalValue", "갱신일 정보 없음"
        )
        self.renewal_value.setProperty("uiRole", "inverseBody")
        current_layout.addWidget(self.current_plan_label, 0, 0)
        current_layout.addWidget(self.current_plan_name, 1, 0)
        current_layout.addWidget(self.current_plan_detail, 2, 0)
        current_layout.addWidget(self.usage_value, 0, 1, 2, 1)
        current_layout.addWidget(self.renewal_value, 2, 1)
        current_layout.setColumnStretch(0, 2)
        current_layout.setColumnStretch(1, 1)
        self.current_plan_layout = current_layout
        self.body.addWidget(self.current_plan_card)

        self.subscription_pair = QWidget()
        self.subscription_pair_layout = QBoxLayout(
            QBoxLayout.Direction.LeftToRight, self.subscription_pair
        )
        self.subscription_pair_layout.setContentsMargins(0, 0, 0, 0)
        self.subscription_pair_layout.setSpacing(Spacing.LG)

        self.plans_card = _Card("subscriptionPlansCard", "요금제 비교")
        plans_layout = QVBoxLayout(self.plans_card)
        plans_layout.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.XL)
        plans_layout.setSpacing(Spacing.MD)
        plans_title = QLabel("요금제 비교")
        plans_title.setProperty("uiRole", "sectionTitle")
        plans_layout.addWidget(plans_title)
        self.plans_host = QWidget()
        self.plans_grid = QGridLayout(self.plans_host)
        self.plans_grid.setContentsMargins(0, 0, 0, 0)
        self.plans_grid.setSpacing(Spacing.MD)
        plans_layout.addWidget(self.plans_host)
        self._plan_widgets: list[QWidget] = []

        self.side_stack = QWidget()
        self.side_stack_layout = QVBoxLayout(self.side_stack)
        self.side_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.side_stack_layout.setSpacing(Spacing.LG)
        support_card = _Card("subscriptionSupportCard", "고객 지원")
        support_layout = QVBoxLayout(support_card)
        support_layout.setContentsMargins(
            Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG
        )
        support_layout.setSpacing(Spacing.MD)
        support_title = QLabel("지원")
        support_title.setProperty("uiRole", "sectionTitle")
        support_description = QLabel(
            "자동화 또는 결제에 문제가 있으면 지원팀에 문의하세요."
        )
        support_description.setProperty("uiRole", "muted")
        support_description.setWordWrap(True)
        self.support_response = QLabel("응답 시간 정보 없음")
        self.support_response.setProperty("uiRole", "muted")
        self.support_button = _button(
            "지원 문의",
            "subscriptionSupportButton",
            "고객 지원 문의",
            kind="secondary",
        )
        self.support_button.clicked.connect(self.support_requested.emit)
        support_layout.addWidget(support_title)
        support_layout.addWidget(support_description)
        support_layout.addWidget(self.support_button)
        support_layout.addWidget(self.support_response)

        management_card = _Card("subscriptionManagementCard", "구독 결제 정보")
        management_layout = QVBoxLayout(management_card)
        management_layout.setContentsMargins(
            Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG
        )
        management_layout.setSpacing(Spacing.MD)
        management_title = QLabel("구독 관리")
        management_title.setProperty("uiRole", "sectionTitle")
        self.billing_date = QLabel("다음 결제일 정보 없음")
        self.billing_date.setProperty("uiRole", "muted")
        self.payment_method = QLabel("결제 수단 정보 없음")
        self.payment_method.setProperty("uiRole", "muted")
        danger_note = QLabel(
            "정기결제 해지와 환불 안내는 구독 관리에서 확인할 수 있습니다."
        )
        danger_note.setWordWrap(True)
        danger_note.setStyleSheet(f"color: {Colors.ERROR}; {Typography.CAPTION}")
        management_action = _button(
            "결제 정보 관리",
            "subscriptionBillingButton",
            "결제 정보와 정기결제 관리",
            kind="secondary",
        )
        management_action.clicked.connect(self.manage_subscription_requested.emit)
        management_layout.addWidget(management_title)
        management_layout.addWidget(self.billing_date)
        management_layout.addWidget(self.payment_method)
        management_layout.addWidget(danger_note)
        management_layout.addWidget(management_action)

        self.side_stack_layout.addWidget(support_card)
        self.side_stack_layout.addWidget(management_card)
        self.subscription_pair_layout.addWidget(self.plans_card, 2)
        self.subscription_pair_layout.addWidget(self.side_stack, 1)
        self.body.addWidget(self.subscription_pair)
        self.body.addStretch(1)

        self.render_subscription()

    def render_subscription(
        self,
        subscription: Mapping[str, Any] | Any | None = None,
        plans: Sequence[Any] | None = None,
    ) -> None:
        if subscription is None:
            self.current_plan_name.setText("구독 정보가 없습니다")
            self.current_plan_detail.setText(
                "구독 데이터가 연결되면 이용 범위가 표시됩니다."
            )
            self.usage_value.setText("작업량 정보 없음")
            self.renewal_value.setText("갱신일 정보 없음")
            self.billing_date.setText("다음 결제일 정보 없음")
            self.payment_method.setText("결제 수단 정보 없음")
            self.support_response.setText("응답 시간 정보 없음")
        else:
            self.current_plan_name.setText(
                _text(
                    _read(
                        subscription,
                        "plan_name",
                        _read(subscription, "name", "구독 정보 없음"),
                    )
                )
            )
            self.current_plan_detail.setText(
                _text(
                    _read(
                        subscription, "detail", _read(subscription, "description", "")
                    )
                )
            )
            usage = _text(
                _read(
                    subscription,
                    "usage_label",
                    _read(subscription, "remaining_label", ""),
                )
            )
            if not usage:
                used = _read(subscription, "usage_used", None)
                limit = _read(subscription, "usage_limit", None)
                usage = (
                    f"{used} / {limit}회 사용"
                    if used is not None and limit is not None
                    else "작업량 정보 없음"
                )
            self.usage_value.setText(usage)
            renewal = _text(_read(subscription, "renewal_date", ""))
            self.renewal_value.setText(
                f"{renewal} 갱신" if renewal else "갱신일 정보 없음"
            )
            billing = _text(_read(subscription, "billing_date", renewal))
            self.billing_date.setText(
                f"다음 결제일 {billing}" if billing else "다음 결제일 정보 없음"
            )
            payment = _text(_read(subscription, "payment_method", ""))
            self.payment_method.setText(
                f"결제 수단 {payment}" if payment else "결제 수단 정보 없음"
            )
            response = _text(_read(subscription, "support_response_time", ""))
            self.support_response.setText(response or "응답 시간 정보 없음")

        _clear_layout(self.plans_grid)
        self._plan_widgets = []
        plan_rows = list(plans or [])
        if not plan_rows:
            self._plan_widgets = [
                _EmptyState(
                    "subscriptionPlansEmpty",
                    "비교할 요금제가 없습니다",
                    "요금제 데이터가 전달되면 혜택과 현재 이용 상태가 표시됩니다.",
                )
            ]
        else:
            self._plan_widgets = [
                self._create_plan_card(plan, index)
                for index, plan in enumerate(plan_rows)
            ]
        self._reflow_plans()

    def _create_plan_card(self, plan: Any, index: int) -> QWidget:
        plan_id = _identifier(plan, str(index))
        name = _text(_read(plan, "name", "요금제"), "요금제")
        current = bool(_read(plan, "current", False))
        card = _Card(f"subscriptionPlanCard{index}", f"{name} 요금제")
        if current:
            card.setStyleSheet(
                f"QFrame#{card.objectName()} {{ background: {Colors.SKY}; border: 2px solid {Colors.ACCENT}; border-radius: {Radius.HERO}; }}"
            )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.SM)
        title = QLabel(name)
        title.setProperty("uiRole", "sectionTitle")
        tagline = QLabel(_text(_read(plan, "tagline", _read(plan, "description", ""))))
        tagline.setProperty("uiRole", "muted")
        tagline.setWordWrap(True)
        price = QLabel(_text(_read(plan, "price", "가격 정보 없음"), "가격 정보 없음"))
        price.setProperty("uiRole", "metricValue")
        layout.addWidget(title)
        layout.addWidget(tagline)
        layout.addWidget(price)
        features = list(_read(plan, "features", []) or [])
        if features:
            for feature in features:
                feature_label = QLabel(f"✓  {_text(feature)}")
                feature_label.setWordWrap(True)
                feature_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
                layout.addWidget(feature_label)
        else:
            no_features = QLabel("혜택 정보가 없습니다.")
            no_features.setProperty("uiRole", "muted")
            layout.addWidget(no_features)
        layout.addStretch(1)
        action_text = _text(
            _read(plan, "action_label", "현재 이용 중" if current else "요금제 선택")
        )
        action = _button(
            action_text,
            f"subscriptionPlanAction{index}",
            f"{name} {action_text}",
            kind="secondary" if current else "primary",
        )
        action.setEnabled(not current)
        action.clicked.connect(
            lambda _checked=False, value=plan_id: self.plan_selected.emit(value)
        )
        layout.addWidget(action)
        return card

    def _reflow_plans(self) -> None:
        for widget in self._plan_widgets:
            self.plans_grid.removeWidget(widget)
        columns = 1 if self._compact else min(2, max(1, len(self._plan_widgets)))
        for index, widget in enumerate(self._plan_widgets):
            self.plans_grid.addWidget(widget, index // columns, index % columns)
        for column in range(2):
            self.plans_grid.setColumnStretch(column, 1 if column < columns else 0)

    def _apply_responsive_layout(self) -> None:
        super()._apply_responsive_layout()
        self.subscription_pair_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self._compact
            else QBoxLayout.Direction.LeftToRight
        )
        for widget in (
            self.current_plan_label,
            self.current_plan_name,
            self.current_plan_detail,
            self.usage_value,
            self.renewal_value,
        ):
            self.current_plan_layout.removeWidget(widget)
        if self._compact:
            self.current_plan_layout.addWidget(self.current_plan_label, 0, 0)
            self.current_plan_layout.addWidget(self.current_plan_name, 1, 0)
            self.current_plan_layout.addWidget(self.current_plan_detail, 2, 0)
            self.current_plan_layout.addWidget(self.usage_value, 3, 0)
            self.current_plan_layout.addWidget(self.renewal_value, 4, 0)
            self.current_plan_layout.setColumnStretch(0, 1)
            self.current_plan_layout.setColumnStretch(1, 0)
        else:
            self.current_plan_layout.addWidget(self.current_plan_label, 0, 0)
            self.current_plan_layout.addWidget(self.current_plan_name, 1, 0)
            self.current_plan_layout.addWidget(self.current_plan_detail, 2, 0)
            self.current_plan_layout.addWidget(self.usage_value, 0, 1, 2, 1)
            self.current_plan_layout.addWidget(self.renewal_value, 2, 1)
            self.current_plan_layout.setColumnStretch(0, 2)
            self.current_plan_layout.setColumnStretch(1, 1)
        self._reflow_plans()


def _normalise_metrics(metrics: Mapping[str, Any] | Sequence[Any] | None) -> list[Any]:
    if not metrics:
        return []
    if isinstance(metrics, Mapping):
        result: list[Any] = []
        for label, value in metrics.items():
            if isinstance(value, Mapping):
                item = dict(value)
                item.setdefault("label", label)
                result.append(item)
            else:
                result.append({"label": label, "value": value})
        return result
    return list(metrics)


def _filter_combo(object_name: str, accessible_name: str) -> QComboBox:
    combo = QComboBox()
    _set_accessible(combo, object_name, accessible_name)
    combo.setMinimumHeight(ControlHeight.INPUT)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(10)
    return combo


def _set_combo_items(combo: QComboBox, values: Sequence[str] | None) -> None:
    current = combo.currentData() or combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    for value in values or []:
        combo.addItem(_text(value), value)
    if current:
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)
    combo.blockSignals(False)


def _make_table(
    object_name: str, accessible_name: str, headers: Sequence[str]
) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    _set_accessible(table, object_name, accessible_name)
    table.setHorizontalHeaderLabels(list(headers))
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setMinimumSectionSize(34)
    table.horizontalHeader().setStretchLastSection(True)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setMinimumWidth(0)
    return table


def _set_table_data(
    table: QTableWidget, rows: Sequence[Any], keys: Sequence[str]
) -> None:
    table.setUpdatesEnabled(False)
    try:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            table.setRowHeight(row_index, 48)
            for column, key in enumerate(keys):
                value = _text(_read(row, key, ""))
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.ItemDataRole.UserRole, _identifier(row, str(row_index)))
                if key in ("status", "result"):
                    item.setForeground(QColor(_status_color(row)))
                table.setItem(row_index, column, item)
    finally:
        table.setUpdatesEnabled(True)


__all__ = [
    "AccountsPage",
    "DashboardPage",
    "HistoryPage",
    "SubscriptionPage",
]
