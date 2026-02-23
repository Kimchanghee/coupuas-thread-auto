import hashlib

import requests

from src import auth_client


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "json": json,
                "timeout": timeout,
                "headers": headers or {},
            }
        )
        return self.response


class _SequenceSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def _next(self):
        if not self.outcomes:
            raise RuntimeError("outcomes is empty")
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "json": json,
                "timeout": timeout,
                "headers": headers or {},
            }
        )
        return self._next()

    def get(self, url, params=None, timeout=None):
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "params": params or {},
                "timeout": timeout,
            }
        )
        return self._next()

def _reset_auth_state():
    auth_client._auth_state.update(
        {
            "user_id": None,
            "username": None,
            "token": None,
            "work_count": 0,
            "work_used": 0,
            "remaining_count": None,
            "plan_type": None,
            "is_paid": None,
            "subscription_status": None,
            "expires_at": None,
        }
    )


def test_login_payload_includes_required_ip(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(200, {"status": "EU001", "message": "EU001"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("SampleUser", "SamplePass123")

    assert result["status"] == "EU001"
    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["id"] == "sampleuser"
    assert payload["pw"] == hashlib.sha256("SamplePass123".encode("utf-8")).hexdigest()
    assert payload["force"] is False
    assert payload["ip"] == "10.20.30.40"


def test_login_422_uses_nested_validation_error_message(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        422,
        {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "입력값이 올바르지 않습니다.",
                "details": [
                    {"type": "missing", "loc": ["body", "ip"], "msg": "Field required"}
                ],
            },
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "127.0.0.1")

    result = auth_client.login("sampleuser", "SamplePass123")

    assert result["status"] is False
    assert "body.ip" in result["message"]


def test_register_422_uses_nested_validation_error_message(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        422,
        {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "입력값이 올바르지 않습니다.",
                "details": [
                    {
                        "type": "value_error",
                        "loc": ["body", "name"],
                        "msg": "Value error, invalid name",
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))

    result = auth_client.register(
        name="Tester1",
        username="sampleuser",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
    )

    assert result["success"] is False
    assert "body.name" in result["message"]


def test_register_payload_hashes_password(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(422, {"success": False, "message": "invalid"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)

    auth_client.register(
        name="Tester1",
        username="sampleuser",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
    )

    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["password"] == hashlib.sha256("SamplePass123".encode("utf-8")).hexdigest()
    assert payload["ym_news_opt_in"] is False


def test_register_payload_supports_news_opt_in(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(422, {"success": False, "message": "invalid"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)

    auth_client.register(
        name="Tester1",
        username="sampleuser",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
        ym_news_opt_in=True,
    )

    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["ym_news_opt_in"] is True


def test_register_200_failure_with_error_object_returns_message(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "success": False,
            "error": {
                "code": "USER_EXISTS",
                "message": "이미 가입한 아이디입니다. 로그인해 주세요.",
            },
            "data": None,
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))

    result = auth_client.register(
        name="Tester1",
        username="existing_user",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
    )

    assert result["success"] is False
    assert result["message"] == "이미 가입한 아이디입니다. 로그인해 주세요."


def test_register_rejects_short_password(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {"success": True, "message": "ok", "data": {"user_id": 1, "token": "t"}},
    )
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.register(
        name="Tester1",
        username="shortpwuser",
        password="1",
        contact="01012345678",
        email="short@example.com",
    )

    assert result["success"] is False
    assert str(auth_client.MIN_REGISTER_PASSWORD_LENGTH) in result["message"]
    assert len(session.calls) == 0


def test_login_rejects_short_password(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(200, {"status": "EU001", "message": "EU001"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("shortuser", "1")

    assert result["status"] is False
    assert str(auth_client.MIN_LOGIN_PASSWORD_LENGTH) in result["message"]
    assert len(session.calls) == 0


def test_login_accepts_legacy_6_digit_password(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(200, {"status": "EU001", "message": "EU001"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("legacyuser", "123456")

    assert result["status"] == "EU001"
    assert len(session.calls) == 1


def test_register_429_normalizes_rate_limit_message(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        429,
        {
            "success": False,
            "error": {
                "code": "RATE_LIMIT_ERROR",
                "message": "Too many login attempts. Please try again later.",
                "retry_after": "5 per 1 hour",
            },
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))

    result = auth_client.register(
        name="Tester1",
        username="rateuser",
        password="SamplePass123",
        contact="01012345678",
        email="rate@example.com",
    )

    assert result["success"] is False
    assert "5 per 1 hour" in result["message"]


def test_login_merges_plan_and_expiry_fields(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "id": 1001,
            "key": "token-1",
            "work_count": 50,
            "work_used": 3,
            "plan_type": "pro",
            "is_paid": True,
            "subscription_status": "active",
            "expires_at": "2026-12-31T23:59:59Z",
            "remaining_count": 47,
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["plan_type"] == "pro"
    assert state["is_paid"] is True
    assert state["subscription_status"] == "active"
    assert state["expires_at"] == "2026-12-31T23:59:59Z"
    assert state["remaining_count"] == 47


def test_login_success_keeps_user_id_when_backend_uses_user_id_field(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "user_id": 9001,
            "key": "token-9001",
            "work_count": 10,
            "work_used": 1,
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == 9001
    assert state["token"] == "token-9001"
    assert auth_client.is_logged_in() is True


def test_login_success_accepts_token_field_when_key_missing(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "id": 1002,
            "token": "token-from-token-field",
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == 1002
    assert state["token"] == "token-from-token-field"
    assert auth_client.is_logged_in() is True


def test_check_username_rejects_empty_input_without_network(monkeypatch):
    _reset_auth_state()
    session = _FakeSession(_FakeResponse(200, {"available": True}))
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.check_username("")

    assert result["available"] is False
    assert "아이디" in result["message"]
    assert session.calls == []


def test_reserve_work_returns_unsupported_on_404(monkeypatch):
    _reset_auth_state()
    auth_client._WORK_RESERVATION_SUPPORTED = None
    auth_client._auth_state["user_id"] = 1
    auth_client._auth_state["token"] = "token-1"
    monkeypatch.setattr(auth_client, "_session", _FakeSession(_FakeResponse(404, {})))

    result = auth_client.reserve_work()

    assert result["success"] is False
    assert result.get("unsupported") is True


def test_reserve_work_short_circuits_when_unsupported_cached(monkeypatch):
    _reset_auth_state()
    auth_client._WORK_RESERVATION_SUPPORTED = False
    auth_client._auth_state["user_id"] = 1
    auth_client._auth_state["token"] = "token-1"
    session = _FakeSession(_FakeResponse(200, {"success": True}))
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.reserve_work()

    assert result["success"] is False
    assert result.get("unsupported") is True
    assert len(session.calls) == 0


def test_remember_username_persists_lowercase(monkeypatch):
    captured = {}

    def _fake_save(payload):
        captured["payload"] = payload

    monkeypatch.setattr(auth_client, "_load_cred", lambda: {})
    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)
    auth_client.remember_username("Test_User")

    assert captured["payload"] == {"username": "test_user"}


def test_remember_login_credentials_persists_username_and_password(monkeypatch):
    captured = {}

    def _fake_save(payload):
        captured["payload"] = payload

    monkeypatch.setattr(auth_client, "_load_cred", lambda: {"token": "token-1"})
    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)
    auth_client.remember_login_credentials("Test_User", "SamplePass123")

    assert captured["payload"] == {
        "token": "token-1",
        "username": "test_user",
        "saved_password": "SamplePass123",
    }


def test_remember_username_empty_clears_saved_value(monkeypatch):
    captured = {}

    def _fake_save(payload):
        captured["payload"] = payload

    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {"username": "test_user", "saved_password": "pw", "token": "token-1"},
    )
    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)
    auth_client.remember_username("")

    assert captured["payload"] == {"token": "token-1"}


def test_get_saved_credentials_normalizes_username(monkeypatch):
    state = {}
    monkeypatch.setattr(auth_client, "_load_cred", lambda: {"username": "Test_User"})

    def _fake_save(payload):
        state["saved"] = payload

    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)

    result = auth_client.get_saved_credentials()

    assert result == {"username": "test_user"}
    assert state["saved"] == {"username": "test_user"}


def test_get_saved_credentials_returns_password_when_present(monkeypatch):
    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {"username": "test_user", "saved_password": "SamplePass123"},
    )

    result = auth_client.get_saved_credentials()

    assert result == {"username": "test_user", "password": "SamplePass123"}


def test_get_saved_credentials_rejects_invalid_username(monkeypatch):
    state = {"cleared": False}
    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {"username": "dpapi:corrupted-token", "saved_password": "pw"},
    )

    def _fake_clear():
        state["cleared"] = True

    monkeypatch.setattr(auth_client, "_clear_cred", _fake_clear)

    result = auth_client.get_saved_credentials()

    assert result is None
    assert state["cleared"] is True


def test_friendly_login_message_localizes_unprotected_api_host_lock():
    result = auth_client.friendly_login_message(
        {
            "status": False,
            "message": "Detected unprotected API host lock file in production mode.",
        }
    )

    assert "API 호스트 잠금" in result


def test_login_network_error_message_is_localized(monkeypatch):
    _reset_auth_state()
    session = _SequenceSession(
        [
            requests.exceptions.ReadTimeout(
                "HTTPSConnectionPool(host='ssmaker-auth-api-m2hewckpba-uc.a.run.app', port=443): Read timed out."
            )
        ]
    )
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("sampleuser", "SamplePass123")

    assert result["status"] is False
    assert "HTTPSConnectionPool" not in result["message"]
    assert "지연" in result["message"] or "통신" in result["message"]


def test_check_username_retries_once_on_connection_error(monkeypatch):
    _reset_auth_state()
    session = _SequenceSession(
        [
            requests.exceptions.ConnectionError(
                "HTTPSConnectionPool(host='ssmaker-auth-api-m2hewckpba-uc.a.run.app', port=443): Max retries exceeded"
            ),
            _FakeResponse(200, {"available": True, "message": "사용 가능한 아이디입니다."}),
        ]
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.check_username("sampleuser")

    assert result["available"] is True
    assert len(session.calls) == 2
