import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src import auth_client, computer_use_agent, login_window, main_window


def test_login_entrypoint_has_qtimer_for_immediate_transition():
    import login_main

    assert login_main.QTimer is QTimer


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)

    def setStyleSheet(self, _value):
        pass


class _Button:
    def __init__(self):
        self.enabled = True
        self.text = ""

    def setEnabled(self, value):
        self.enabled = bool(value)

    def setText(self, value):
        self.text = str(value)


def test_save_session_reports_encrypted_persistence_failure():
    agent = object.__new__(computer_use_agent.ComputerUseAgent)
    agent.context = SimpleNamespace(storage_state=lambda: {"cookies": []})
    agent._write_storage_state = lambda _state: False

    with pytest.raises(RuntimeError, match="세션을 저장"):
        agent.save_session()


def test_encrypted_session_replace_failure_preserves_previous_file(
    monkeypatch,
    tmp_path,
):
    agent = object.__new__(computer_use_agent.ComputerUseAgent)
    agent.profile_name = "test-profile"
    agent.profile_path = tmp_path
    agent.legacy_profile_path = None
    secure_path = tmp_path / "storage_state.sec"
    secure_path.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(
        computer_use_agent,
        "protect_secret",
        lambda *_args: "encrypted-new-state",
    )
    monkeypatch.setattr(
        computer_use_agent.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("replace failed")),
    )

    assert agent._write_storage_state({"cookies": [{"name": "sessionid"}]}) is False
    assert secure_path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.glob("*.tmp")) == []


def test_session_expiry_redirects_once_without_a_blocking_popup(monkeypatch):
    redirects = []

    class FakeWindow:
        _heartbeat_in_flight = True
        _closed = False
        _session_expiry_notified = False
        _redirecting_to_login = False
        _online_dot = _Label()
        _connection_label = _Label()
        status_label = _Label()
        _server_label = _Label()

        def _redirect_to_login_window(self, message):
            redirects.append(message)
            self._redirecting_to_login = True

    monkeypatch.setattr(
        main_window,
        "show_warning",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("session expiry must not stack modal popups")
        ),
    )
    window = FakeWindow()

    main_window.MainWindow._apply_heartbeat_result(window, {"state": "logged_out"})
    main_window.MainWindow._apply_heartbeat_result(window, {"state": "logged_out"})

    assert window._session_expiry_notified is True
    assert window._redirecting_to_login is True
    assert len(redirects) == 1


def test_session_expiry_redirect_does_not_wait_for_logout_network_call():
    source = (main_window.Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )
    redirect = source[
        source.index("    def _redirect_to_login_window") : source.index(
            "    def _do_logout", source.index("    def _redirect_to_login_window")
        )
    ]

    assert "auth_client.clear_local_session()" in redirect
    assert "auth_client.logout()" not in redirect


def test_logout_returns_to_login_screen_without_quitting(monkeypatch):
    events = []

    class FakeCleanupAgent:
        def __init__(self, **kwargs):
            events.append(("cleanup_created", kwargs["profile_dir"]))

        def clear_saved_session(self):
            events.append(("cleanup_finished", None))

    class FakeWindow:
        is_running = False

        def _get_profile_dir(self):
            return "test-profile"

        def _redirect_to_login_window(self, message, *, reason):
            events.append(("redirect", (message, reason)))

    monkeypatch.setattr(main_window, "ask_yes_no", lambda *_args: True)
    monkeypatch.setattr(auth_client, "logout", lambda: events.append(("logout", None)))
    monkeypatch.setattr(computer_use_agent, "ComputerUseAgent", FakeCleanupAgent)
    monkeypatch.setattr(
        main_window.QApplication,
        "quit",
        lambda: (_ for _ in ()).throw(AssertionError("logout must keep the app open")),
    )

    main_window.MainWindow._do_logout(FakeWindow())

    assert events == [
        ("logout", None),
        ("cleanup_created", "test-profile"),
        ("cleanup_finished", None),
        (
            "redirect",
            ("로그아웃되었습니다. 다시 로그인해 주세요.", "logout"),
        ),
    ]


def test_login_redirect_shows_login_before_closing_main(monkeypatch):
    app = QApplication.instance() or QApplication([])
    events = []

    class FakePassword:
        def clear(self):
            events.append("password_cleared")

    class FakeLoginWindow:
        login_pw = FakePassword()
        login_status = _Label()

        def show(self):
            events.append("login_shown")

        def raise_(self):
            events.append("login_raised")

        def activateWindow(self):
            events.append("login_activated")

    class FakeWindow:
        _redirecting_to_login = False
        _closed = False
        _login_ref = FakeLoginWindow()

        def close(self):
            events.append("main_closed")

    window = FakeWindow()
    app._main_window = window
    monkeypatch.setattr(
        auth_client,
        "clear_local_session",
        lambda: events.append("local_session_cleared"),
    )

    main_window.MainWindow._redirect_to_login_window(
        window,
        "로그아웃되었습니다. 다시 로그인해 주세요.",
        reason="logout",
    )

    assert events == [
        "local_session_cleared",
        "password_cleared",
        "login_shown",
        "login_raised",
        "login_activated",
        "main_closed",
    ]
    assert window._force_close_for_relogin is True
    assert app._main_window is None
    assert window._login_ref.login_status.text == "로그아웃되었습니다. 다시 로그인해 주세요."


def test_real_windows_show_login_again_after_logout(monkeypatch):
    app = QApplication.instance() or QApplication([])

    class FakeCleanupAgent:
        def __init__(self, **_kwargs):
            pass

        def clear_saved_session(self):
            pass

    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    monkeypatch.setattr(auth_client, "logout", lambda: None)
    monkeypatch.setattr(auth_client, "clear_local_session", lambda: None)
    monkeypatch.setattr(computer_use_agent, "ComputerUseAgent", FakeCleanupAgent)
    monkeypatch.setattr(main_window, "ask_yes_no", lambda *_args: True)

    login = login_window.LoginWindow()
    window = main_window.MainWindow()
    window._login_ref = login
    window._get_profile_dir = lambda: "test-profile"
    window._save_resume_state = lambda *_args: None
    app._login_window = login
    app._main_window = window
    login.hide()
    window.show()
    app.processEvents()

    window._do_logout()
    app.processEvents()

    assert login.isVisible() is True
    assert window.isVisible() is False
    assert app._main_window is None
    assert login.login_pw.text() == ""
    assert login.login_status.text() == "로그아웃되었습니다. 다시 로그인해 주세요."

    login.close()
    login.deleteLater()
    window.deleteLater()
    app.processEvents()


def test_login_request_is_ignored_while_another_login_is_in_flight(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = login_window.LoginWindow()
    window.login_id.setText("tester")
    window.login_pw.setText("password")
    window._login_in_flight = True
    monkeypatch.setattr(
        login_window,
        "LoginWorker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a duplicate login worker must not be created")
        ),
    )

    window._do_login()

    assert window._login_in_flight is True
    window.close()
    window.deleteLater()
    app.processEvents()


def test_successful_registration_uses_issued_session_without_second_login(monkeypatch):
    emitted = []

    class _Signal:
        def emit(self, value):
            emitted.append(value)

    class FakeWindow:
        btn_register = _Button()
        login_success = _Signal()

    monkeypatch.setattr(
        login_window,
        "show_info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("successful registration should enter the app immediately")
        ),
    )
    result = {
        "success": True,
        "data": {
            "user_id": 42,
            "username": "new_user",
            "token": "issued-token",
            "work_count": 5,
        },
    }

    login_window.LoginWindow._on_register_result(FakeWindow(), result)

    assert emitted == [
        {
            "status": True,
            "id": 42,
            "user_id": 42,
            "username": "new_user",
            "key": "issued-token",
            "token": "issued-token",
            "work_count": 5,
        }
    ]


def test_duplicate_login_is_blocked_without_session_replacement():
    login_attempts = []

    class FakeWindow:
        btn_login = _Button()
        login_status = _Label()
        _login_in_flight = True

        def _do_login(self):
            login_attempts.append(True)

    window = FakeWindow()

    login_window.LoginWindow._on_login_result(window, {"status": "EU003"})

    assert not hasattr(login_window, "ask_yes_no")
    assert login_attempts == []
    assert "이미 로그인" in window.login_status.text
    assert "로그아웃" in window.login_status.text


def test_registration_requires_legal_consent_and_exposes_policy_links(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = login_window.LoginWindow()
    messages = []
    window._show_msg = messages.append

    assert "https://coupuas-thread-auto-ten.vercel.app/terms" in window.reg_legal_links.text()
    assert "https://coupuas-thread-auto-ten.vercel.app/privacy" in window.reg_legal_links.text()

    window.reg_name.setText("테스트")
    window.reg_email.setText("test@example.com")
    window.reg_username.setText("tester")
    window._username_available = True
    window._username_available_for = "tester"
    window.reg_pw.setText("Password1!")
    window.reg_pw_confirm.setText("Password1!")
    window.reg_contact.setText("010-1234-5678")
    window.reg_legal_consent.setChecked(False)

    window._do_register()

    assert messages == ["회원가입을 계속하려면 이용약관과 개인정보처리방침에 동의해 주세요."]
    assert not hasattr(window, "_reg_worker")
    window.close()
    window.deleteLater()
    app.processEvents()


def test_registration_passes_required_consent_to_worker(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    captured = {}

    class FakeSignal:
        def connect(self, callback):
            captured["callback"] = callback

    class FakeRegisterWorker:
        finished_signal = FakeSignal()

        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(login_window, "RegisterWorker", FakeRegisterWorker)
    window = login_window.LoginWindow()
    window.reg_name.setText("테스트")
    window.reg_email.setText("test@example.com")
    window.reg_username.setText("tester")
    window._username_available = True
    window._username_available_for = "tester"
    window.reg_pw.setText("Password1!")
    window.reg_pw_confirm.setText("Password1!")
    window.reg_contact.setText("010-1234-5678")
    window.reg_legal_consent.setChecked(True)

    window._do_register()

    assert captured["kwargs"]["terms_accepted"] is True
    assert captured["kwargs"]["privacy_accepted"] is True
    assert captured["started"] is True
    window.close()
    window.deleteLater()
    app.processEvents()


def test_registration_password_confirmation_updates_live(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = login_window.LoginWindow()

    assert window.reg_pw_match_status.text() == ""
    window.reg_pw.setText("Password1!")
    window.reg_pw_confirm.setText("Password2!")
    assert window.reg_pw_match_status.text() == "✗ 비밀번호가 일치하지 않습니다"

    window.reg_pw_confirm.setText("Password1!")
    assert window.reg_pw_match_status.text() == "✓ 비밀번호가 일치합니다"

    window.reg_pw.setText("Changed1!")
    assert window.reg_pw_match_status.text() == "✗ 비밀번호가 일치하지 않습니다"

    window.reg_pw_confirm.clear()
    assert window.reg_pw_match_status.text() == ""
    window.close()
    window.deleteLater()
    app.processEvents()


def test_stale_username_check_restores_button_without_authorizing_new_value(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = login_window.LoginWindow()
    window.reg_username.setText("first_user")
    token = window._username_check_token
    window.btn_check_user.setEnabled(False)
    window.btn_check_user.setText("확인중...")

    window.reg_username.setText("second_user")
    window._on_username_checked(token, "first_user", True, "available")

    assert window.btn_check_user.isEnabled() is True
    assert window.btn_check_user.text() == "중복확인"
    assert window._username_available is False
    assert window._username_available_for is None
    assert window.reg_user_status.text() == ""
    window.close()
    window.deleteLater()
    app.processEvents()


def test_login_worker_persists_preferences_before_final_signal(monkeypatch):
    app = QApplication.instance() or QApplication([])
    events = []
    monkeypatch.setattr(
        auth_client,
        "login",
        lambda *_args: events.append("login") or {"status": True, "id": "user-1"},
    )
    monkeypatch.setattr(
        auth_client,
        "remember_login_credentials",
        lambda *_args, **_kwargs: events.append("remember") or True,
    )
    monkeypatch.setattr(
        login_window,
        "_queue_telemetry",
        lambda *_args: events.append("telemetry_queued"),
    )
    worker = login_window.LoginWorker(
        "tester", "Password1!", remember_credentials=True, auto_login=True
    )
    worker.finished_signal.connect(lambda _result: events.append("signal"))

    worker.run()

    assert events == ["login", "remember", "telemetry_queued", "signal"]
    assert worker._password_bytes == bytearray()
    app.processEvents()


def test_register_worker_emits_only_after_password_cleanup(monkeypatch):
    app = QApplication.instance() or QApplication([])
    worker = login_window.RegisterWorker(
        "Tester",
        "tester",
        "Password1!",
        "01012345678",
        "tester@example.com",
        terms_accepted=True,
        privacy_accepted=True,
    )
    events = []
    monkeypatch.setattr(
        auth_client,
        "register",
        lambda *_args, **_kwargs: events.append("register") or {"success": True},
    )
    monkeypatch.setattr(
        login_window,
        "_queue_telemetry",
        lambda *_args: events.append("telemetry_queued"),
    )
    worker.finished_signal.connect(
        lambda _result: events.append(("signal", worker._password_bytes))
    )

    worker.run()

    assert events == ["register", "telemetry_queued", ("signal", bytearray())]
    app.processEvents()


def test_login_success_callback_does_not_perform_network_or_credential_io(monkeypatch):
    emitted = []

    class FakeWindow:
        btn_login = _Button()
        login_status = _Label()
        _login_in_flight = True
        login_success = type("Signal", (), {"emit": lambda self, value: emitted.append(value)})()

    monkeypatch.setattr(
        auth_client,
        "log_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("UI callback must not log")),
    )
    monkeypatch.setattr(
        auth_client,
        "remember_login_credentials",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("UI callback must not persist")),
    )

    result = {"status": True, "id": "user-1"}
    login_window.LoginWindow._on_login_result(FakeWindow(), result)

    assert emitted == [result]


def test_register_success_callback_does_not_send_activity_log(monkeypatch):
    class FakeWindow:
        btn_register = _Button()
        reg_username = type("Field", (), {"text": lambda self: "tester"})()
        reg_pw = type("Field", (), {"text": lambda self: "Password1!"})()
        login_id = type("Field", (), {"setText": lambda self, _value: None})()
        login_pw = type("Field", (), {"setText": lambda self, _value: None})()
        stack = type("Stack", (), {"setCurrentIndex": lambda self, _value: None})()

    monkeypatch.setattr(login_window, "show_info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        auth_client,
        "log_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("UI callback must not log")),
    )

    login_window.LoginWindow._on_register_result(FakeWindow(), {"success": True})
