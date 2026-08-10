from src.services.coupang_parser import CoupangParser
from src.services.marketplaces import (
    COUPANG_DISCLOSURE,
    GENERAL_AFFILIATE_DISCLOSURE,
    KURLY_DISCLOSURE,
    MUSINSA_DISCLOSURE,
    NAVER_DISCLOSURE,
    OHOUSE_DISCLOSURE,
    OLIVEYOUNG_DISCLOSURE,
    TOSS_DISCLOSURE,
    analyze_product_link_input,
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
    def get(self, url, allow_redirects=False, timeout=15, stream=False):
        assert url == "https://www.aliexpress.com/item/1005001234567890.html"
        assert allow_redirects is False
        assert stream is True
        return _HtmlResponse()


def test_marketplace_catalog_accepts_supported_product_hosts_only():
    assert marketplace_for_url("https://link.coupang.com/a/example").marketplace_id == "coupang"
    assert marketplace_for_url("https://smartstore.naver.com/main/products/123").marketplace_id == "naver"
    assert marketplace_for_url("https://shopping.toss.im/products/123").marketplace_id == "toss"
    assert marketplace_for_url("https://s.click.aliexpress.com/e/example").marketplace_id == "aliexpress"
    assert marketplace_for_url("https://ohou.se/productions/123/selling?af=creator").marketplace_id == "ohouse"
    assert marketplace_for_url("https://ozip.me/hfjSggf?af").marketplace_id == "ohouse"
    assert marketplace_for_url("https://link.ohou.se/@ohouse/affiliate?content=production_123").marketplace_id == "ohouse"
    assert marketplace_for_url("https://www.musinsa.com/curator/goods/YhSMK4").marketplace_id == "musinsa"
    assert marketplace_for_url("https://lounge.kurly.com/link/IbLp-JCWu").marketplace_id == "kurly"
    assert marketplace_for_url("https://oy.run/1JMdYcb").marketplace_id == "oliveyoung"
    assert marketplace_for_url("https://toss.im/_m/7bMVzp83").marketplace_id == "toss"
    assert marketplace_for_url("https://brandconnect.naver.com/affiliates/bridge?channelProductNo=123").marketplace_id == "naver"
    assert marketplace_for_url("https://evil.example/aliexpress.com/item/123") is None
    assert marketplace_for_url("https://pay.toss.im/order/123") is None
    assert marketplace_for_url("http://smartstore.naver.com/main/products/123") is None
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


def test_link_input_analysis_keeps_channel_duplicate_and_exclusion_feedback():
    text = (
        "쿠팡 https://link.coupang.com/a/example\n"
        "네이버 https://naver.me/example\n"
        "중복 https://link.coupang.com/a/example\n"
        "미지원 https://example.com/item/1\n"
        "안전하지 않음 http://smartstore.naver.com/main/products/123\n"
        "메모만 있는 줄"
    )

    analyses = analyze_product_link_input(text)

    assert [item.status for item in analyses] == [
        "supported",
        "supported",
        "duplicate",
        "unsupported",
        "invalid",
        "invalid",
    ]
    assert [item.marketplace.marketplace_id for item in analyses[:3]] == [
        "coupang",
        "naver",
        "coupang",
    ]
    assert analyses[2].line_number == 3
    assert analyses[3].reason == "현재 지원하지 않는 쇼핑 채널입니다."
    assert analyses[4].normalized_url == ""
    assert analyses[5].source_text == "메모만 있는 줄"


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


def test_marketplaces_use_program_specific_disclosures():
    assert marketplace_for_url("https://link.coupang.com/a/example").disclosure == COUPANG_DISCLOSURE
    assert marketplace_for_url("https://smartstore.naver.com/main/products/123").disclosure == NAVER_DISCLOSURE
    assert marketplace_for_url("https://toss.im/_m/example").disclosure == TOSS_DISCLOSURE
    assert marketplace_for_url("https://ohou.se/productions/123/selling").disclosure == OHOUSE_DISCLOSURE
    assert marketplace_for_url("https://www.musinsa.com/products/123").disclosure == MUSINSA_DISCLOSURE
    assert marketplace_for_url("https://www.kurly.com/goods/123").disclosure == KURLY_DISCLOSURE
    assert marketplace_for_url("https://oy.run/example").disclosure == OLIVEYOUNG_DISCLOSURE
    assert marketplace_for_url("https://www.aliexpress.com/item/123.html").disclosure == GENERAL_AFFILIATE_DISCLOSURE
