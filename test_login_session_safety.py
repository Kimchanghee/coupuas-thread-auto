import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src import auth_client, login_window, main_window


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


def test_forced_duplicate_login_failure_does_not_reopen_confirmation(monkeypatch):
    prompts = []
    forced_attempts = []

    class FakeWindow:
        btn_login = _Button()
        login_status = _Label()
        _login_in_flight = True
        _duplicate_login_prompt_open = False
        _force_login_attempted = True

        def _do_login(self, force=False):
            forced_attempts.append(force)

    monkeypatch.setattr(
        login_window,
        "ask_yes_no",
        lambda *_args: prompts.append(True) or True,
    )
    window = FakeWindow()

    login_window.LoginWindow._on_login_result(window, {"status": "EU003"})

    assert prompts == []
    assert forced_attempts == []
    assert "기존 세션" in window.login_status.text


def test_registration_requires_legal_consent_and_exposes_policy_links(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = login_window.LoginWindow()
    messages = []
    window._show_msg = messages.append

    assert "https://coupuas-thread-auto-three.vercel.app/terms" in window.reg_legal_links.text()
    assert "https://coupuas-thread-auto-three.vercel.app/privacy" in window.reg_legal_links.text()

    window.reg_name.setText("테스트")
    window.reg_email.setText("test@example.com")
    window.reg_username.setText("tester")
    window._username_available = True
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
