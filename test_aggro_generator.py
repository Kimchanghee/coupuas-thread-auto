from src.services.aggro_generator import AggroGenerator


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
