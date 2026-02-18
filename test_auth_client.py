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

    def post(self, url, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.response


def test_login_payload_includes_required_ip(monkeypatch):
    response = _FakeResponse(200, {"status": "EU001", "message": "EU001"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    result = auth_client.login("SampleUser", "SamplePass123")

    assert result["status"] == "EU001"
    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert payload["id"] == "sampleuser"
    assert payload["pw"] == "SamplePass123"
    assert payload["force"] is False
    assert payload["ip"] == "10.20.30.40"


def test_login_422_uses_nested_validation_error_message(monkeypatch):
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


def test_register_200_failure_with_error_object_returns_message(monkeypatch):
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


def test_register_allows_short_password_with_backend_normalization(monkeypatch):
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

    assert result["success"] is True
    assert len(session.calls) == 1
    assert session.calls[0]["json"]["password"].startswith("spw_")
    assert len(session.calls[0]["json"]["password"]) >= 8


def test_login_normalizes_short_password_for_backend(monkeypatch):
    response = _FakeResponse(200, {"status": "EU001", "message": "EU001"})
    session = _FakeSession(response)
    monkeypatch.setattr(auth_client, "_session", session)
    monkeypatch.setattr(auth_client, "_resolve_client_ip", lambda: "10.20.30.40")

    auth_client.login("shortuser", "1")

    payload = session.calls[0]["json"]
    assert payload["pw"].startswith("spw_")
    assert len(payload["pw"]) >= 8


def test_register_429_normalizes_rate_limit_message(monkeypatch):
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
    assert "제한" in result["message"]
    assert "5 per 1 hour" in result["message"]
