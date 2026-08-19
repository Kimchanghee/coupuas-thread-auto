# -*- coding: utf-8 -*-
"""Small reusable widgets for the Thread Auto desktop interface."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

from src.theme import Colors, Radius


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
            f"QPushButton {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 16px; font-size: 10pt;"
            " font-weight: 700; padding: 0; min-height: 0; }"
            f"QPushButton:hover, QPushButton:focus {{ color: {Colors.TEXT_PRIMARY};"
            f" border: 2px solid {Colors.ACCENT}; background-color: {Colors.ACCENT_SUBTLE}; }}"
            f"QPushButton:checked {{ color: {Colors.BG_DARK}; background-color: {Colors.ACCENT};"
            f" border-color: {Colors.ACCENT}; }}"
        )
        self.toggled.connect(self.helpToggled.emit)


class InlineHelpPanel(QFrame):
    """Compact in-page guidance panel; it never opens a secondary window."""

    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setObjectName("inlineHelpPanel")
        self.setStyleSheet(
            f"QFrame#inlineHelpPanel {{ background-color: {Colors.ACCENT_SUBTLE};"
            f" border: 1px solid {Colors.ACCENT}; border-radius: {Radius.LG}; }}"
        )
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            f"color: {Colors.ACCENT_LIGHT}; font-size: 10pt; font-weight: 700;"
            " background: transparent; border: none;"
        )
        self.body_label = QLabel(body, self)
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 500;"
            " background: transparent; border: none;"
        )
        self.setAccessibleName(title)
        self.setAccessibleDescription(body)

    def set_content(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.setAccessibleName(title)
        self.setAccessibleDescription(body)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(0, self.width() - 32)
        self.title_label.setGeometry(16, 10, width, 18)
        self.body_label.setGeometry(16, 31, width, max(20, self.height() - 39))
