"""
Themed UI feedback components:
- ThemedPopup: replaces QMessageBox with a design-consistent dialog.
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from src.theme import Colors, Radius


class ThemedPopup(QDialog):
    KIND_INFO = "info"
    KIND_WARN = "warn"
    KIND_ERROR = "error"
    KIND_QUESTION = "question"

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        message: str,
        kind: str = KIND_INFO,
        ok_text: str = "확인",
        yes_text: str = "예",
        no_text: str = "아니오",
        show_cancel: bool = False,
    ):
        super().__init__(parent)
        self._kind = kind
        self._message = message
        self._result_yes = False

        self.setModal(True)
        self.setWindowTitle(title)
        # Frameless, theme-first popup (no OS chrome mismatch).
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._build_ui(title, message, ok_text, yes_text, no_text, show_cancel)

    def _kind_color(self) -> str:
        if self._kind == self.KIND_ERROR:
            return Colors.ERROR
        if self._kind == self.KIND_WARN:
            return Colors.WARNING
        if self._kind == self.KIND_QUESTION:
            return Colors.INFO
        return Colors.ACCENT

    def _build_ui(self, title: str, message: str, ok_text: str, yes_text: str, no_text: str, show_cancel: bool):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 14px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 160))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        # Header row: icon + title + close
        header = QHBoxLayout()
        header.setSpacing(12)

        color = self._kind_color()
        icon = QLabel("!", card)
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"""
            QLabel {{
                background-color: {color}22;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 17px;
                font-size: 14pt;
                font-weight: 800;
            }}
        """)
        header.addWidget(icon, 0)

        title_lbl = QLabel(title, card)
        title_lbl.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 12pt; font-weight: 800; letter-spacing: -0.2px;"
        )
        header.addWidget(title_lbl, 1)

        close_btn = QPushButton("\u2715", card)
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                border: none;
                border-radius: 8px;
                font-size: 11pt;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton:hover {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignRight)

        layout.addLayout(header)

        msg = QLabel(message, card)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10pt; line-height: 1.45;")
        msg.setMinimumWidth(420)
        layout.addWidget(msg)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        def ghost_btn(text: str) -> QPushButton:
            b = QPushButton(text, card)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(36)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: {Radius.MD};
                    font-size: 9.5pt;
                    font-weight: 700;
                    padding: 6px 14px;
                }}
                QPushButton:hover {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY}; }}
            """)
            return b

        def primary_btn(text: str) -> QPushButton:
            b = QPushButton(text, card)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(36)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.ACCENT};
                    color: #FFFFFF;
                    border: none;
                    border-radius: {Radius.MD};
                    font-size: 9.5pt;
                    font-weight: 800;
                    padding: 6px 16px;
                }}
                QPushButton:hover {{ background-color: {Colors.ACCENT_LIGHT}; }}
                QPushButton:pressed {{ background-color: {Colors.ACCENT_DARK}; }}
            """)
            return b

        if self._kind == self.KIND_QUESTION:
            no_btn = ghost_btn(no_text)
            no_btn.clicked.connect(self._on_no)
            btn_row.addWidget(no_btn)

            yes_btn = primary_btn(yes_text)
            yes_btn.clicked.connect(self._on_yes)
            btn_row.addWidget(yes_btn)
        else:
            if show_cancel:
                cancel_btn = ghost_btn("닫기")
                cancel_btn.clicked.connect(self.reject)
                btn_row.addWidget(cancel_btn)
            ok_btn = primary_btn(ok_text)
            ok_btn.clicked.connect(self.accept)
            btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

        # Size: compact but stable.
        self.setFixedWidth(520)

    def _on_yes(self):
        self._result_yes = True
        self.accept()

    def _on_no(self):
        self._result_yes = False
        self.reject()

    @property
    def result_yes(self) -> bool:
        return self._result_yes


def popup_info(parent, title: str, message: str) -> None:
    ThemedPopup(parent, title=title, message=message, kind=ThemedPopup.KIND_INFO).exec_()


def popup_warning(parent, title: str, message: str) -> None:
    ThemedPopup(parent, title=title, message=message, kind=ThemedPopup.KIND_WARN).exec_()


def popup_error(parent, title: str, message: str) -> None:
    ThemedPopup(parent, title=title, message=message, kind=ThemedPopup.KIND_ERROR).exec_()


def popup_confirm(parent, title: str, message: str, *, yes_text: str = "예", no_text: str = "아니오") -> bool:
    dlg = ThemedPopup(
        parent,
        title=title,
        message=message,
        kind=ThemedPopup.KIND_QUESTION,
        yes_text=yes_text,
        no_text=no_text,
    )
    dlg.exec_()
    return dlg.result_yes
