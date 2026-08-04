from src.services.aggro_generator import AggroGenerator
from src.services.managed_ai_client import ManagedGeneration, ManagedVariant


class _ManagedClientStub:
    def __init__(self):
        self.calls = 0

    def generate_variants(self, _product_info):
        self.calls += 1
        return ManagedGeneration(
            ai_job_id="job-1",
            reservation_id="res-1",
            quota_mode="legacy",
            prompt_version="threads-ko-v1",
            model="xai/grok-4.3",
            degraded=False,
            degraded_reason="",
            variants=tuple(
                ManagedVariant(
                    variant_id=variant_id,
                    root_text=f"{variant_id} 호기심을 만드는 첫 글입니다. 다음 글에서 정체를 확인해봐요.",
                    product_comment_text="상품 링크와 제휴 고지",
                )
                for variant_id in (
                    "target_direct",
                    "convenience_contrast",
                    "fun_reveal",
                    "use_scene_story",
                )
            ),
        )


def test_managed_provider_generates_four_variants_with_one_server_call():
    managed = _ManagedClientStub()
    generator = AggroGenerator(
        ai_provider="managed",
        managed_client=managed,
    )
    product = {
        "title": "휴대용 선풍기",
        "original_url": "https://link.coupang.com/a/example",
        "search_keywords": "여름 출퇴근",
        "image_path": "media/product.jpg",
    }

    variants = generator.generate_product_variants(product)

    assert managed.calls == 1
    assert len(variants) == 4
    assert {item["hook_variant"] for item in variants} == {
        "target_direct",
        "convenience_contrast",
        "fun_reveal",
        "use_scene_story",
    }
    assert variants[0]["managed_ai_reservation_id"] == "res-1"
    assert variants[0]["managed_ai_quota_mode"] == "legacy"
    assert variants[0]["first_post"]["media_path"] is None
    assert variants[0]["second_post"]["media_path"] == "media/product.jpg"
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


def test_product_post_uses_general_disclosure_for_naver():
    from src.services.marketplaces import GENERAL_AFFILIATE_DISCLOSURE

    generator = AggroGenerator()
    result = generator.generate_product_post(
        {
            "title": "접이식 캠핑 의자",
            "search_keywords": "캠핑 의자",
            "original_url": "https://smartstore.naver.com/example/products/123",
            "marketplace": "naver",
            "affiliate_disclosure": GENERAL_AFFILIATE_DISCLOSURE,
        }
    )
    assert GENERAL_AFFILIATE_DISCLOSURE in result["second_post"]["text"]
    assert AggroGenerator.COUPANG_DISCLOSURE not in result["second_post"]["text"]


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
    assert payload[0]["image_path"] is None
    assert payload[1]["image_path"] == "product.jpg"
    assert "https://link.coupang.com/a/test" not in payload[0]["text"]
    assert "https://link.coupang.com/a/test" in payload[1]["text"]


def test_four_hook_variants_use_target_pain_benefit_and_fun_logic():
    generator = AggroGenerator()
    posts = generator.generate_product_variants(
        {
            "title": "Zoomland 허리벨트형 팽창식 구명조끼",
            "search_keywords": "선상 낚시 허리 구명조끼",
            "original_url": "https://link.coupang.com/a/test",
            "image_path": "lifejacket.jpg",
        }
    )

    assert [post["hook_variant"] for post in posts] == [
        "target_direct",
        "convenience_contrast",
        "fun_reveal",
        "use_scene_story",
    ]
    assert len({post["root_post"]["text"] for post in posts}) == 4
    assert all(post["root_post"]["media_path"] is None for post in posts)
    assert all(post["product_comment"]["media_path"] == "lifejacket.jpg" for post in posts)
    assert all("https://link.coupang.com/a/test" not in post["root_post"]["text"] for post in posts)
    assert all("https://link.coupang.com/a/test" in post["product_comment"]["text"] for post in posts)


def test_hook_variant_prompt_requires_target_convenience_fun_and_open_loop():
    prompts = "\n".join(
        AggroGenerator.build_hook_variant_prompt(variant["id"])
        for variant in AggroGenerator.HOOK_VARIANTS
    )

    assert "핵심 타깃" in prompts
    assert "편하게" in prompts
    assert "재미있는 비유" in prompts
    assert "미완성 결말" in prompts


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


def test_clean_model_output_preserves_leading_product_quantity():
    cleaned = AggroGenerator._clean_first_post_candidate(
        "1인 자취인데 프라이팬 설거지까지 하는 거 번거롭지 않냐 🍳\n"
        "그래서 4L 에어프라이어 스펙을 좀 뜯어봄 👀",
        "에어프라이어 4L 가성비 1인 자취",
        "에어프라이어 자취 주방",
    )

    assert cleaned.startswith("1인 자취")


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
