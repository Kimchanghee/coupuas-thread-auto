from src.services.coupang_parser import CoupangParser
from src.services.marketplaces import (
    COUPANG_DISCLOSURE,
    GENERAL_AFFILIATE_DISCLOSURE,
    extract_supported_product_links,
    marketplace_for_url,
    normalize_product_url,
)


class _HtmlResponse:
    status_code = 200
    headers = {}
    encoding = "utf-8"
    content = b"""
        <html><head>
        <meta property="og:title" content="Portable Mini Fan">
        <meta property="og:image" content="https://ae01.alicdn.com/item.jpg">
        <meta property="product:price:amount" content="12.50">
        </head></html>
    """


class _HtmlSession:
    def get(self, url, allow_redirects=False, timeout=15):
        assert url == "https://www.aliexpress.com/item/1005001234567890.html"
        assert allow_redirects is False
        return _HtmlResponse()


def test_marketplace_catalog_accepts_supported_product_hosts_only():
    assert marketplace_for_url("https://link.coupang.com/a/example").marketplace_id == "coupang"
    assert marketplace_for_url("https://smartstore.naver.com/main/products/123").marketplace_id == "naver"
    assert marketplace_for_url("https://shopping.toss.im/products/123").marketplace_id == "toss"
    assert marketplace_for_url("https://s.click.aliexpress.com/e/example").marketplace_id == "aliexpress"
    assert marketplace_for_url("https://evil.example/aliexpress.com/item/123") is None
    assert marketplace_for_url("https://pay.toss.im/order/123") is None
    assert normalize_product_url("https://user:pass@shopping.naver.com/product/1") == ""
    assert normalize_product_url("https://shopping.naver.com:444/product/1") == ""


def test_extract_supported_links_preserves_order_and_removes_duplicates():
    text = (
        "네이버 https://smartstore.naver.com/main/products/123,\n"
        "알리 https://www.aliexpress.com/item/456.html\n"
        "중복 https://smartstore.naver.com/main/products/123\n"
        "무시 https://example.com/item/1"
    )

    assert extract_supported_product_links(text) == [
        "https://smartstore.naver.com/main/products/123",
        "https://www.aliexpress.com/item/456.html",
    ]


def test_marketplace_parser_extracts_public_metadata_without_marketplace_api():
    parser = CoupangParser()
    parser.session = _HtmlSession()

    result = parser.parse_link("https://www.aliexpress.com/item/1005001234567890.html")

    assert result["marketplace"] == "aliexpress"
    assert result["marketplace_label"] == "AliExpress"
    assert result["title"] == "Portable Mini Fan"
    assert result["image_url"] == "https://ae01.alicdn.com/item.jpg"
    assert result["price"] == "12.50"
    assert result["product_id"] == "1005001234567890"
    assert result["affiliate_disclosure"] == GENERAL_AFFILIATE_DISCLOSURE


def test_coupang_and_general_disclosures_are_not_conflated():
    assert marketplace_for_url("https://link.coupang.com/a/example").disclosure == COUPANG_DISCLOSURE
    assert (
        marketplace_for_url("https://smartstore.naver.com/main/products/123").disclosure
        == GENERAL_AFFILIATE_DISCLOSURE
    )
