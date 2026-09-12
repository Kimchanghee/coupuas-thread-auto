import json
import requests
import pytest
from src import auth_client


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_client, "_CRED_DIR", tmp_path)
    monkeypatch.setattr(auth_client, "_CRED_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(auth_client, "_check_api_url", lambda: None)
    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        lambda *a, **k: pytest.fail("Unexpected network request"),
    )
    auth_client._clear_auth_state_memory()
    yield
    auth_client._clear_auth_state_memory()


def test_password_is_never_serialized_even_for_direct_save():
    assert auth_client._save_cred(
        {"username": "test_user", "saved_password": "dpapi:Example123!"}
    )
    content = auth_client._CRED_FILE.read_text()
    assert "Example123" not in content and "saved_password" not in content


def test_legacy_password_is_purged_on_startup():
    auth_client._CRED_FILE.write_text(
        json.dumps(
            {
                "username": "test_user",
                "saved_password": "dpapi:Example123!",
                "auto_login": True,
            }
        )
    )
    assert auth_client.get_saved_credentials() == {"username": "test_user"}
    content = auth_client._CRED_FILE.read_text()
    assert "saved_password" not in content and "auto_login" not in content


def test_refresh_rotates_and_loads_full_identity(monkeypatch):
    assert auth_client._save_cred(
        {"username": "test_user", "auto_login": True, "refresh_token": "r" * 43}
    )
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return type(
            "Response",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "status": True,
                    "data": {
                        "data": {
                            "id": "12",
                            "username": "test_user",
                            "work_count": 20,
                            "work_used": 2,
                        },
                        "token": "new-access-token",
                    },
                    "refresh_token": "s" * 43,
                },
            },
        )()

    monkeypatch.setattr(auth_client._session, "post", post)
    result = auth_client.resume_saved_session()
    assert result["status"] is True
    assert str(auth_client.get_auth_state()["user_id"]) == "12"
    assert auth_client.get_auth_state()["work_count"] == 20
    assert auth_client._load_cred()["refresh_token"] == "s" * 43
    assert "refresh_token" not in result
    assert calls[0][1]["allow_redirects"] is False


def test_ambiguous_rotation_is_not_retried(monkeypatch):
    assert auth_client._save_cred(
        {"username": "test_user", "auto_login": True, "refresh_token": "r" * 43}
    )
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout()

    monkeypatch.setattr(auth_client._session, "post", post)
    assert auth_client.resume_saved_session()["status"] is False
    assert len(calls) == 1
    assert "refresh_token" not in auth_client._load_cred()


def test_logout_revokes_refresh_even_when_access_missing(monkeypatch):
    assert auth_client._save_cred(
        {"username": "test_user", "auto_login": True, "refresh_token": "r" * 43}
    )
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return type("Response", (), {"status_code": 200})()

    monkeypatch.setattr(auth_client._session, "post", post)
    assert auth_client.logout()
    assert calls[0][0].endswith("/user/session/revoke")
    assert "refresh_token" not in auth_client._load_cred()


def test_mfa_dialog_clears_recovery_codes_on_close(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from src.account_security_dialog import AccountSecurityDialog
    app = QApplication.instance() or QApplication([])
    dialog = AccountSecurityDialog()
    dialog.result({"recovery_codes": ["test-one-time-code"]})
    assert "test-one-time-code" in dialog.output.toPlainText()
    dialog.reject()
    assert not dialog.output.toPlainText()
    dialog.deleteLater()
    app.processEvents()
