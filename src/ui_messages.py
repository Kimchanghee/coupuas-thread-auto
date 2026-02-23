# -*- coding: utf-8 -*-
"""Themed popup alert helpers for PyQt6."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.app_icon import apply_window_icon
from src.theme import Colors, Radius, Typography


_KIND_META = {
    "info": {
        "tag": "안내",
        "icon": "i",
        "accent": Colors.INFO,
        "status": "정보 메시지",
    },
    "warning": {
        "tag": "주의",
        "icon": "!",
        "accent": Colors.WARNING,
        "status": "주의가 필요한 항목",
    },
    "error": {
        "tag": "오류",
        "icon": "x",
        "accent": Colors.ERROR,
        "status": "문제를 확인해주세요",
    },
    "question": {
        "tag": "확인",
        "icon": "?",
        "accent": Colors.ACCENT,
        "status": "선택이 필요합니다",
    },
}


class ThemedAlertDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        message: str,
        kind: str,
        ask_yes_no: bool = False,
        default_yes: bool = True,
    ) -> None:
        super().__init__(parent)
        self._answer = False
        self._ask_yes_no = bool(ask_yes_no)
        self._default_yes = bool(default_yes)
        self._meta = _KIND_META.get(kind, _KIND_META["info"])

        self.setWindowTitle(str(title or "?뚮┝"))
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(460)
        self.setMaximumWidth(620)
        apply_window_icon(self)

        self._build_ui(str(message or ""))

    def _build_ui(self, message: str) -> None:
        self.setStyleSheet(
            f"""
            QDialog#alertDialog {{
                background-color: #0C1423;
                border: 1px solid rgba(59, 123, 255, 0.28);
                border-radius: {Radius.LG};
            }}
            QFrame#alertHeader {{
                background-color: #172A4A;
                border-top-left-radius: {Radius.LG};
                border-top-right-radius: {Radius.LG};
                border: none;
                border-bottom: 1px solid rgba(59, 123, 255, 0.20);
            }}
            QFrame#statusStrip {{
                background-color: #1A2740;
                border: 1px solid rgba(59, 123, 255, 0.20);
                border-radius: {Radius.MD};
            }}
            QPushButton#primaryBtn {{
                background-color: #E31639;
                color: #FFFFFF;
                border: none;
                border-radius: {Radius.MD};
                min-width: 124px;
                min-height: 40px;
                font-size: 10pt;
                font-weight: 700;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: #C41231;
            }}
            QPushButton#primaryBtn:pressed {{
                background-color: #A01028;
            }}
            QPushButton#secondaryBtn {{
                background: #24344F;
                color: #D2DCEB;
                border: 1px solid rgba(114, 143, 183, 0.55);
                border-radius: {Radius.MD};
                min-width: 124px;
                min-height: 40px;
                font-size: 10pt;
                font-weight: 700;
            }}
            QPushButton#secondaryBtn:hover {{
                background: #2C3E5D;
                color: #FFFFFF;
                border-color: rgba(160, 186, 223, 0.75);
            }}
            """
        )
        self.setObjectName("alertDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("alertHeader")
        header.setFixedHeight(62)
        root.addWidget(header)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 10)
        header_layout.setSpacing(10)

        icon_badge = QLabel(self._meta["icon"], header)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(28, 28)
        icon_badge.setStyleSheet(
            f"background-color: {self._meta['accent']}22; color: {self._meta['accent']};"
            f"border: 1px solid {self._meta['accent']}55; border-radius: 14px;"
            "font-size: 11pt; font-weight: 700;"
        )
        header_layout.addWidget(icon_badge)

        title_label = QLabel(self.windowTitle(), header)
        title_label.setFont(QFont(Typography.FAMILY, 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        header_layout.addWidget(title_label, 1)

        if not self._ask_yes_no:
            tag_label = QLabel(self._meta["tag"], header)
            tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag_label.setFixedHeight(26)
            tag_label.setStyleSheet(
                f"background-color: {self._meta['accent']}22; color: {self._meta['accent']};"
                f"border: 1px solid {self._meta['accent']}55; border-radius: 13px;"
                "padding: 0 10px; font-size: 9pt; font-weight: 700;"
            )
            header_layout.addWidget(tag_label)

        body = QWidget(self)
        root.addWidget(body)

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 16, 18, 16)
        body_layout.setSpacing(12)

        message_label = QLabel(message, body)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        message_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent;"
            "font-size: 10pt; line-height: 1.5;"
        )
        body_layout.addWidget(message_label)

        if not self._ask_yes_no:
            status_strip = QFrame(body)
            status_strip.setObjectName("statusStrip")
            body_layout.addWidget(status_strip)

            status_layout = QHBoxLayout(status_strip)
            status_layout.setContentsMargins(10, 8, 10, 8)
            status_layout.setSpacing(8)

            dot = QLabel("", status_strip)
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background-color: {self._meta['accent']}; border-radius: 4px;"
            )
            status_layout.addWidget(dot)

            status_text = QLabel(self._meta["status"], status_strip)
            status_text.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;"
            )
            status_layout.addWidget(status_text, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 2, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch(1)

        if self._ask_yes_no:
            no_btn = QPushButton("아니요", body)
            no_btn.setObjectName("secondaryBtn")
            no_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            no_btn.clicked.connect(lambda: self._finish(False))
            button_row.addWidget(no_btn)

            yes_btn = QPushButton("예", body)
            yes_btn.setObjectName("primaryBtn")
            yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            yes_btn.clicked.connect(lambda: self._finish(True))
            button_row.addWidget(yes_btn)

            if self._default_yes:
                yes_btn.setDefault(True)
                yes_btn.setFocus()
            else:
                no_btn.setDefault(True)
                no_btn.setFocus()
        else:
            ok_btn = QPushButton("확인", body)
            ok_btn.setObjectName("primaryBtn")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_btn.clicked.connect(lambda: self._finish(True))
            ok_btn.setDefault(True)
            ok_btn.setFocus()
            button_row.addWidget(ok_btn)

        body_layout.addLayout(button_row)

    def _finish(self, answer: bool) -> None:
        self._answer = bool(answer)
        if self._answer:
            self.accept()
        else:
            self.reject()

    def ask(self) -> bool:
        self.exec()
        return self._answer


def _show(parent, title: str, message: str, kind: str) -> None:
    dialog = ThemedAlertDialog(
        parent,
        title=title,
        message=message,
        kind=kind,
        ask_yes_no=False,
    )
    dialog.exec()


def show_info(parent, title: str, message: str) -> None:
    _show(parent, title, message, "info")


def show_warning(parent, title: str, message: str) -> None:
    _show(parent, title, message, "warning")


def show_error(parent, title: str, message: str) -> None:
    _show(parent, title, message, "error")


def ask_yes_no(parent, title: str, message: str, default_yes: bool = True) -> bool:
    dialog = ThemedAlertDialog(
        parent,
        title=title,
        message=message,
        kind="question",
        ask_yes_no=True,
        default_yes=default_yes,
    )
    return dialog.ask()



