"""Reusable Editorial Control Room widgets for the desktop interface.

These components intentionally expose layouts rather than hiding page content
behind fixed geometry.  They can therefore be placed in responsive Qt layouts
at the 1360, 900 and 760 DIP breakpoints defined by the UI blueprint.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.theme import Colors, ControlHeight, Radius, Spacing


class BrandMark(QWidget):
    """Vector brand mark that remains crisp without relying on font glyphs."""

    def __init__(self, parent=None, *, background=None, foreground=None):
        super().__init__(parent)
        self._background = QColor(background or Colors.SIGNAL_TEAL)
        self._foreground = QColor(foreground or Colors.PAPER)
        self.setAccessibleName("Thread Auto")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = max(6.0, min(rect.width(), rect.height()) * 0.28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background)
        painter.drawRoundedRect(rect, radius, radius)

        width = float(rect.width())
        height = float(rect.height())
        left = float(rect.left())
        top = float(rect.top())
        bolt = QPolygonF(
            [
                QPointF(left + width * 0.57, top + height * 0.14),
                QPointF(left + width * 0.29, top + height * 0.53),
                QPointF(left + width * 0.48, top + height * 0.53),
                QPointF(left + width * 0.39, top + height * 0.86),
                QPointF(left + width * 0.72, top + height * 0.42),
                QPointF(left + width * 0.53, top + height * 0.42),
            ]
        )
        painter.setBrush(self._foreground)
        painter.drawPolygon(bolt)


class HelpButton(QPushButton):
    """Keyboard-accessible button that toggles nearby contextual guidance."""

    helpToggled = pyqtSignal(bool)

    def __init__(self, accessible_name: str, parent=None):
        super().__init__("?", parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(32, 32)
        self.setAccessibleName(accessible_name)
        self.setAccessibleDescription("현재 화면 안에서 도움말을 펼치거나 접습니다.")
        self.setToolTip(accessible_name)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PAPER}; color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 16px; font-size: 10pt;"
            " font-weight: 700; padding: 0; min-height: 0; }"
            f"QPushButton:hover, QPushButton:focus {{ color: {Colors.TEXT_PRIMARY};"
            f" border: 2px solid {Colors.ACCENT}; background-color: {Colors.SKY}; }}"
            f"QPushButton:checked {{ color: {Colors.TEXT_BRIGHT}; background-color: {Colors.ACCENT};"
            f" border-color: {Colors.ACCENT}; }}"
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED};"
            f" background-color: {Colors.BG_ELEVATED}; border-color: {Colors.BORDER}; }}"
        )
        self.toggled.connect(self.helpToggled.emit)


class InlineHelpPanel(QFrame):
    """Compact in-page guidance panel; it never opens a secondary window."""

    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setObjectName("inlineHelpPanel")
        self.setStyleSheet(
            f"QFrame#inlineHelpPanel {{ background-color: {Colors.SKY};"
            f" border: 1px solid {Colors.ACCENT}; border-radius: {Radius.LG}; }}"
        )
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 10.5pt; font-weight: 700;"
            " background: transparent; border: none;"
        )
        self.body_label = QLabel(body, self)
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9.5pt; font-weight: 500;"
            " background: transparent; border: none;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label, 1)
        self.setAccessibleName(title)
        self.setAccessibleDescription(body)

    def set_content(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.setAccessibleName(title)
        self.setAccessibleDescription(body)


class Card(QFrame):
    """Paper surface with blueprint spacing and a responsive content layout."""

    def __init__(
        self,
        parent=None,
        *,
        accessible_name: str = "콘텐츠 카드",
        compact: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("editorialCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(
            f"QFrame#editorialCard {{ background-color: {Colors.PAPER};"
            f" border: 1px solid {Colors.LINE}; border-radius: {Radius.CARD}; }}"
            f"QFrame#editorialCard:disabled {{ background-color: {Colors.BG_ELEVATED};"
            f" border-color: {Colors.BORDER_SUBTLE}; }}"
        )
        self.content_layout = QVBoxLayout(self)
        inset = Spacing.LG if compact else Spacing.XL
        self.content_layout.setContentsMargins(inset, inset, inset, inset)
        self.content_layout.setSpacing(Spacing.LG)
        self.setAccessibleName(accessible_name)

    @property
    def body_layout(self) -> QVBoxLayout:
        """Alias used by section-like consumers."""

        return self.content_layout

    def set_compact(self, compact: bool) -> None:
        inset = Spacing.LG if compact else Spacing.XL
        self.content_layout.setContentsMargins(inset, inset, inset, inset)


class SectionCard(Card):
    """Card with a stable title region and an open body layout."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent=None,
        *,
        compact: bool = False,
    ):
        super().__init__(parent, accessible_name=title, compact=compact)

        self.title_label = QLabel(title, self)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"color: {Colors.INK}; font-size: 12.5pt; font-weight: 700;"
            " background: transparent; border: none;"
        )
        self.content_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet(
            f"color: {Colors.SLATE}; font-size: 10.5pt; font-weight: 400;"
            " background: transparent; border: none;"
        )
        self.subtitle_label.setVisible(bool(subtitle))
        self.content_layout.addWidget(self.subtitle_label)

        self.separator = QFrame(self)
        self.separator.setFixedHeight(1)
        self.separator.setStyleSheet(
            f"background-color: {Colors.LINE}; border: none;"
        )
        self.content_layout.addWidget(self.separator)

        self.body = QWidget(self)
        self.body.setStyleSheet("background: transparent; border: none;")
        self._body_layout = QVBoxLayout(self.body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(Spacing.MD)
        self.content_layout.addWidget(self.body)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._body_layout.addWidget(widget, stretch)

    def set_subtitle(self, subtitle: str) -> None:
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))
        self.setAccessibleDescription(subtitle)


class StatusPill(QLabel):
    """Compact, non-interactive status label with semantic colour states."""

    _STATES: ClassVar[dict[str, tuple[str, str, str]]] = {
        "neutral": (Colors.TEXT_SECONDARY, Colors.BG_ELEVATED, Colors.BORDER),
        "success": (Colors.EMERALD, "#E0F1EB", "#B7DBCE"),
        "running": (Colors.DEEP_TEAL, Colors.SKY, "#B7DDE0"),
        "warning": ("#8A5700", "#FFF0D2", "#F2D497"),
        "error": (Colors.CORAL, "#F9E0DE", "#EDBCB8"),
        "info": (Colors.DEEP_TEAL, Colors.SKY, "#B7DDE0"),
    }
    _ALIASES: ClassVar[dict[str, str]] = {
        "available": "success",
        "complete": "success",
        "completed": "success",
        "progress": "running",
        "pending": "warning",
        "retry": "warning",
        "invalid": "error",
        "needs_attention": "error",
    }

    def __init__(self, text: str = "대기", status: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(28)
        self.setMinimumWidth(88)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("상태")
        self._status = "neutral"
        self.set_status(status)

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str, text: str | None = None) -> None:
        normalized = self._ALIASES.get(str(status).lower(), str(status).lower())
        if normalized not in self._STATES:
            normalized = "neutral"
        self._status = normalized
        if text is not None:
            self.setText(text)
        foreground, background, border = self._STATES[normalized]
        self.setStyleSheet(
            f"QLabel {{ color: {foreground}; background-color: {background};"
            f" border: 1px solid {border}; border-radius: 14px; padding: 0 12px;"
            " font-size: 9.5pt; font-weight: 700; }"
            f"QLabel:disabled {{ color: {Colors.TEXT_MUTED};"
            f" background-color: {Colors.BG_ELEVATED}; border-color: {Colors.BORDER}; }}"
        )
        self.setProperty("status", normalized)
        self.setAccessibleDescription(f"{self.text()} ({normalized})")


class PipelineRail(QFrame):
    """Live four-stage automation rail with complete/current/error states."""

    progressChanged = pyqtSignal(int)
    DEFAULT_STAGES = ("링크 분석", "콘텐츠 생성", "Threads 업로드", "완료")

    def __init__(self, stages: Sequence[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("pipelineRail")
        self.setStyleSheet("QFrame#pipelineRail { background: transparent; border: none; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(84)
        self.setAccessibleName("자동화 진행 단계")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.SM)
        self._stage_nodes: list[QLabel] = []
        self._stage_labels: list[QLabel] = []
        self._connectors: list[QFrame] = []
        self._stages: tuple[str, ...] = ()
        self._current_index = 0
        self._error_index: int | None = None
        self.set_stages(stages or self.DEFAULT_STAGES)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def stages(self) -> tuple[str, ...]:
        return self._stages

    @property
    def stage_count(self) -> int:
        return len(self._stages)

    def set_stages(self, stages: Sequence[str]) -> None:
        labels = tuple(str(stage).strip() for stage in stages if str(stage).strip())
        if not labels:
            raise ValueError("PipelineRail requires at least one stage")

        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._stage_nodes.clear()
        self._stage_labels.clear()
        self._connectors.clear()
        self._stages = labels

        for index, stage in enumerate(labels):
            stage_widget = QWidget(self)
            stage_widget.setStyleSheet("background: transparent; border: none;")
            stage_widget.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
            )
            stage_layout = QVBoxLayout(stage_widget)
            stage_layout.setContentsMargins(0, 0, 0, 0)
            stage_layout.setSpacing(Spacing.SM)
            stage_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            node = QLabel(str(index + 1), stage_widget)
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node.setFixedSize(ControlHeight.ICON, ControlHeight.ICON)
            node.setAccessibleName(stage)
            stage_layout.addWidget(node, 0, Qt.AlignmentFlag.AlignHCenter)

            label = QLabel(stage, stage_widget)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            label.setWordWrap(True)
            label.setMinimumWidth(72)
            stage_layout.addWidget(label)

            self._layout.addWidget(stage_widget)
            self._stage_nodes.append(node)
            self._stage_labels.append(label)

            if index < len(labels) - 1:
                connector = QFrame(self)
                connector.setFixedHeight(2)
                connector.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                self._layout.addWidget(connector, 1, Qt.AlignmentFlag.AlignVCenter)
                self._connectors.append(connector)

        self._current_index = min(self._current_index, len(labels))
        self._apply_state()

    def set_current_stage(self, index: int, *, error: bool = False) -> None:
        self.set_progress(index, error_index=index if error else None)

    def set_step(self, index: int, status: str) -> None:
        """Apply a controller-friendly sequential status to one stage.

        Supported values include ``running``, ``complete``, ``error`` and
        ``pending`` plus their common aliases.  The rail is deliberately
        sequential: completing stage *n* advances the current position to
        *n + 1*.
        """

        stage = int(index)
        if not 0 <= stage < len(self._stages):
            raise IndexError(f"pipeline stage index out of range: {stage}")
        normalized = str(status).strip().lower().replace("-", "_")
        if normalized in {"running", "current", "active", "processing", "progress"}:
            self.set_progress(stage)
        elif normalized in {"complete", "completed", "success", "done"}:
            self.set_progress(max(self._current_index, stage + 1))
        elif normalized in {"error", "failed", "failure"}:
            self.set_progress(stage, error_index=stage)
        elif normalized in {"pending", "waiting", "idle", "reset"}:
            self.set_progress(max(0, stage - 1))
        else:
            raise ValueError(f"unsupported pipeline status: {status}")

    def reset(self) -> None:
        """Return the rail to the first stage and clear any error marker."""

        self.set_progress(0)

    def complete(self) -> None:
        """Mark every stage complete."""

        self.set_progress(len(self._stages))

    def set_progress(self, current_index: int, error_index: int | None = None) -> None:
        current = max(0, min(int(current_index), len(self._stages)))
        error_value = None
        if error_index is not None:
            candidate = int(error_index)
            if 0 <= candidate < len(self._stages):
                error_value = candidate
        changed = current != self._current_index
        self._current_index = current
        self._error_index = error_value
        self._apply_state()
        if changed:
            self.progressChanged.emit(current)

    def _apply_state(self) -> None:
        descriptions: list[str] = []
        for index, (node, label) in enumerate(zip(self._stage_nodes, self._stage_labels)):
            if index == self._error_index:
                state = "오류"
                foreground, background, border, marker = (
                    Colors.PAPER,
                    Colors.CORAL,
                    Colors.CORAL,
                    "!",
                )
                label_color = Colors.CORAL
            elif index < self._current_index:
                state = "완료"
                foreground, background, border, marker = (
                    Colors.PAPER,
                    Colors.EMERALD,
                    Colors.EMERALD,
                    "✓",
                )
                label_color = Colors.EMERALD
            elif index == self._current_index and self._current_index < len(self._stages):
                state = "진행 중"
                foreground, background, border, marker = (
                    Colors.PAPER,
                    Colors.SIGNAL_TEAL,
                    Colors.SIGNAL_TEAL,
                    str(index + 1),
                )
                label_color = Colors.DEEP_TEAL
            else:
                state = "대기"
                foreground, background, border, marker = (
                    Colors.SLATE,
                    Colors.BG_ELEVATED,
                    Colors.LINE,
                    str(index + 1),
                )
                label_color = Colors.SLATE

            node.setText(marker)
            node.setStyleSheet(
                f"QLabel {{ color: {foreground}; background-color: {background};"
                f" border: 2px solid {border}; border-radius: 20px;"
                " font-size: 11pt; font-weight: 800; }}"
            )
            node.setAccessibleDescription(state)
            label.setStyleSheet(
                f"color: {label_color}; background: transparent; border: none;"
                " font-size: 9pt; font-weight: 650;"
            )
            descriptions.append(f"{self._stages[index]} {state}")

        for index, connector in enumerate(self._connectors):
            color = Colors.EMERALD if index < self._current_index else Colors.LINE
            if self._error_index is not None and index == self._error_index - 1:
                color = Colors.CORAL
            connector.setStyleSheet(f"background-color: {color}; border: none;")

        self.setAccessibleDescription(", ".join(descriptions))
