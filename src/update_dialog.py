"""
쿠팡 파트너스 스레드 자동화 - 업데이트 다이얼로그
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from src.theme import (
    Colors, Gradients, Typography,
    accent_btn_style, ghost_btn_style, progress_bar_style,
    dialog_style, header_title_style
)
from src.auto_updater import AutoUpdater
from src.ui_messages import ask_yes_no, show_error, show_warning


class UpdateCheckThread(QThread):
    """백그라운드 업데이트 체크 스레드"""
    update_found = pyqtSignal(dict)  # 업데이트 정보
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            updater = AutoUpdater(self.current_version)
            update_info = updater.check_for_updates()

            if update_info:
                self.update_found.emit(update_info)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))


class UpdateDownloadThread(QThread):
    """백그라운드 다운로드 스레드"""
    progress = pyqtSignal(float)  # 진행률 (0-100)
    finished = pyqtSignal(str)  # 다운로드된 파일 경로
    error = pyqtSignal(str)

    def __init__(self, current_version, update_info):
        super().__init__()
        self.current_version = current_version
        self.update_info = update_info

    def run(self):
        try:
            updater = AutoUpdater(self.current_version)
            file_path = updater.download_update(
                self.update_info,
                progress_callback=lambda p: self.progress.emit(p)
            )

            if file_path:
                self.finished.emit(file_path)
            else:
                self.error.emit("다운로드 실패")
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """업데이트 다이얼로그 - Stitch Blue 테마"""

    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_info = None
        self.download_path = None

        self.setWindowTitle("업데이트 확인")
        self.setFixedSize(520, 450)
        self.setModal(True)

        self._build_ui()
        self._check_for_updates()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 헤더
        header = QLabel("업데이트 확인")
        header.setStyleSheet(header_title_style("18pt"))
        layout.addWidget(header)

        # 현재 버전
        self.current_label = QLabel(f"현재 버전: {self.current_version}")
        self.current_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 10pt;
                background: transparent;
            }}
        """)
        layout.addWidget(self.current_label)

        # 상태 레이블
        self.status_label = QLabel("업데이트를 확인하는 중...")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(self.status_label)

        # 변경사항 (처음엔 숨김)
        changelog_label = QLabel("변경사항:")
        changelog_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 9pt;
                font-weight: 600;
                background: transparent;
                margin-top: 8px;
            }}
        """)
        layout.addWidget(changelog_label)

        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_INPUT};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 12px;
                font-size: 9pt;
                font-family: {Typography.FAMILY_MONO};
            }}
        """)
        self.changelog_text.setVisible(False)
        layout.addWidget(self.changelog_text)

        changelog_label.setVisible(False)
        self.changelog_label = changelog_label

        # 진행바 (처음엔 숨김)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(progress_bar_style())
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addStretch()

        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.close_btn = QPushButton("닫기")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                font-size: 10pt;
                font-weight: 600;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.TEXT_MUTED};
            }}
        """)
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        self.download_btn = QPushButton("다운로드 및 설치")
        self.download_btn.setFixedHeight(40)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 10pt;
                font-weight: 600;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {Gradients.ACCENT_BTN_HOVER};
            }}
            QPushButton:disabled {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self.download_btn)

        layout.addLayout(btn_layout)

        # 다이얼로그 스타일
        self.setStyleSheet(dialog_style())

    def _check_for_updates(self):
        """백그라운드에서 업데이트 확인"""
        self.check_thread = UpdateCheckThread(self.current_version)
        self.check_thread.update_found.connect(self._on_update_found)
        self.check_thread.no_update.connect(self._on_no_update)
        self.check_thread.error.connect(self._on_error)
        self.check_thread.start()

    def _on_update_found(self, update_info):
        """업데이트 발견됨"""
        self.update_info = update_info

        self.status_label.setText(
            f"새 버전 발견: v{update_info['version']} "
            f"({update_info['size_mb']:.1f} MB)"
        )
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SUCCESS};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)

        # 변경사항 표시
        self.changelog_label.setVisible(True)
        self.changelog_text.setVisible(True)
        changelog = AutoUpdater.get_changelog_summary(update_info['changelog'])
        self.changelog_text.setPlainText(changelog)

        # 다운로드 버튼 활성화
        self.download_btn.setEnabled(True)

    def _on_no_update(self):
        """최신 버전 사용 중"""
        self.status_label.setText("최신 버전을 사용 중입니다.")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SUCCESS};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)

    def _on_error(self, error_msg):
        """에러 발생"""
        self.status_label.setText(f"업데이트 확인 실패: {error_msg}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.ERROR};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)

    def _start_download(self):
        """다운로드 시작"""
        if not self.update_info:
            return

        # 다운로드 확인
        if not ask_yes_no(
            self,
            "업데이트 다운로드",
            f"v{self.update_info['version']} 버전을 다운로드하시겠습니까?\n\n"
            f"크기: {self.update_info['size_mb']:.1f} MB\n"
            f"다운로드 후 자동으로 설치됩니다.",
        ):
            return

        # UI 업데이트
        self.status_label.setText("다운로드 중...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        # 다운로드 시작
        self.download_thread = UpdateDownloadThread(
            self.current_version,
            self.update_info
        )
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_download_progress(self, percent):
        """다운로드 진행률 업데이트"""
        self.progress_bar.setValue(int(percent))

    def _on_download_finished(self, file_path):
        """다운로드 완료"""
        self.download_path = file_path
        self.status_label.setText("다운로드 완료!")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.SUCCESS};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)

        # 설치 확인
        if ask_yes_no(
            self,
            "업데이트 설치",
            "다운로드가 완료되었습니다.\n지금 설치하시겠습니까?\n\n"
            "설치를 시작하면 프로그램이 종료되고,\n"
            "자동으로 업데이트가 적용됩니다.",
        ):
            self._install_update()
        else:
            self.close_btn.setEnabled(True)

    def _on_download_error(self, error_msg):
        """다운로드 에러"""
        self.status_label.setText(f"다운로드 실패: {error_msg}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.ERROR};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
        """)
        self.download_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

    def _install_update(self):
        """업데이트 설치"""
        if not self.download_path:
            return

        try:
            updater = AutoUpdater(self.current_version)
            success = updater.install_update(self.download_path)

            if success:
                # 설치 스크립트가 실행되면 프로그램 종료
                import sys
                sys.exit(0)
            else:
                show_warning(
                    self,
                    "업데이트 실패",
                    "업데이트 설치에 실패했습니다.\n"
                    "개발 모드에서는 자동 업데이트가 지원되지 않습니다.",
                )
                self.close_btn.setEnabled(True)

        except Exception as e:
            show_error(self, "오류", f"업데이트 설치 중 오류가 발생했습니다:\n{e}")
            self.close_btn.setEnabled(True)
