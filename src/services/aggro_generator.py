"""
어그로 문구 생성 서비스 (v2 — 2026 Threads 바이럴 패턴 반영).

웹 리서치 기반 개선:
- 공정위 2024.12 개정: 본문 첫머리에 대가성 문구 명시 (글 마지막/댓글은 위반)
- 첫 줄 후킹: 부정형 명령("배달 끊어라"), 의문/충격 숫자, 일상 공감
- 카테고리 해시태그 + 강조 이모지(🔥 ⭐ ❗️ ✨ 👀)
- 짧은 글 + 줄바꿈 + 불릿으로 가독성

참고: facilitye.kr 2026, foxcg.com 2026, threads viral examples
"""
import re
import random
import google.generativeai as genai


class AggroGenerator:
    """어그로 문구 생성기 (Threads 최적화)."""

    # 공정위 가이드 (2024.12 개정 후 — 본문 첫머리 권장)
    COUPANG_DISCLOSURE_FULL = (
        "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
        "이에 따른 일정액의 수수료를 제공받습니다."
    )
    # 짧은 버전 (첫 포스트 첫줄에 부착)
    COUPANG_DISCLOSURE_SHORT = "[쿠팡 파트너스 · 수수료 제공]"

    # 활동 시 주의사항 — 가이드용 (별도 포스트)
    ACTIVITY_WARNING = """*활동 시 주의 사항

1. 게시글 작성 시, 아래 문구를 반드시 기재해 주세요.
"이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

쿠팡 파트너스의 활동은 공정거래위원회의 심사지침에 따라 추천, 보증인인 파트너스 회원과 당사의 경제적 이해관계에 대하여 공개하여야 합니다.

2. 바로가기 아이콘 이용 시, 수신자의 사전 동의를 얻지 않은 메신저, SNS 등으로 메시지를 발송하는 행위는 불법 스팸 전송 행위로 간주되어 규제기관의 행정제재 또는 형사 처벌의 대상이 될 수 있으니 이 점 유의하시기 바랍니다."""

    # 카테고리별 해시태그 풀 (Threads에서 자주 보이는 어그로 해시태그)
    CATEGORY_HASHTAGS = {
        "자취": ["#자취필수템", "#자취요리", "#자취생살림", "#1인가구", "#자취꿀템"],
        "주방": ["#주방템", "#살림템", "#주방꿀템", "#살림꿀팁"],
        "다이어트": ["#다이어트", "#다이어트간식", "#건강간식", "#저칼로리"],
        "뷰티": ["#뷰티템", "#스킨케어", "#화장품추천", "#피부관리"],
        "패션": ["#데일리룩", "#코디추천", "#패션템"],
        "생활": ["#생활꿀템", "#생활용품", "#일상꿀템"],
        "전자": ["#가전추천", "#전자제품", "#가성비템"],
        "유아": ["#육아템", "#아기용품", "#육아꿀템"],
        "반려": ["#반려동물", "#강아지용품", "#고양이용품"],
        "default": ["#쿠팡추천", "#쿠팡꿀템", "#쿠팡추천템", "#내돈내산"],
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-exp")
        else:
            self.model = None

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-exp")

    # ─── 카테고리 추론 ──────────────────────────────────────
    @classmethod
    def infer_category(cls, title: str, keywords: str = "") -> str:
        """상품 제목/키워드에서 카테고리 추론 (해시태그 풀 선택용)."""
        text = f"{title} {keywords}".lower()
        rules = [
            ("자취", ["자취", "1인가구", "원룸"]),
            ("주방", ["주방", "후라이팬", "냄비", "도마", "에어프라이어", "주방용품"]),
            ("다이어트", ["다이어트", "저칼로리", "단백질", "헬스"]),
            ("뷰티", ["스킨", "로션", "에센스", "마스크팩", "선크림", "뷰티"]),
            ("패션", ["옷", "셔츠", "원피스", "코디", "패션", "신발"]),
            ("전자", ["전자", "충전기", "이어폰", "노트북", "모니터", "스피커"]),
            ("유아", ["아기", "유아", "기저귀", "분유", "아동"]),
            ("반려", ["강아지", "고양이", "반려", "사료", "캣타워"]),
            ("생활", ["청소", "세제", "수건", "베개", "이불", "샴푸"]),
        ]
        for cat, kws in rules:
            for kw in kws:
                if kw in text:
                    return cat
        return "default"

    # ─── 해시태그 생성 ──────────────────────────────────────
    @classmethod
    def make_hashtags(cls, title: str, keywords: str = "", limit: int = 7) -> str:
        """카테고리별 해시태그 + 기본 풀에서 limit개 조합."""
        cat = cls.infer_category(title, keywords)
        pool = list(cls.CATEGORY_HASHTAGS.get(cat, []))
        # default와 합쳐 다양성 확보
        if cat != "default":
            pool += cls.CATEGORY_HASHTAGS["default"]
        # 중복 제거하면서 순서 유지
        seen, ordered = set(), []
        for tag in pool:
            if tag not in seen:
                seen.add(tag)
                ordered.append(tag)
        random.shuffle(ordered)
        return " ".join(ordered[:limit])

    # ─── 어그로 한줄 후킹 ───────────────────────────────────
    def generate_aggro_text(self, product_title: str, product_keywords: str = "") -> str:
        """
        Threads 첫 줄 후킹 — 부정형 명령 / 충격 숫자 / 일상 공감 패턴.

        2026 Threads 바이럴 분석 결과 반영:
          - 첫 줄 한 문장으로 스크롤 멈춤
          - "XX 끊어라", "XX 버리지마", "왜 이제 알려줬어" 등의 패턴
          - 강조 이모지 1~2개
          - 25~45자
        """
        if not self.model:
            return self._fallback_hook(product_title)

        try:
            prompt = f"""상품명: {product_title}

너는 Threads(스레드) 바이럴 카피라이터다. 첫 줄 후킹 한 문장만 작성해.

[2026 Threads 어그로 패턴]
1) **부정형 명령** — 통념을 뒤집는 강한 시작
   예: "배달 끊어라 진짜 돈 아깝다", "낡은 의자 버리지마세요"
2) **충격 숫자/가격** — 구체적 수치로 가치감
   예: "1만 9천원에 이게 된다고?", "3일 만에 5kg 빠진 비결"
3) **일상 공감/뒤늦은 발견** — 후회·억울함 정서
   예: "엄마한테 보여줬더니 왜 이제 알려줬냐고 화냄",
       "이거 왜 진작 안 샀지 진심 후회 중"
4) **반전/의문** — 호기심 자극
   예: "솔직히 이 가격에 이게 된다고? 사기 아님?",
       "친구가 이거 사고 인생 바뀌었다는데 실화냐"

[반드시 지킬 것]
- 한 줄, 25~45자
- 강조 이모지 1~2개 (🔥 ⭐ ❗️ ✨ 👀 😱 💥 중 선택)
- 광고티 NO ("추천드려요" "좋은 상품" 금지)
- 해시태그 NO, 영문/한자 NO
- 따옴표 없이 한 줄만 출력

좋은 예시:
배달 끊어라 진짜 돈 아깝다 ❗️에어프라이어로 끝내는 자취 요리
낡은 의자 그만 버리세요 👀 의자 다리에 끼우는 이거 하나면 끝
이거 보고 충동구매 했는데 후회 1도 없음 ✨
솔직히 이 가격에 이게 된다고? 사기인 줄 😱

나쁜 예시:
좋은 상품입니다 (광고티)
이거 추천드려요 (광고티)
이거 실화? (너무 짧음, 정보 0)

한 줄만 출력:"""
            resp = self.model.generate_content(prompt)
            text = (resp.text or "").strip().strip("\"'")
            text = text.replace("\n", " ").strip()
            text = re.sub(r"[一-鿿]+", "", text)  # 한자 제거
            text = re.sub(r"#\S+", "", text).strip()       # 해시태그 제거
            text = re.sub(r"\s{2,}", " ", text)
            return text or self._fallback_hook(product_title)
        except Exception as e:
            print(f"  ⚠️ 어그로 문구 생성 오류: {e}")
            return self._fallback_hook(product_title)

    @staticmethod
    def _fallback_hook(title: str) -> str:
        templates = [
            f"이거 보고 충동구매 했는데 후회 1도 없음 ✨",
            f"왜 이제 알려줬어 진짜 억울해 😱",
            f"솔직히 이 가격에 이게 된다고? 사기 아님? 👀",
            f"친구가 이거 사고 인생 바뀌었다는데 실화냐 🔥",
            f"이거 모르고 살았으면 평생 손해였을 듯 ❗️",
        ]
        return random.choice(templates)

    # ─── 본문 (첫 포스트) ───────────────────────────────────
    def generate_first_post_text(
        self, hook: str, title: str, keywords: str = "",
        compliant_inline: bool = True
    ) -> str:
        """
        첫 포스트 본문 = (선택) 공정위 첫줄 + 어그로 후킹 + 짧은 어필 3줄 + 해시태그.

        공정위 2024.12 가이드: 본문 '첫머리'에 대가성 표기 권장.
        compliant_inline=True 면 첫 줄에 짧은 disclosure 부착.
        """
        if not self.model:
            body = self._fallback_body(title)
        else:
            try:
                prompt = f"""상품명: {title}
검색 키워드: {keywords}
첫줄 후킹: {hook}

위 후킹 다음에 이어질 본문을 작성해. Threads 게시물용.

[규칙]
- 빈 줄 한 번 띄우고
- 짧은 한국어 문장 3~4줄 (각 줄 30자 이내)
- 불릿/이모지로 핵심 셀링 포인트 강조 (🔥 ✨ ❗️ ⭐ 👇 중 선택)
- 마지막 줄은 "👇 더 보기" "👇 가격 확인" 같은 행동 유도
- 광고티 NO, 거짓 효능 NO
- 따옴표 없이 본문만

좋은 예시:
\\n
✨ 한 번 쓰면 다른 거 못 쓰는 그 감성
🔥 자취 4년차가 인정한 가성비
👇 가격이 더 미친 건 함정"""
                resp = self.model.generate_content(prompt)
                body = (resp.text or "").strip().strip("\"'")
                body = re.sub(r"[一-鿿]+", "", body)
                body = re.sub(r"#\S+", "", body).strip()
            except Exception:
                body = self._fallback_body(title)

        prefix = (self.COUPANG_DISCLOSURE_SHORT + "\n") if compliant_inline else ""
        return f"{prefix}{hook}\n\n{body}".strip()

    @staticmethod
    def _fallback_body(title: str) -> str:
        return (
            "✨ 솔직히 이 가격에 이 퀄리티는 반칙\n"
            "🔥 한 번 쓰면 빠져나올 수 없는 그 맛\n"
            "👇 지금 가격 확인하고 사세요"
        )

    # ─── 풀 포스트 패키지 ───────────────────────────────────
    def generate_product_post(self, product_info: dict, compliant_inline: bool = True) -> dict:
        """
        Threads 멀티 포스트 (3개) 생성.

        first_post  : 공정위 첫줄(짧은) + 후킹 + 본문 + 해시태그 + 미디어
        second_post : 링크 + 공정위 풀 문구
        third_post  : 활동 주의사항 (운영자용 가이드)

        compliant_inline=True 면 첫 포스트 첫 줄에 짧은 disclosure 부착 (2024.12 가이드 준수).
        """
        title = product_info.get("title", "")
        keywords = product_info.get("search_keywords", "")
        original_url = product_info.get("original_url", "")
        image_path = product_info.get("image_path")
        video_path = product_info.get("video_path")

        hook = self.generate_aggro_text(title, keywords)
        body = self.generate_first_post_text(
            hook, title, keywords, compliant_inline=compliant_inline
        )
        hashtags = self.make_hashtags(title, keywords, limit=7)
        first_text = f"{body}\n\n{hashtags}".strip()

        media_path = video_path if video_path else image_path

        second_text = (
            f"👇 제품 구경하기\n{original_url}\n\n{self.COUPANG_DISCLOSURE_FULL}"
        )
        third_text = self.ACTIVITY_WARNING

        return {
            "first_post": {
                "text": first_text,
                "media_path": media_path,
                "media_type": "video" if video_path else "image",
            },
            "second_post": {
                "text": second_text,
                "media_path": None,
                "media_type": None,
            },
            "third_post": {
                "text": third_text,
                "media_path": None,
                "media_type": None,
            },
            "product_title": title,
            "original_url": original_url,
            "hook": hook,
            "hashtags": hashtags,
        }

    def generate_batch(self, products: list) -> list:
        results = []
        for i, product in enumerate(products, 1):
            print(
                f"  📝 [{i}/{len(products)}] 어그로 문구 생성: "
                f"{product.get('title', '')[:30]}..."
            )
            results.append(self.generate_product_post(product))
        return results


# 테스트
if __name__ == "__main__":
    import os

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    gen = AggroGenerator(api_key)

    sample = {
        "title": "에어프라이어 4L 가성비 1인 자취",
        "original_url": "https://link.coupang.com/a/test123",
        "search_keywords": "에어프라이어 자취",
        "image_path": "media/test.jpg",
        "video_path": None,
    }
    out = gen.generate_product_post(sample)
    print("\n--- FIRST POST ---")
    print(out["first_post"]["text"])
    print("\n--- SECOND POST ---")
    print(out["second_post"]["text"][:120], "...")
    print("\n--- HASHTAGS ---")
    print(out["hashtags"])
