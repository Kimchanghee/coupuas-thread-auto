# -*- coding: utf-8 -*-
"""
로그인/회원가입 윈도우 (PyQt6)
쇼츠스레드메이커 전용 - Stitch Blue 테마
"""
import re
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QLineEdit,
    QPushButton, QCheckBox, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QPoint
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QLinearGradient, QPainterPath, QFontDatabase
)

from src.theme import (Colors, Typography, Radius, Gradients,
                       input_style, accent_btn_style, window_control_btn_style,
                       muted_text_style)
from src import auth_client
from src.ui_messages import ask_yes_no, show_info, show_warning

logger = logging.getLogger(__name__)

# ─── Font helper ────────────────────────────────────────────
_FONT_FAMILY = None

def _get_font():
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        candidates = ["Pretendard", "맑은 고딕", "Malgun Gothic", "Apple SD Gothic Neo", "Segoe UI"]
        available = QFontDatabase.families()
        for name in candidates:
            if name in available:
                _FONT_FAMILY = name
                break
        if _FONT_FAMILY is None:
            _FONT_FAMILY = ""
    return _FONT_FAMILY


# ─── Username Check Worker ──────────────────────────────────
class UsernameCheckWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, username):
        super().__init__()
        self.username = username

    def run(self):
        result = auth_client.check_username(self.username)
        self.finished.emit(result.get("available", False), result.get("message", ""))


# ─── Login / Register Window ───────────────────────────────
class LoginWindow(QMainWindow):
    """로그인 및 회원가입 통합 윈도우"""

    login_success = pyqtSignal(dict)  # 로그인 성공 시 결과 전달

    def __init__(self):
        super().__init__()
        self.oldPos = None
        self._username_available = False
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("쇼츠스레드메이커 - 로그인")
        self.setFixedSize(720, 520)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        central = QWidget()
        self.setCentralWidget(central)

        # ─── Left Panel (Brand) ─────────────────────────────
        self.left_panel = QFrame(central)
        self.left_panel.setGeometry(0, 0, 300, 520)

        # ─── Right Panel (Forms) ────────────────────────────
        self.right_panel = QFrame(central)
        self.right_panel.setGeometry(300, 0, 420, 520)
        self.right_panel.setStyleSheet(f"background-color: {Colors.BG_DARK};")

        # Stacked widget for login / register
        self.stack = QStackedWidget(self.right_panel)
        self.stack.setGeometry(0, 0, 420, 520)
        self.stack.setStyleSheet("background: transparent;")

        self._build_login_page()
        self._build_register_page()

        self.stack.setCurrentIndex(0)

        # ─── Window controls ────────────────────────────────
        self.btn_minimize = QPushButton("─", central)
        self.btn_minimize.setGeometry(670, 8, 20, 20)
        self.btn_minimize.setStyleSheet(window_control_btn_style(is_close=False))
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.clicked.connect(self.showMinimized)

        self.btn_close = QPushButton("✕", central)
        self.btn_close.setGeometry(694, 8, 20, 20)
        self.btn_close.setStyleSheet(window_control_btn_style(is_close=True))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._close_app)

    # ─── Left Panel Paint ───────────────────────────────────
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        fn = _get_font()

        # Gradient background
        grad = QLinearGradient(0, 0, 300, 520)
        grad.setColorAt(0, QColor("#0A1628"))
        grad.setColorAt(0.3, QColor("#0D2040"))
        grad.setColorAt(0.7, QColor("#0A47C8"))
        grad.setColorAt(1, QColor("#0D59F2"))
        painter.fillRect(0, 0, 300, 520, grad)

        # Top accent line
        top_grad = QLinearGradient(0, 0, 300, 0)
        top_grad.setColorAt(0, QColor(13, 89, 242, 0))
        top_grad.setColorAt(0.5, QColor(Colors.ACCENT_LIGHT))
        top_grad.setColorAt(1, QColor(13, 89, 242, 0))
        painter.fillRect(0, 0, 300, 2, top_grad)

        # Brand icon
        painter.setPen(Qt.PenStyle.NoPen)
        cx, cy = 150, 160
        # Glow
        painter.setBrush(QColor(59, 123, 255, 30))
        painter.drawEllipse(cx - 50, cy - 50, 100, 100)
        # Ring
        from PyQt6.QtGui import QPen
        painter.setPen(QPen(QColor(Colors.ACCENT_LIGHT), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(cx - 30, cy - 30, 60, 60, 30 * 16, 300 * 16)
        # Letter
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 22, QFont.Weight.Bold))
        from PyQt6.QtCore import QRectF
        painter.drawText(QRectF(cx - 30, cy - 30, 60, 60), Qt.AlignmentFlag.AlignCenter, "ST")

        # Title
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 16, QFont.Weight.Bold))
        painter.drawText(0, 220, 300, 30, Qt.AlignmentFlag.AlignCenter, "쇼츠스레드메이커")

        # Subtitle
        painter.setPen(QColor(Colors.ACCENT_LIGHT))
        painter.setFont(QFont(fn, 11))
        painter.drawText(0, 258, 300, 22, Qt.AlignmentFlag.AlignCenter, "Shorts Thread Maker")

        # Tagline
        painter.setPen(QColor(255, 255, 255, 230))
        painter.setFont(QFont(fn, 10, QFont.Weight.DemiBold))
        painter.drawText(0, 310, 300, 40, Qt.AlignmentFlag.AlignCenter, "쿠팡 파트너스 Threads\n자동 업로드 솔루션")

        # Features
        painter.setPen(QColor(255, 255, 255, 200))
        painter.setFont(QFont(fn, 9, QFont.Weight.DemiBold))
        painter.drawText(0, 400, 300, 20, Qt.AlignmentFlag.AlignCenter, "AI 분석  |  자동 포스팅  |  성과 추적")

        # Version
        painter.setPen(QColor(255, 255, 255, 180))
        painter.setFont(QFont(fn, 9))
        painter.drawText(0, 488, 300, 20, Qt.AlignmentFlag.AlignCenter, "v2.2.0")

        # Border right
        painter.setPen(QColor(Colors.BORDER))
        painter.drawLine(300, 0, 300, 520)

    # ─── Login Page ─────────────────────────────────────────
    def _build_login_page(self):
        page = QWidget()
        fn = _get_font()

        title = QLabel("로그인", page)
        title.setGeometry(50, 70, 320, 35)
        title.setFont(QFont(fn, 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")

        subtitle = QLabel("쇼츠스레드메이커에 오신 것을 환영합니다", page)
        subtitle.setGeometry(50, 108, 320, 22)
        subtitle.setFont(QFont(fn, 10))
        subtitle.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")

        # ID
        lbl_id = QLabel("아이디", page)
        lbl_id.setGeometry(50, 168, 100, 20)
        lbl_id.setFont(QFont(fn, 10, QFont.Weight.Bold))
        lbl_id.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")

        self.login_id = QLineEdit(page)
        self.login_id.setGeometry(50, 192, 320, 42)
        self.login_id.setPlaceholderText("아이디를 입력하세요")
        self._apply_input_style(self.login_id)

        # PW
        lbl_pw = QLabel("비밀번호", page)
        lbl_pw.setGeometry(50, 248, 100, 20)
        lbl_pw.setFont(QFont(fn, 10, QFont.Weight.Bold))
        lbl_pw.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")

        self.login_pw = QLineEdit(page)
        self.login_pw.setGeometry(50, 272, 320, 42)
        self.login_pw.setPlaceholderText("비밀번호를 입력하세요")
        self.login_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.login_pw)

        # Remember
        self.remember_cb = QCheckBox("아이디/비밀번호 저장", page)
        self.remember_cb.setGeometry(50, 328, 200, 22)
        self.remember_cb.setFont(QFont(fn, 9))
        self.remember_cb.setStyleSheet(f"""
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; background: transparent; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {Colors.BORDER_LIGHT};
                border-radius: 4px; background: {Colors.BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background: {Colors.ACCENT}; border-color: {Colors.ACCENT};
            }}
        """)
        self.remember_cb.setCursor(Qt.CursorShape.PointingHandCursor)

        # Login button
        self.btn_login = QPushButton("로그인", page)
        self.btn_login.setGeometry(50, 370, 320, 46)
        self.btn_login.setFont(QFont(fn, 12, QFont.Weight.Bold))
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN}; color: white;
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
        """)
        self.btn_login.clicked.connect(self._do_login)

        # Register button
        self.btn_go_register = QPushButton("회원가입", page)
        self.btn_go_register.setGeometry(50, 430, 320, 42)
        self.btn_go_register.setFont(QFont(fn, 11, QFont.Weight.Bold))
        self.btn_go_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go_register.setStyleSheet(f"""
            QPushButton {{
                color: #FFFFFF; background: transparent;
                border: 2px solid {Colors.ACCENT_LIGHT}; border-radius: 8px;
            }}
            QPushButton:hover {{ background: rgba(13, 89, 242, 0.15); }}
        """)
        self.btn_go_register.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        # Status
        self.login_status = QLabel("", page)
        self.login_status.setGeometry(50, 480, 320, 20)
        self.login_status.setFont(QFont(fn, 9))
        self.login_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")
        self.login_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(page)

        # Load saved credentials
        self._load_saved_login()

    def _load_saved_login(self):
        """Load saved username/password"""
        cred = auth_client.get_saved_credentials()
        if cred and cred.get("username"):
            self.login_id.setText(cred["username"])
            self.remember_cb.setChecked(True)
            if cred.get("remember_pw"):
                self.login_pw.setText(cred["remember_pw"])

    # ─── Register Page ──────────────────────────────────────
    def _build_register_page(self):
        page = QWidget()
        fn = _get_font()

        # Back button
        btn_back = QPushButton("← 돌아가기", page)
        btn_back.setGeometry(15, 12, 100, 30)
        btn_back.setFont(QFont(fn, 9))
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_SECONDARY};
                border: none;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        title = QLabel("회원가입", page)
        title.setGeometry(30, 50, 360, 30)
        title.setFont(QFont(fn, 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")

        sub = QLabel("가입 정보를 입력해주세요. (체험판 제공)", page)
        sub.setGeometry(30, 82, 360, 18)
        sub.setFont(QFont(fn, 9))
        sub.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")

        y = 100
        row_h = 56  # label height + input height + gap

        # Name
        self._reg_name_lbl = QLabel("가입자 명", page)
        self._reg_name_lbl.setGeometry(30, y, 100, 18)
        self._reg_name_lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        self._reg_name_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_name = QLineEdit(page)
        self.reg_name.setGeometry(30, y + 20, 360, 36)
        self.reg_name.setPlaceholderText("이름을 입력하세요")
        self._apply_input_style(self.reg_name)

        y += row_h
        # Email
        lbl = QLabel("이메일", page)
        lbl.setGeometry(30, y, 100, 18)
        lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_email = QLineEdit(page)
        self.reg_email.setGeometry(30, y + 20, 360, 36)
        self.reg_email.setPlaceholderText("example@email.com")
        self._apply_input_style(self.reg_email)

        y += row_h
        # Username + check
        lbl = QLabel("아이디", page)
        lbl.setGeometry(30, y, 100, 18)
        lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_username = QLineEdit(page)
        self.reg_username.setGeometry(30, y + 20, 270, 36)
        self.reg_username.setPlaceholderText("영문, 숫자, 밑줄(_)")
        self._apply_input_style(self.reg_username)
        self.reg_username.textChanged.connect(self._on_reg_username_changed)

        self.btn_check_user = QPushButton("중복확인", page)
        self.btn_check_user.setGeometry(308, y + 20, 82, 36)
        self.btn_check_user.setFont(QFont(fn, 9))
        self.btn_check_user.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_user.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_ELEVATED}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {Colors.BG_HOVER}; color: {Colors.TEXT_PRIMARY}; }}
        """)
        self.btn_check_user.clicked.connect(self._check_username)

        self.reg_user_status = QLabel("", page)
        self.reg_user_status.setGeometry(30, y + 58, 360, 14)
        self.reg_user_status.setFont(QFont(fn, 9))
        self.reg_user_status.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")

        y += row_h + 10
        # Password
        lbl = QLabel("비밀번호", page)
        lbl.setGeometry(30, y, 100, 18)
        lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_pw = QLineEdit(page)
        self.reg_pw.setGeometry(30, y + 20, 360, 36)
        self.reg_pw.setPlaceholderText("비밀번호를 입력하세요")
        self.reg_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.reg_pw)

        y += row_h
        # Password confirm
        lbl = QLabel("비밀번호 확인", page)
        lbl.setGeometry(30, y, 120, 18)
        lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_pw_confirm = QLineEdit(page)
        self.reg_pw_confirm.setGeometry(30, y + 20, 360, 36)
        self.reg_pw_confirm.setPlaceholderText("비밀번호를 다시 입력")
        self.reg_pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.reg_pw_confirm)

        y += row_h
        # Contact
        lbl = QLabel("연락처", page)
        lbl.setGeometry(30, y, 100, 18)
        lbl.setFont(QFont(fn, 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.reg_contact = QLineEdit(page)
        self.reg_contact.setGeometry(30, y + 20, 360, 36)
        self.reg_contact.setPlaceholderText("010-1234-5678")
        self._apply_input_style(self.reg_contact)

        y += row_h
        # Submit
        self.btn_register = QPushButton("회원가입", page)
        self.btn_register.setGeometry(30, y, 360, 44)
        self.btn_register.setFont(QFont(fn, 11, QFont.Weight.Bold))
        self.btn_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_register.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN}; color: white;
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}
        """)
        self.btn_register.clicked.connect(self._do_register)

        self.stack.addWidget(page)

    # ─── Style helpers ──────────────────────────────────────
    def _apply_input_style(self, widget):
        widget.setFont(QFont(_get_font(), 10))
        widget.setStyleSheet(input_style())

    # ─── Login logic ────────────────────────────────────────
    def _do_login(self, force=False):
        uid = self.login_id.text().strip()
        pw = self.login_pw.text()

        if not uid or not pw:
            self.login_status.setText("아이디와 비밀번호를 입력해주세요.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("로그인 중...")
        self.login_status.setText("")

        # Run login in thread
        self._login_thread = LoginWorker(uid, pw, force)
        self._login_thread.finished_signal.connect(self._on_login_result)
        self._login_thread.start()

    def _on_login_result(self, result: dict):
        self.btn_login.setEnabled(True)
        self.btn_login.setText("로그인")

        status = result.get("status")
        if status is True:
            logger.info(f"Login success: user_id={result.get('id')}")

            # Save credentials if remember is checked
            if self.remember_cb.isChecked():
                auth_client._save_cred({
                    "user_id": result.get("id"),
                    "username": self.login_id.text().strip().lower(),
                    "token": result.get("key"),
                    "remember_pw": self.login_pw.text(),
                })

            self.login_success.emit(result)
        elif status == "EU003":
            if ask_yes_no(
                self,
                "중복 로그인",
                "다른 곳에서 이미 로그인되어 있습니다.\n기존 세션을 종료하고 여기서 로그인하시겠습니까?",
            ):
                self._do_login(force=True)
        else:
            msg = auth_client.friendly_login_message(result)
            self.login_status.setText(msg)
            self.login_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")

    # ─── Register logic ─────────────────────────────────────
    def _on_reg_username_changed(self):
        self._username_available = False
        self.reg_user_status.setText("")

    def _check_username(self):
        username = self.reg_username.text().strip().lower()
        if not username or len(username) < 4:
            self._show_msg("아이디는 4자 이상이어야 합니다.")
            return
        if not re.match(r'^[a-z0-9_]+$', username):
            self._show_msg("아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.")
            return

        self.btn_check_user.setEnabled(False)
        self.btn_check_user.setText("확인중...")

        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(self._on_username_checked)
        self._username_worker.start()

    def _on_username_checked(self, available: bool, message: str):
        self.btn_check_user.setEnabled(True)
        self.btn_check_user.setText("중복확인")

        if available:
            self._username_available = True
            self.reg_user_status.setText("✓ 사용 가능한 아이디입니다")
            self.reg_user_status.setStyleSheet(f"color: {Colors.SUCCESS}; background: transparent;")
        else:
            self._username_available = False
            self.reg_user_status.setText(f"✗ {message}")
            self.reg_user_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")

    def _do_register(self):
        name = self.reg_name.text().strip()
        email = self.reg_email.text().strip()
        username = self.reg_username.text().strip().lower()
        pw = self.reg_pw.text()
        pw2 = self.reg_pw_confirm.text()
        contact = self.reg_contact.text().strip()

        # Validation
        if not name or len(name) < 2:
            self._show_msg("가입자 명을 2자 이상 입력해주세요.")
            return
        if not email or "@" not in email or "." not in email:
            self._show_msg("올바른 이메일 주소를 입력해주세요.")
            return
        if not username or len(username) < 4:
            self._show_msg("아이디를 4자 이상 입력해주세요.")
            return
        if not self._username_available:
            self._show_msg("아이디 중복확인을 해주세요.")
            return
        if not pw:
            self._show_msg("비밀번호를 입력해주세요.")
            return
        if pw != pw2:
            self._show_msg("비밀번호가 일치하지 않습니다.")
            return
        contact_clean = re.sub(r'[^0-9]', '', contact)
        if len(contact_clean) < 10:
            self._show_msg("올바른 연락처를 입력해주세요.")
            return

        self.btn_register.setEnabled(False)
        self.btn_register.setText("처리 중...")

        self._reg_worker = RegisterWorker(name, username, pw, contact_clean, email)
        self._reg_worker.finished_signal.connect(self._on_register_result)
        self._reg_worker.start()

    def _on_register_result(self, result: dict):
        self.btn_register.setEnabled(True)
        self.btn_register.setText("회원가입")

        if result.get("success"):
            show_info(self, "가입 완료", "회원가입이 완료되었습니다!\n바로 로그인해주세요.")
            # Auto-fill login
            self.login_id.setText(self.reg_username.text().strip().lower())
            self.login_pw.setText(self.reg_pw.text())
            self.stack.setCurrentIndex(0)
        else:
            self._show_msg(result.get("message", "회원가입에 실패했습니다."))

    # ─── Helpers ────────────────────────────────────────────
    def _show_msg(self, msg):
        show_warning(self, "알림", msg)

    def _close_app(self):
        QApplication.quit()

    # ─── Window Dragging ────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = current_pos

    def mouseReleaseEvent(self, event):
        self.oldPos = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.stack.currentIndex() == 0:
                self._do_login()


# ─── Background Workers ────────────────────────────────────

class LoginWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, username, password, force=False):
        super().__init__()
        self.username = username
        self.password = password
        self.force = force

    def run(self):
        result = auth_client.login(self.username, self.password, self.force)
        self.finished_signal.emit(result)


class RegisterWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, name, username, password, contact, email):
        super().__init__()
        self.name = name
        self.username = username
        self.password = password
        self.contact = contact
        self.email = email

    def run(self):
        result = auth_client.register(
            self.name, self.username, self.password, self.contact, self.email
        )
        self.finished_signal.emit(result)
