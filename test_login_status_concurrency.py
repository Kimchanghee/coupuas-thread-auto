import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication

from src.config import config
from src.events import LoginStatusEvent
from src.main_window import MainWindow
from src.models.threads_account import ThreadsAccount


def test_login_check_button_waits_for_every_inflight_account(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    first = ThreadsAccount.create("first_account")
    second = ThreadsAccount.create("second_account")
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")
    monkeypatch.setattr(config, "threads_accounts", [first, second])
    monkeypatch.setattr(config, "active_threads_account_id", second.account_id)
    monkeypatch.setattr(config, "instagram_username", second.expected_username)
    monkeypatch.setattr(config, "save", lambda: True)

    window = MainWindow()
    try:
        window._upload_account_tabs.setCurrentIndex(1)
        window._login_check_inflight = {
            first.account_id: 11,
            second.account_id: 12,
        }
        window.check_login_btn.setEnabled(False)

        first_event = LoginStatusEvent(
            (True, first.expected_username, first.account_id, first.expected_username, 11)
        )
        assert window.event(first_event) is True
        assert not window.check_login_btn.isEnabled()
        assert window.check_login_btn.text() == "확인 중..."
        assert window.login_status_label.text() == "@second_account · 확인 필요"

        second_event = LoginStatusEvent(
            (True, second.expected_username, second.account_id, second.expected_username, 12)
        )
        assert window.event(second_event) is True
        assert window.check_login_btn.isEnabled()
        assert window.check_login_btn.text() == "로그인 상태 확인"
        assert window.login_status_label.text() == "@second_account · 마지막 확인"
    finally:
        window._closed = True
        window.close()
        app.processEvents()
