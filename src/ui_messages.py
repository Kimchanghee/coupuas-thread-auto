# -*- coding: utf-8 -*-
"""Korean-localized message box helpers for PyQt6."""
from PyQt6.QtWidgets import QMessageBox


def _build_message_box(parent, title: str, message: str, icon: QMessageBox.Icon) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(message)
    return box


def show_info(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, QMessageBox.Icon.Information)
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def show_warning(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, QMessageBox.Icon.Warning)
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def show_error(parent, title: str, message: str) -> None:
    box = _build_message_box(parent, title, message, QMessageBox.Icon.Critical)
    ok_btn = box.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()


def ask_yes_no(parent, title: str, message: str, default_yes: bool = True) -> bool:
    box = _build_message_box(parent, title, message, QMessageBox.Icon.Question)
    yes_btn = box.addButton("예", QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton("아니오", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(yes_btn if default_yes else no_btn)
    box.exec()
    return box.clickedButton() is yes_btn
