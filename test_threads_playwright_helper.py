from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.threads_playwright_helper import ThreadsPlaywrightHelper


class _FakeElement:
    def __init__(self, text: str = "", *, visible: bool = True, row=None):
        self.text = text
        self.visible = visible
        self.row = row
        self.click_calls = 0

    def is_visible(self, timeout=None) -> bool:
        return self.visible

    def evaluate(self, script: str):
        if "isConnected" in script:
            return True
        if "tagName" in script:
            return "DIV"
        return self.text

    def click(self):
        self.click_calls += 1

    def evaluate_handle(self, _script: str, _container):
        return _FakeJSHandle(self.row)


class _FakeJSHandle:
    def __init__(self, element):
        self.element = element

    def as_element(self):
        return self.element


class _FakeRow:
    def __init__(self):
        self.preview_count = 0
        self.processing = False
        self.error = False

    def query_selector_all(self, selector: str):
        if selector == ThreadsPlaywrightHelper._MEDIA_PREVIEW_SELECTOR:
            return [_FakeElement() for _ in range(self.preview_count)]
        if selector == ThreadsPlaywrightHelper._MEDIA_PROCESSING_SELECTOR:
            return [_FakeElement()] if self.processing else []
        if selector == ThreadsPlaywrightHelper._MEDIA_ERROR_SELECTOR:
            return [_FakeElement()] if self.error else []
        return []


class _FakeLocator:
    def __init__(
        self,
        count: int = 0,
        visible: bool = True,
        *,
        text: str = "",
        children=None,
        handles=None,
        items=None,
        attrs=None,
    ):
        self._count = count
        self._visible = visible
        self._text = text
        self._children = dict(children or {})
        self._handles = list(handles or [])
        self._items = list(items) if items is not None else None
        self._attrs = dict(attrs or {})
        self.clicked = False
        self.click_calls = 0

    @property
    def first(self):
        if self._items:
            return self._items[0]
        return self

    def nth(self, index: int):
        if self._items is not None:
            return self._items[index]
        return self

    def count(self) -> int:
        if self._items is not None:
            return len(self._items)
        return self._count

    def is_visible(self, timeout=None) -> bool:
        return self._visible and self._count > 0

    def locator(self, selector: str):
        return self._children.get(selector, _FakeLocator())

    def element_handles(self):
        return list(self._handles)

    def element_handle(self):
        return self

    def inner_text(self):
        return self._text

    def get_attribute(self, name: str):
        return self._attrs.get(name)

    def click(self, **_kwargs):
        self.clicked = True
        self.click_calls += 1


class _FakeFileInput(_FakeLocator):
    def __init__(self, *, verify_state: bool = True, on_select=None):
        super().__init__(1)
        self.verify_state = verify_state
        self.on_select = on_select
        self.selected_path: str | None = None

    def set_input_files(self, path: str):
        self.selected_path = path
        if self.on_select:
            self.on_select()

    def evaluate(self, script: str):
        if "el.files" not in script or not self.verify_state or not self.selected_path:
            return {"count": 0, "names": []}
        return {
            "count": 1,
            "names": [Path(self.selected_path).name],
        }


class _FakePage:
    url = "https://www.threads.net"

    def __init__(self):
        self.goto_calls: list[str] = []
        self.compose_open = False

    def locator(self, selector: str):
        if self.compose_open and selector == 'div[role="dialog"]':
            editor = _FakeElement()
            return _FakeLocator(
                1,
                children={
                    ThreadsPlaywrightHelper._COMPOSE_EDITOR_SELECTOR: _FakeLocator(
                        1,
                        handles=[editor],
                    ),
                    ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR: _FakeLocator(
                        1,
                        text="Post",
                    ),
                },
            )
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


class _ScopedComposePage:
    url = "https://www.threads.net/"

    def __init__(self):
        self.unrelated_visible_editor = _FakeElement("unrelated page draft")
        editor_handles = [
            _FakeElement("root\npost"),
            _FakeElement("product   comment"),
            _FakeElement("hidden stale editor", visible=False),
        ]
        self.compose = _FakeLocator(
            1,
            children={
                ThreadsPlaywrightHelper._COMPOSE_EDITOR_SELECTOR: _FakeLocator(
                    3,
                    handles=editor_handles,
                ),
                ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR: _FakeLocator(
                    1,
                    text="게시",
                ),
            },
        )

    def locator(self, selector: str):
        if selector == ThreadsPlaywrightHelper._COMPOSE_EDITOR_SELECTOR:
            raise AssertionError("editors must never be queried from the page root")
        if selector == 'div[role="dialog"]':
            return self.compose
        return _FakeLocator()


class _UploadComposePage:
    url = "https://www.threads.net/"

    def __init__(
        self,
        *,
        verify_state: bool = True,
        add_preview: bool = True,
        processing: bool = False,
        upload_error: bool = False,
    ):
        self.rows = [_FakeRow(), _FakeRow()]
        self.editors = [
            _FakeElement(row=self.rows[0]),
            _FakeElement(row=self.rows[1]),
        ]

        def complete_target_upload():
            self.rows[1].preview_count = 1 if add_preview else 0
            self.rows[1].processing = processing
            self.rows[1].error = upload_error

        self.file_inputs = [
            _FakeFileInput(),
            _FakeFileInput(
                verify_state=verify_state,
                on_select=complete_target_upload,
            ),
        ]
        self.post_control = _FakeLocator(1, text="Post")
        self.compose = _FakeLocator(
            1,
            children={
                ThreadsPlaywrightHelper._COMPOSE_EDITOR_SELECTOR: _FakeLocator(
                    2,
                    handles=self.editors,
                ),
                ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR: self.post_control,
                'input[type="file"]': _FakeLocator(items=self.file_inputs),
            },
        )

    def locator(self, selector: str):
        if selector in {
            ThreadsPlaywrightHelper._COMPOSE_EDITOR_SELECTOR,
            'input[type="file"]',
        }:
            raise AssertionError("compose descendants must not be queried globally")
        if selector == 'div[role="dialog"]':
            return self.compose
        return _FakeLocator()


class _PostEvidencePage:
    url = "https://www.threads.net/"

    def __init__(self, articles=None):
        self.articles = list(articles or [])

    def locator(self, selector: str):
        if selector == "article":
            return _FakeLocator(items=self.articles)
        return _FakeLocator()


def _post_evidence_article(*, text: str, timestamp: float, username: str):
    timestamp_value = datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).isoformat()
    return _FakeLocator(
        1,
        children={
            '[data-testid="post-text"], div[dir="auto"], span[dir="auto"]': _FakeLocator(
                1,
                text=text,
            ),
            "time[datetime]": _FakeLocator(
                1,
                attrs={"datetime": timestamp_value},
            ),
            'a[href*="/post/"]': _FakeLocator(
                1,
                attrs={"href": f"/@{username}/post/new-post-id"},
            ),
        },
    )


class _IdentityItem:
    def __init__(self, href: str, *, visible: bool = True, in_article: bool = False):
        self.href = href
        self.visible = visible
        self.in_article = in_article

    def is_visible(self, timeout=None):
        return self.visible

    def get_attribute(self, name: str):
        return self.href if name == "href" else None

    def evaluate(self, _script: str):
        return not self.in_article


class _IdentityLocator:
    def __init__(self, items=None):
        self.items = list(items or [])

    def count(self):
        return len(self.items)

    def nth(self, index: int):
        return self.items[index]


class _IdentityPage:
    def __init__(self, selectors=None, *, url="https://www.threads.net/"):
        self.url = url
        self.selectors = dict(selectors or {})
        self.requested_selectors: list[str] = []

    def locator(self, selector: str):
        self.requested_selectors.append(selector)
        return _IdentityLocator(self.selectors.get(selector, []))


def test_click_new_thread_falls_back_to_direct_intent_route(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_THREADS_BASE_URL", "https://www.threads.net")
    monkeypatch.delenv("THREAD_AUTO_THREADS_BASE_URLS", raising=False)

    page = _FakePage()
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_new_thread() is True
    assert page.goto_calls[0] == "https://www.threads.net/intent/post"


def test_compose_editors_are_scoped_and_hidden_or_unrelated_editors_are_ignored():
    helper = ThreadsPlaywrightHelper(_ScopedComposePage())

    assert helper.count_textareas() == 2
    assert helper._read_compose_editor_texts() == [
        "root\npost",
        "product   comment",
    ]
    assert helper._verify_compose_paragraphs(
        ["root post", "product comment"]
    ) is True


def test_post_button_uses_one_normal_click_inside_active_compose_only():
    page = _ScopedComposePage()
    post_control = page.compose._children[
        ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR
    ]
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_post_button() is True
    assert post_control.click_calls == 1
    assert helper.external_post_attempted is True


def test_add_to_thread_click_is_exact_unique_and_compose_scoped(monkeypatch):
    page = _ScopedComposePage()
    post_control = _FakeLocator(1, text="Post")
    add_control = _FakeLocator(1, text="Add to thread")
    hidden_add = _FakeLocator(1, visible=False, text="Add to thread")
    page.compose._children[
        ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR
    ] = _FakeLocator(items=[post_control, add_control, hidden_add])
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)

    assert helper.click_add_to_thread() is True
    assert add_control.click_calls == 1
    assert post_control.click_calls == 0
    assert hidden_add.click_calls == 0


def test_post_button_ambiguity_does_not_mark_external_attempt():
    page = _ScopedComposePage()
    page.compose._children[
        ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR
    ] = _FakeLocator(2, text="Post")
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_post_button() is False
    assert helper.external_post_attempted is False
    assert helper.last_error == "post_button_ambiguous"


def test_post_click_exception_after_invocation_remains_an_external_attempt():
    page = _ScopedComposePage()
    post_control = page.compose._children[
        ThreadsPlaywrightHelper._COMPOSE_POST_CONTROL_SELECTOR
    ]

    def fail_during_click():
        raise RuntimeError("navigation destroyed execution context")

    post_control.click = fail_during_click
    helper = ThreadsPlaywrightHelper(page)

    assert helper.click_post_button() is False
    assert helper.external_post_attempted is True
    assert helper.last_error == "post_button_click_failed"


def test_upload_image_uses_matching_compose_row_and_verifies_file_state(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"test image")
    page = _UploadComposePage()
    helper = ThreadsPlaywrightHelper(page)

    assert helper.upload_image(str(image_path), post_index=1) is True
    assert page.file_inputs[0].selected_path is None
    assert page.file_inputs[1].selected_path == str(image_path.resolve())


def test_shared_compose_file_input_is_bound_by_focusing_exact_target_row(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"test image")
    page = _UploadComposePage()

    def complete_upload():
        page.rows[1].preview_count = 1

    shared_input = _FakeFileInput(on_select=complete_upload)
    page.file_inputs = [shared_input]
    page.compose._children['input[type="file"]'] = _FakeLocator(
        items=[shared_input]
    )
    helper = ThreadsPlaywrightHelper(page)

    assert helper.upload_image(str(image_path), post_index=1) is True
    assert page.editors[0].click_calls == 0
    assert page.editors[1].click_calls == 1


def test_upload_image_fails_closed_when_attachment_state_is_not_confirmed(
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"test image")
    page = _UploadComposePage(verify_state=True, add_preview=False)
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setenv("THREAD_AUTO_MEDIA_VERIFY_POLLS", "1")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)

    assert helper.upload_image(str(image_path), post_index=1) is False
    assert helper.last_error == "media_attachment_unverified"


def test_upload_image_rejects_row_error_even_when_file_list_is_populated(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"test image")
    helper = ThreadsPlaywrightHelper(
        _UploadComposePage(verify_state=True, upload_error=True)
    )

    assert helper.upload_image(str(image_path), post_index=1) is False
    assert helper.last_error == "media_attachment_rejected"


def test_upload_image_rejects_preview_that_never_finishes_processing(
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"test image")
    helper = ThreadsPlaywrightHelper(
        _UploadComposePage(verify_state=True, add_preview=True, processing=True)
    )
    monkeypatch.setenv("THREAD_AUTO_MEDIA_VERIFY_POLLS", "2")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)

    assert helper.upload_image(str(image_path), post_index=1) is False
    assert helper.last_error == "media_attachment_unverified"


def test_compose_disappearance_or_url_change_is_not_post_success_evidence(monkeypatch):
    helper = ThreadsPlaywrightHelper(_PostEvidencePage())
    monkeypatch.setattr(
        "src.threads_playwright_helper.goto_threads_with_fallback",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    monkeypatch.setattr(helper, "verify_account", lambda _username: True)

    assert helper.verify_post_success(
        "root post",
        expected_username="expected_user",
        attempted_after=1000.0,
    ) is False
    assert helper.last_error == "posting_unknown"


def test_post_success_requires_exact_text_recent_timestamp_and_self_permalink(
    monkeypatch,
):
    attempted_after = 1000.0
    article = _post_evidence_article(
        text="root\n  post",
        timestamp=attempted_after + 1,
        username="expected_user",
    )
    helper = ThreadsPlaywrightHelper(_PostEvidencePage([article]))
    monkeypatch.setattr(
        "src.threads_playwright_helper.goto_threads_with_fallback",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    monkeypatch.setattr(helper, "verify_account", lambda _username: True)

    assert helper.verify_post_success(
        "root post",
        expected_username="expected_user",
        attempted_after=attempted_after,
    ) is True


def test_old_matching_profile_post_is_not_evidence_for_current_attempt(monkeypatch):
    attempted_after = 1000.0
    article = _post_evidence_article(
        text="root post",
        timestamp=attempted_after - 60,
        username="expected_user",
    )
    helper = ThreadsPlaywrightHelper(_PostEvidencePage([article]))
    monkeypatch.setattr(
        "src.threads_playwright_helper.goto_threads_with_fallback",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    monkeypatch.setattr(helper, "verify_account", lambda _username: True)

    assert helper.verify_post_success(
        "root post",
        expected_username="expected_user",
        attempted_after=attempted_after,
    ) is False
    assert helper.last_error == "posting_unknown"


def test_feed_author_and_public_profile_url_cannot_prove_self_identity(monkeypatch):
    page = _IdentityPage(
        {
            # This selector was the old false-positive path. It is deliberately
            # not an authoritative self-profile control and must never be read.
            'a[href*="/@"][role="link"]': [_IdentityItem("/@expected_user")],
        },
        url="https://www.threads.net/@expected_user",
    )
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.get_logged_in_username() is None
    assert helper.verify_account("expected_user") is False
    assert 'a[href*="/@"][role="link"]' not in page.requested_selectors
    assert helper.last_error == "self_identity_unknown"


def test_profile_like_link_inside_feed_article_is_not_identity_evidence(monkeypatch):
    selector = 'a[data-testid="nav-profile"][href*="/@"]'
    page = _IdentityPage(
        {selector: [_IdentityItem("/@feed_author", in_article=True)]}
    )
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.verify_account("feed_author") is False
    assert helper.last_error == "self_identity_unknown"


def test_recommendation_profile_link_outside_navigation_is_not_identity_evidence(
    monkeypatch,
):
    selector = 'a[role="link"][aria-label="Profile"][href*="/@"]'
    page = _IdentityPage({selector: [_IdentityItem("/@recommended_user")]})
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.verify_account("recommended_user") is False
    assert selector not in page.requested_selectors
    assert helper.last_error == "self_identity_unknown"


def test_authoritative_self_profile_control_proves_identity(monkeypatch):
    selector = 'nav a[aria-label="Profile"][href*="/@"]'
    page = _IdentityPage(
        {selector: [_IdentityItem("https://www.threads.net/@Expected.User/")]}
    )
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.get_logged_in_username() == "expected.user"
    assert helper.verify_account("@EXPECTED.USER") is True


def test_conflicting_authoritative_self_profile_controls_fail_closed(monkeypatch):
    page = _IdentityPage(
        {
            'nav a[aria-label="Profile"][href*="/@"]': [
                _IdentityItem("/@first_user")
            ],
            'nav a[aria-label="프로필"][href*="/@"]': [
                _IdentityItem("/@other_user")
            ],
        }
    )
    helper = ThreadsPlaywrightHelper(page)
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.get_logged_in_username() is None
    assert helper.verify_account("first_user") is False
    assert helper.last_error == "self_identity_conflict"


def test_account_verification_requires_an_expected_username(monkeypatch):
    selector = 'nav a[aria-label="Profile"][href*="/@"]'
    helper = ThreadsPlaywrightHelper(
        _IdentityPage({selector: [_IdentityItem("/@signed_in_user")]})
    )
    monkeypatch.setattr(helper, "check_login_status", lambda: True)

    assert helper.verify_account("") is False
    assert helper.last_error == "expected_identity_missing"


class _PostingHelper(ThreadsPlaywrightHelper):
    def __init__(self, page):
        super().__init__(page)
        self.typed: list[tuple[str, int]] = []
        self.verify_calls: list[str] = []
        self.identity_matches = True

    def click_new_thread(self) -> bool:
        self.page.compose_open = True
        return True

    def verify_account(self, expected_username: str) -> bool:
        self.verify_calls.append(expected_username)
        return self.identity_matches

    def type_in_textarea(self, text, index=0, require_empty=False) -> bool:
        self.typed.append((text, index))
        return True

    def count_textareas(self) -> int:
        return 2

    def find_empty_textarea_index(self):
        return 1

    def _read_compose_editor_texts(self):
        latest_by_index = {index: text for text, index in self.typed}
        return [latest_by_index[index] for index in sorted(latest_by_index)]

    def click_post_button(self) -> bool:
        self.external_post_attempted = True
        return True

    def verify_post_success(
        self,
        first_paragraph: str,
        *,
        expected_username: str,
        attempted_after: float,
    ) -> bool:
        return True


class _MediaPostingHelper(_PostingHelper):
    def __init__(self, page, *, upload_result=True):
        super().__init__(page)
        self.upload_result = upload_result
        self.uploaded: list[tuple[str, int]] = []
        self.post_clicked = False

    def upload_image(self, image_path, *, post_index=0):
        self.uploaded.append((image_path, post_index))
        return self.upload_result

    def click_post_button(self) -> bool:
        self.post_clicked = True
        self.external_post_attempted = True
        return True


class _FinalCountMismatchHelper(_MediaPostingHelper):
    def __init__(self, page):
        super().__init__(page)
        self._count_calls = 0

    def count_textareas(self) -> int:
        self._count_calls += 1
        return 2

    def _read_compose_editor_texts(self):
        return ["root"]


class _ContentMismatchHelper(_MediaPostingHelper):
    def _read_compose_editor_texts(self):
        return ["root", "different comment"]


def test_create_thread_ignores_hidden_login_text_when_compose_is_open(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setenv("THREAD_AUTO_FORCE_SINGLE_POST", "1")

    page = _FakePage()
    helper = _PostingHelper(page)

    assert helper.create_thread_direct(
        ["first post", "second post"],
        expected_username="expected_user",
    ) is True
    assert helper.last_error is None
    assert helper.external_post_attempted is True
    assert helper.verify_calls == ["expected_user"]
    assert [text for text, _ in helper.typed] == ["first post", "second post"]


def test_create_thread_rejects_any_payload_except_root_and_comment(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    page = _FakePage()
    helper = _PostingHelper(page)

    assert helper.create_thread_direct(
        ["root only"],
        expected_username="expected_user",
    ) is False
    assert helper.last_error == "invalid_thread_structure"
    assert helper.typed == []


@pytest.mark.parametrize(
    "payload",
    [
        ["root", "", "comment"],
        ["root", ""],
        ["root", {"text": "comment"}],
    ],
)
def test_create_thread_rejects_extra_empty_or_mixed_payload_shapes(
    monkeypatch,
    payload,
):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    helper = _PostingHelper(_FakePage())

    assert helper.create_thread_direct(
        payload,
        expected_username="expected_user",
    ) is False
    assert helper.last_error == "invalid_thread_structure"
    assert helper.external_post_attempted is False


def test_create_thread_attaches_media_to_each_matching_payload(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    helper = _MediaPostingHelper(_FakePage())

    assert helper.create_thread_direct(
        [
            {"text": "root", "image_path": "root.jpg"},
            {"text": "comment", "image_path": "comment.jpg"},
        ],
        expected_username="expected_user",
    ) is True

    assert helper.uploaded == [("root.jpg", 0), ("comment.jpg", 1)]
    assert helper.post_clicked is True


def test_create_thread_aborts_when_requested_media_cannot_be_attached(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    helper = _MediaPostingHelper(_FakePage(), upload_result=False)

    assert helper.create_thread_direct(
        [
            {"text": "root", "image_path": None},
            {"text": "comment", "image_path": "missing.jpg"},
        ],
        expected_username="expected_user",
    ) is False

    assert helper.last_error == "media_upload_failed:1"
    assert helper.post_clicked is False


def test_create_thread_aborts_when_final_thread_structure_cannot_be_verified(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    helper = _FinalCountMismatchHelper(_FakePage())

    assert helper.create_thread_direct(
        [
            {"text": "root", "image_path": None},
            {"text": "comment", "image_path": None},
        ],
        expected_username="expected_user",
    ) is False

    assert helper.last_error == "thread_structure_unverified"
    assert helper.external_post_attempted is False
    assert helper.post_clicked is False


def test_create_thread_aborts_before_post_when_editor_text_does_not_exactly_match(
    monkeypatch,
):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    helper = _ContentMismatchHelper(_FakePage())

    assert helper.create_thread_direct(
        [
            {"text": "root", "image_path": None},
            {"text": "comment", "image_path": None},
        ],
        expected_username="expected_user",
    ) is False

    assert helper.last_error == "thread_content_unverified"
    assert helper.external_post_attempted is False
    assert helper.post_clicked is False


def test_create_thread_requires_keyword_only_expected_username():
    helper = _PostingHelper(_FakePage())

    with pytest.raises(TypeError):
        helper.create_thread_direct(["root", "comment"])


def test_create_thread_blocks_identity_change_before_external_post(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "30")
    monkeypatch.setattr("src.threads_playwright_helper.time.sleep", lambda *_args: None)
    helper = _MediaPostingHelper(_FakePage())
    helper.identity_matches = False

    assert helper.create_thread_direct(
        [
            {"text": "root", "image_path": None},
            {"text": "comment", "image_path": None},
        ],
        expected_username="expected_user",
    ) is False

    assert helper.verify_calls == ["expected_user"]
    assert helper.external_post_attempted is False
    assert helper.post_clicked is False
    assert helper.last_error == "account_identity_unverified"
