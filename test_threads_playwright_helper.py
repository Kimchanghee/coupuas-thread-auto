from __future__ import annotations

from src.threads_playwright_helper import ThreadsPlaywrightHelper


class _FakeLocator:
    def __init__(self, count: int = 0, visible: bool = True):
        self._count = count
        self._visible = visible
        self.clicked = False

    @property
    def first(self):
        return self

    def nth(self, index: int):
        return self

    def count(self) -> int:
        return self._count

    def is_visible(self, timeout=None) -> bool:
        return self._visible and self._count > 0

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

    def content(self):
        return "hidden footer: 가입 / log in"


def test_click_new_thread_falls_back_to_direct_intent_route(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URL", "https://www.threads.net")
    monkeypatch.delenv("THREAD_AUTO_THREADS_BASE_URLS", raising=False)

    page = _FakePage()
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_new_thread() is True
    assert page.goto_calls[0] == "https://www.threads.net/intent/post"


class _PostingHelper(ThreadsPlaywrightHelper):
    def __init__(self, page):
        super().__init__(page)
        self.typed: list[tuple[str, int]] = []

    def click_new_thread(self) -> bool:
        self.page.compose_open = True
        return True

    def type_in_textarea(self, text, index=0, require_empty=False) -> bool:
        self.typed.append((text, index))
        return True

    def count_textareas(self) -> int:
        return 2

    def find_empty_textarea_index(self):
        return 1

    def click_post_button(self) -> bool:
        return True

    def verify_post_success(self, first_paragraph: str = "") -> bool:
        return True


def test_create_thread_ignores_hidden_login_text_when_compose_is_open(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setenv("THREAD_AUTO_FORCE_SINGLE_POST", "1")

    page = _FakePage()
    helper = _PostingHelper(page)

    assert helper.create_thread_direct(["first post", "second post"]) is True
    assert helper.last_error is None
    assert [text for text, _ in helper.typed] == ["first post", "second post"]


def test_create_thread_rejects_any_payload_except_root_and_comment(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    page = _FakePage()
    helper = _PostingHelper(page)

    assert helper.create_thread_direct(["root only"]) is False
    assert helper.last_error == "invalid_thread_structure"
    assert helper.typed == []
