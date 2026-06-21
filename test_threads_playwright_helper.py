from __future__ import annotations

from src.threads_playwright_helper import ThreadsPlaywrightHelper


class _FakeLocator:
    def __init__(self, count: int = 0):
        self._count = count
        self.clicked = False

    @property
    def first(self):
        return self

    def count(self) -> int:
        return self._count

    def click(self):
        self.clicked = True


class _FakePage:
    url = "https://www.threads.net"

    def __init__(self):
        self.goto_calls: list[str] = []
        self.compose_open = False

    def locator(self, selector: str):
        if self.compose_open and selector == 'textarea, div[contenteditable="true"]':
            return _FakeLocator(1)
        return _FakeLocator(0)

    def get_by_text(self, text: str):
        return _FakeLocator(0)

    def evaluate(self, script: str):
        return False

    def goto(self, url: str, wait_until=None, timeout=None):
        self.goto_calls.append(url)
        if url.endswith("/intent/post"):
            self.compose_open = True
        self.url = url
        return None


def test_click_new_thread_falls_back_to_direct_intent_route(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URL", "https://www.threads.net")
    monkeypatch.delenv("THREAD_AUTO_THREADS_BASE_URLS", raising=False)

    page = _FakePage()
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_new_thread() is True
    assert page.goto_calls[0] == "https://www.threads.net/intent/post"
