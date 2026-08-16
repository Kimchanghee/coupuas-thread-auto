import base64
import hashlib
import json
import time

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

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "params": params or {},
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

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append(
            {
                "method": "GET",
                "url": url,
                "params": params or {},
                "timeout": timeout,
                "headers": headers or {},
            }
        )
        return self._next()

def _reset_auth_state():
    auth_client._auth_state.update(
        {
            "user_id": None,
            "username": None,
            "token": None,
            "token_issued_at": None,
            "phone": None,
            "work_count": 0,
            "work_used": 0,
            "remaining_count": None,
            "user_type": None,
            "plan_type": None,
            "plan_id": None,
            "plan_name": None,
            "account_limit": 1,
            "billing_interval": None,
            "is_recurring": False,
            "commerce_scope": "coupang",
            "shopping_trial_ends_at": None,
            "offer_eligible": False,
            "offer_plan_id": None,
            "offer_price_krw": None,
            "offer_cycles": None,
            "is_paid": None,
            "subscription_status": None,
            "expires_at": None,
            "subscription_url": None,
        }
    )


def _make_unverified_jwt(payload):
    header = {"alg": "none", "typ": "JWT"}
    header_part = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    payload_part = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{header_part}.{payload_part}."


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


def test_login_never_requests_active_session_replacement(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(200, {"status": "EU003", "message": "EU003"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("SampleUser", "SamplePass123", force=True)

    assert result["status"] == "EU003"
    assert session.calls[0]["json"]["force"] is False


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
        terms_accepted=True,
        privacy_accepted=True,
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
        terms_accepted=True,
        privacy_accepted=True,
    )

    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["password"] == hashlib.sha256("SamplePass123".encode("utf-8")).hexdigest()
    assert payload["ym_news_opt_in"] is False
    assert payload["terms_accepted"] is True
    assert payload["privacy_accepted"] is True
    assert payload["terms_version"] == "2026-08-08"
    assert payload["privacy_version"] == "2026-08-08"


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
        terms_accepted=True,
        privacy_accepted=True,
    )

    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["ym_news_opt_in"] is True


def test_register_rejects_missing_terms_consent(monkeypatch):
    _reset_auth_state()
    session = _FakeSession(_FakeResponse(200, {"success": True}))
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.register(
        name="Tester1",
        username="sampleuser",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
    )

    assert result["success"] is False
    assert "동의" in result["message"]
    assert session.calls == []


def test_register_rejects_missing_privacy_consent(monkeypatch):
    _reset_auth_state()
    session = _FakeSession(_FakeResponse(200, {"success": True}))
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.register(
        name="Tester1",
        username="sampleuser",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
        terms_accepted=True,
    )

    assert result["success"] is False
    assert "개인정보" in result["message"]
    assert session.calls == []


def test_log_action_can_be_disabled_by_environment(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "user-1"
    auth_client._auth_state["token"] = "token-1"
    auth_client._auth_state["token_issued_at"] = time.time()
    session = _FakeSession(_FakeResponse(200, {}))
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setenv("THREAD_AUTO_DISABLE_ACTIVITY_LOGS", "1")

    auth_client.log_action("test", "content")

    assert session.calls == []


def test_log_action_suppresses_retries_after_timeout(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "user-1"
    auth_client._auth_state["token"] = "token-1"
    auth_client._auth_state["token_issued_at"] = time.time()
    auth_client._LOG_ACTION_FAILURE_COUNT = 0
    auth_client._LOG_ACTION_FAILURE_SUPPRESS_UNTIL = 0.0
    session = _SequenceSession([requests.Timeout("boom"), _FakeResponse(200, {})])
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.delenv("THREAD_AUTO_DISABLE_ACTIVITY_LOGS", raising=False)

    auth_client.log_action("test", "first")
    auth_client.log_action("test", "second")

    assert len(session.calls) == 1


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
        terms_accepted=True,
        privacy_accepted=True,
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
        terms_accepted=True,
        privacy_accepted=True,
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


def test_heartbeat_merges_user_type_and_marks_paid(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = 1001
    auth_client._auth_state["token"] = "token-1"
    monkeypatch.setattr(
        auth_client,
        "_session",
        _FakeSession(_FakeResponse(200, {"status": True, "user_type": "subscriber"})),
    )

    result = auth_client.heartbeat(current_task="idle")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_type"] == "subscriber"
    assert state["is_paid"] is True


def test_heartbeat_payload_includes_ip(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = 1001
    auth_client._auth_state["token"] = "token-1"
    session = _FakeSession(_FakeResponse(200, {"status": True}))
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.heartbeat(current_task="idle", app_version="1.2.3")

    assert result["status"] is True
    assert session.calls
    payload = session.calls[-1]["json"]
    assert payload["id"] == 1001
    assert payload["key"] == "token-1"
    assert payload["ip"] == "10.20.30.40"
    assert payload["current_task"] == "idle"
    assert payload["app_version"] == "1.2.3"


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


def test_login_promotion_id_never_overwrites_account_identity(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "key": "token-account-owner",
            "shopping_promotion": {
                "id": "shopping-pro-existing-customer-2026",
                "offer_eligible": True,
            },
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("account_owner", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == "account_owner"
    assert state["username"] == "account_owner"


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


def test_login_success_without_user_id_falls_back_to_username(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "key": "token-without-user-id",
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == "paiduser"
    assert state["token"] == "token-without-user-id"
    assert auth_client.is_logged_in() is True


def test_login_success_without_user_id_does_not_trust_unverified_token_sub(monkeypatch):
    _reset_auth_state()
    token = _make_unverified_jwt({"sub": 9999})
    response = _FakeResponse(
        200,
        {
            "status": True,
            "key": token,
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == "paiduser"
    assert state["token"] == token


def test_login_success_ignores_null_like_user_id_and_uses_username(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "id": "None",
            "key": "token-null-id",
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == "paiduser"
    assert state["token"] == "token-null-id"
    assert auth_client.is_logged_in() is True


def test_login_extracts_nested_user_id_from_data_data(monkeypatch):
    _reset_auth_state()
    response = _FakeResponse(
        200,
        {
            "status": True,
            "data": {
                "data": {
                    "id": "7001",
                    "username": "paiduser",
                },
                "token": "nested-token",
            },
        },
    )
    monkeypatch.setattr(auth_client, "_session", _FakeSession(response))
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("paiduser", "SamplePass123")

    assert result["status"] is True
    state = auth_client.get_auth_state()
    assert state["user_id"] == "7001"
    assert state["token"] == "nested-token"


def test_get_session_user_and_token_does_not_trust_unverified_token_sub():
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "wrong-user"
    auth_client._auth_state["token"] = _make_unverified_jwt({"sub": 321})

    user_id, token = auth_client._get_session_user_and_token()

    assert user_id == "wrong-user"
    assert token == auth_client._auth_state["token"]
    assert auth_client._auth_state["user_id"] == "wrong-user"


def test_create_payapp_checkout_uses_server_session_user_id_not_unverified_token_sub(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "wrong-user"
    auth_client._auth_state["token"] = _make_unverified_jwt({"sub": 777})
    session = _FakeSession(
        _FakeResponse(200, {"success": True, "payurl": "https://payapp.kr/ok?token=secret"})
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.create_payapp_checkout("01012345678")

    assert result["success"] is True
    assert session.calls, "payment request should be sent"
    sent = session.calls[-1]
    assert sent["headers"]["X-User-ID"] == "wrong-user"
    assert sent["json"]["user_id"] == "wrong-user"
    assert auth_client._auth_state["user_id"] == "wrong-user"


def test_create_payapp_checkout_rejects_untrusted_payment_url(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "user-1"
    auth_client._auth_state["token"] = "server-token"
    session = _FakeSession(
        _FakeResponse(200, {"success": True, "payurl": "https://evil.example/pay"})
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.create_payapp_checkout("01012345678")

    assert result["success"] is False
    assert "신뢰할 수 없는 결제 URL" in result["message"]


def test_create_payapp_checkout_routes_shopping_pro_week_plan(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "7001"
    auth_client._auth_state["token"] = "server-token"
    session = _FakeSession(
        _FakeResponse(
            200,
            {
                "success": True,
                "plan_id": "stmaker_shopping_pro_week",
                "payurl": "https://payapp.kr/pro-week",
            },
        )
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.create_payapp_checkout(
        "01012345678",
        plan_id="stmaker_shopping_pro_week",
    )

    assert result["success"] is True
    assert session.calls[-1]["json"]["plan_id"] == "stmaker_shopping_pro_week"


def test_create_payapp_subscription_routes_shopping_pro_month_plan(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "7001"
    auth_client._auth_state["token"] = "server-token"
    session = _FakeSession(
        _FakeResponse(
            200,
            {
                "success": True,
                "plan_id": "stmaker_shopping_pro_month",
                "payurl": "https://payapp.kr/pro-month",
            },
        )
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.create_payapp_subscription(
        "01012345678",
        plan_id="stmaker_shopping_pro_month",
    )

    assert result["success"] is True
    assert session.calls[-1]["json"]["plan_id"] == "stmaker_shopping_pro_month"


def test_merge_account_state_includes_server_shopping_entitlement():
    _reset_auth_state()

    auth_client._merge_account_state(
        {
            "commerce_scope": "multi",
            "shopping_trial_ends_at": "2026-10-04T00:00:00+00:00",
            "shopping_promotion": {
                "offer_eligible": True,
                "offer_plan_id": "stmaker_shopping_pro_founder_month",
                "offer_price_krw": 59_000,
                "offer_cycles": 6,
            },
        }
    )

    state = auth_client.get_auth_state()
    assert state["commerce_scope"] == "multi"
    assert state["offer_eligible"] is True
    assert state["offer_price_krw"] == 59_000
    assert state["offer_cycles"] == 6


def test_subscription_status_sends_server_required_user_header(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "7001"
    auth_client._auth_state["token"] = "server-token"
    session = _FakeSession(
        _FakeResponse(
            200,
            {
                "success": True,
                "is_trial": False,
                "work_count": 100,
                "work_used": 0,
                "remaining": 100,
                "can_work": True,
                "plan_id": "stmaker_pro_month",
                "account_limit": 10,
            },
        )
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.get_subscription_status()

    assert result["success"] is True
    sent = session.calls[-1]
    assert sent["method"] == "GET"
    assert sent["headers"]["Authorization"] == "Bearer server-token"
    assert sent["headers"]["X-User-ID"] == "7001"


def test_payapp_subscription_status_and_cancel_are_bound_to_session_user(monkeypatch):
    _reset_auth_state()
    auth_client._auth_state["user_id"] = "7001"
    auth_client._auth_state["token"] = "server-token"
    session = _SequenceSession(
        [
            _FakeResponse(200, {"subscriptions": [{"rebill_no": "rebill-1", "status": "active"}]}),
            _FakeResponse(200, {"success": True, "message": "cancelled"}),
        ]
    )
    monkeypatch.setattr(auth_client, "_session", session)

    status = auth_client.get_payapp_subscriptions()
    cancelled = auth_client.cancel_payapp_subscription("rebill-1")

    assert status["success"] is True
    assert cancelled["success"] is True
    assert session.calls[0]["headers"]["X-User-ID"] == "7001"
    assert session.calls[1]["headers"]["X-User-ID"] == "7001"
    assert session.calls[1]["json"] == {"user_id": "7001", "rebill_no": "rebill-1"}


def test_payment_url_helpers_allow_only_https_payapp():
    assert auth_client.is_trusted_payment_url("https://payapp.kr/pay/123")
    assert auth_client.is_trusted_payment_url("https://m.payapp.kr/pay/123?secret=1")
    assert not auth_client.is_trusted_payment_url("http://payapp.kr/pay/123")
    assert not auth_client.is_trusted_payment_url("https://payapp.kr.evil.example/pay")
    assert auth_client.safe_url_for_log("https://m.payapp.kr/pay/123?secret=1#frag") == "https://m.payapp.kr/pay/123"


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


def test_reserve_work_sends_stable_idempotency_key(monkeypatch):
    _reset_auth_state()
    auth_client._WORK_RESERVATION_SUPPORTED = None
    auth_client._auth_state["user_id"] = 1
    auth_client._auth_state["token"] = "token-1"
    session = _FakeSession(
        _FakeResponse(200, {"success": True, "reservation_id": "reservation-1"})
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.reserve_work("queue-item-1")

    assert result["success"] is True
    assert session.calls[-1]["json"]["idempotency_key"] == "queue-item-1"
    assert session.calls[-1]["headers"]["Idempotency-Key"] == "queue-item-1"


def test_reserve_work_recovers_exact_replayed_reservation(monkeypatch):
    _reset_auth_state()
    auth_client._WORK_RESERVATION_SUPPORTED = None
    auth_client._auth_state["user_id"] = 1
    auth_client._auth_state["token"] = "token-1"
    monkeypatch.setattr(
        auth_client,
        "_session",
        _FakeSession(
            _FakeResponse(
                200,
                {
                    "success": False,
                    "code": "IDEMPOTENCY_REPLAY",
                    "reservation_id": "existing-reservation",
                    "reservation_status": "reserved",
                },
            )
        ),
    )

    result = auth_client.reserve_work("persisted-queue-key")

    assert result["success"] is True
    assert result["recovered"] is True
    assert result["reservation_id"] == "existing-reservation"


def test_reserve_work_does_not_recover_released_replay(monkeypatch):
    _reset_auth_state()
    auth_client._WORK_RESERVATION_SUPPORTED = None
    auth_client._auth_state["user_id"] = 1
    auth_client._auth_state["token"] = "token-1"
    monkeypatch.setattr(
        auth_client,
        "_session",
        _FakeSession(
            _FakeResponse(
                200,
                {
                    "success": False,
                    "code": "IDEMPOTENCY_REPLAY",
                    "reservation_id": "released-reservation",
                    "reservation_status": "released",
                },
            )
        ),
    )

    result = auth_client.reserve_work("released-key")

    assert result["success"] is False
    assert result.get("recovered") is not True


def test_default_weekly_checkout_uses_supported_card_method(monkeypatch):
    monkeypatch.delenv("THREAD_AUTO_PAYAPP_PAYMENT_TYPE", raising=False)
    assert auth_client._resolve_default_payapp_payment_type() == "card"
    assert "card" in auth_client._ALLOWED_PAYAPP_PAYMENT_TYPES
    assert "vbank" not in auth_client._ALLOWED_PAYAPP_PAYMENT_TYPES


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


def test_remember_login_credentials_persists_auto_login_opt_in(monkeypatch):
    captured = {}

    def _fake_save(payload):
        captured["payload"] = payload

    monkeypatch.setattr(auth_client, "_load_cred", lambda: {})
    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)
    auth_client.remember_login_credentials("Test_User", "SamplePass123", auto_login=True)

    assert captured["payload"] == {
        "username": "test_user",
        "saved_password": "SamplePass123",
        "auto_login": True,
    }


def test_remember_login_credentials_clears_auto_login_without_password(monkeypatch):
    captured = {}

    def _fake_save(payload):
        captured["payload"] = payload

    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {
            "username": "test_user",
            "saved_password": "SamplePass123",
            "auto_login": True,
            "token": "token-1",
        },
    )
    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)
    auth_client.remember_login_credentials("Test_User", "")

    assert captured["payload"] == {"username": "test_user", "token": "token-1"}


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


def test_get_saved_credentials_returns_auto_login_when_password_present(monkeypatch):
    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {
            "username": "test_user",
            "saved_password": "SamplePass123",
            "auto_login": True,
        },
    )

    result = auth_client.get_saved_credentials()

    assert result == {
        "username": "test_user",
        "password": "SamplePass123",
        "auto_login": True,
    }


def test_get_saved_credentials_clears_auto_login_without_password(monkeypatch):
    state = {}
    monkeypatch.setattr(
        auth_client,
        "_load_cred",
        lambda: {"username": "test_user", "auto_login": True},
    )

    def _fake_save(payload):
        state["saved"] = payload

    monkeypatch.setattr(auth_client, "_save_cred", _fake_save)

    result = auth_client.get_saved_credentials()

    assert result == {"username": "test_user"}
    assert state["saved"] == {"username": "test_user"}


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


def test_localize_message_for_missing_payapp_userid():
    result = auth_client._localize_message(
        "Payment configuration is incomplete. Please contact support. (PAYAPP_USERID missing)"
    )

    assert "결제 서버 설정" in result
    assert "PAYAPP_USERID" in result


def test_localize_message_for_missing_payapp_linkkey_linkval():
    result = auth_client._localize_message(
        "Payment configuration is incomplete. Please contact support. (PAYAPP_LINKKEY/PAYAPP_LINKVAL missing)"
    )

    assert "결제 서버 설정" in result
    assert "PAYAPP_LINKKEY" in result
    assert "PAYAPP_LINKVAL" in result


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


def test_register_does_not_retry_ambiguous_connection_failure(monkeypatch):
    _reset_auth_state()
    session = _SequenceSession(
        [
            requests.exceptions.ConnectionError("registration response was lost"),
            _FakeResponse(200, {"success": True}),
        ]
    )
    monkeypatch.setattr(auth_client, "_session", session)

    result = auth_client.register(
        name="Tester1",
        username="no_retry_user",
        password="SamplePass123",
        contact="01012345678",
        email="sample@example.com",
        terms_accepted=True,
        privacy_accepted=True,
    )

    assert result["success"] is False
    assert len(session.calls) == 1


def test_credential_save_fails_closed_when_temp_acl_fails(monkeypatch, tmp_path):
    cred_dir = tmp_path / "credentials"
    monkeypatch.setattr(auth_client, "_CRED_DIR", cred_dir)
    monkeypatch.setattr(auth_client, "_CRED_FILE", cred_dir / "auth.json")
    monkeypatch.setattr(auth_client, "_API_HOST_LOCK_FILE", cred_dir / "api_host.lock")
    monkeypatch.setattr(auth_client, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(auth_client, "secure_file_permissions", lambda _path: False)

    assert auth_client._save_cred({"username": "tester"}) is False
    assert not auth_client._CRED_FILE.exists()
    assert list(cred_dir.glob("auth_*.tmp")) == []


def test_credential_save_removes_published_file_when_final_acl_fails(
    monkeypatch, tmp_path
):
    cred_dir = tmp_path / "credentials"
    results = iter([True, False])
    monkeypatch.setattr(auth_client, "_CRED_DIR", cred_dir)
    monkeypatch.setattr(auth_client, "_CRED_FILE", cred_dir / "auth.json")
    monkeypatch.setattr(auth_client, "_API_HOST_LOCK_FILE", cred_dir / "api_host.lock")
    monkeypatch.setattr(auth_client, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(
        auth_client, "secure_file_permissions", lambda _path: next(results)
    )

    assert auth_client._save_cred({"username": "tester"}) is False
    assert not auth_client._CRED_FILE.exists()


def test_explicit_remember_clear_deletes_unreadable_existing_credentials(
    monkeypatch, tmp_path
):
    cred_dir = tmp_path / "credentials"
    cred_dir.mkdir()
    cred_file = cred_dir / "auth.json"
    cred_file.write_text('{"saved_password":"stale"}', encoding="utf-8")
    monkeypatch.setattr(auth_client, "_CRED_DIR", cred_dir)
    monkeypatch.setattr(auth_client, "_CRED_FILE", cred_file)
    monkeypatch.setattr(auth_client, "secure_file_permissions", lambda _path: False)

    assert auth_client.remember_login_credentials("", "") is True
    assert not cred_file.exists()


def test_clear_local_session_deletes_unreadable_existing_token(monkeypatch, tmp_path):
    cred_dir = tmp_path / "credentials"
    cred_dir.mkdir()
    cred_file = cred_dir / "auth.json"
    cred_file.write_text('{"token":"stale-token"}', encoding="utf-8")
    monkeypatch.setattr(auth_client, "_CRED_DIR", cred_dir)
    monkeypatch.setattr(auth_client, "_CRED_FILE", cred_file)
    monkeypatch.setattr(auth_client, "secure_file_permissions", lambda _path: False)

    auth_client.clear_local_session()

    assert not cred_file.exists()


def test_secret_protection_failure_removes_stale_credentials(monkeypatch, tmp_path):
    cred_dir = tmp_path / "credentials"
    cred_dir.mkdir()
    cred_file = cred_dir / "auth.json"
    cred_file.write_text('{"saved_password":"stale"}', encoding="utf-8")
    monkeypatch.setattr(auth_client, "_CRED_DIR", cred_dir)
    monkeypatch.setattr(auth_client, "_CRED_FILE", cred_file)
    monkeypatch.setattr(auth_client, "_protect_secret", lambda _value: None)

    assert auth_client._save_cred({"saved_password": "replacement"}) is False
    assert not cred_file.exists()
