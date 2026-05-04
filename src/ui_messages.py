# -*- coding: utf-8 -*-
"""Korean-localized message box helpers — Claude Dark theme.

QMessageBox의 OS 기본 아이콘(파란 'i', 노란 '!' 등)이 코랄 톤과 부딪쳐서
의도적으로 NoIcon을 사용하고, 메시지 텍스트의 첫 줄에 의미 라벨을 붙여
다이얼로그 본문이 깔끔히 코랄/차콜 톤으로만 통일되도록 한다.
"""
from PyQt6.QtWidgets import QMessageBox

from src.theme import Colors, Gradients, Radius


def _scope_style() -> str:
    """이 다이얼로그에만 적용되는 보강 스타일.

    global_stylesheet의 QMessageBox 룰을 한 번 더 명시해
    부모 위젯 컨텍스트에 상관없이 일관된 톤으로 그려지도록 한다.
    """
    return f"""
        QMessageBox {{
            background-color: {Colors.BG_CARD};
        }}
        QMessageBox QLabel {{
            color: {Colors.TEXT_PRIMARY};
            font-size: 11pt;
            min-width: 320px;
            padding: 4px 4px 8px 4px;
        }}
        QMessageBox QPushButton {{
            background: {Gradients.ACCENT_BTN};
            color: {Colors.TEXT_BRIGHT};
            border: none;
            border-radius: {Radius.MD};
            padding: 9px 26px;
            min-width: 88px;
            font-weight: 600;
        }}
        QMessageBox QPushButton:hover {{
            background: {Gradients.ACCENT_BTN_HOVER};
        }}
        QMessageBox QPushButton:pressed {{
            background: {Gradients.ACCENT_BTN_PRESSED};
        }}
    """


def _build_message_box(parent, title: str, message: str, kind: str) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.NoIcon)        # OS 아이콘 제거 (코랄 톤과 충돌 방지)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStyleSheet(_scope_style())
    box.setProperty("kind", kind)
    return box


def show_info(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, "info")
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def show_warning(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, "warning")
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def show_error(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, "error")
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def ask_yes_no(parent, title: str, message: str, default_yes: bool = True) -> bool:
    box = _build_message_box(parent, title, message, "question")
    yes_btn = box.addButton("예", QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton("아니오", QMessageBox.ButtonRole.NoRole)
    # "아니오"는 보조(고스트) 톤으로 강등해 시각적 위계 부여
    no_btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {Colors.TEXT_SECONDARY};"
        f" border: 1px solid {Colors.BORDER_LIGHT}; border-radius: {Radius.MD};"
        f" padding: 9px 26px; min-width: 88px; font-weight: 600; }}"
        f"QPushButton:hover {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY}; }}"
    )
    box.setDefaultButton(yes_btn if default_yes else no_btn)
    box.exec()
    return box.clickedButton() is yes_btn
