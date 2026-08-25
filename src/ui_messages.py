# -*- coding: utf-8 -*-
"""Themed popup alert helpers for PyQt6."""

from __future__ import annotations

import re

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


_INTERNAL_MESSAGE_MAP = {
    "process_error": "작업 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
    "quota_commit_failed": "게시 완료 후 작업량 동기화에 실패했습니다. 잠시 후 다시 확인해주세요.",
    "quota_commit_pending": "게시 완료 후 작업량 확인이 필요합니다.",
    "history_write_pending": "게시 기록 저장을 완료하지 못했습니다. 저장 공간을 확인한 뒤 다시 시도해주세요.",
    "quota_reservation_unsupported": "작업량을 안전하게 확인할 수 없어 작업을 중단했습니다.",
    "reservation_release_pending": "작업량 예약 해제를 확인하는 중입니다. 잠시 후 다시 시도해주세요.",
    "uncertain_external_post": "게시 결과를 확인하지 못했습니다. Threads에서 게시 여부를 확인해주세요.",
    "upload_failed": "게시글 업로드를 완료하지 못했습니다. Threads 로그인 상태를 확인해주세요.",
}
_TECHNICAL_MESSAGE_RE = re.compile(
    r"(?:traceback|\bexception\b|"
    r"\b(?:runtime|value|type|key|os|io|filenotfound|permission|connection|"
    r"timeout|request|http|ssl|jsondecode|playwright)error\b|"
    r"target page, context or browser has been closed|"
    r"browser has been closed|context has been closed|"
    r"\blocator\.[a-z]+\b|strict mode violation|"
    r"\bsqlstate\b|\bno module named\b|\bis not defined\b|"
    r"not attached to the dom|\bnet::err_[a-z_]+\b|"
    r"\bstack\s*trace\b|\bsyntaxerror\b|\bnameerror\b|"
    r"https?connectionpool|maximum retries|max retries exceeded|"
    r"provider unavailable|permission denied|exit code\s*\d+|"
    r"(?:[a-z]:\\|/)[^\n]*\.py\b|\bline\s+\d+\b)",
    re.IGNORECASE,
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HANGUL_RE = re.compile(r"[가-힣]")
_USER_SAFE_ASCII_TERMS = {
    "ai",
    "api",
    "chrome",
    "cli",
    "coupang",
    "gemini",
    "grok",
    "id",
    "mb",
    "oauth",
    "payapp",
    "pc",
    "qr",
    "threads",
    "url",
    "windows",
}


def user_friendly_message(value, fallback: str) -> str:
    """Return user-safe Korean copy while keeping raw details out of the UI."""
    fallback_text = str(fallback or "문제가 발생했습니다. 잠시 후 다시 시도해주세요.").strip()
    text = _CONTROL_CHAR_RE.sub("", str(value or "")).strip()
    if not text:
        return fallback_text

    normalized = re.sub(r"\s+", "_", text.lower()).strip("_.: ")
    mapped = _INTERNAL_MESSAGE_MAP.get(normalized)
    if mapped:
        return mapped

    if _TECHNICAL_MESSAGE_RE.search(text):
        return fallback_text

    # A server or subprocess may return an arbitrary English implementation
    # detail. Product/brand names inside otherwise Korean guidance are kept.
    if re.search(r"[A-Za-z]", text) and not _HANGUL_RE.search(text):
        return fallback_text
    ascii_terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text)
    }
    if ascii_terms.difference(_USER_SAFE_ASCII_TERMS):
        return fallback_text

    if len(text) > 600:
        text = text[:597].rstrip() + "..."
    return text


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

        self.setWindowTitle(str(title or "알림"))
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(460)
        self.setMaximumWidth(620)
        apply_window_icon(self)

        self._build_ui(str(message or ""))

    def _build_ui(self, message: str) -> None:
        # Claude Dark — warm charcoal + coral, kind별 accent는 _meta에서 동적 적용
        self.setStyleSheet(
            f"""
            QDialog#alertDialog {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG};
            }}
            QFrame#alertHeader {{
                background-color: {Colors.BG_HEADER};
                border-top-left-radius: {Radius.LG};
                border-top-right-radius: {Radius.LG};
                border: none;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
            QFrame#statusStrip {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
            }}
            QPushButton#primaryBtn {{
                background-color: {Colors.ACCENT};
                color: {Colors.TEXT_BRIGHT};
                border: none;
                border-radius: {Radius.MD};
                min-width: 124px;
                min-height: 44px;
                font-size: 10.5pt;
                font-weight: 700;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {Colors.ACCENT_LIGHT};
            }}
            QPushButton#primaryBtn:pressed {{
                background-color: {Colors.ACCENT_DARK};
            }}
            QPushButton#secondaryBtn {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: {Radius.MD};
                min-width: 124px;
                min-height: 44px;
                font-size: 10.5pt;
                font-weight: 700;
            }}
            QPushButton#secondaryBtn:hover {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border-color: {Colors.ACCENT};
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
        title_label.setFont(QFont(Typography.FAMILY, 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        header_layout.addWidget(title_label, 1)

        if not self._ask_yes_no:
            tag_label = QLabel(self._meta["tag"], header)
            tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag_label.setFixedHeight(26)
            tag_label.setStyleSheet(
                f"background-color: {self._meta['accent']}22; color: {self._meta['accent']};"
                f"border: 1px solid {self._meta['accent']}55; border-radius: 13px;"
                "padding: 0 10px; font-size: 9.5pt; font-weight: 700;"
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
            "font-size: 10.5pt; line-height: 1.5;"
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
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; font-size: 9.5pt;"
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
    display_message = str(message or "")
    if kind == "warning":
        display_message = user_friendly_message(
            display_message,
            "요청을 처리하지 못했습니다. 입력 내용과 연결 상태를 확인한 뒤 다시 시도해주세요.",
        )
    elif kind == "error":
        display_message = user_friendly_message(
            display_message,
            "문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )
    dialog = ThemedAlertDialog(
        parent,
        title=title,
        message=display_message,
        kind=kind,
        ask_yes_no=False,
    )
    try:
        dialog.exec()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()


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
    try:
        return dialog.ask()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()



