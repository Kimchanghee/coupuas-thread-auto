import pytest

from src.services.cancellation import OperationCancelled
from src.services.image_search import ImageSearchService


def test_image_search_obeys_cancel_check_before_work():
    service = ImageSearchService.__new__(ImageSearchService)

    with pytest.raises(OperationCancelled):
        service.search_product_images(
            {"title": "테스트 상품"},
            cancel_check=lambda: True,
        )
