from src.services.aggro_generator import AggroGenerator
from src.services.post_concepts import (
    CONCEPT_BUYING_GUIDE,
    CONCEPT_PROBLEM_SOLUTION,
    CONCEPT_TODAY_ISSUE,
    DEFAULT_POST_CONCEPT_ID,
    get_post_concept,
    normalize_concept_id,
)
from src.services.thread_payload import (
    PRODUCT_COMMENT,
    ROOT_POST,
    build_product_thread_payload,
)


def test_first_post_fallback_is_product_specific_and_link_free():
    generator = AggroGenerator()

    text = generator.generate_aggro_text(
        "켈리마 차량용 선풍기 R8037 탄",
        "켈리마 차량용 선풍기 R8037 탄",
    )

    assert "선풍기" in text
    assert "http" not in text
    assert "쿠팡 파트너스" not in text
    assert "수수료" not in text
    assert AggroGenerator._EMOJI_PATTERN.search(text)
    assert len([line for line in text.splitlines() if line.strip()]) == 2


def test_product_post_keeps_link_only_in_second_post():
    generator = AggroGenerator()
    result = generator.generate_product_post(
        {
            "title": "켈리마 차량용 선풍기 R8037 탄",
            "search_keywords": "켈리마 차량용 선풍기 R8037 탄",
            "original_url": "https://link.coupang.com/a/dVx6gM6fm0",
            "image_path": None,
        }
    )

    first_text = result["first_post"]["text"]
    second_text = result["second_post"]["text"]

    assert "https://link.coupang.com/a/dVx6gM6fm0" not in first_text
    assert "https://link.coupang.com/a/dVx6gM6fm0" in second_text
    assert second_text.startswith("🔗")
    assert AggroGenerator.COUPANG_DISCLOSURE in second_text


def test_product_post_exposes_fixed_root_and_product_comment_payload():
    generator = AggroGenerator()
    result = generator.generate_product_post(
        {
            "title": "휴대용 선풍기",
            "search_keywords": "휴대용 선풍기",
            "original_url": "https://link.coupang.com/a/test",
            "image_path": "product.jpg",
        }
    )

    payload = build_product_thread_payload(result)

    assert result[ROOT_POST] is result["first_post"]
    assert result[PRODUCT_COMMENT] is result["second_post"]
    assert [item["role"] for item in payload] == [ROOT_POST, PRODUCT_COMMENT]
    assert payload[0]["image_path"] == "product.jpg"
    assert payload[1]["image_path"] is None
    assert "https://link.coupang.com/a/test" not in payload[0]["text"]
    assert "https://link.coupang.com/a/test" in payload[1]["text"]


def test_bad_model_output_falls_back_to_clean_first_post():
    generator = AggroGenerator()

    dirty = (
        "구매 링크: https://link.coupang.com/a/test\n"
        "이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다."
    )

    cleaned = generator._clean_first_post_candidate(
        dirty,
        "켈리마 차량용 선풍기 R8037 탄",
        "켈리마 차량용 선풍기 R8037 탄",
    )

    assert cleaned == ""


def test_plain_model_output_gets_playful_emojis():
    generator = AggroGenerator()

    cleaned = generator._clean_first_post_candidate(
        "차량용 선풍기 하나 때문에 차 안 분위기가 은근 달라 보임\n"
        "작은 물건인데 필요한 순간이 너무 선명함",
        "켈리마 차량용 선풍기 R8037 탄",
        "켈리마 차량용 선풍기 R8037 탄",
    )

    assert "선풍기" in cleaned
    assert AggroGenerator._EMOJI_PATTERN.search(cleaned)
    assert len([line for line in cleaned.splitlines() if line.strip()]) == 2


def test_awkward_copy_is_rejected():
    generator = AggroGenerator()

    cleaned = generator._clean_first_post_candidate(
        "🥵 차 안에서 등짝만 익어가는데, 검은 선풍기 달긴 또 싫었던 사람?\n"
        "탄색 차량용 선풍기라니... 이건 차꾸 감성 쪽으로 살짝 반칙임 👀",
        "켈리마 차량용 선풍기 R8037 탄",
        "켈리마 차량용 선풍기 R8037 탄",
    )

    assert cleaned == ""


def test_post_concept_ids_are_normalized():
    assert normalize_concept_id("2") == CONCEPT_TODAY_ISSUE
    assert normalize_concept_id("3") == CONCEPT_PROBLEM_SOLUTION
    assert normalize_concept_id("4") == CONCEPT_BUYING_GUIDE
    assert normalize_concept_id("unknown") == DEFAULT_POST_CONCEPT_ID
    assert get_post_concept("2").number == 2


def test_today_issue_concept_fallback_uses_current_headline(monkeypatch):
    monkeypatch.setattr(
        "src.services.aggro_generator.fetch_korean_issue_headlines",
        lambda: ["폭염 위기경보가 확대된다는 뉴스"],
    )
    generator = AggroGenerator()

    text = generator.generate_aggro_text(
        "휴대용 선풍기",
        "휴대용 선풍기",
        concept_id=CONCEPT_TODAY_ISSUE,
    )

    assert "폭염" in text
    assert "http" not in text
    assert len([line for line in text.splitlines() if line.strip()]) == 2


def test_product_post_records_selected_concept(monkeypatch):
    monkeypatch.setattr(
        "src.services.aggro_generator.fetch_korean_issue_headlines",
        lambda: ["장마와 폭염이 번갈아 온다는 뉴스"],
    )
    generator = AggroGenerator()

    result = generator.generate_product_post(
        {
            "title": "여름 쿨매트",
            "search_keywords": "여름 쿨매트",
            "original_url": "https://link.coupang.com/a/test",
            "image_path": None,
        },
        concept_id=CONCEPT_TODAY_ISSUE,
    )

    assert result["post_concept"] == CONCEPT_TODAY_ISSUE
    assert "https://link.coupang.com/a/test" not in result["first_post"]["text"]
    assert "https://link.coupang.com/a/test" in result["second_post"]["text"]
