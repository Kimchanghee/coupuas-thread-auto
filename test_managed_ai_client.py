from unittest.mock import Mock

import pytest
import requests

from src.services.managed_ai_client import (
    DEFAULT_MANAGED_AI_URL,
    ManagedAiClient,
    ManagedAiClientError,
)


def _success_payload():
    return {
        "success": True,
        "ai_job_id": "job-1",
        "reservation_id": "res-1",
        "quota_mode": "legacy",
        "prompt_version": "threads-ko-v1",
        "model": "xai/grok-4.3",
        "degraded": False,
        "degraded_reason": "",
        "variants": [
            {
                "variant_id": variant_id,
                "root_text": f"{variant_id} 첫 글",
                "product_comment_text": "상품 댓글",
            }
            for variant_id in (
                "target_direct",
                "convenience_contrast",
                "fun_reveal",
                "use_scene_story",
            )
        ],
    }


def test_managed_client_uses_application_login(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "login-token", "user_id": "42"}),
    )
    response = Mock(ok=True, status_code=200)
    response.json.return_value = _success_payload()
    session = Mock()
    session.post.return_value = response
    client = ManagedAiClient(DEFAULT_MANAGED_AI_URL, session=session)

    result = client.generate_variants(
        {
            "title": "휴대용 선풍기",
            "original_url": "https://link.coupang.com/a/example",
            "search_keywords": "여름 출퇴근",
        }
    )

    assert result.reservation_id == "res-1"
    assert result.quota_mode == "legacy"
    assert result.degraded is False
    assert len(result.variants) == 4
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer login-token"
    assert kwargs["json"]["user_id"] == "42"
    assert "api_key" not in str(kwargs).lower()


def test_managed_client_reuses_caller_persisted_idempotency_key(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "login-token", "user_id": "42"}),
    )
    response = Mock(ok=True, status_code=200)
    response.json.return_value = _success_payload()
    session = Mock()
    session.post.return_value = response
    client = ManagedAiClient(DEFAULT_MANAGED_AI_URL, session=session)
    product = {"title": "상품", "original_url": "https://example.com/item"}

    client.generate_variants(product, idempotency_key="durable-queue-key")
    client.generate_variants(product, idempotency_key="durable-queue-key")

    assert [
        call.kwargs["headers"]["Idempotency-Key"]
        for call in session.post.call_args_list
    ] == ["durable-queue-key", "durable-queue-key"]


def test_managed_client_requires_login(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {}),
    )
    with pytest.raises(ManagedAiClientError) as exc_info:
        ManagedAiClient(DEFAULT_MANAGED_AI_URL).generate_variants(
            {"title": "상품", "original_url": "https://example.com"}
        )
    assert exc_info.value.code == "AUTH_REQUIRED"


def test_managed_client_surfaces_subscription_error(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=False, status_code=403)
    response.json.return_value = {
        "success": False,
        "code": "SUBSCRIPTION_REQUIRED",
        "message": "구독이 필요합니다.",
    }
    session = Mock()
    session.post.return_value = response
    client = ManagedAiClient(DEFAULT_MANAGED_AI_URL, session=session)

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com"}
        )
    assert exc_info.value.code == "SUBSCRIPTION_REQUIRED"


def test_managed_client_preserves_only_safe_release_reconciliation_metadata(
    monkeypatch,
):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=False, status_code=503)
    response.json.return_value = {
        "success": False,
        "code": "AI_TEMPORARILY_UNAVAILABLE",
        "message": "잠시 후 다시 시도해주세요.",
        "reservation_release_pending": True,
        "reservation_id": "reservation-reconcile-1",
        "ai_job_id": "job-reconcile-1",
        "provider_secret": "must-not-escape",
        "debug": {"prompt": "private prompt"},
    }
    session = Mock(post=Mock(return_value=response))
    client = ManagedAiClient(DEFAULT_MANAGED_AI_URL, session=session)

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="durable-key",
        )

    error = exc_info.value
    assert error.status_code == 503
    assert error.reservation_release_pending is True
    assert error.reservation_id == "reservation-reconcile-1"
    assert error.ai_job_id == "job-reconcile-1"
    assert "must-not-escape" not in str(error)
    assert "private prompt" not in repr(vars(error))


def test_released_replay_preserves_only_retry_with_new_key_signal(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=False, status_code=409)
    response.json.return_value = {
        "success": False,
        "code": "DUPLICATE_REQUEST",
        "message": "새 요청 키로 다시 시도해주세요.",
        "retry_with_new_idempotency_key": True,
        "ai_job_id": "lost-response-key",
        "debug": {"prompt": "private"},
    }
    client = ManagedAiClient(
        DEFAULT_MANAGED_AI_URL,
        session=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="lost-response-key",
        )

    error = exc_info.value
    assert error.retry_with_new_idempotency_key is True
    assert error.reservation_release_pending is False
    assert error.reservation_id == ""
    assert error.ai_job_id == "lost-response-key"
    assert "private" not in repr(vars(error))


def test_malformed_success_preserves_reservation_for_release(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {
        "success": True,
        "reservation_id": "reservation-malformed-1",
        "ai_job_id": "job-malformed-1",
        "variants": [{"variant_id": "only-one"}],
    }
    client = ManagedAiClient(
        DEFAULT_MANAGED_AI_URL,
        session=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="durable-key",
        )

    error = exc_info.value
    assert error.code == "INVALID_SERVER_RESPONSE"
    assert error.reservation_release_pending is True
    assert error.reservation_id == "reservation-malformed-1"
    assert error.ai_job_id == "job-malformed-1"


def test_post_timeout_marks_durable_request_for_reservation_reconciliation(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    client = ManagedAiClient(
        DEFAULT_MANAGED_AI_URL,
        session=Mock(post=Mock(side_effect=requests.Timeout("response lost"))),
    )

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="durable-timeout-key",
        )

    error = exc_info.value
    assert error.reservation_release_pending is True
    assert error.reservation_id == ""
    assert error.ai_job_id == "durable-timeout-key"


@pytest.mark.parametrize("payload", [pytest.param(None, id="non-json"), [], "invalid"])
def test_unstructured_success_marks_request_for_reservation_reconciliation(
    monkeypatch,
    payload,
):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=True, status_code=200)
    if payload is None:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = payload
    client = ManagedAiClient(
        DEFAULT_MANAGED_AI_URL,
        session=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="durable-unstructured-key",
        )

    error = exc_info.value
    assert error.reservation_release_pending is True
    assert error.reservation_id == ""
    assert error.ai_job_id == "durable-unstructured-key"


def test_malformed_success_without_reservation_marks_request_for_reconciliation(
    monkeypatch,
):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {"success": True, "variants": []}
    client = ManagedAiClient(
        DEFAULT_MANAGED_AI_URL,
        session=Mock(post=Mock(return_value=response)),
    )

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com/item"},
            idempotency_key="durable-malformed-key",
        )

    error = exc_info.value
    assert error.reservation_release_pending is True
    assert error.reservation_id == ""
    assert error.ai_job_id == "durable-malformed-key"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://coupuas-thread-auto-ten.vercel.app",
        "https://evil.example",
        "https://coupuas-thread-auto-ten.vercel.app.evil.example",
        "https://user:pass@coupuas-thread-auto-ten.vercel.app",
        "https://coupuas-thread-auto-ten.vercel.app/other",
    ],
)
def test_managed_client_rejects_untrusted_login_token_destinations(base_url):
    with pytest.raises(ValueError, match="not trusted"):
        ManagedAiClient(base_url)
