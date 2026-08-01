import subprocess

import pytest

from src.ai_provider import (
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_GROK_CLI,
    AI_PROVIDER_MANAGED,
    normalize_ai_provider,
)
from src.services.aggro_generator import AggroGenerator
from src.services.grok_cli_provider import (
    GrokCliError,
    GrokCliProvider,
    find_grok_cli,
)
from src.coupang_uploader import CoupangPartnersPipeline


def test_ai_provider_normalization_defaults_to_managed():
    assert normalize_ai_provider(None) == AI_PROVIDER_MANAGED
    assert normalize_ai_provider("gemini") == AI_PROVIDER_GEMINI
    assert normalize_ai_provider("GROK_CLI") == AI_PROVIDER_GROK_CLI


def test_find_grok_cli_honors_explicit_path(monkeypatch, tmp_path):
    executable = tmp_path / "grok.exe"
    executable.write_bytes(b"placeholder")
    monkeypatch.setenv("GROK_CLI_PATH", str(executable))

    assert find_grok_cli() == str(executable.resolve())


def test_grok_status_is_ready_when_version_and_models_succeed(monkeypatch):
    provider = GrokCliProvider(executable="C:/fake/grok.exe")
    results = iter(
        [
            subprocess.CompletedProcess(["grok", "version"], 0, "grok 0.2.1", ""),
            subprocess.CompletedProcess(["grok", "models"], 0, "grok-4.5", ""),
        ]
    )
    monkeypatch.setattr(provider, "_run", lambda *args, **kwargs: next(results))

    status = provider.status()

    assert status.ready
    assert status.code == "ready"
    assert "로그인됨" in status.message


def test_grok_status_detects_expired_auth_from_stderr(monkeypatch):
    provider = GrokCliProvider(executable="C:/fake/grok.exe")
    results = iter(
        [
            subprocess.CompletedProcess(["grok", "version"], 0, "grok 0.2.1", ""),
            subprocess.CompletedProcess(
                ["grok", "sessions", "list"],
                0,
                "",
                "Your auth token is invalid or expired. Run `grok login`.",
            ),
        ]
    )
    monkeypatch.setattr(provider, "_run", lambda *args, **kwargs: next(results))

    status = provider.status()

    assert status.code == "not_logged_in"
    assert not status.ready


def test_grok_login_uses_official_browser_oauth(monkeypatch):
    provider = GrokCliProvider(executable="C:/fake/grok.exe")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(["grok"], 0, "", "")

    monkeypatch.setattr(provider, "_run", fake_run)
    monkeypatch.setattr(
        provider,
        "status",
        lambda: type("Status", (), {"code": "ready", "ready": True})(),
    )

    status = provider.login()

    assert calls == [["login", "--oauth"]]
    assert status.ready


def test_grok_generation_uses_headless_plain_output(monkeypatch):
    provider = GrokCliProvider(executable="C:/fake/grok.exe")
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return subprocess.CompletedProcess(
            ["grok"],
            0,
            "🚗 차량용 선풍기 하나로 답답한 차 안이 달라 보임\n작지만 필요한 순간은 확실한 아이템 👀",
            "",
        )

    monkeypatch.setattr(provider, "_run", fake_run)

    output = provider.generate_text("두 줄로 작성")

    assert "차량용 선풍기" in output
    assert "--no-auto-update" in captured["args"]
    assert "--disable-web-search" in captured["args"]
    tools_index = captured["args"].index("--tools")
    assert captured["args"][tools_index + 1] == ""
    max_turns_index = captured["args"].index("--max-turns")
    assert captured["args"][max_turns_index + 1] == "1"
    assert "--output-format" in captured["args"]
    assert "plain" in captured["args"]


def test_grok_generation_classifies_free_limit(monkeypatch):
    provider = GrokCliProvider(executable="C:/fake/grok.exe")
    monkeypatch.setattr(
        provider,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["grok"],
            1,
            "",
            "Free-usage limit reached. Upgrade to continue.",
        ),
    )

    with pytest.raises(GrokCliError) as exc_info:
        provider.generate_text("두 줄로 작성")

    assert exc_info.value.code == "free_limit"


def test_aggro_generator_can_use_grok_provider_without_api_key():
    class FakeGrokClient:
        def __init__(self):
            self.prompts = []

        def generate_text(self, prompt):
            self.prompts.append(prompt)
            return (
                "🚗 차량용 선풍기 하나 때문에 답답한 차 안이 은근 달라 보임\n"
                "작은 물건인데 필요한 순간은 너무 선명함 👀"
            )

    fake_client = FakeGrokClient()
    generator = AggroGenerator(
        ai_provider=AI_PROVIDER_GROK_CLI,
        grok_client=fake_client,
    )

    text = generator.generate_aggro_text(
        "켈리마 차량용 선풍기",
        "차량용 선풍기",
    )

    assert "차량용 선풍기" in text
    assert len(text.splitlines()) == 2
    assert fake_client.prompts


def test_pipeline_does_not_use_gemini_key_when_grok_is_selected():
    pipeline = CoupangPartnersPipeline(
        google_api_key="stored-gemini-key",
        ai_provider=AI_PROVIDER_GROK_CLI,
    )

    assert pipeline._resolve_google_api_key() == ""
    assert pipeline.aggro_generator.ai_provider == AI_PROVIDER_GROK_CLI

    pipeline.set_ai_provider(AI_PROVIDER_GEMINI)

    assert pipeline._resolve_google_api_key() == "stored-gemini-key"
    assert pipeline.aggro_generator.ai_provider == AI_PROVIDER_GEMINI
