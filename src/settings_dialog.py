"""
설정 다이얼로그 (PyQt6)
Stitch Blue 디자인 - 좌표 기반 배치
"""
import re
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QSpinBox,
    QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QPainter, QLinearGradient

from src.config import config
from src.theme import (
    Colors, Radius, Spacing, Gradients, Typography,
    section_title_style, section_icon_style, header_title_style,
    close_btn_style, ghost_btn_style, accent_btn_style,
    input_style, muted_text_style, hint_text_style,
    scroll_area_style, dialog_style, global_stylesheet
)
from src.ui_messages import show_info, show_warning


# ─── Events ─────────────────────────────────────────────────

class LoginStatusEvent(QEvent):
    EventType = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result):
        super().__init__(LoginStatusEvent.EventType)
        self.result = result


# ─── Section Card ────────────────────────────────────────────

class SectionCard(QFrame):
    """설정 섹션 카드 (아이콘 + 제목 + 내용)"""
    def __init__(self, title, icon_char="", parent=None):
        super().__init__(parent)
        self._title = title
        self.setObjectName("sectionCard")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(14)

        # 제목 행
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        if icon_char:
            icon = QLabel(icon_char)
            icon.setStyleSheet(section_icon_style())
            icon.setFixedWidth(22)
            title_row.addWidget(icon)

        title_label = QLabel(title)
        title_label.setStyleSheet(section_title_style())
        title_row.addWidget(title_label)
        title_row.addStretch()
        self._layout.addLayout(title_row)

        # 구분선
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self._layout.addWidget(sep)

    def content_layout(self):
        return self._layout

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(Colors.BORDER))
        painter.setBrush(QColor(Colors.BG_CARD))
        painter.drawRoundedRect(
            self.rect().adjusted(0, 0, -1, -1), 12, 12
        )


# ─── Form Field ─────────────────────────────────────────────

class FormField(QWidget):
    """레이블 + 입력 위젯 쌍"""
    def __init__(self, label_text, input_widget, hint="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; letter-spacing: 0.5px;"
        )
        top.addWidget(label)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setStyleSheet(hint_text_style())
            top.addStretch()
            top.addWidget(hint_label)

        layout.addLayout(top)
        layout.addWidget(input_widget)


# ─── Dialog Header ──────────────────────────────────────────

class DialogHeader(QFrame):
    """다이얼로그 상단 바 (그라디언트 배경)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(Colors.BG_CARD))
        grad.setColorAt(0.5, QColor("#131A2A"))
        grad.setColorAt(1, QColor(Colors.BG_CARD))
        painter.fillRect(self.rect(), grad)
        painter.setPen(QColor(Colors.BORDER))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Settings Dialog ────────────────────────────────────────

class SettingsDialog(QDialog):
    """자동화 설정 다이얼로그 - 좌표 기반 배치"""

    DLG_W = 540
    DLG_H = 740
    HEADER_H = 54
    FOOTER_H = 62

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(self.DLG_W, self.DLG_H)
        self.setModal(True)

        self._closed = False
        self._browser_cancel = threading.Event()

        self._build_ui()
        self.setStyleSheet(global_stylesheet())
        self._load_settings()

    def done(self, result):
        self._closed = True
        self._browser_cancel.set()
        super().done(result)

    def _build_ui(self):
        # 최상위에 레이아웃 없이 좌표 기반 배치

        # ── 헤더 ──
        header = DialogHeader(self)
        header.setGeometry(0, 0, self.DLG_W, self.HEADER_H)

        close_btn = QPushButton("\u2715", header)
        close_btn.setGeometry(12, 11, 32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(close_btn_style())
        close_btn.clicked.connect(self.reject)

        title = QLabel("자동화 설정", header)
        title.setGeometry(52, 10, 350, 34)
        title.setStyleSheet(header_title_style("14pt"))

        accent_icon = QLabel("*", header)
        accent_icon.setGeometry(self.DLG_W - 42, 14, 22, 26)
        accent_icon.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 16pt; font-weight: 700; background: transparent;"
        )

        # ── 스크롤 영역 ──
        scroll_h = self.DLG_H - self.HEADER_H - self.FOOTER_H
        scroll = QScrollArea(self)
        scroll.setGeometry(0, self.HEADER_H, self.DLG_W, scroll_h)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(scroll_area_style())

        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(16, 14, 16, 14)
        self.content_layout.setSpacing(12)

        self._build_api_section()
        self._build_upload_section()
        self._build_telegram_section()
        self._build_threads_section()

        self.content_layout.addStretch()
        scroll.setWidget(scroll_content)

        # ── 푸터 ──
        footer_y = self.DLG_H - self.FOOTER_H
        footer = QFrame(self)
        footer.setGeometry(0, footer_y, self.DLG_W, self.FOOTER_H)
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)

        # 저장 버튼 (오른쪽)
        self.save_btn = QPushButton("저장", footer)
        self.save_btn.setGeometry(self.DLG_W - 20 - 100, 12, 100, 38)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_settings)

        # 취소 버튼
        self.cancel_btn = QPushButton("취소", footer)
        self.cancel_btn.setGeometry(self.DLG_W - 20 - 100 - 10 - 90, 12, 90, 38)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setProperty("class", "ghost")
        self.cancel_btn.clicked.connect(self.reject)

    # ── Sections ──

    def _build_api_section(self):
        section = SectionCard("API 설정", "*")
        layout = section.content_layout()

        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("Gemini API 키를 입력하세요")
        layout.addWidget(FormField("마스터 API 키", self.gemini_key_edit, "Google AI Studio에서 발급"))

        self.content_layout.addWidget(section)

    def _build_upload_section(self):
        section = SectionCard("업로드 설정", "*")
        layout = section.content_layout()

        # 업로드 간격
        interval_widget = QWidget()
        interval_row = QHBoxLayout(interval_widget)
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(10)

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setFixedWidth(80)
        self.hour_spin.setSuffix(" 시간")
        interval_row.addWidget(self.hour_spin)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setFixedWidth(72)
        self.min_spin.setSuffix(" 분")
        interval_row.addWidget(self.min_spin)

        self.sec_spin = QSpinBox()
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setFixedWidth(72)
        self.sec_spin.setSuffix(" 초")
        interval_row.addWidget(self.sec_spin)

        interval_row.addStretch()

        layout.addWidget(FormField("업로드 간격", interval_widget, "최소 30초"))

        self.video_check = QCheckBox("이미지보다 영상 업로드 우선")
        layout.addWidget(self.video_check)

        self.content_layout.addWidget(section)

    def _build_telegram_section(self):
        section = SectionCard("텔레그램 알림", "*")
        layout = section.content_layout()

        self.telegram_check = QCheckBox("텔레그램 알림 활성화")
        layout.addWidget(self.telegram_check)

        self.bot_token_edit = QLineEdit()
        self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bot_token_edit.setPlaceholderText("BotFather 토큰")
        layout.addWidget(FormField("봇 토큰", self.bot_token_edit))

        self.chat_id_edit = QLineEdit()
        self.chat_id_edit.setPlaceholderText("채팅 ID")
        layout.addWidget(FormField("채팅 ID", self.chat_id_edit))

        self.content_layout.addWidget(section)

    def _build_threads_section(self):
        section = SectionCard("Threads 계정", "*")
        layout = section.content_layout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("예: myaccount")
        layout.addWidget(FormField("계정 이름", self.username_edit, "프로필 식별용"))

        # 상태 표시
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        status_dot = QLabel()
        status_dot.setFixedSize(10, 10)
        status_dot.setStyleSheet(f"""
            background-color: {Colors.TEXT_MUTED};
            border-radius: 5px;
        """)
        self._status_dot = status_dot
        status_row.addWidget(status_dot)

        self.login_status_label = QLabel("연결 안됨")
        self.login_status_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;"
        )
        status_row.addWidget(self.login_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # 로그인 버튼들
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.threads_login_btn = QPushButton("Threads 로그인")
        self.threads_login_btn.setFixedHeight(40)
        self.threads_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)
        btn_row.addWidget(self.threads_login_btn)

        self.check_login_btn = QPushButton("상태 확인")
        self.check_login_btn.setFixedHeight(40)
        self.check_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_login_btn.setProperty("class", "ghost")
        self.check_login_btn.clicked.connect(self._check_login_status)
        btn_row.addWidget(self.check_login_btn)

        layout.addLayout(btn_row)

        # 안내 문구
        hint1 = QLabel("로그인 후 브라우저를 닫으면 세션이 자동 저장됩니다.")
        hint1.setStyleSheet(hint_text_style())
        layout.addWidget(hint1)

        self.content_layout.addWidget(section)

    # ── Data ──

    def _load_settings(self):
        self.gemini_key_edit.setText(config.gemini_api_key)

        total = config.upload_interval
        self.hour_spin.setValue(total // 3600)
        self.min_spin.setValue((total % 3600) // 60)
        self.sec_spin.setValue(total % 60)

        self.video_check.setChecked(config.prefer_video)
        self.telegram_check.setChecked(config.telegram_enabled)
        self.bot_token_edit.setText(config.telegram_bot_token)
        self.chat_id_edit.setText(config.telegram_chat_id)
        self.username_edit.setText(config.instagram_username)

    def _save_settings(self):
        interval = (
            self.hour_spin.value() * 3600 +
            self.min_spin.value() * 60 +
            self.sec_spin.value()
        )
        if interval < 30:
            interval = 30
            show_info(self, "알림", "최소 업로드 간격은 30초입니다.")

        config.gemini_api_key = self.gemini_key_edit.text().strip()
        config.upload_interval = interval
        config.prefer_video = self.video_check.isChecked()
        config.telegram_enabled = self.telegram_check.isChecked()
        config.telegram_bot_token = self.bot_token_edit.text().strip()
        config.telegram_chat_id = self.chat_id_edit.text().strip()
        config.instagram_username = self.username_edit.text().strip()

        config.save()

        show_info(self, "저장 완료", "설정이 저장되었습니다.")
        self.accept()

    # ── Threads Login ──

    @staticmethod
    def _sanitize_profile_name(username):
        """프로필 디렉터리 이름용 사용자명 정리"""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def _get_profile_dir(self):
        username = self.username_edit.text().strip()
        if username:
            profile_name = self._sanitize_profile_name(username)
            return f".threads_profile_{profile_name}"
        return ".threads_profile"

    def _open_threads_login(self):
        username = self.username_edit.text().strip()
        if not username:
            show_warning(self, "알림", "먼저 계정 이름을 입력하세요.")
            return

        config.instagram_username = username
        config.save()

        self.threads_login_btn.setEnabled(False)
        self.threads_login_btn.setText("여는 중...")
        self._update_login_status("pending", "브라우저 여는 중...")

        self._browser_cancel.clear()
        cancel_event = self._browser_cancel

        def open_browser():
            try:
                from src.computer_use_agent import ComputerUseAgent

                profile_dir = self._get_profile_dir()
                agent = ComputerUseAgent(
                    api_key=config.gemini_api_key,
                    headless=False,
                    profile_dir=profile_dir
                )
                agent.start_browser()
                agent.page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=30000)

                import time
                for _ in range(300):
                    if cancel_event.is_set():
                        break
                    time.sleep(1)
                    try:
                        agent.page.url
                    except Exception:
                        break

                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    pass

            except Exception as e:
                print(f"브라우저 오류: {e}")

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, self._restore_login_btn)

    def _restore_login_btn(self):
        if self._closed:
            return
        self.threads_login_btn.setEnabled(True)
        self.threads_login_btn.setText("Threads 로그인")

    def _check_login_status(self):
        self.check_login_btn.setEnabled(False)
        self.check_login_btn.setText("확인 중...")
        self._update_login_status("pending", "확인 중...")

        def check_status():
            try:
                from src.computer_use_agent import ComputerUseAgent
                from src.threads_playwright_helper import ThreadsPlaywrightHelper

                profile_dir = self._get_profile_dir()
                agent = ComputerUseAgent(
                    api_key=config.gemini_api_key,
                    headless=True,
                    profile_dir=profile_dir
                )
                agent.start_browser()

                try:
                    agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                    import time
                    time.sleep(2)

                    helper = ThreadsPlaywrightHelper(agent.page)
                    is_logged_in = helper.check_login_status()
                    logged_user = helper.get_logged_in_username() if is_logged_in else None

                    return is_logged_in, logged_user
                finally:
                    try:
                        agent.close()
                    except Exception:
                        pass

            except Exception as e:
                print(f"로그인 확인 오류: {e}")
                return False, None

        def run_check():
            result = check_status()
            if self._closed:
                return
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.postEvent(self, LoginStatusEvent(result))

        thread = threading.Thread(target=run_check, daemon=True)
        thread.start()

    def _update_login_status(self, state, text):
        color_map = {
            "success": Colors.SUCCESS,
            "error": Colors.ERROR,
            "pending": Colors.WARNING,
            "unknown": Colors.TEXT_MUTED,
        }
        color = color_map.get(state, Colors.TEXT_MUTED)
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self.login_status_label.setText(text)
        self.login_status_label.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: 600;")

    def event(self, event):
        if event.type() == LoginStatusEvent.EventType:
            if self._closed:
                return True
            is_logged_in, username = event.result
            self.check_login_btn.setEnabled(True)
            self.check_login_btn.setText("상태 확인")

            if is_logged_in:
                name = f"@{username}" if username else "연결됨"
                self._update_login_status("success", name)
            else:
                self._update_login_status("error", "연결 안됨")
            return True
        return super().event(event)
