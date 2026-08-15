import logging
from pathlib import Path

import pytest

from build_installer import _validated_version
from src import auth_client
from src.app_logging import _normalize_record_message
from src.computer_use_agent import ComputerUseAgent
from src.threads_playwright_helper import ThreadsPlaywrightHelper


def test_frozen_auth_endpoint_ignores_external_override():
    assert (
        auth_client._normalize_api_server_url("https://evil.example", frozen=True)
        == auth_client._DEFAULT_API_SERVER_URL
    )


def test_development_auth_endpoint_requires_explicit_trust(monkeypatch):
    monkeypatch.delenv("THREAD_AUTO_ALLOW_CUSTOM_API_URL", raising=False)
    monkeypatch.delenv("THREAD_AUTO_TRUST_CUSTOM_API_URL", raising=False)
    assert (
        auth_client._normalize_api_server_url("https://staging.example", frozen=False)
        == auth_client._DEFAULT_API_SERVER_URL
    )

    monkeypatch.setenv("THREAD_AUTO_ALLOW_CUSTOM_API_URL", "1")
    monkeypatch.setenv("THREAD_AUTO_TRUST_CUSTOM_API_URL", "1")
    assert (
        auth_client._normalize_api_server_url("https://staging.example", frozen=False)
        == "https://staging.example"
    )


def test_log_normalization_blocks_record_forging_and_redacts_secrets():
    record = logging.LogRecord(
        "test",
        logging.WARNING,
        __file__,
        1,
        "message=%s",
        ("first\nFAKE ERROR token=secret-value",),
        None,
    )
    _normalize_record_message(record)

    assert "\n" not in record.getMessage()
    assert "secret-value" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()


def test_legacy_browser_session_path_is_confined(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ComputerUseAgent._resolve_legacy_profile_path(".threads_profile") == (
        tmp_path / ".threads_profile"
    ).resolve()
    assert ComputerUseAgent._resolve_legacy_profile_path("../outside") is None
    assert ComputerUseAgent._resolve_legacy_profile_path(str(tmp_path / "absolute")) is None


def test_session_cookie_domain_requires_a_real_service_boundary():
    assert ThreadsPlaywrightHelper._is_trusted_session_cookie_domain(".threads.net")
    assert ThreadsPlaywrightHelper._is_trusted_session_cookie_domain("www.threads.com")
    assert not ThreadsPlaywrightHelper._is_trusted_session_cookie_domain("evilthreads.net")
    assert not ThreadsPlaywrightHelper._is_trusted_session_cookie_domain("threads.com.evil.example")


def test_installer_version_rejects_compiler_arguments():
    assert _validated_version("v3.0.72") == "3.0.72"
    with pytest.raises(ValueError):
        _validated_version("3.0.72 /DOutputDir=outside")


def test_release_workflow_has_verified_installer_fallback():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")

    assert "foreach ($attempt in 1..3)" in workflow
    assert "jrsoftware/issrc/releases/download/is-6_6_1/innosetup-6.6.1.exe" in workflow
    assert "d243ce440c02705530699554fb9612b9b2bd7a2a90629cdb7f41e66f5faeb91f" in workflow
    assert "Inno Setup installer checksum mismatch" in workflow
