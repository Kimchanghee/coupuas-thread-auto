"""
로그인/회원가입 윈도우 (PyQt6)
스레드 쇼핑 자동화 전용 - Nordic Bento 테마
"""
import atexit
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QPointF, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QLinearGradient,
    QPainter,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src import auth_client
from src.app_icon import apply_window_icon
from src.theme import (
    Colors,
    Gradients,
    Typography,
    input_style,
    window_control_btn_style,
)
from src.ui_components import BrandMark
from src.ui_messages import show_info, show_warning, user_friendly_message

logger = logging.getLogger(__name__)
_TELEMETRY_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="ui-telemetry",
)
atexit.register(_TELEMETRY_EXECUTOR.shutdown, wait=False, cancel_futures=True)


def _send_telemetry(action: str, detail: str) -> None:
    try:
        auth_client.log_action(action, detail)
    except Exception:
        logger.debug("활동 로그 전송에 실패했습니다: %s", action, exc_info=True)


def _queue_telemetry(action: str, detail: str) -> None:
    try:
        _TELEMETRY_EXECUTOR.submit(_send_telemetry, action, detail)
    except RuntimeError:
        logger.debug("종료 중이어서 활동 로그를 건너뜁니다: %s", action)


MIN_LOGIN_PASSWORD_LENGTH = getattr(auth_client, "MIN_LOGIN_PASSWORD_LENGTH", 6)
MIN_REGISTER_PASSWORD_LENGTH = getattr(auth_client, "MIN_REGISTER_PASSWORD_LENGTH", 8)
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 760
LEFT_PANEL_WIDTH = 300
RIGHT_PANEL_WIDTH = WINDOW_WIDTH - LEFT_PANEL_WIDTH
REGISTER_PAGE_HEIGHT = 980
WEBSITE_BASE_URL = "https://coupuas-thread-auto-ten.vercel.app"
COMPACT_BRAND_HEIGHT = 58


def _resolve_app_version() -> str:
    """Resolve app version once to avoid per-frame imports in paintEvent."""
    for module_name in ("__main__", "main"):
        module = sys.modules.get(module_name)
        version = getattr(module, "VERSION", None)
        if isinstance(version, str) and version.strip():
            return version.strip()
    return "unknown"


def _get_font():
    """theme.resolve_fonts()에서 설정된 Typography.FAMILY를 반환"""
    return Typography.FAMILY


# ─── Username Check Worker ──────────────────────────────────
class UsernameCheckWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, username):
        super().__init__()
        self.username = username

    def run(self):
        result = auth_client.check_username(self.username)
        self.finished.emit(result.get("available", False), result.get("message", ""))


class AuthBrandPanel(QFrame):
    """Paints the wide authentication value proposition in its own surface."""

    def __init__(self, version, parent=None):
        super().__init__(parent)
        self._version = version
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        width, height = self.width(), self.height()
        fn = _get_font()

        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor("#101F27"))
        gradient.setColorAt(0.68, QColor("#102730"))
        gradient.setColorAt(1, QColor("#0D3138"))
        painter.fillRect(self.rect(), gradient)
        painter.fillRect(0, 0, width, 3, QColor("#25B9BC"))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#25B9BC"))
        painter.drawRoundedRect(38, 42, 42, 42, 12, 12)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(62, 48),
                    QPointF(50, 65),
                    QPointF(58, 65),
                    QPointF(54, 78),
                    QPointF(68, 59),
                    QPointF(60, 59),
                ]
            )
        )
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 13, QFont.Weight.Bold))
        painter.drawText(94, 51, width - 112, 22, Qt.AlignmentFlag.AlignVCenter, "THREAD AUTO")
        painter.setPen(QColor("#A9C2C9"))
        painter.setFont(QFont(fn, 7, QFont.Weight.DemiBold))
        painter.drawText(94, 72, width - 112, 14, Qt.AlignmentFlag.AlignVCenter, "COMMERCE PUBLISHING OS")

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(fn, 17, QFont.Weight.Bold))
        painter.drawText(38, 152, width - 68, 62, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "상품 링크에서\n게시까지 한 흐름으로.")
        painter.setPen(QColor("#C3D4D9"))
        painter.setFont(QFont(fn, 9))
        painter.drawText(38, 224, width - 68, 48, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "여러 쇼핑 채널의 제휴 링크를 검사하고\nThreads 게시까지 자동화합니다.")

        metrics_y = min(326, max(286, height - 380))
        metrics = (("8", "지원 쇼핑 채널"), ("10", "Threads 계정"), ("4", "자동 복구 단계"))
        for index, (value, label) in enumerate(metrics):
            y = metrics_y + index * 58
            painter.setPen(QColor("#25B9BC"))
            painter.setFont(QFont(fn, 15, QFont.Weight.Bold))
            painter.drawText(38, y, 42, 24, Qt.AlignmentFlag.AlignVCenter, value)
            painter.setPen(QColor("#D8E4E7"))
            painter.setFont(QFont(fn, 9, QFont.Weight.DemiBold))
            painter.drawText(82, y, width - 106, 24, Qt.AlignmentFlag.AlignVCenter, label)

        painter.setPen(QColor(169, 194, 201, 180))
        painter.setFont(QFont(fn, 8))
        version_text = (
            f"Thread Auto v{self._version}"
            if self._version and self._version.lower() != "unknown"
            else "Thread Auto"
        )
        painter.drawText(38, height - 38, width - 68, 18, Qt.AlignmentFlag.AlignLeft, version_text)


# ─── Login / Register Window ───────────────────────────────
class LoginWindow(QMainWindow):
    """로그인 및 회원가입 통합 윈도우"""

    login_success = pyqtSignal(dict)  # 로그인 성공 시 결과 전달

    def __init__(self):
        super().__init__()
        self.oldPos = None
        self._username_available = False
        self._username_available_for = None
        self._username_check_token = 0
        self._app_version = _resolve_app_version()
        self._auto_login_pending = False
        self._login_in_flight = False
        self._setup_ui()
        if self._auto_login_pending:
            QTimer.singleShot(450, self._maybe_start_auto_login)

    def _setup_ui(self):
        self.setWindowTitle("스레드 쇼핑 자동화 - 로그인")
        self.setMinimumSize(420, 560)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(WINDOW_WIDTH, max(420, available.width() - 32)),
                min(WINDOW_HEIGHT, max(560, available.height() - 32)),
            )
        else:
            self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        apply_window_icon(self)

        central = QWidget()
        central.setObjectName("authRoot")
        central.setStyleSheet(f"#authRoot {{ background: {Colors.BG_CARD}; }}")
        self.setCentralWidget(central)

        # Wide mode uses a persistent product story panel. Compact mode swaps it
        # for a 58 DIP wordmark bar, leaving the full remaining height to forms.
        self.left_panel = AuthBrandPanel(self._app_version, central)
        self.left_panel.setObjectName("authBrandPanel")
        self.left_panel.setGeometry(0, 0, LEFT_PANEL_WIDTH, WINDOW_HEIGHT)

        self.right_panel = QFrame(central)
        self.right_panel.setObjectName("authFormPanel")
        self.right_panel.setGeometry(LEFT_PANEL_WIDTH, 0, RIGHT_PANEL_WIDTH, WINDOW_HEIGHT)
        self.right_panel.setStyleSheet(f"#authFormPanel {{ background-color: {Colors.BG_CARD}; }}")

        self.compact_brand_bar = QFrame(central)
        self.compact_brand_bar.setObjectName("compactBrandBar")
        self.compact_brand_bar.setStyleSheet(
            "#compactBrandBar { background: #101F27; border: none; }"
        )
        compact_brand_layout = QHBoxLayout(self.compact_brand_bar)
        compact_brand_layout.setContentsMargins(20, 0, 100, 0)
        compact_brand_layout.setSpacing(10)
        compact_mark = BrandMark()
        compact_mark.setFixedSize(34, 34)
        compact_wordmark = QLabel("THREAD AUTO")
        compact_wordmark.setFont(QFont(_get_font(), 13, QFont.Weight.Bold))
        compact_wordmark.setStyleSheet("color: #FFFFFF; background: transparent;")
        compact_brand_layout.addWidget(compact_mark)
        compact_brand_layout.addWidget(compact_wordmark)
        compact_brand_layout.addStretch(1)

        self._form_scroll = QScrollArea(self.right_panel)
        self._form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._form_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._form_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BG_CARD}; border: none; }}"
            f"QScrollBar:vertical {{ background: {Colors.BG_CARD}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: {Colors.BORDER_LIGHT}; border-radius: 5px; min-height: 28px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._form_scroll.viewport().setStyleSheet(f"background-color: {Colors.BG_CARD};")

        self.stack = QStackedWidget()
        self.stack.setObjectName("authStack")
        self.stack.resize(RIGHT_PANEL_WIDTH, WINDOW_HEIGHT)
        self.stack.setStyleSheet("background: transparent;")
        self._form_scroll.setWidget(self.stack)

        self._build_login_page()
        self._build_register_page()

        self.stack.currentChanged.connect(self._on_auth_page_changed)
        self.stack.setCurrentIndex(0)
        self._on_auth_page_changed(0)

        # 40 DIP targets remain operable at 200% Windows scaling.
        self.btn_minimize = QPushButton("−", central)
        self.btn_minimize.setGeometry(WINDOW_WIDTH - 88, 8, 40, 40)
        self.btn_minimize.setAccessibleName("창 최소화")
        self.btn_minimize.setFont(QFont("Segoe UI Symbol", 13, QFont.Weight.DemiBold))
        self.btn_minimize.setStyleSheet(window_control_btn_style(is_close=False))
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.clicked.connect(self.showMinimized)

        self.btn_close = QPushButton("×", central)
        self.btn_close.setGeometry(WINDOW_WIDTH - 44, 8, 40, 40)
        self.btn_close.setAccessibleName("창 닫기")
        self.btn_close.setFont(QFont("Segoe UI Symbol", 15, QFont.Weight.DemiBold))
        self.btn_close.setStyleSheet(window_control_btn_style(is_close=True))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._close_app)
        self._relayout_window()
        # Restore credentials before __init__ decides whether to schedule
        # automatic login.  Loading them only after opening registration would
        # leave the primary login surface blank on every app start.
        self._load_saved_login()

    def _relayout_window(self):
        """Keep login usable on narrow or short logical work areas."""
        width = self.centralWidget().width() if self.centralWidget() else self.width()
        height = self.centralWidget().height() if self.centralWidget() else self.height()
        show_brand = width >= 680
        left_width = max(240, width - RIGHT_PANEL_WIDTH) if show_brand else 0
        right_width = min(RIGHT_PANEL_WIDTH, width)
        right_x = left_width if show_brand else max(0, (width - right_width) // 2)
        compact_y = 0 if show_brand else COMPACT_BRAND_HEIGHT
        form_height = max(1, height - compact_y)
        self._left_panel_width = left_width
        self.left_panel.setVisible(show_brand)
        self.left_panel.setGeometry(0, 0, left_width, height)
        self.compact_brand_bar.setVisible(not show_brand)
        self.compact_brand_bar.setGeometry(right_x, 0, right_width, COMPACT_BRAND_HEIGHT)
        self.right_panel.setGeometry(right_x, compact_y, right_width, form_height)
        self._form_scroll.setGeometry(0, 0, right_width, form_height)
        self.btn_minimize.setGeometry(width - 88, 8, 40, 40)
        self.btn_close.setGeometry(width - 44, 8, 40, 40)
        self._compact_mode = not show_brand
        if hasattr(self, "_login_title"):
            self._login_layout.setContentsMargins(40, 32 if self._compact_mode else 84, 40, 18)
            self._login_title.setText(
                "콘텐츠 운영을 시작하세요"
                if self._compact_mode
                else "다시 오신 것을 환영합니다"
            )
            self._login_subtitle.setText(
                "저장된 작업과 연결 계정을 이어서 사용합니다."
                if self._compact_mode
                else "계정에 로그인하고 자동화를 이어가세요."
            )
            self._restore_notice.setVisible(not self._compact_mode)
        self._on_auth_page_changed(self.stack.currentIndex())
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_form_scroll"):
            self._relayout_window()

    def _on_auth_page_changed(self, index: int) -> None:
        """Size only the active auth flow; the compact login never scrolls."""
        if not hasattr(self, "_form_scroll"):
            return
        viewport_h = max(1, self._form_scroll.height())
        if int(index) == 0:
            content_h = viewport_h
        else:
            # Each registration step is short enough at 720 x 760. On the
            # 420 x 560 compact canvas, only registration may scroll.
            content_h = max(viewport_h, 720)
        self.stack.resize(max(1, self._form_scroll.width()), content_h)
        self._form_scroll.verticalScrollBar().setValue(0)
        if hasattr(self, "_register_steps") and int(index) == 1:
            self._update_register_step_ui()

    # ─── Login Page ─────────────────────────────────────────
    def _build_login_page(self):
        page = QWidget()
        page.setObjectName("loginPage")
        fn = _get_font()
        layout = QVBoxLayout(page)
        self._login_layout = layout
        layout.setContentsMargins(40, 34, 40, 18)
        layout.setSpacing(7)

        self._login_title = QLabel("다시 오신 것을 환영합니다")
        self._login_title.setMinimumHeight(34)
        self._login_title.setFont(QFont(fn, 17, QFont.Weight.Bold))
        self._login_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(self._login_title)

        self._login_subtitle = QLabel("계정에 로그인하고 자동화를 이어가세요.")
        self._login_subtitle.setWordWrap(True)
        self._login_subtitle.setMinimumHeight(32)
        self._login_subtitle.setFont(QFont(fn, 10))
        self._login_subtitle.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        layout.addWidget(self._login_subtitle)
        layout.addSpacing(12)

        def _field_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setFixedHeight(18)
            label.setFont(QFont(fn, 10, QFont.Weight.Bold))
            label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
            return label

        layout.addWidget(_field_label("아이디"))
        self.login_id = QLineEdit()
        self.login_id.setPlaceholderText("아이디를 입력하세요")
        self.login_id.setAccessibleName("로그인 아이디")
        self._apply_input_style(self.login_id)
        self.login_id.setFixedHeight(50)
        layout.addWidget(self.login_id)
        layout.addSpacing(5)

        layout.addWidget(_field_label("비밀번호"))
        self.login_pw = QLineEdit()
        self.login_pw.setPlaceholderText("비밀번호를 입력하세요")
        self.login_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pw.setAccessibleName("로그인 비밀번호")
        self._apply_input_style(self.login_pw)
        self.login_pw.setFixedHeight(50)
        layout.addWidget(self.login_pw)
        layout.addSpacing(5)

        option_row = QHBoxLayout()
        option_row.setContentsMargins(0, 0, 0, 0)
        option_row.setSpacing(8)
        self.remember_cb = QCheckBox("로그인 정보 저장")
        self.remember_cb.setMinimumHeight(28)
        self.remember_cb.setFont(QFont(fn, 9))
        self.remember_cb.setStyleSheet(f"""
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; background: transparent; font-size: 9.5pt; spacing: 7px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 4px; background: {Colors.BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background: {Colors.ACCENT}; border-color: {Colors.ACCENT};
            }}
        """)
        self.remember_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remember_cb.toggled.connect(self._on_remember_toggled)
        option_row.addWidget(self.remember_cb, 1)

        self.auto_login_cb = QCheckBox("자동 로그인")
        self.auto_login_cb.setMinimumHeight(28)
        self.auto_login_cb.setFixedWidth(112)
        self.auto_login_cb.setFont(QFont(fn, 9))
        self.auto_login_cb.setStyleSheet(self.remember_cb.styleSheet())
        self.auto_login_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_login_cb.toggled.connect(self._on_auto_login_toggled)
        option_row.addWidget(self.auto_login_cb, 0)
        layout.addLayout(option_row)

        self.btn_login = QPushButton("로그인")
        self.btn_login.setFixedHeight(48)
        self.btn_login.setAccessibleName("로그인 실행")
        self.btn_login.setFont(QFont(fn, 11, QFont.Weight.Bold))
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
        layout.addWidget(self.btn_login)

        self._password_reset_btn = QPushButton("비밀번호 재설정")
        self._password_reset_btn.setMinimumHeight(30)
        self._password_reset_btn.setFont(QFont(fn, 10, QFont.Weight.DemiBold))
        self._password_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._password_reset_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Colors.ACCENT_LIGHT}; border: none;
                padding: 0; min-height: 30px; }}
            QPushButton:hover {{ color: {Colors.ACCENT}; text-decoration: underline; }}
        """)
        self._password_reset_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"{WEBSITE_BASE_URL}/forgot-password"))
        )
        layout.addWidget(self._password_reset_btn)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background: {Colors.BORDER_SUBTLE}; border: none; max-height: 1px;")
        layout.addWidget(divider)

        join_row = QHBoxLayout()
        join_row.setContentsMargins(0, 0, 0, 0)
        join_row.addStretch(1)
        join_copy = QLabel("계정이 없으신가요?")
        join_copy.setFont(QFont(fn, 9))
        join_copy.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        join_row.addWidget(join_copy)
        self.btn_go_register = QPushButton("계정 만들기")
        self.btn_go_register.setMinimumHeight(46)
        self.btn_go_register.setMinimumWidth(104)
        self.btn_go_register.setFont(QFont(fn, 9, QFont.Weight.Bold))
        self.btn_go_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go_register.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.ACCENT_LIGHT}; background: transparent; border: none;
                padding: 0 6px; min-height: 46px;
            }}
            QPushButton:hover {{ color: {Colors.ACCENT}; text-decoration: underline; }}
        """)
        self.btn_go_register.clicked.connect(self._open_registration)
        join_row.addWidget(self.btn_go_register)
        join_row.addStretch(1)
        layout.addLayout(join_row)

        self.login_status = QLabel("")
        self.login_status.setWordWrap(True)
        self.login_status.setMinimumHeight(28)
        self.login_status.setFont(QFont(fn, 9))
        self.login_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")
        self.login_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.login_status)

        self._restore_notice = QFrame()
        self._restore_notice.setObjectName("restoreNotice")
        self._restore_notice.setMinimumHeight(58)
        self._restore_notice.setStyleSheet(
            f"#restoreNotice {{ background: {Colors.INFO_BG}; border: 1px solid {Colors.INFO_BORDER}; border-radius: 10px; }}"
        )
        restore_layout = QHBoxLayout(self._restore_notice)
        restore_layout.setContentsMargins(16, 8, 16, 8)
        restore_layout.setSpacing(10)
        restore_icon = QLabel("✓")
        restore_icon.setFont(QFont(fn, 14, QFont.Weight.Bold))
        restore_icon.setStyleSheet(f"color: {Colors.ACCENT}; background: transparent;")
        restore_copy = QLabel("로그인 후 마지막 작업과 연결 상태를 자동으로 복원합니다.")
        restore_copy.setWordWrap(True)
        restore_copy.setFont(QFont(fn, 9))
        restore_copy.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        restore_layout.addWidget(restore_icon)
        restore_layout.addWidget(restore_copy, 1)
        layout.addStretch(1)
        layout.addWidget(self._restore_notice)

        self.stack.addWidget(page)

    def _open_registration(self) -> None:
        self._show_register_step(0)
        self.stack.setCurrentIndex(1)

    def _load_saved_login(self):
        """Load saved username/password."""
        cred = auth_client.get_saved_credentials()
        if cred and cred.get("username"):
            self.login_id.setText(cred["username"])
            self.login_pw.setText(cred.get("password", ""))
            self.remember_cb.setChecked(True)
            self.auto_login_cb.setChecked(bool(cred.get("auto_login")) and bool(cred.get("password")))
            self._auto_login_pending = self.auto_login_cb.isChecked()

    def _on_remember_toggled(self, checked: bool):
        if checked:
            return
        self.auto_login_cb.setChecked(False)
        try:
            auth_client.remember_login_credentials("", "")
        except Exception:
            logger.exception("아이디 저장 해제 상태를 반영하지 못했습니다.")

    def _on_auto_login_toggled(self, checked: bool):
        if checked and not self.remember_cb.isChecked():
            self.remember_cb.setChecked(True)

    def _maybe_start_auto_login(self):
        if self.stack.currentIndex() != 0:
            return
        if not self.auto_login_cb.isChecked():
            return
        if not self.login_id.text().strip() or not self.login_pw.text():
            return
        if not self.btn_login.isEnabled():
            return

        self.login_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self.login_status.setText("자동 로그인 중...")
        self._do_login()

    # ─── Register Page ──────────────────────────────────────
    def _build_register_page(self):
        page = QWidget()
        page.setObjectName("registerPage")
        fn = _get_font()
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 14, 28, 18)
        root.setSpacing(7)

        def _field_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setFixedHeight(18)
            lbl.setFont(QFont(fn, 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
            return lbl

        self._register_back_btn = QPushButton("←  돌아가기")
        self._register_back_btn.setFixedHeight(34)
        self._register_back_btn.setFont(QFont(fn, 10, QFont.Weight.DemiBold))
        self._register_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._register_back_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Colors.TEXT_SECONDARY};
                border: none; padding: 0; min-height: 34px; text-align: left; }}
            QPushButton:hover {{ color: {Colors.ACCENT_LIGHT}; }}
        """)
        self._register_back_btn.clicked.connect(self._register_back)
        root.addWidget(self._register_back_btn)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self._register_title = QLabel("계정 만들기")
        self._register_title.setFont(QFont(fn, 17, QFont.Weight.Bold))
        self._register_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        title_row.addWidget(self._register_title, 1)
        self._register_step_text = QLabel("1 / 2")
        self._register_step_text.setFont(QFont(fn, 10, QFont.Weight.Bold))
        self._register_step_text.setStyleSheet(f"color: {Colors.ACCENT_LIGHT}; background: transparent;")
        title_row.addWidget(self._register_step_text)
        root.addLayout(title_row)

        self._register_subtitle = QLabel("필요한 정보만 입력하세요.")
        self._register_subtitle.setFont(QFont(fn, 10))
        self._register_subtitle.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        root.addWidget(self._register_subtitle)

        self._register_progress = QProgressBar()
        self._register_progress.setRange(0, 2)
        self._register_progress.setValue(1)
        self._register_progress.setTextVisible(False)
        self._register_progress.setFixedHeight(6)
        self._register_progress.setStyleSheet(f"""
            QProgressBar {{ background: {Colors.BORDER_SUBTLE}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {Colors.ACCENT}; border-radius: 3px; }}
        """)
        root.addWidget(self._register_progress)
        root.addSpacing(5)

        self._register_steps = QStackedWidget()
        self._register_steps.setObjectName("registerSteps")
        self._register_steps.setStyleSheet("background: transparent;")
        root.addWidget(self._register_steps, 1)

        # Step 1: identity and sign-in credentials. Values remain in these
        # widgets while the local QStackedWidget moves to step 2.
        identity_page = QWidget()
        identity_layout = QVBoxLayout(identity_page)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(5)

        identity_layout.addWidget(_field_label("이름"))
        self.reg_name = QLineEdit()
        self.reg_name.setPlaceholderText("이름을 입력하세요")
        self.reg_name.setAccessibleName("회원가입 이름")
        self._apply_input_style(self.reg_name)
        self.reg_name.setFixedHeight(50)
        identity_layout.addWidget(self.reg_name)

        identity_layout.addWidget(_field_label("이메일"))
        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("example@email.com")
        self.reg_email.setAccessibleName("회원가입 이메일")
        self._apply_input_style(self.reg_email)
        self.reg_email.setFixedHeight(50)
        identity_layout.addWidget(self.reg_email)

        identity_layout.addWidget(_field_label("아이디"))
        username_row = QHBoxLayout()
        username_row.setSpacing(8)
        self.reg_username = QLineEdit()
        self.reg_username.setPlaceholderText("영문, 숫자, 밑줄(_)")
        self.reg_username.setAccessibleName("회원가입 아이디")
        self._apply_input_style(self.reg_username)
        self.reg_username.setFixedHeight(50)
        self.reg_username.textChanged.connect(self._on_reg_username_changed)
        username_row.addWidget(self.reg_username, 1)

        self.btn_check_user = QPushButton("중복확인")
        self.btn_check_user.setFixedSize(104, 48)
        self.btn_check_user.setFont(QFont(fn, 10))
        self.btn_check_user.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_user.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_ELEVATED}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {Colors.BG_HOVER}; color: {Colors.TEXT_PRIMARY}; }}
        """)
        self.btn_check_user.clicked.connect(self._check_username)
        username_row.addWidget(self.btn_check_user, 0)
        identity_layout.addLayout(username_row)

        self.reg_user_status = QLabel("")
        self.reg_user_status.setFont(QFont(fn, 9))
        self.reg_user_status.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        self.reg_user_status.setWordWrap(True)
        self.reg_user_status.setFixedHeight(24)
        identity_layout.addWidget(self.reg_user_status)

        identity_layout.addWidget(_field_label("비밀번호"))
        self.reg_pw = QLineEdit()
        self.reg_pw.setPlaceholderText(f"{MIN_REGISTER_PASSWORD_LENGTH}자 이상 입력하세요")
        self.reg_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_pw.setAccessibleName("회원가입 비밀번호")
        self._apply_input_style(self.reg_pw)
        self.reg_pw.setFixedHeight(50)
        self.reg_pw.textChanged.connect(self._update_password_match_status)
        identity_layout.addWidget(self.reg_pw)

        identity_layout.addWidget(_field_label("비밀번호 확인"))
        self.reg_pw_confirm = QLineEdit()
        self.reg_pw_confirm.setPlaceholderText("비밀번호를 다시 입력")
        self.reg_pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_pw_confirm.setAccessibleName("회원가입 비밀번호 확인")
        self._apply_input_style(self.reg_pw_confirm)
        self.reg_pw_confirm.setFixedHeight(50)
        self.reg_pw_confirm.textChanged.connect(self._update_password_match_status)
        identity_layout.addWidget(self.reg_pw_confirm)

        self.reg_pw_match_status = QLabel("")
        self.reg_pw_match_status.setFont(QFont(fn, 9))
        self.reg_pw_match_status.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; background: transparent;"
        )
        self.reg_pw_match_status.setWordWrap(True)
        self.reg_pw_match_status.setFixedHeight(24)
        identity_layout.addWidget(self.reg_pw_match_status)

        self._register_next_btn = QPushButton("다음")
        self._register_next_btn.setFixedHeight(48)
        self._register_next_btn.setFont(QFont(fn, 11, QFont.Weight.Bold))
        self._register_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._register_next_btn.setStyleSheet(f"""
            QPushButton {{ background: {Gradients.ACCENT_BTN}; color: white; border: none;
                border-radius: 9px; min-height: 48px; }}
            QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}
        """)
        self._register_next_btn.clicked.connect(self._go_register_step_two)
        identity_layout.addWidget(self._register_next_btn)
        self._register_steps.addWidget(identity_page)

        # Step 2: contact and consent.
        consent_page = QWidget()
        consent_layout = QVBoxLayout(consent_page)
        consent_layout.setContentsMargins(0, 0, 0, 0)
        consent_layout.setSpacing(8)
        consent_layout.addWidget(_field_label("연락처"))
        self.reg_contact = QLineEdit()
        self.reg_contact.setPlaceholderText("010-1234-5678")
        self.reg_contact.setAccessibleName("회원가입 연락처")
        self._apply_input_style(self.reg_contact)
        self.reg_contact.setFixedHeight(50)
        consent_layout.addWidget(self.reg_contact)

        consent_title = QLabel("약관 동의")
        consent_title.setFont(QFont(fn, 10, QFont.Weight.Bold))
        consent_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        consent_layout.addWidget(consent_title)

        check_style = f"""
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; background: transparent; font-size: 9.5pt; spacing: 9px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 5px; background: {Colors.BG_INPUT}; }}
            QCheckBox::indicator:checked {{ background: {Colors.ACCENT}; border-color: {Colors.ACCENT}; }}
            QCheckBox::indicator:hover {{ border-color: {Colors.ACCENT}; }}
        """
        self.reg_legal_consent = QCheckBox("필수   이용약관 및 개인정보처리방침에 동의")
        self.reg_legal_consent.setFont(QFont(fn, 9, QFont.Weight.DemiBold))
        self.reg_legal_consent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reg_legal_consent.setMinimumHeight(44)
        self.reg_legal_consent.setStyleSheet(check_style)
        consent_layout.addWidget(self.reg_legal_consent)

        self.reg_news_opt_in = QCheckBox("선택   프로그램 소식과 활용 정보 이메일")
        self.reg_news_opt_in.setFont(QFont(fn, 9))
        self.reg_news_opt_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reg_news_opt_in.setMinimumHeight(44)
        self.reg_news_opt_in.setStyleSheet(check_style)
        consent_layout.addWidget(self.reg_news_opt_in)

        self.reg_legal_links = QLabel(
            f'<a href="{WEBSITE_BASE_URL}/terms" style="color:{Colors.ACCENT_LIGHT};">이용약관 보기</a>'
            f' &nbsp;·&nbsp; '
            f'<a href="{WEBSITE_BASE_URL}/privacy" style="color:{Colors.ACCENT_LIGHT};">개인정보처리방침 보기</a>'
        )
        self.reg_legal_links.setFont(QFont(fn, 9))
        self.reg_legal_links.setOpenExternalLinks(True)
        self.reg_legal_links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.reg_legal_links.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self.reg_legal_links.setWordWrap(True)
        self.reg_legal_links.setToolTip("웹사이트에서 최신 약관과 개인정보처리방침을 확인합니다.")
        consent_layout.addWidget(self.reg_legal_links)

        ready_card = QFrame()
        ready_card.setObjectName("registrationReadyCard")
        ready_card.setMinimumHeight(92)
        ready_card.setStyleSheet(
            f"#registrationReadyCard {{ background: {Colors.BG_SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: 10px; }}"
        )
        ready_layout = QVBoxLayout(ready_card)
        ready_layout.setContentsMargins(16, 12, 16, 12)
        ready_layout.setSpacing(4)
        ready_title = QLabel("가입 후 바로 할 일")
        ready_title.setFont(QFont(fn, 10, QFont.Weight.Bold))
        ready_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        ready_desc = QLabel("Threads 계정을 연결하고 첫 게시 준비를 시작합니다.\n설정은 시작 준비 마법사가 안내합니다.")
        ready_desc.setWordWrap(True)
        ready_desc.setFont(QFont(fn, 9))
        ready_desc.setStyleSheet(f"color: {Colors.TEXT_MUTED}; background: transparent;")
        ready_layout.addWidget(ready_title)
        ready_layout.addWidget(ready_desc)
        consent_layout.addWidget(ready_card)
        consent_layout.addStretch(1)

        self.btn_register = QPushButton("가입하고 시작 준비")
        self.btn_register.setFixedHeight(48)
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
        consent_layout.addWidget(self.btn_register)

        self._register_prev_btn = QPushButton("이전 단계")
        self._register_prev_btn.setMinimumHeight(38)
        self._register_prev_btn.setFont(QFont(fn, 10, QFont.Weight.Bold))
        self._register_prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._register_prev_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Colors.ACCENT_LIGHT}; border: none;
                padding: 0; min-height: 38px; }}
            QPushButton:hover {{ color: {Colors.ACCENT}; text-decoration: underline; }}
        """)
        self._register_prev_btn.clicked.connect(lambda: self._show_register_step(0))
        consent_layout.addWidget(self._register_prev_btn)
        self._register_steps.addWidget(consent_page)
        self._register_steps.currentChanged.connect(lambda _index: self._update_register_step_ui())
        self._register_steps.setCurrentIndex(0)

        self.stack.addWidget(page)

    def _register_back(self):
        if self._register_steps.currentIndex() > 0:
            self._show_register_step(0)
        else:
            self.stack.setCurrentIndex(0)

    def _show_register_step(self, index: int) -> None:
        self._register_steps.setCurrentIndex(max(0, min(1, int(index))))
        self._update_register_step_ui()

    def _go_register_step_two(self) -> None:
        """Validate the local draft before exposing contact and consent."""
        name = self.reg_name.text().strip()
        email = self.reg_email.text().strip()
        username = self.reg_username.text().strip().lower()
        password = self.reg_pw.text()
        confirmation = self.reg_pw_confirm.text()
        if len(name) < 2:
            self._show_msg("이름을 2자 이상 입력해주세요.")
            return
        if not email or "@" not in email or "." not in email:
            self._show_msg("올바른 이메일 주소를 입력해주세요.")
            return
        if len(username) < 4:
            self._show_msg("아이디를 4자 이상 입력해주세요.")
            return
        if not self._username_available or self._username_available_for != username:
            self._show_msg("아이디 중복확인을 해주세요.")
            return
        if len(password) < MIN_REGISTER_PASSWORD_LENGTH:
            self._show_msg(f"비밀번호는 최소 {MIN_REGISTER_PASSWORD_LENGTH}자 이상이어야 합니다.")
            return
        if password != confirmation:
            self._show_msg("비밀번호가 일치하지 않습니다.")
            return
        self._show_register_step(1)
        self.reg_contact.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_register_step_ui(self) -> None:
        if not hasattr(self, "_register_steps"):
            return
        index = self._register_steps.currentIndex()
        self._register_step_text.setText(f"{index + 1} / 2")
        self._register_progress.setValue(index + 1)
        self._register_subtitle.setText(
            "필요한 정보만 입력하세요."
            if index == 0
            else "연락처와 필수 약관을 확인해주세요."
        )
        self._register_back_btn.setText("←  돌아가기" if index == 0 else "←  이전 단계")

    # ─── Style helpers ──────────────────────────────────────
    def _apply_input_style(self, widget):
        widget.setFont(QFont(_get_font(), 11))
        widget.setStyleSheet(
            input_style()
            + "QLineEdit { min-height: 48px; max-height: 48px; }"
        )
        widget.setTextMargins(14, 0, 14, 0)
        widget.setMinimumHeight(48)

    # ─── Login logic ────────────────────────────────────────
    def _do_login(self):
        if self._login_in_flight:
            return

        uid = self.login_id.text().strip()
        pw = self.login_pw.text()

        if not uid or not pw:
            self.login_status.setText("아이디와 비밀번호를 입력해주세요.")
            return
        if len(pw) < MIN_LOGIN_PASSWORD_LENGTH:
            self.login_status.setText(f"비밀번호는 최소 {MIN_LOGIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
            return

        self._login_in_flight = True
        self.btn_login.setEnabled(False)
        self.remember_cb.setEnabled(False)
        self.auto_login_cb.setEnabled(False)
        self.btn_login.setText("로그인 중...")
        self.login_status.setText("")

        # Run login in thread
        self._login_thread = LoginWorker(
            uid,
            pw,
            remember_credentials=self.remember_cb.isChecked(),
            auto_login=self.auto_login_cb.isChecked(),
        )
        self._login_thread.finished_signal.connect(self._on_login_result)
        self._login_thread.start()

    def _on_login_result(self, result: dict):
        self._login_in_flight = False
        self.btn_login.setEnabled(True)
        if hasattr(self, "remember_cb"):
            self.remember_cb.setEnabled(True)
        if hasattr(self, "auto_login_cb"):
            self.auto_login_cb.setEnabled(True)
        self.btn_login.setText("로그인")

        status = result.get("status")
        if status is True:
            logger.info("로그인 성공: user_id=%s", result.get("id") or result.get("user_id"))
            self.login_success.emit(result)
        elif status == "EU003":
            self.login_status.setText(
                "다른 곳에서 이미 로그인되어 있습니다. 기존 기기에서 로그아웃한 뒤 다시 시도해 주세요."
            )
            self.login_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")
        else:
            msg = user_friendly_message(
                auth_client.friendly_login_message(result),
                "로그인에 실패했습니다. 입력한 정보와 네트워크 상태를 확인해주세요.",
            )
            self.login_status.setText(msg)
            self.login_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")

    # ─── Register logic ─────────────────────────────────────
    def _on_reg_username_changed(self):
        self._username_available = False
        self._username_available_for = None
        self._username_check_token += 1
        self.reg_user_status.setText("")

    def _update_password_match_status(self):
        password = self.reg_pw.text()
        confirmation = self.reg_pw_confirm.text()
        if not confirmation:
            self.reg_pw_match_status.setText("")
            self.reg_pw_match_status.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; background: transparent;"
            )
        elif password == confirmation:
            self.reg_pw_match_status.setText("✓ 비밀번호가 일치합니다")
            self.reg_pw_match_status.setStyleSheet(
                f"color: {Colors.SUCCESS}; background: transparent;"
            )
        else:
            self.reg_pw_match_status.setText("✗ 비밀번호가 일치하지 않습니다")
            self.reg_pw_match_status.setStyleSheet(
                f"color: {Colors.ERROR}; background: transparent;"
            )

    def _check_username(self):
        if hasattr(self, "_username_worker") and self._username_worker.isRunning():
            return
        username = self.reg_username.text().strip().lower()
        if not username or len(username) < 4:
            self._show_msg("아이디는 4자 이상이어야 합니다.")
            return
        if not re.match(r'^[a-z0-9_]+$', username):
            self._show_msg("아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.")
            return

        self.btn_check_user.setEnabled(False)
        self.btn_check_user.setText("확인중...")

        self._username_check_token += 1
        token = self._username_check_token
        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(
            lambda available, message, t=token, u=username: self._on_username_checked(
                t, u, available, message
            )
        )
        self._username_worker.start()

    def _on_username_checked(self, token: int, username: str, available: bool, message: str):
        self.btn_check_user.setEnabled(True)
        self.btn_check_user.setText("중복확인")

        current_username = self.reg_username.text().strip().lower()
        if token != self._username_check_token or username != current_username:
            return

        if available:
            self._username_available = True
            self._username_available_for = username
            self.reg_user_status.setText("✓ 사용 가능한 아이디입니다")
            self.reg_user_status.setStyleSheet(f"color: {Colors.SUCCESS}; background: transparent;")
        else:
            self._username_available = False
            self._username_available_for = None
            safe_message = user_friendly_message(
                message,
                "아이디 사용 가능 여부를 확인하지 못했습니다. 잠시 후 다시 시도해주세요.",
            )
            self.reg_user_status.setText(f"✗ {safe_message}")
            self.reg_user_status.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")

    def _do_register(self):
        name = self.reg_name.text().strip()
        email = self.reg_email.text().strip()
        username = self.reg_username.text().strip().lower()
        pw = self.reg_pw.text()
        pw2 = self.reg_pw_confirm.text()
        contact = self.reg_contact.text().strip()
        ym_news_opt_in = bool(self.reg_news_opt_in.isChecked())

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
        if not self._username_available or self._username_available_for != username:
            self._show_msg("아이디 중복확인을 해주세요.")
            return
        if not pw:
            self._show_msg("비밀번호를 입력해주세요.")
            return
        if len(pw) < MIN_REGISTER_PASSWORD_LENGTH:
            self._show_msg(f"비밀번호는 최소 {MIN_REGISTER_PASSWORD_LENGTH}자 이상이어야 합니다.")
            return
        if pw != pw2:
            self._show_msg("비밀번호가 일치하지 않습니다.")
            return
        contact_clean = re.sub(r'[^0-9]', '', contact)
        if len(contact_clean) < 10:
            self._show_msg("올바른 연락처를 입력해주세요.")
            return
        if not self.reg_legal_consent.isChecked():
            self._show_msg("회원가입을 계속하려면 이용약관과 개인정보처리방침에 동의해 주세요.")
            return

        self.btn_register.setEnabled(False)
        self.btn_register.setText("처리 중...")

        self._reg_worker = RegisterWorker(
            name,
            username,
            pw,
            contact_clean,
            email,
            ym_news_opt_in=ym_news_opt_in,
            terms_accepted=True,
            privacy_accepted=True,
        )
        self._reg_worker.finished_signal.connect(self._on_register_result)
        self._reg_worker.start()

    def _on_register_result(self, result: dict):
        self.btn_register.setEnabled(True)
        self.btn_register.setText("가입하고 시작 준비")

        if result.get("success"):
            account = result.get("data") if isinstance(result.get("data"), dict) else {}
            user_id = account.get("user_id")
            token = str(account.get("token") or "").strip()
            if user_id is not None and token:
                username = str(
                    account.get("username") or self.reg_username.text().strip().lower()
                )
                self.login_success.emit(
                    {
                        "status": True,
                        "id": user_id,
                        "user_id": user_id,
                        "username": username,
                        "key": token,
                        "token": token,
                        "work_count": account.get("work_count", 0),
                    }
                )
                return

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
            elif self._register_steps.currentIndex() == 0:
                self._go_register_step_two()
            else:
                self._do_register()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.stack.currentIndex() == 1:
            self._register_back()
            event.accept()
            return
        super().keyPressEvent(event)


# ─── Background Workers ────────────────────────────────────

class LoginWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        username,
        password,
        *,
        remember_credentials=False,
        auto_login=False,
    ):
        super().__init__()
        self.username = username
        self._password_bytes = bytearray(str(password or "").encode("utf-8"))
        self.remember_credentials = bool(remember_credentials)
        self.auto_login = bool(auto_login)

    def run(self):
        password = ""
        result = {"status": False, "message": "로그인 처리 중 오류가 발생했습니다."}
        try:
            password = self._password_bytes.decode("utf-8", errors="ignore")
            result = auth_client.login(self.username, password)
            if result.get("status") is True:
                try:
                    if self.remember_credentials:
                        saved = auth_client.remember_login_credentials(
                            self.username,
                            password,
                            auto_login=self.auto_login,
                        )
                    else:
                        saved = auth_client.remember_login_credentials("", "")
                    if saved is False:
                        logger.warning("로그인 정보의 보안 저장을 완료하지 못했습니다.")
                except Exception:
                    logger.exception("아이디 저장 설정을 반영하지 못했습니다.")
                _queue_telemetry("ui_login_success", "로그인 창에서 로그인 성공")
        except Exception:
            logger.exception("로그인 워커 실행에 실패했습니다.")
            result = {
                "status": False,
                "message": "로그인 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            }
        finally:
            for i in range(len(self._password_bytes)):
                self._password_bytes[i] = 0
            self._password_bytes = bytearray()
            password = None
        self.finished_signal.emit(result)


class RegisterWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        name,
        username,
        password,
        contact,
        email,
        ym_news_opt_in=False,
        terms_accepted=False,
        privacy_accepted=False,
    ):
        super().__init__()
        self.name = name
        self.username = username
        self._password_bytes = bytearray(str(password or "").encode("utf-8"))
        self.contact = contact
        self.email = email
        self.ym_news_opt_in = bool(ym_news_opt_in)
        self.terms_accepted = bool(terms_accepted)
        self.privacy_accepted = bool(privacy_accepted)

    def run(self):
        password = ""
        result = {"success": False, "message": "회원가입 처리 중 오류가 발생했습니다."}
        try:
            password = self._password_bytes.decode("utf-8", errors="ignore")
            result = auth_client.register(
                self.name,
                self.username,
                password,
                self.contact,
                self.email,
                ym_news_opt_in=self.ym_news_opt_in,
                terms_accepted=self.terms_accepted,
                privacy_accepted=self.privacy_accepted,
            )
            if result.get("success"):
                _queue_telemetry(
                    "ui_register_success",
                    f"username={self.username}",
                )
        except Exception:
            logger.exception("회원가입 워커 실행에 실패했습니다.")
            result = {
                "success": False,
                "message": "회원가입 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            }
        finally:
            for i in range(len(self._password_bytes)):
                self._password_bytes[i] = 0
            self._password_bytes = bytearray()
            password = None
        self.finished_signal.emit(result)
