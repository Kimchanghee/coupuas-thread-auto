import pytest

from src.services.cancellation import OperationCancelled
from src.services.coupang_parser import CoupangParser


class _Response:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class _RedirectSession:
    def __init__(self):
        self.head_calls = 0
        self.get_calls = 0

    def head(self, url, allow_redirects=False, timeout=10):
        self.head_calls += 1
        return _Response(200)

    def get(self, url, allow_redirects=False, timeout=10):
        self.get_calls += 1
        if self.get_calls == 1:
            return _Response(
                302,
                {"Location": "https://www.coupang.com/vp/products/123456?itemId=7"},
            )
        return _Response(200)


def test_follow_redirect_falls_back_to_get_when_head_does_not_resolve_product():
    parser = CoupangParser()
    session = _RedirectSession()
    parser.session = session

    final_url = parser._follow_redirect("https://link.coupang.com/a/example")

    assert final_url == "https://www.coupang.com/vp/products/123456?itemId=7"
    assert session.head_calls == 1
    assert session.get_calls == 2


def test_follow_redirect_obeys_cancel_check_before_network_request():
    parser = CoupangParser()

    with pytest.raises(OperationCancelled):
        parser._follow_redirect(
            "https://link.coupang.com/a/example",
            cancel_check=lambda: True,
        )


def test_validate_link_accepts_only_partner_short_links():
    parser = CoupangParser()

    assert parser.validate_link("https://link.coupang.com/a/abc123")
    assert not parser.validate_link("https://www.coupang.com/vp/products/123456")
    assert not parser.validate_link("https://coupang.com/vp/products/123456")


def test_extract_links_from_text_ignores_raw_product_urls():
    parser = CoupangParser()

    links = parser.extract_links_from_text(
        "원본 https://www.coupang.com/vp/products/123456 "
        "파트너스 https://link.coupang.com/a/abc123"
    )

    assert links == ["https://link.coupang.com/a/abc123"]
