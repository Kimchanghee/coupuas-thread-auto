# -*- coding: utf-8 -*-
"""Generate short promotional Threads copy for product posts."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from src.services.post_concepts import (
    CONCEPT_BUYING_GUIDE,
    CONCEPT_PROBLEM_SOLUTION,
    CONCEPT_TODAY_ISSUE,
    DEFAULT_POST_CONCEPT_ID,
    format_current_issue_context,
    get_post_concept,
    normalize_concept_id,
)
from src.services.trending_news import fetch_korean_issue_headlines


class AggroGenerator:
    """Create ad-like short copy and multi-post payloads."""

    COUPANG_DISCLOSURE = (
        "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
        "이에 따른 일정액의 수수료를 제공받습니다."
    )

    ACTIVITY_WARNING = (
        "*파트너스 활동 주의사항*\n\n"
        "1. 게시글 작성 시 아래 문구를 반드시 포함해 주세요.\n"
        "\"이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
        "이에 따른 일정액의 수수료를 제공받습니다.\"\n\n"
        "2. 수신자 동의 없는 메시지/SNS 발송은 스팸으로 간주될 수 있습니다."
    )
    MAX_HOOK_LENGTH = 82
    MAX_SUPPORT_LENGTH = 62
    _FIRST_POST_BLOCK_PATTERNS = (
        re.compile(r"https?://\S+", re.IGNORECASE),
        re.compile(r"\b(link\.coupang\.com|www\.coupang\.com)\S*", re.IGNORECASE),
        re.compile(r"(쿠팡\s*파트너스|파트너스\s*활동|수수료를\s*제공받습니다)", re.IGNORECASE),
        re.compile(r"(구매\s*링크|제품\s*확인\s*링크|확인\s*링크|바로\s*가기|링크는\s*여기)", re.IGNORECASE),
    )
    _FORBIDDEN_CLAIM_PATTERNS = (
        re.compile(r"\b(100%|무조건|확정|보장)\b", re.IGNORECASE),
        re.compile(r"(부작용\s*없|완치|치료)", re.IGNORECASE),
        re.compile(r"(소음\s*없이|무소음|칼바람|완벽하게|확실하게)", re.IGNORECASE),
        re.compile(r"(사진을\s*공개|영상\s*공개|장착\s*사진|리뷰\s*공개)", re.IGNORECASE),
    )
    _AWKWARD_COPY_PATTERNS = (
        re.compile(r"(등짝|차꾸|감성\s*쪽|살려버리|송풍구\s*감성)"),
        re.compile(r"(반칙임|킹받|노골적으로|숨은\s*비결|소문난|비주얼은)"),
        re.compile(r"(검은\s+선풍기\s+달|시커먼\s+선풍기\s+달)"),
    )
    _EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF]")

    def __init__(self, api_key: str = "") -> None:
        self._client = None
        self._model_name = os.environ.get("GOOGLE_GEMINI_MODEL", "gemini-3.5-flash")
        self.set_api_key(api_key)

    def set_api_key(self, api_key: str) -> None:
        """Initialize Gemini client without global SDK configuration."""
        key = str(api_key or "").strip()
        if not key:
            self._client = None
            return
        try:
            from google import genai

            self._client = genai.Client(api_key=key)
        except Exception:
            self._client = None

    def _generate_text(self, prompt: str) -> str:
        if self._client is None:
            return ""
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = str(getattr(part, "text", "") or "").strip()
                if part_text:
                    return part_text
        return ""

    @staticmethod
    def _normalize_text(value: str) -> str:
        text = str(value or "")
        text = text.replace("\r", "\n")
        text = text.replace("\u200b", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _trim_line(cls, value: str, max_len: int) -> str:
        text = cls._normalize_text(value).replace("\n", " ")
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    @classmethod
    def _contains_forbidden_claim(cls, text: str) -> bool:
        normalized = str(text or "")
        return any(pattern.search(normalized) for pattern in cls._FORBIDDEN_CLAIM_PATTERNS)

    @classmethod
    def _contains_awkward_copy(cls, text: str) -> bool:
        normalized = str(text or "")
        return any(pattern.search(normalized) for pattern in cls._AWKWARD_COPY_PATTERNS)

    @staticmethod
    def _select_core_keyword(title: str, keywords: str) -> str:
        merged = " ".join([str(title or ""), str(keywords or "")]).strip()
        raw_candidates = [
            token.strip()
            for token in re.split(r"[\s,/|]+", merged)
            if token and token.strip()
        ]
        color_words = {
            "블랙", "화이트", "그레이", "실버", "레드", "블루", "그린", "핑크",
            "브라운", "베이지", "탄", "아이보리", "네이비",
        }
        modifier_words = {"되는", "있는", "없는", "가능", "전용"}
        korean_tokens = [
            token
            for token in raw_candidates
            if re.search(r"[가-힣]", token)
            and len(token) >= 2
            and token not in color_words
            and token not in modifier_words
        ]
        if len(korean_tokens) >= 2:
            return " ".join(korean_tokens[-2:])[:16]
        if len(korean_tokens) == 1:
            return korean_tokens[0][:16]

        candidates = raw_candidates
        candidates = [token for token in candidates if len(token) >= 2]
        if not candidates:
            return "추천템"
        candidates = [
            token
            for token in candidates
            if not re.fullmatch(r"[A-Za-z]*\d[A-Za-z0-9_-]*", token)
            and token not in color_words
        ] or candidates
        # 길이가 적당하고 정보량 있는 토큰 우선
        candidates.sort(key=lambda x: (abs(len(x) - 6), -len(x)))
        return candidates[0][:16]

    @classmethod
    def _build_fallback_first_post(
        cls,
        title: str,
        keywords: str,
        concept_id: str | None = None,
        issue_headlines: Optional[List[str]] = None,
    ) -> str:
        token = cls._select_core_keyword(title, keywords)
        concept_id = normalize_concept_id(concept_id or DEFAULT_POST_CONCEPT_ID)
        if concept_id == CONCEPT_TODAY_ISSUE:
            issue_hint = "오늘 이슈"
            if issue_headlines:
                issue_hint = " ".join(str(issue_headlines[0]).split())[:20]
            hook = f"오늘 {issue_hint} 보다가 {token} 생각난 사람 꽤 있을 듯"
            support = "뉴스보다 내 생활에 바로 닿는 쪽이라 더 눈에 들어옵니다"
            return f"{cls._trim_line(hook, cls.MAX_HOOK_LENGTH)}\n{cls._trim_line(support, cls.MAX_SUPPORT_LENGTH)}"
        if concept_id == CONCEPT_PROBLEM_SOLUTION:
            hook = f"{token}, 막상 필요할 때 없으면 제일 귀찮은 쪽"
            support = "작은 불편 하나 줄이려는 사람한테 먼저 보이는 제품입니다"
            return f"{cls._trim_line(hook, cls.MAX_HOOK_LENGTH)}\n{cls._trim_line(support, cls.MAX_SUPPORT_LENGTH)}"
        if concept_id == CONCEPT_BUYING_GUIDE:
            hook = f"{token} 고를 때 은근히 놓치는 기준 하나"
            support = "예쁜지보다 실제로 자주 쓰게 될지가 먼저 보입니다"
            return f"{cls._trim_line(hook, cls.MAX_HOOK_LENGTH)}\n{cls._trim_line(support, cls.MAX_SUPPORT_LENGTH)}"
        hook_templates = [
            f"🚗 에어컨을 켜도 차 안이 묘하게 답답할 때 있죠?",
            f"🌀 {token} 찾다 보면 색깔 때문에 망설여질 때도 있죠",
            f"👀 차 안 분위기 해치지 않는 {token}, 은근 찾기 어렵습니다",
            f"🤔 {token}, 필요할 땐 확실히 떠오르는데 고르기는 애매하죠",
            f"✨ 검정 일색이 싫었다면 이 {token}는 눈이 좀 갑니다",
        ]
        support_templates = [
            "탄색이라 차 안에 둬도 튀지 않는 쪽이라 눈길이 갑니다 👀",
            "기능보다 먼저 '내 차에 어울리나'가 걸렸던 분들용입니다 🌀",
            "필요한 순간이 떠오르는 사람한테만 딱 꽂히는 제품이에요 🔍",
            "가볍게 넘기려다 한 번 더 보게 되는 쪽입니다 🚗",
            "차량용 제품도 색감 신경 쓰는 분이면 볼 만합니다 ✨",
        ]
        seed = sum(ord(ch) for ch in f"{title}|{keywords}")
        hook = hook_templates[seed % len(hook_templates)]
        support = support_templates[(seed // 3) % len(support_templates)]
        hook = cls._trim_line(hook, cls.MAX_HOOK_LENGTH)
        support = cls._trim_line(support, cls.MAX_SUPPORT_LENGTH)
        return f"{hook}\n{support}"

    @classmethod
    def _emoji_pair_for_product(cls, title: str, keywords: str) -> tuple[str, str]:
        text = f"{title} {keywords}"
        if re.search(r"(차량|자동차|차박|운전|차\s)", text):
            return "🚗", "👀"
        if re.search(r"(선풍기|쿨링|냉각|바람)", text):
            return "🌀", "😮"
        if re.search(r"(텀블러|컵|커피|음료|보온|보냉)", text):
            return "☕", "🤔"
        if re.search(r"(주방|요리|냄비|후라이팬|칼|도마)", text):
            return "🍳", "✨"
        if re.search(r"(캠핑|야외|등산|낚시)", text):
            return "🏕️", "🔥"
        return "👀", "✨"

    @classmethod
    def _ensure_playful_emojis(cls, hook: str, support: str, title: str, keywords: str) -> tuple[str, str]:
        first_emoji, second_emoji = cls._emoji_pair_for_product(title, keywords)
        joined = f"{hook}\n{support}"
        emoji_count = len(cls._EMOJI_PATTERN.findall(joined))

        if emoji_count == 0:
            hook = f"{first_emoji} {hook}"
            support = f"{support} {second_emoji}"
        elif emoji_count == 1 and not cls._EMOJI_PATTERN.search(support):
            support = f"{support} {second_emoji}"

        return cls._trim_line(hook, cls.MAX_HOOK_LENGTH), cls._trim_line(
            support,
            cls.MAX_SUPPORT_LENGTH,
        )

    @classmethod
    def _clean_first_post_candidate(cls, text: str, title: str, keywords: str) -> str:
        """Keep the first post as pure curiosity copy with no link/disclosure."""
        cleaned = cls._normalize_text(str(text or "").strip("\"'` "))
        if not cleaned:
            return ""

        for pattern in cls._FIRST_POST_BLOCK_PATTERNS:
            if pattern.search(cleaned):
                return ""

        cleaned = re.sub(r"[\u4e00-\u9fff]+", "", cleaned)
        cleaned = re.sub(r"#\S+", "", cleaned)
        cleaned = cls._normalize_text(cleaned)

        lines = [line.strip(" -•0123456789.()") for line in cleaned.split("\n") if line.strip()]
        if not lines:
            return ""
        if len(lines) == 1:
            lines.append("왜 필요한지 보면 바로 감이 옵니다.")

        hook = cls._trim_line(lines[0], cls.MAX_HOOK_LENGTH)
        support = cls._trim_line(lines[1], cls.MAX_SUPPORT_LENGTH)
        hook, support = cls._ensure_playful_emojis(hook, support, title, keywords)
        merged = f"{hook}\n{support}"
        if cls._contains_forbidden_claim(merged):
            return ""
        if cls._contains_awkward_copy(merged):
            return ""

        token = cls._select_core_keyword(title, keywords)
        token_parts = [part for part in token.split() if len(part) >= 2]
        if token_parts and not any(part in merged for part in token_parts):
            return ""
        return merged

    def generate_aggro_text(
        self,
        product_title: str,
        product_keywords: str = "",
        api_key: str = "",
        concept_id: str | None = None,
    ) -> str:
        """Generate engagement-oriented first post copy for Threads."""
        if api_key:
            self.set_api_key(api_key)

        concept = get_post_concept(concept_id)
        issue_headlines = (
            fetch_korean_issue_headlines()
            if concept.uses_current_issues
            else []
        )
        issue_context = (
            format_current_issue_context(issue_headlines)
            if concept.uses_current_issues
            else ""
        )

        seed_text = str(product_title or product_keywords or "").strip()
        if not seed_text:
            seed_text = "추천 상품"

        if self._client is None:
            return self._build_fallback_first_post(
                product_title,
                product_keywords,
                concept.id,
                issue_headlines,
            )

        try:
            prompt = (
                f"상품명: {seed_text}\n\n"
                f"작성 컨셉: {concept.display_label} ({concept.short_label})\n"
                f"{concept.description}\n"
                f"{concept.prompt}\n\n"
                f"{issue_context}\n\n"
                "Threads 첫 번째 글에 들어갈 초강력 호기심 유발 문구 2줄을 작성해줘.\n"
                "규칙:\n"
                "- 이 글은 첫 번째 글이다. URL, 쿠팡 링크, 구매 링크, 광고 고지 문구는 절대 넣지 마\n"
                "- 1줄차: 상품의 실제 사용 장면과 불편함을 뒤집는 어그로 훅 (35~65자)\n"
                "- 2줄차: 더 보고 싶게 만드는 짧은 보조 문장 (20~45자)\n"
                "- 이모지 1~2개를 자연스럽게 넣어. 너무 많이 넣지 마\n"
                "- 말투는 Threads처럼 짧고 장난기 있게. 광고 설명문처럼 쓰지 마\n"
                "- 딱딱한 표현 금지: 주목하세요, 확인하세요, 정리했습니다, 포인트입니다\n"
                "- 어색한 신조어/억지 밈 금지: 등짝, 차꾸, 반칙임, 킹받는, 감성 쪽, 살려버리네, 숨은 비결, 소문난\n"
                "- 자연스러운 한국어 구어체로 써. 사람이 실제로 말할 법한 문장만 사용\n"
                "- 상품군이 드러나야 한다. 너무 일반적인 문구 금지\n"
                "- '대박', '무조건 사라', '역대급', '꿀템' 같은 흔한 표현 금지\n"
                "- 독특하고 아이디어가 느껴지는 문장으로 작성\n"
                "- 실제 확인하지 않은 성능 단정, 소음/풍량 단정, 사진/영상 공개 표현 금지\n"
                "- 병원/치료/완치, 100%보장, 무조건 같은 표현 금지\n"
                "- 허위 후기처럼 보이는 표현 금지\n"
                "- 해시태그 금지\n"
                "- 한국어만 사용\n"
                "- 줄바꿈 1회만 사용 (총 2줄)\n"
                "- 따옴표/번호/불릿 없이 문구 본문만 출력\n"
            )
            result = self._generate_text(prompt).strip()
            if not result:
                raise ValueError("empty response")

            merged = self._clean_first_post_candidate(result, product_title, product_keywords)
            if not merged:
                raise ValueError("invalid first post candidate")
            return merged
        except Exception as exc:
            print(f"  애그로 문구 생성 오류: {exc}")
            return self._build_fallback_first_post(
                product_title,
                product_keywords,
                concept.id,
                issue_headlines,
            )

    @classmethod
    def _build_second_post_text(cls, original_url: str, title: str, keywords: str) -> str:
        token = cls._select_core_keyword(title, keywords)
        compact_title = cls._trim_line(title or token, 28)
        lines = [
            f"🔗 {compact_title} 확인 링크",
            original_url,
            cls.COUPANG_DISCLOSURE,
        ]
        return "\n".join(lines)

    def generate_product_post(
        self,
        product_info: dict,
        api_key: str = "",
        concept_id: str | None = None,
    ) -> Dict[str, object]:
        """Build 3-part post payload with media metadata."""
        title = str(product_info.get("title", "") or "")
        keywords = str(product_info.get("search_keywords", "") or "")
        original_url = str(product_info.get("original_url", "") or "")
        image_path: Optional[str] = product_info.get("image_path")
        video_path: Optional[str] = product_info.get("video_path")

        selected_concept_id = normalize_concept_id(
            concept_id or product_info.get("post_concept") or DEFAULT_POST_CONCEPT_ID
        )
        aggro_text = self.generate_aggro_text(
            title,
            keywords,
            api_key=api_key,
            concept_id=selected_concept_id,
        )
        media_path = video_path if video_path else image_path

        second_text = self._build_second_post_text(original_url, title, keywords)

        return {
            "first_post": {
                "text": aggro_text,
                "media_path": media_path,
                "media_type": "video" if video_path else "image",
            },
            "second_post": {
                "text": second_text,
                "media_path": None,
                "media_type": None,
            },
            "third_post": {
                "text": self.ACTIVITY_WARNING,
                "media_path": None,
                "media_type": None,
            },
            "product_title": title,
            "original_url": original_url,
            "post_concept": selected_concept_id,
        }

    def generate_batch(self, products: list, api_key: str = "") -> List[Dict[str, object]]:
        """Generate post payloads for multiple products."""
        results: List[Dict[str, object]] = []
        for index, product in enumerate(products, 1):
            title = str(product.get("title", "") or "")
            print(f"  [{index}/{len(products)}] 애그로 문구 생성: {title[:30]}...")
            results.append(self.generate_product_post(product, api_key=api_key))
        return results


if __name__ == "__main__":
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    generator = AggroGenerator(api_key)
    test_product = {
        "title": "충전 되는 가열용 텀블러",
        "original_url": "https://link.coupang.com/a/test123",
        "search_keywords": "가열 텀블러 충전",
        "image_path": "media/test.jpg",
        "video_path": None,
    }
    result = generator.generate_product_post(test_product)
    print(f"\n첫 번째 포스트: {result['first_post']['text']}")
    print(f"두 번째 포스트: {result['second_post']['text'][:100]}...")
