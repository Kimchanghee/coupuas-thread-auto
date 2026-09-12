"""Account-owned, asynchronous authenticator setup dialog."""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
)
from src import auth_client


class SecurityRequest(QThread):
    completed = pyqtSignal(dict)

    def __init__(self, action, password, code, parent=None):
        super().__init__(parent)
        self.action, self.password, self.code = action, password, code
        self.user_id, self.token = auth_client._get_session_user_and_token()

    def run(self):
        try:
            if auth_client._check_api_url() or not self.token:
                raise ValueError("No active session")
            response = auth_client._session.post(
                f"{auth_client.API_SERVER_URL}/user/mfa/{self.action}",
                json={
                    "password": auth_client._normalize_password_for_backend(
                        self.password
                    )
                    if self.password
                    else "",
                    "code": self.code,
                },
                headers=auth_client._build_auth_headers(self.token),
                timeout=12,
                allow_redirects=False,
            )
            if auth_client._get_session_user_and_token() != (self.user_id, self.token):
                raise ValueError("Session changed")
            payload = (
                response.json()
                if response.status_code == 200
                else {
                    "error": "설정을 완료하지 못했습니다. 비밀번호·인증 코드와 서버 설정을 확인해주세요."
                }
            )
        except Exception:
            payload = {
                "error": "보안 설정을 완료하지 못했습니다. 연결 상태를 확인하고 다시 시도해주세요."
            }
        finally:
            self.password = self.code = self.token = ""
        self.completed.emit(payload)


class AccountSecurityDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("2단계 인증")
        self.resize(480, 520)
        self.worker = None
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "인증 앱으로 계정을 보호하세요. 설정·해제에는 현재 비밀번호가 필요합니다."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("현재 비밀번호")
        layout.addWidget(self.password)
        self.code = QLineEdit()
        self.code.setPlaceholderText("인증 앱 코드 또는 일회용 복구 코드")
        self.code.setMaxLength(64)
        layout.addWidget(self.code)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.buttons = []
        for label, action in (
            ("인증 앱 설정 시작", "enroll"),
            ("코드 확인 및 설정 완료", "confirm"),
            ("2단계 인증 해제", "disable"),
        ):
            button = QPushButton(label)
            button.setMinimumHeight(38)
            button.clicked.connect(lambda _=False, a=action: self.submit(a))
            layout.addWidget(button)
            self.buttons.append(button)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        layout.addWidget(close)

    def submit(self, action):
        if self.worker and self.worker.isRunning():
            return
        self.worker = SecurityRequest(
            action, self.password.text(), self.code.text(), self
        )
        self.password.clear()
        self.code.clear()
        self.output.clear()
        self.status.setText("확인 중…")
        for button in self.buttons:
            button.setEnabled(False)
        self.worker.completed.connect(self.result)
        self.worker.start()

    def result(self, payload):
        for button in self.buttons:
            button.setEnabled(True)
        if payload.get("error"):
            self.status.setText(payload["error"])
            return
        if payload.get("secret"):
            self.output.setPlainText(
                "인증 앱에서 수동으로 계정을 추가하세요.\n계정: ThreadPilot\n설정 키: "
                + payload["secret"]
            )
            self.status.setText(
                "앱에 표시된 6자리 코드를 입력한 뒤 ‘설정 완료’를 누르세요."
            )
        elif payload.get("recovery_codes"):
            self.output.setPlainText(
                "다음 복구 코드는 각각 한 번만 사용할 수 있습니다.\n안전한 별도 장소에 보관하세요.\n\n"
                + "\n".join(payload["recovery_codes"])
            )
            self.status.setText(
                "2단계 인증 설정 완료. 다른 기기의 세션과 자동 로그인을 취소했습니다."
            )
        else:
            self.status.setText("2단계 인증을 해제했습니다.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            event.ignore()
            return
        self.output.clear()
        self.password.clear()
        self.code.clear()
        super().closeEvent(event)

    def reject(self):
        if self.worker and self.worker.isRunning():
            return
        self.output.clear()
        self.password.clear()
        self.code.clear()
        super().reject()
