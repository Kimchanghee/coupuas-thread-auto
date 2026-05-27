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


class _ImageSearch:
    def search_product_images(self, product_info, api_key="", cancel_check=None):
        assert product_info["product_id"] == "123456"
        assert api_key == "test-key"
        assert callable(cancel_check)
        assert cancel_check() is False
        return []


class _AggroGenerator:
    COUPANG_DISCLOSURE = "[파트너스 활동]"

    def generate_product_post(self, product_info, api_key=""):
        assert product_info["title"] == "테스트 상품"
        assert api_key == "test-key"
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
