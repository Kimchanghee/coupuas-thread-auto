import pytest

from src.coupang_uploader import CancelledException, CoupangPartnersPipeline
from src.services.cancellation import OperationCancelled


class _Parser:
    def parse_link(self, url, cancel_check=None):
        assert url == "https://link.coupang.com/a/example"
        assert callable(cancel_check)
        assert cancel_check() is False
        return {
            "product_id": "123456",
            "title": "테스트 상품",
            "search_keywords": "테스트 상품",
        }


class _CancellingParser:
    def parse_link(self, url, cancel_check=None):
        raise OperationCancelled("cancelled")


class _EmptyParser:
    def parse_link(self, url, cancel_check=None):
        return None


class _ImageSearch:
    def search_product_images(self, product_info, api_key="", cancel_check=None):
        assert product_info["product_id"] == "123456"
        assert api_key == ""
        assert callable(cancel_check)
        assert cancel_check() is False
        return []


class _KeywordImageSearch:
    def search_product_images(self, product_info, api_key="", cancel_check=None):
        assert product_info["search_keywords"] == "사용자 지정 상품 키워드"
        return []


class _AggroGenerator:
    COUPANG_DISCLOSURE = "[파트너스 활동]"

    def generate_product_post(self, product_info, api_key="", concept_id=None):
        assert product_info["title"] in {"테스트 상품", "사용자 지정 상품 키워드"}
        assert api_key == ""
        assert concept_id
        return {
            "first_post": {"text": "첫 번째 게시글"},
            "second_post": {"text": "두 번째 게시글"},
        }


def _pipeline_with_fakes(parser):
    pipeline = CoupangPartnersPipeline("test-key")
    pipeline._coupang_parser = parser
    pipeline._image_search = _ImageSearch()
    pipeline._aggro_generator = _AggroGenerator()
    return pipeline


def test_process_link_passes_cancel_callback_to_parser_and_image_search():
    pipeline = _pipeline_with_fakes(_Parser())

    post_data = pipeline.process_link("https://link.coupang.com/a/example")

    assert post_data["first_post"]["text"] == "첫 번째 게시글"
    assert post_data["second_post"]["text"].startswith("[파트너스 활동]")


def test_process_link_converts_service_cancellation_to_pipeline_cancellation():
    pipeline = _pipeline_with_fakes(_CancellingParser())

    with pytest.raises(CancelledException):
        pipeline.process_link("https://link.coupang.com/a/example")


def test_user_keyword_can_recover_supported_link_without_public_metadata():
    pipeline = _pipeline_with_fakes(_EmptyParser())
    pipeline._image_search = _KeywordImageSearch()

    post_data = pipeline.process_link(
        "https://link.coupang.com/a/example",
        user_keywords="사용자 지정 상품 키워드",
    )

    assert post_data["first_post"]["text"] == "첫 번째 게시글"
    assert "https://link.coupang.com/a/example" in post_data["second_post"]["text"]


def test_publish_boundary_repairs_managed_comment_disclosure_and_original_url():
    pipeline = CoupangPartnersPipeline("test-key")
    original_url = "https://ohou.se/productions/123/selling?af=creator-1"
    disclosure = "오늘의집 제휴 고지"
    variant = {
        "first_post": {"text": "첫 글"},
        "second_post": {"text": "AI가 만든 상품 설명\nhttps://wrong.example/item"},
    }
    post_data = {
        "first_post": {"text": "첫 글"},
        "second_post": {"text": f"상품 설명\n{original_url}\n{disclosure}\n{original_url}"},
        "all_managed_variants": [variant],
    }

    result = pipeline._normalize_second_post_disclosure(
        post_data,
        {
            "affiliate_disclosure": disclosure,
            "affiliate_url": original_url,
        },
    )

    assert result["first_post"]["text"] == "첫 글"
    assert result["second_post"]["text"].startswith(disclosure)
    assert result["second_post"]["text"].count(original_url) == 1
    assert "https://wrong.example/item" not in result["second_post"]["text"]
    assert variant["second_post"]["text"].startswith(disclosure)
    assert variant["second_post"]["text"].count(original_url) == 1
    assert "https://wrong.example/item" not in variant["second_post"]["text"]
