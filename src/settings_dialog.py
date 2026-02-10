"""
Settings Dialog (PyQt5)
Stitch Blue Design
"""
import re
import threading
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QMessageBox, QSpinBox,
    QScrollArea, QWidget
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QPainter, QLinearGradient

from src.config import config
from src.theme import Colors, global_stylesheet


# ─── Events ─────────────────────────────────────────────────

class LoginStatusEvent(QEvent):
    EventType = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result):
        super().__init__(LoginStatusEvent.EventType)
        self.result = result


# ─── Section Card ────────────────────────────────────────────

class SectionCard(QFrame):
    """Settings section with icon, title and content"""
    def __init__(self, title, icon_char="", parent=None):
        super().__init__(parent)
        self._title = title
        self.setObjectName("sectionCard")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(14)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        if icon_char:
            icon = QLabel(icon_char)
            icon.setStyleSheet(f"color: {Colors.ACCENT}; font-size: 14pt; font-weight: 700;")
            icon.setFixedWidth(22)
            title_row.addWidget(icon)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 11pt;
            font-weight: 700;
            background: transparent;
            border: none;
            padding: 0;
        """)
        title_row.addWidget(title_label)
        title_row.addStretch()
        self._layout.addLayout(title_row)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; border: none;")
        self._layout.addWidget(sep)

    def content_layout(self):
        return self._layout

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(Colors.BORDER))
        painter.setBrush(QColor(Colors.BG_CARD))
        painter.drawRoundedRect(
            self.rect().adjusted(0, 0, -1, -1), 12, 12
        )


# ─── Form Field ─────────────────────────────────────────────

class FormField(QWidget):
    """Label + input pair"""
    def __init__(self, label_text, input_widget, hint="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        top.addWidget(label)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 8pt;")
            top.addStretch()
            top.addWidget(hint_label)

        layout.addLayout(top)
        layout.addWidget(input_widget)


# ─── Dialog Header ──────────────────────────────────────────

class DialogHeader(QFrame):
    """Dialog top bar with blur-style gradient"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(Colors.BG_CARD))
        grad.setColorAt(0.5, QColor("#131A2A"))
        grad.setColorAt(1, QColor(Colors.BG_CARD))
        painter.fillRect(self.rect(), grad)
        painter.setPen(QColor(Colors.BORDER))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Settings Dialog ────────────────────────────────────────

class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(540, 740)
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
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = DialogHeader()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        close_btn = QPushButton("X")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                border: none;
                border-radius: 8px;
                font-size: 11pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)

        title = QLabel("Automation Settings")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 14pt; font-weight: 700; letter-spacing: -0.3px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        accent_icon = QLabel("*")
        accent_icon.setStyleSheet(f"color: {Colors.ACCENT}; font-size: 16pt; font-weight: 700;")
        header_layout.addWidget(accent_icon)

        root.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {Colors.BG_DARK};
                border: none;
            }}
        """)

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
        root.addWidget(scroll, 1)

        # Footer buttons
        footer = QFrame()
        footer.setFixedHeight(62)
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(100, 38)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setProperty("class", "ghost")
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedSize(120, 38)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_settings)
        footer_layout.addWidget(self.save_btn)

        root.addWidget(footer)

    # ── Sections ──

    def _build_api_section(self):
        section = SectionCard("API Configuration", "*")
        layout = section.content_layout()

        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_key_edit.setPlaceholderText("Enter your Gemini API key")
        layout.addWidget(FormField("Master API Key", self.gemini_key_edit, "from Google AI Studio"))

        self.content_layout.addWidget(section)

    def _build_upload_section(self):
        section = SectionCard("Upload Settings", "*")
        layout = section.content_layout()

        # Interval
        interval_widget = QWidget()
        interval_row = QHBoxLayout(interval_widget)
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(10)

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setFixedWidth(72)
        self.hour_spin.setSuffix(" h")
        interval_row.addWidget(self.hour_spin)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setFixedWidth(72)
        self.min_spin.setSuffix(" m")
        interval_row.addWidget(self.min_spin)

        self.sec_spin = QSpinBox()
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setFixedWidth(72)
        self.sec_spin.setSuffix(" s")
        interval_row.addWidget(self.sec_spin)

        interval_row.addStretch()

        layout.addWidget(FormField("Upload Interval", interval_widget, "min 30s"))

        self.video_check = QCheckBox("Prefer video over image uploads")
        self.video_check.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 10pt;")
        layout.addWidget(self.video_check)

        self.content_layout.addWidget(section)

    def _build_telegram_section(self):
        section = SectionCard("Telegram Notifications", "*")
        layout = section.content_layout()

        self.telegram_check = QCheckBox("Enable Telegram alerts")
        self.telegram_check.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 10pt;")
        layout.addWidget(self.telegram_check)

        self.bot_token_edit = QLineEdit()
        self.bot_token_edit.setEchoMode(QLineEdit.Password)
        self.bot_token_edit.setPlaceholderText("BotFather token")
        layout.addWidget(FormField("Bot Token", self.bot_token_edit))

        self.chat_id_edit = QLineEdit()
        self.chat_id_edit.setPlaceholderText("Your Chat ID")
        layout.addWidget(FormField("Chat ID", self.chat_id_edit))

        self.content_layout.addWidget(section)

    def _build_threads_section(self):
        section = SectionCard("Threads Account", "*")
        layout = section.content_layout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("e.g. myaccount")
        layout.addWidget(FormField("Account Name", self.username_edit, "for profile identification"))

        # Status indicator
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

        self.login_status_label = QLabel("Disconnected")
        self.login_status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt; font-weight: 600;")
        status_row.addWidget(self.login_status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Login buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.threads_login_btn = QPushButton("Login with Threads")
        self.threads_login_btn.setFixedHeight(40)
        self.threads_login_btn.setCursor(Qt.PointingHandCursor)
        self.threads_login_btn.clicked.connect(self._open_threads_login)
        btn_row.addWidget(self.threads_login_btn)

        self.check_login_btn = QPushButton("Check Status")
        self.check_login_btn.setFixedHeight(40)
        self.check_login_btn.setCursor(Qt.PointingHandCursor)
        self.check_login_btn.setProperty("class", "ghost")
        self.check_login_btn.clicked.connect(self._check_login_status)
        btn_row.addWidget(self.check_login_btn)

        layout.addLayout(btn_row)

        # Hint
        hint1 = QLabel("Close the browser after login to auto-save session.")
        hint1.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 8pt;")
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
            QMessageBox.information(self, "Notice", "Minimum upload interval is 30 seconds.")

        config.gemini_api_key = self.gemini_key_edit.text().strip()
        config.upload_interval = interval
        config.prefer_video = self.video_check.isChecked()
        config.telegram_enabled = self.telegram_check.isChecked()
        config.telegram_bot_token = self.bot_token_edit.text().strip()
        config.telegram_chat_id = self.chat_id_edit.text().strip()
        config.instagram_username = self.username_edit.text().strip()

        config.save()

        QMessageBox.information(self, "Saved", "Settings have been saved.")
        self.accept()

    # ── Threads Login ──

    @staticmethod
    def _sanitize_profile_name(username):
        """Sanitize username for use as profile directory name."""
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
            QMessageBox.warning(self, "Notice", "Please enter an account name first.")
            return

        config.instagram_username = username
        config.save()

        self.threads_login_btn.setEnabled(False)
        self.threads_login_btn.setText("Opening...")
        self._update_login_status("pending", "Browser opening...")

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
                print(f"Browser error: {e}")

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, self._restore_login_btn)

    def _restore_login_btn(self):
        if self._closed:
            return
        self.threads_login_btn.setEnabled(True)
        self.threads_login_btn.setText("Login with Threads")

    def _check_login_status(self):
        self.check_login_btn.setEnabled(False)
        self.check_login_btn.setText("Checking...")
        self._update_login_status("pending", "Checking...")

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
                print(f"Login check error: {e}")
                return False, None

        def run_check():
            result = check_status()
            if self._closed:
                return
            from PyQt5.QtWidgets import QApplication
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
            self.check_login_btn.setText("Check Status")

            if is_logged_in:
                name = f"@{username}" if username else "Connected"
                self._update_login_status("success", name)
            else:
                self._update_login_status("error", "Disconnected")
            return True
        return super().event(event)
