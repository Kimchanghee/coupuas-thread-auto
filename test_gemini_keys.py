from types import SimpleNamespace

import pytest

from src.gemini_keys import (
    DEFAULT_GEMINI_MODEL,
    generate_content_with_model_fallback,
    get_gemini_model_candidates,
)


class _FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        model = kwargs["model"]
        self.calls.append(kwargs)
        if model == "bad-model":
            raise RuntimeError("404 model not found")
        return SimpleNamespace(text="ok")


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_get_gemini_model_candidates_prefers_override_then_latest(monkeypatch):
    monkeypatch.setenv("GOOGLE_GEMINI_MODEL", "env-model, gemini-flash-latest")

    candidates = get_gemini_model_candidates(["preferred-model", "env-model"])

    assert candidates[:3] == ["preferred-model", "env-model", DEFAULT_GEMINI_MODEL]
    assert len(candidates) == len(set(candidates))


def test_generate_content_with_model_fallback_retries_model_errors():
    client = _FakeClient()

    response, model = generate_content_with_model_fallback(
        client,
        preferred_model=["bad-model", "good-model"],
        contents="ping",
    )

    assert response.text == "ok"
    assert model == "good-model"
    assert [call["model"] for call in client.models.calls] == ["bad-model", "good-model"]


def test_generate_content_with_model_fallback_raises_non_model_errors():
    class Models:
        def generate_content(self, **kwargs):
            raise RuntimeError("permission denied")

    class Client:
        models = Models()

    with pytest.raises(RuntimeError, match="permission denied"):
        generate_content_with_model_fallback(
            Client(),
            preferred_model="bad-model",
            contents="ping",
        )
