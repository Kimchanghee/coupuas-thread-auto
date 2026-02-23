from __future__ import annotations

from src.threads_navigation import (
    friendly_threads_navigation_error,
    goto_threads_with_fallback,
    is_browser_launch_error,
)


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status


class _FakePage:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def goto(self, url, wait_until=None, timeout=None):  # noqa: D401 - Playwright-compatible stub
        self.calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        if not self._outcomes:
            raise RuntimeError("no more outcomes")
        item = self._outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_goto_threads_with_fallback_uses_next_domain_when_first_fails(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URL", "https://www.threads.net")
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URLS", "https://www.threads.com")

    page = _FakePage(
        [
            RuntimeError("net::ERR_HTTP_RESPONSE_CODE_FAILURE"),
            _FakeResponse(200),
        ]
    )

    resolved = goto_threads_with_fallback(page, path="/login", retries_per_url=0)

    assert resolved == "https://www.threads.com/login"
    assert page.calls[0]["url"] == "https://www.threads.net/login"
    assert page.calls[1]["url"] == "https://www.threads.com/login"


def test_goto_threads_with_fallback_rejects_http_500_and_fallbacks(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URL", "https://www.threads.net")
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URLS", "https://www.threads.com")

    page = _FakePage([_FakeResponse(500), _FakeResponse(200)])
    resolved = goto_threads_with_fallback(page, path="/", retries_per_url=0)

    assert resolved == "https://www.threads.com"
    assert len(page.calls) == 2


def test_friendly_threads_navigation_error_localizes_http_500():
    message = friendly_threads_navigation_error("net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://www.threads.net/login")
    assert "HTTP 500" in message


def test_is_browser_launch_error_detects_missing_executable():
    assert is_browser_launch_error("Browser executable doesn't exist at C:\\foo")

