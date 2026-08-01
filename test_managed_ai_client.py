from unittest.mock import Mock

import pytest

from src.services.managed_ai_client import ManagedAiClient, ManagedAiClientError


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
    client = ManagedAiClient("https://managed.example", session=session)

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


def test_managed_client_requires_login(monkeypatch):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {}),
    )
    with pytest.raises(ManagedAiClientError) as exc_info:
        ManagedAiClient("https://managed.example").generate_variants(
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
    client = ManagedAiClient("https://managed.example", session=session)

    with pytest.raises(ManagedAiClientError) as exc_info:
        client.generate_variants(
            {"title": "상품", "original_url": "https://example.com"}
        )
    assert exc_info.value.code == "SUBSCRIPTION_REQUIRED"
