# -*- coding: utf-8 -*-
"""Login-to-main transition loading dialog."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.app_icon import apply_window_icon
from src.theme import Colors, Typography, Radius

logger = logging.getLogger(__name__)


class _ChecklistItem(QFrame):
    def __init__(self, title: str, description: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._title = title
        self._description = description
        self._build_ui()
        self.set_waiting()

    def _build_ui(self) -> None:
        self.setObjectName("loginLoadingChecklistItem")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"""
            QFrame#loginLoadingChecklistItem {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.icon_label = QLabel("○")
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(Typography.FAMILY, 10, QFont.Weight.Bold))
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        self.title_label = QLabel(self._title)
        self.title_label.setFont(QFont(Typography.FAMILY, 9, QFont.Weight.DemiBold))
        text_col.addWidget(self.title_label)

        self.desc_label = QLabel(self._description)
        self.desc_label.setFont(QFont(Typography.FAMILY, 8))
        text_col.addWidget(self.desc_label)

        layout.addLayout(text_col, 1)

        self.state_label = QLabel("대기")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.state_label.setFont(QFont(Typography.FAMILY, 8, QFont.Weight.DemiBold))
        self.state_label.setFixedWidth(56)
        layout.addWidget(self.state_label)

    def _set_state(self, icon: str, color: str, state_text: str) -> None:
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self.desc_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        self.state_label.setText(state_text)
        self.state_label.setStyleSheet(f"color: {color}; background: transparent;")

    def set_waiting(self) -> None:
        self._set_state("○", Colors.TEXT_MUTED, "대기")

    def set_checking(self) -> None:
        self._set_state("◔", Colors.ACCENT_LIGHT, "진행 중")

    def set_success(self) -> None:
        self._set_state("●", Colors.SUCCESS, "완료")


class LoginLoadingDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        apply_window_icon(self)
        self._on_finished: Optional[Callable[[], None]] = None
        self._step_index = 0
        self._steps = [
            ("auth", "로그인 인증 확인", "사용자 인증 정보를 확인하고 있습니다.", 220),
            ("session", "계정 세션 준비", "계정 세션과 권한 정보를 동기화하고 있습니다.", 240),
            ("workspace", "작업 환경 초기화", "메인 화면에서 사용할 작업 환경을 준비하고 있습니다.", 260),
            ("ready", "메인 화면 진입", "프로그램 화면을 최종 구성하고 있습니다.", 220),
        ]
        self._items: dict[str, _ChecklistItem] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setModal(True)
        self.setFixedSize(620, 440)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("loginLoadingDialog")
        self.setStyleSheet(
            f"""
            QDialog#loginLoadingDialog {{
                background: transparent;
                border: none;
            }}
            QFrame#loginLoadingCard {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.XL};
            }}
            QFrame#loginLoadingHeader {{
                border: none;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.ACCENT_DARK},
                    stop:1 {Colors.ACCENT_LIGHT}
                );
            }}
            QFrame#loginLoadingBody {{
                background: transparent;
                border: none;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("loginLoadingCard")
        card.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QFrame(card)
        header.setObjectName("loginLoadingHeader")
        header.setFrameShape(QFrame.Shape.NoFrame)
        header.setFixedHeight(96)
        card_layout.addWidget(header)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(4)

        title = QLabel("로그인 완료")
        title.setFont(QFont(Typography.FAMILY, 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent;")
        header_layout.addWidget(title)

        self.status_label = QLabel("메인 화면을 준비하고 있습니다...")
        self.status_label.setFont(QFont(Typography.FAMILY, 9))
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.92); background: transparent;")
        header_layout.addWidget(self.status_label)

        body = QFrame(card)
        body.setObjectName("loginLoadingBody")
        body.setFrameShape(QFrame.Shape.NoFrame)
        card_layout.addWidget(body, 1)

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(8)

        for key, title_text, desc, _ in self._steps:
            item = _ChecklistItem(title_text, desc, body)
            self._items[key] = item
            body_layout.addWidget(item)

        body_layout.addStretch(1)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(2, 6, 2, 2)
        progress_row.setSpacing(10)

        self.progress_bar = QProgressBar(body)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT_LIGHT});
                border-radius: 5px;
            }}
            """
        )
        progress_row.addWidget(self.progress_bar, 1)

        self.percent_label = QLabel("0%")
        self.percent_label.setFixedWidth(42)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.percent_label.setFont(QFont(Typography.FAMILY, 9, QFont.Weight.DemiBold))
        self.percent_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        progress_row.addWidget(self.percent_label)

        body_layout.addLayout(progress_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.parent():
            geo = self.parent().frameGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def start(self, on_finished: Optional[Callable[[], None]] = None) -> None:
        self._on_finished = on_finished
        self._step_index = 0
        self._set_progress(0)
        for item in self._items.values():
            item.set_waiting()
        QTimer.singleShot(80, self._advance_step)

    def _set_progress(self, value: int) -> None:
        bounded = max(0, min(100, int(value)))
        self.progress_bar.setValue(bounded)
        self.percent_label.setText(f"{bounded}%")

    def _advance_step(self) -> None:
        if self._step_index >= len(self._steps):
            self.status_label.setText("메인 화면을 여는 중입니다...")
            self._set_progress(100)
            if callable(self._on_finished):
                QTimer.singleShot(140, self._safe_finish)
            return

        key, _title, desc, duration = self._steps[self._step_index]
        item = self._items.get(key)
        if item:
            item.set_checking()
        self.status_label.setText(desc)
        QTimer.singleShot(duration, self._complete_step)

    def _complete_step(self) -> None:
        if self._step_index >= len(self._steps):
            return

        key, *_rest = self._steps[self._step_index]
        item = self._items.get(key)
        if item:
            item.set_success()

        self._step_index += 1
        self._set_progress((self._step_index * 100) // len(self._steps))
        QTimer.singleShot(100, self._advance_step)

    def _safe_finish(self) -> None:
        try:
            if callable(self._on_finished):
                self._on_finished()
        except Exception:
            logger.exception("로그인 후 메인 화면 전환 중 오류가 발생했습니다.")
