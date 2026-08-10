from src.services.coupang_parser import CoupangParser


class _Response:
    def __init__(self, status=200, *, location="", html="", content_type="text/html; charset=utf-8"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self.encoding = "utf-8"
        self.content = html.encode("utf-8")


class _RouteSession:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.requested = []

    def get(self, url, allow_redirects=False, timeout=15, stream=False):
        assert allow_redirects is False
        assert stream is True
        self.requested.append(url)
        response = self.routes.get(url)
        if response is None:
            raise AssertionError(f"unexpected fetch: {url}")
        return response


class _StreamingResponse:
    status_code = 200
    headers = {"Content-Type": "text/html"}
    encoding = "utf-8"

    def __init__(self):
        self.chunks_read = 0
        self.closed = False

    @property
    def content(self):
        raise AssertionError("streamed responses must not buffer response.content")

    def iter_content(self, chunk_size=64 * 1024):
        del chunk_size
        for _ in range(4):
            self.chunks_read += 1
            yield b"x" * (1024 * 1024)

    def close(self):
        self.closed = True


def _og(title, image="https://images.example/product.jpg"):
    return (
        "<html><head>"
        f'<meta property="og:title" content="{title}">'
        f'<meta property="og:image" content="{image}">'
        "</head></html>"
    )


def test_naver_shopping_connect_short_link_keeps_attribution_and_bridge_identity():
    entry = "https://naver.me/xG02SKVM"
    bridge = "https://brandconnect.naver.com/affiliates/bridge?channelProductNo=1170001&tr=abc"
    parser = CoupangParser()
    parser.session = _RouteSession({
        entry: _Response(307, location=bridge),
        bridge: _Response(html="<html><head><title>네이버 쇼핑 커넥트</title></head></html>"),
    })

    result = parser.parse_link(entry)

    assert result["marketplace"] == "naver"
    assert result["product_id"] == "1170001"
    assert result["affiliate_url"] == entry
    assert result["original_url"] == entry
    assert result["resolved_product_url"] == bridge


def test_toss_sharelink_follows_registered_multi_host_chain():
    entry = "https://toss.im/_m/7bMVzp83"
    bridge = "https://service.toss.im/shopping/c/991?referrer=affiliate"
    landing = "https://toss.shopping/i/991"
    parser = CoupangParser()
    parser.session = _RouteSession({
        entry: _Response(307, location=bridge),
        bridge: _Response(302, location=landing),
        landing: _Response(html=_og("토스 테스트 상품")),
    })

    result = parser.parse_link(entry)

    assert result["marketplace"] == "toss"
    assert result["title"] == "토스 테스트 상품"
    assert result["product_id"] == "991"
    assert result["affiliate_url"] == entry
    assert result["resolved_product_url"] == landing


def test_musinsa_onelink_and_curator_redirect_to_product():
    entry = "https://www.musinsa.com/curator/goods/YhSMK4"
    bridge = "https://musinsa.onelink.me/abc/curator"
    landing = "https://www.musinsa.com/products/5837896?pid=curator&utm_source=creator"
    parser = CoupangParser()
    parser.session = _RouteSession({
        entry: _Response(307, location=bridge),
        bridge: _Response(301, location=landing),
        landing: _Response(html=_og("무신사 테스트 상품")),
    })

    result = parser.parse_link(entry)

    assert result["marketplace"] == "musinsa"
    assert result["product_id"] == "5837896"
    assert result["original_url"] == entry
    assert result["resolved_product_url"] == landing


def test_ohouse_and_kurly_public_metadata_pages_are_supported():
    fixtures = (
        ("https://ohou.se/productions/987/selling?af=creator", "ohouse", "오늘의집 상품", "987"),
        ("https://lounge.kurly.com/link/IbLp-JCWu", "kurly", "컬리 상품", None),
    )
    for entry, marketplace_id, title, product_id in fixtures:
        parser = CoupangParser()
        parser.session = _RouteSession({entry: _Response(html=_og(title))})

        result = parser.parse_link(entry)

        assert result["marketplace"] == marketplace_id
        assert result["title"] == title
        assert result.get("product_id") == product_id
        assert result["affiliate_url"] == entry


def test_ohouse_curator_short_link_follows_only_registered_hosts():
    entry = "https://ozip.me/hfjSggf?af"
    bridge = "https://link.ohou.se/@ohouse/affiliate?content=production_2568445"
    landing = "https://ohou.se/productions/2568445/selling?utm_source=affiliate"
    parser = CoupangParser()
    parser.session = _RouteSession({
        entry: _Response(302, location=bridge),
        bridge: _Response(302, location=landing),
        landing: _Response(403),
    })

    result = parser.parse_link(entry)

    assert result["marketplace"] == "ohouse"
    assert result["product_id"] == "2568445"
    assert result["original_url"] == entry
    assert result["resolved_product_url"] == landing


def test_oliveyoung_known_server_data_bridge_resolves_without_executing_script():
    entry = "https://oy.run/1JMdYcb"
    landing = "https://m.oliveyoung.co.kr/m/goods/getGoodsDetail.do?goodsNo=A00001&utm_source=shutter&utm_medium=affiliate"
    bridge_html = (
        "<html><script>window.__SERVER_DATA__="
        '{"targetUrl":"' + landing.replace("&", "&amp;") + '"};</script></html>'
    )
    parser = CoupangParser()
    parser.session = _RouteSession({
        entry: _Response(html=bridge_html),
        landing: _Response(html=_og("올리브영 상품")),
    })

    result = parser.parse_link(entry)

    assert result["marketplace"] == "oliveyoung"
    assert result["product_id"] == "A00001"
    assert result["title"] == "올리브영 상품"
    assert result["affiliate_url"] == entry
    assert result["resolved_product_url"] == landing


def test_cross_provider_redirect_is_rejected_before_unsafe_fetch():
    entry = "https://toss.im/_m/bad"
    parser = CoupangParser()
    session = _RouteSession({
        entry: _Response(302, location="https://evil.example/steal"),
    })
    parser.session = session

    assert parser.parse_link(entry) is None
    assert session.requested == [entry]


def test_unknown_oliveyoung_embedded_url_field_is_not_followed():
    entry = "https://oy.run/unknown"
    parser = CoupangParser()
    session = _RouteSession({
        entry: _Response(html='<script>window.__SERVER_DATA__={"url":"https://evil.example"};</script>'),
    })
    parser.session = session

    assert parser.parse_link(entry) is None
    assert session.requested == [entry]


def test_redirect_loop_is_stopped_without_refetching_same_url():
    entry = "https://naver.me/loop-a"
    second = "https://naver.me/loop-b"
    parser = CoupangParser()
    session = _RouteSession({
        entry: _Response(302, location=second),
        second: _Response(302, location=entry),
    })
    parser.session = session

    assert parser.parse_link(entry) is None
    assert session.requested == [entry, second]


def test_non_html_short_link_response_is_not_treated_as_product_metadata():
    entry = "https://oy.run/download"
    parser = CoupangParser()
    session = _RouteSession({
        entry: _Response(html="binary", content_type="application/octet-stream"),
    })
    parser.session = session

    assert parser.parse_link(entry) is None
    assert session.requested == [entry]


def test_unkeyed_meta_tag_does_not_abort_later_open_graph_metadata():
    info = CoupangParser._metadata_from_html(
        '<html><head><meta charset="utf-8"><meta property="og:title" content="정상 상품"></head></html>',
        "https://www.kurly.com/goods/123",
    )

    assert info["title"] == "정상 상품"


def test_html_fetch_streams_only_the_configured_response_budget():
    entry = "https://lounge.kurly.com/link/large"
    response = _StreamingResponse()
    parser = CoupangParser()
    parser.session = _RouteSession({entry: response})

    final_url, page_html = parser._fetch_supported_html(entry)

    assert final_url == entry
    assert len(page_html.encode("utf-8")) == 2_000_000
    assert response.chunks_read == 2
    assert response.closed is True
