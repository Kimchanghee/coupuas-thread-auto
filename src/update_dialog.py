"""Responsive update center used by both manual and automatic checks."""

from typing import ClassVar

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.app_icon import apply_window_icon
from src.auto_updater import AutoUpdater
from src.theme import Colors, Gradients, Radius, progress_bar_style
from src.ui_messages import user_friendly_message


class UpdateCheckThread(QThread):
    """Check GitHub releases without blocking the Qt event loop."""

    update_found = pyqtSignal(dict)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            update_info = AutoUpdater(self.current_version).check_for_updates()
            if update_info:
                self.update_found.emit(update_info)
            else:
                self.no_update.emit()
        except Exception as exc:  # noqa: BLE001 - worker must convert every provider failure to UI state
            self.error.emit(
                user_friendly_message(
                    exc,
                    "업데이트 정보를 확인하지 못했습니다. 네트워크 연결을 확인해주세요.",
                )
            )


class UpdateDialog(QDialog):
    """Polished update center with six explicit, testable UI states."""

    install_requested = pyqtSignal(object)
    VALID_STATES: ClassVar[set[str]] = {
        "checking",
        "latest",
        "available",
        "downloading",
        "installing",
        "error",
    }

    def __init__(self, current_version: str, parent=None, *, update_info=None):
        super().__init__(parent)
        self.current_version = str(current_version or "").strip() or "알 수 없음"
        self.update_info = None
        self._busy = False
        self._check_thread = None
        self._state = "checking"

        self.setWindowTitle("Thread Auto 업데이트")
        self.setModal(False)
        self.setMinimumSize(560, 520)
        self.setSizeGripEnabled(True)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(660, max(560, available.width() - 48)),
                min(600, max(520, available.height() - 48)),
            )
        else:
            self.resize(640, 580)
        self.setFont(QApplication.font())
        apply_window_icon(self)

        self._build_ui()
        if isinstance(update_info, dict) and update_info:
            self._on_update_found(update_info)
        else:
            self._check_for_updates()

    def _build_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
            }}
            QFrame#updateHero {{
                background: {getattr(Colors, 'INK', '#101C24')};
                border: 1px solid {getattr(Colors, 'INK', '#101C24')};
                border-radius: {Radius.XL};
            }}
            QLabel {{ background: transparent; }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 16, 28, 16)
        root.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.header_title = QLabel("업데이트 센터")
        self.header_title.setFont(self._ui_font(18, QFont.Weight.Bold))
        self.header_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        subtitle = QLabel("안전하게 내려받고, 설치 후 하던 작업을 이어갈 수 있어요.")
        subtitle.setFont(self._ui_font(10.5))
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        subtitle.setWordWrap(True)
        title_box.addWidget(self.header_title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box, 1)
        self.state_badge = QLabel("확인 중")
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_badge.setMinimumSize(84, 30)
        self.state_badge.setStyleSheet(
            f"background: {Colors.ACCENT_SUBTLE}; color: {Colors.ACCENT_LIGHT};"
            f"border: 1px solid {Colors.INFO_BORDER}; border-radius: 14px;"
            "font-size: 9.5pt; font-weight: 800; letter-spacing: 0.3px;"
        )
        top.addWidget(self.state_badge, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        hero = QFrame()
        hero.setObjectName("updateHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 14, 20, 14)
        hero_layout.setSpacing(8)

        version_row = QHBoxLayout()
        version_row.setSpacing(12)
        current_box = self._version_box("현재 버전", self.current_version, "#FFFFFF")
        self.target_version_value = QLabel("확인 중")
        target_box = self._version_box(
            "새 버전", "", "#25B9BC", self.target_version_value
        )
        version_row.addWidget(current_box, 1)
        version_row.addWidget(target_box, 1)
        hero_layout.addLayout(version_row)

        self.status_label = QLabel("최신 버전을 확인하고 있어요")
        self.status_label.setFont(self._ui_font(12, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #FFFFFF;")
        self.status_label.setWordWrap(True)
        hero_layout.addWidget(self.status_label)

        self.status_detail = QLabel("잠시만 기다려 주세요.")
        self.status_detail.setFont(self._ui_font(9.5))
        self.status_detail.setStyleSheet("color: #B8C7CB;")
        self.status_detail.setWordWrap(True)
        hero_layout.addWidget(self.status_detail)
        root.addWidget(hero)

        changelog_header = QHBoxLayout()
        changelog_title = QLabel("이번 버전에서 달라진 점")
        changelog_title.setFont(self._ui_font(10.5, QFont.Weight.Bold))
        changelog_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        changelog_header.addWidget(changelog_title)
        changelog_header.addStretch()
        self.size_label = QLabel("")
        self.size_label.setFont(self._ui_font(9.5))
        self.size_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        changelog_header.addWidget(self.size_label)
        root.addLayout(changelog_header)

        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setMinimumHeight(72)
        self.changelog_text.setFont(self._ui_font(10.5))
        self.changelog_text.setPlaceholderText("업데이트 내용을 불러오는 중입니다.")
        self.changelog_text.setStyleSheet(
            f"QTextEdit {{ background-color: {Colors.BG_INPUT}; color: {Colors.TEXT_PRIMARY};"
            f"border: 1px solid {Colors.BORDER}; border-radius: {Radius.LG};"
            "padding: 14px; line-height: 1.5; }"
        )
        root.addWidget(self.changelog_text, 1)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(10)
        self.progress_bar.setStyleSheet(progress_bar_style())
        self.progress_bar.setVisible(False)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        self.progress_label.setMinimumWidth(44)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.progress_label.setStyleSheet(f"color: {Colors.ACCENT_LIGHT}; font-weight: 700;")
        self.progress_label.setVisible(False)
        progress_row.addWidget(self.progress_label)
        root.addLayout(progress_row)

        self.safety_frame = QFrame()
        self.safety_frame.setObjectName("updateSafetyFrame")
        self.safety_frame.setMinimumHeight(54)
        self.safety_frame.setStyleSheet(
            f"#updateSafetyFrame {{ background: {Colors.INFO_BG}; border: 1px solid {Colors.INFO_BORDER};"
            f" border-radius: {Radius.MD}; }}"
        )
        safety_layout = QHBoxLayout(self.safety_frame)
        safety_layout.setContentsMargins(14, 8, 14, 8)
        safety_layout.setSpacing(10)
        safety_icon = QLabel("✓")
        safety_icon.setFont(self._ui_font(14, QFont.Weight.Bold))
        safety_icon.setStyleSheet(f"color: {Colors.ACCENT};")
        self.safety_label = QLabel("현재 대기열은 자동 저장됩니다. 설치 후 중단 지점부터 이어서 시작합니다.")
        self.safety_label.setWordWrap(True)
        self.safety_label.setFont(self._ui_font(8.5))
        self.safety_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        safety_layout.addWidget(safety_icon)
        safety_layout.addWidget(self.safety_label, 1)
        root.addWidget(self.safety_frame)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        self.manual_download_btn = QPushButton("설치 파일 받기")
        self.manual_download_btn.setMinimumSize(140, 48)
        self.manual_download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_download_btn.setVisible(False)
        self.manual_download_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Colors.ACCENT_LIGHT};"
            f"border: 1px solid {Colors.ACCENT_DARK}; border-radius: {Radius.MD};"
            "padding: 0 18px; min-height: 48px; max-height: 48px;"
            "font-size: 10.5pt; font-weight: 700; }"
            f"QPushButton:hover {{ background: {Colors.ACCENT_SUBTLE}; }}"
        )
        self.manual_download_btn.setFixedHeight(48)
        self.manual_download_btn.clicked.connect(self._open_manual_download)
        buttons.addWidget(self.manual_download_btn)

        self.close_btn = QPushButton("나중에")
        self.close_btn.setMinimumSize(120, 48)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Colors.TEXT_SECONDARY};"
            f"border: 1px solid {Colors.BORDER_LIGHT}; border-radius: {Radius.MD};"
            "padding: 0 22px; min-height: 48px; max-height: 48px;"
            "font-size: 10.5pt; font-weight: 700; }"
            f"QPushButton:hover {{ background: {Colors.BG_HOVER}; color: {Colors.TEXT_PRIMARY}; }}"
        )
        self.close_btn.setFixedHeight(48)
        self.close_btn.clicked.connect(self.close)
        buttons.addWidget(self.close_btn)

        self.install_btn = QPushButton("지금 업데이트")
        self.install_btn.setMinimumSize(176, 48)
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.setEnabled(False)
        self.install_btn.setStyleSheet(
            f"QPushButton {{ background: {Gradients.ACCENT_BTN}; color: #FFFFFF; border: none;"
            f"border-radius: {Radius.MD}; padding: 0 26px; min-height: 48px; max-height: 48px;"
            "font-size: 10.5pt; font-weight: 800; }"
            f"QPushButton:hover {{ background: {Gradients.ACCENT_BTN_HOVER}; }}"
            f"QPushButton:pressed {{ background: {Gradients.ACCENT_BTN_PRESSED}; }}"
            f"QPushButton:disabled {{ background: {Colors.BG_ELEVATED}; color: {Colors.TEXT_MUTED}; }}"
        )
        self.install_btn.setFixedHeight(48)
        self.install_btn.clicked.connect(self._request_install)
        buttons.addWidget(self.install_btn)
        root.addLayout(buttons)

        # Compatibility alias for older callers and UI tests.
        self.download_btn = self.install_btn
        self._set_state("checking")

    @property
    def state(self):
        """Current presentation state for automation and accessibility tests."""
        return self._state

    def _set_state(self, state):
        if state not in self.VALID_STATES:
            raise ValueError(f"Unknown update dialog state: {state}")
        self._state = state
        labels = {
            "checking": "확인 중",
            "latest": "최신",
            "available": "UPDATE",
            "downloading": "다운로드",
            "installing": "설치 중",
            "error": "다시 확인",
        }
        self.state_badge.setText(labels[state])
        is_error = state == "error"
        self.state_badge.setStyleSheet(
            f"background: {Colors.ERROR_BG if is_error else Colors.ACCENT_SUBTLE};"
            f" color: {Colors.ERROR if is_error else Colors.ACCENT_LIGHT};"
            f" border: 1px solid {Colors.ERROR_BORDER if is_error else Colors.INFO_BORDER};"
            " border-radius: 14px; font-size: 9.5pt; font-weight: 800; letter-spacing: 0.3px;"
        )

    def _ui_font(self, point_size, weight=None):
        """Return the same family used by the rest of the application."""
        font = QFont(self.font())
        font.setPointSizeF(float(point_size))
        if weight is not None:
            font.setWeight(weight)
        return font

    def _version_box(self, caption, value, color, value_label=None):
        frame = QFrame()
        frame.setObjectName("updateVersionBox")
        frame.setStyleSheet(
            "QFrame#updateVersionBox { background-color: rgba(255, 255, 255, 0.04);"
            " border: 1px solid rgba(255, 255, 255, 0.12);"
            f"border-radius: {Radius.MD}; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)
        caption_label = QLabel(caption)
        caption_label.setFont(self._ui_font(9))
        caption_label.setStyleSheet("color: #B8C7CB; border: none;")
        layout.addWidget(caption_label)
        label = value_label or QLabel(value)
        label.setText(value or label.text())
        label.setWordWrap(True)
        label.setMinimumHeight(34)
        label.setToolTip(label.text())
        label.setFont(self._ui_font(12, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(label)
        return frame

    def set_checking(self):
        """Render the checking state without starting external I/O."""
        self._busy = True
        self._set_state("checking")
        self.header_title.setText("업데이트를 확인하고 있어요")
        self.target_version_value.setText("확인 중")
        self.status_label.setText("최신 버전을 확인하고 있어요")
        self.status_label.setStyleSheet("color: #FFFFFF;")
        self.status_detail.setText("잠시만 기다려 주세요.")
        self.install_btn.setVisible(True)
        self.install_btn.setText("확인 중")
        self.install_btn.setEnabled(False)
        self.close_btn.setVisible(True)
        self.close_btn.setText("나중에")
        self.close_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

    def _check_for_updates(self):
        if self._check_thread is not None and self._check_thread.isRunning():
            return
        self.set_checking()
        self._check_thread = UpdateCheckThread(self.current_version)
        self._check_thread.update_found.connect(self._on_update_found)
        self._check_thread.no_update.connect(self._on_no_update)
        self._check_thread.error.connect(self._on_check_error)
        self._check_thread.start()

    def _on_update_found(self, update_info):
        self._busy = False
        self._set_state("available")
        self.update_info = dict(update_info)
        version = str(update_info.get("version", "") or "").strip()
        self.header_title.setText("새 업데이트가 준비되었습니다")
        self.target_version_value.setText(version or "새 버전")
        self.status_label.setText(f"{version or '새 버전'} 업데이트를 사용할 수 있어요")
        self.status_label.setStyleSheet(f"color: {Colors.SUCCESS};")
        size_mb = float(update_info.get("size_mb", 0) or 0)
        self.size_label.setText(f"약 {size_mb:.1f} MB" if size_mb else "")
        self.status_detail.setText("업데이트 후 프로그램이 자동으로 다시 시작됩니다.")
        changelog = AutoUpdater.get_changelog_summary(update_info.get("changelog", ""))
        self.changelog_text.setPlainText(changelog or "안정성과 사용성을 개선했습니다.")
        self.install_btn.setVisible(True)
        self.install_btn.setText("지금 업데이트")
        self.install_btn.setEnabled(True)
        self.manual_download_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.close_btn.setVisible(True)
        self.close_btn.setText("나중에")
        self.close_btn.setEnabled(True)
        self.safety_label.setText("현재 대기열은 자동 저장됩니다. 설치 후 중단 지점부터 이어서 시작합니다.")

    def _on_no_update(self):
        self._busy = False
        self._set_state("latest")
        self.header_title.setText("최신 버전을 사용 중입니다")
        self.target_version_value.setText(self.current_version)
        self.status_label.setText("현재 최신 버전을 사용하고 있어요")
        self.status_label.setStyleSheet(f"color: {Colors.SUCCESS};")
        self.status_detail.setText("새 업데이트가 나오면 실행 중에도 자동으로 알려드릴게요.")
        self.changelog_text.setPlainText("추가로 설치할 업데이트가 없습니다.")
        self.install_btn.setVisible(False)
        self.manual_download_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.close_btn.setVisible(True)
        self.close_btn.setText("확인")
        self.close_btn.setEnabled(True)
        self.safety_label.setText("추가로 설치할 항목이 없습니다. 새 버전이 있으면 실행 중에 알려드립니다.")

    def _on_check_error(self, error_message):
        self._busy = False
        self._set_state("error")
        self.header_title.setText("업데이트를 확인하지 못했어요")
        self.target_version_value.setText("확인 실패")
        self.status_label.setText("업데이트 정보를 확인하지 못했어요")
        self.status_label.setStyleSheet(f"color: {Colors.ERROR};")
        self.status_detail.setText(
            user_friendly_message(
                error_message,
                "업데이트 정보를 확인하지 못했습니다. 네트워크 연결을 확인해주세요.",
            )
        )
        self.changelog_text.setPlainText("잠시 후 다시 시도해 주세요.")
        self.install_btn.setVisible(True)
        self.install_btn.setText("다시 확인")
        self.install_btn.setEnabled(True)
        self.manual_download_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.close_btn.setVisible(True)
        self.close_btn.setEnabled(True)
        self.safety_label.setText("현재 작업과 대기열에는 영향이 없습니다. 네트워크를 확인한 뒤 다시 시도하세요.")

    def _request_install(self):
        if self._busy:
            return
        if not isinstance(self.update_info, dict):
            if self._state == "error":
                self._check_for_updates()
            return
        self._busy = True
        self._set_state("downloading")
        self.header_title.setText("업데이트를 준비하고 있어요")
        self.manual_download_btn.setVisible(False)
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("0%")
        self.progress_label.setVisible(True)
        self.status_label.setText("업데이트를 준비하고 있어요")
        self.status_label.setStyleSheet(f"color: {Colors.ACCENT_LIGHT};")
        self.status_detail.setText("현재 작업을 안전하게 확인한 뒤 다운로드를 시작합니다.")
        self.safety_label.setText("현재 작업과 대기열을 저장했습니다. 안전하게 다운로드를 시작합니다.")
        self.install_requested.emit(dict(self.update_info))

    def _open_manual_download(self):
        if not isinstance(self.update_info, dict):
            return
        download_url = str(self.update_info.get("download_url", "") or "").strip()
        if not AutoUpdater._is_allowed_download_url(download_url):
            return
        QDesktopServices.openUrl(QUrl(download_url))

    def set_download_progress(self, percent):
        value = max(0, min(100, int(float(percent or 0))))
        self._busy = True
        self._set_state("downloading")
        self.header_title.setText("업데이트를 내려받고 있어요")
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"{value}%")
        self.status_label.setText("업데이트를 내려받고 있어요")
        self.status_detail.setText("완료되면 설치 프로그램이 자동으로 시작됩니다.")
        self.safety_label.setText("다운로드 중에도 저장된 대기열은 보호됩니다.")
        self.install_btn.setText("다운로드 중")
        self.install_btn.setEnabled(False)
        self.close_btn.setVisible(True)
        self.close_btn.setText("닫기")
        self.close_btn.setEnabled(True)

    def set_installing(self):
        self._busy = True
        self._set_state("installing")
        self.header_title.setText("새 버전을 설치하고 있어요")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setVisible(False)
        self.status_label.setText("설치를 시작하고 있어요")
        self.status_detail.setText("잠시 후 프로그램이 종료되고 새 버전으로 다시 실행됩니다.")
        self.safety_label.setText("설치가 완료되면 프로그램이 재시작되고 중단 지점을 복원합니다.")
        self.install_btn.setText("설치 중")
        self.install_btn.setEnabled(False)
        self.close_btn.setVisible(False)
        self.close_btn.setEnabled(False)

    def set_install_error(self, message):
        self._busy = False
        self._set_state("error")
        self.header_title.setText("업데이트를 완료하지 못했어요")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.status_label.setText("업데이트를 완료하지 못했어요")
        self.status_label.setStyleSheet(f"color: {Colors.ERROR};")
        self.status_detail.setText(
            user_friendly_message(
                message,
                "업데이트를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.",
            )
        )
        self.install_btn.setText("다시 시도")
        self.install_btn.setEnabled(True)
        self.close_btn.setVisible(True)
        self.close_btn.setEnabled(True)
        self.safety_label.setText("저장된 작업은 유지됩니다. 재시도하거나 공식 설치 파일을 사용하세요.")
        download_url = (
            str(self.update_info.get("download_url", "") or "").strip()
            if isinstance(self.update_info, dict)
            else ""
        )
        self.manual_download_btn.setVisible(
            AutoUpdater._is_allowed_download_url(download_url)
        )
