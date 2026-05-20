# -*- coding: utf-8 -*-
"""Generate short promotional Threads copy for product posts."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional


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
    MAX_HOOK_LENGTH = 65
    MAX_SUPPORT_LENGTH = 55
    _FORBIDDEN_CLAIM_PATTERNS = (
        re.compile(r"\b(100%|무조건|확정|보장)\b", re.IGNORECASE),
        re.compile(r"(부작용\s*없|완치|치료)", re.IGNORECASE),
    )

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

    @staticmethod
    def _select_core_keyword(title: str, keywords: str) -> str:
        merged = " ".join([str(title or ""), str(keywords or "")]).strip()
        candidates = [
            token.strip()
            for token in re.split(r"[\s,/|]+", merged)
            if token and token.strip()
        ]
        candidates = [token for token in candidates if len(token) >= 2]
        if not candidates:
            return "추천템"
        # 길이가 적당하고 정보량 있는 토큰 우선
        candidates.sort(key=lambda x: (abs(len(x) - 6), -len(x)))
        return candidates[0][:16]

    @classmethod
    def _build_fallback_first_post(cls, title: str, keywords: str) -> str:
        token = cls._select_core_keyword(title, keywords)
        hook_templates = [
            f"{token} 찾는 사람들, 이거 먼저 봐도 괜찮을 듯",
            f"{token} 고민 중이면 비교 포인트부터 체크해보세요",
            f"{token} 살 때 실패 줄이는 기준, 이거였어요",
            f"{token} 고를 때 제일 많이 헷갈리는 부분 정리해봄",
            f"{token} 그냥 사기 전에 이것만 보면 시간 아껴요",
        ]
        support_templates = [
            "광고지만 과장 없이 핵심만 짧게 남겨둘게요.",
            "실사용 기준으로 고른 이유만 간단히 적어볼게요.",
            "비슷한 용도 제품이랑 비교한 포인트도 같이 남깁니다.",
            "가격보다 사용 장면 기준으로 보면 선택이 빨라져요.",
            "저처럼 선택장애 있는 분들 기준으로 정리해봤어요.",
        ]
        seed = sum(ord(ch) for ch in f"{title}|{keywords}")
        hook = hook_templates[seed % len(hook_templates)]
        support = support_templates[(seed // 3) % len(support_templates)]
        hook = cls._trim_line(hook, cls.MAX_HOOK_LENGTH)
        support = cls._trim_line(support, cls.MAX_SUPPORT_LENGTH)
        return f"{hook}\n{support}"

    def generate_aggro_text(
        self, product_title: str, product_keywords: str = "", api_key: str = ""
    ) -> str:
        """Generate engagement-oriented first post copy for Threads."""
        if api_key:
            self.set_api_key(api_key)

        seed_text = str(product_title or product_keywords or "").strip()
        if not seed_text:
            seed_text = "추천 상품"

        if self._client is None:
            return self._build_fallback_first_post(product_title, product_keywords)

        try:
            prompt = (
                f"상품명: {seed_text}\n\n"
                "Threads용 제휴 홍보 문구 2줄을 작성해줘.\n"
                "규칙:\n"
                "- 1줄차: 질문형/문제해결형/비교형 훅 (22~45자)\n"
                "- 2줄차: 과장 없는 보조 설명 + 자연스러운 참여 유도 (18~38자)\n"
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

            result = result.strip("\"'`")
            result = re.sub(r"[\u4e00-\u9fff]+", "", result)
            result = re.sub(r"#\S+", "", result).strip()
            result = self._normalize_text(result)

            lines = [line.strip(" -•") for line in result.split("\n") if line.strip()]
            if not lines:
                raise ValueError("empty lines")
            if len(lines) == 1:
                lines.append("실사용 기준으로 핵심만 간단히 남길게요.")
            hook = self._trim_line(lines[0], self.MAX_HOOK_LENGTH)
            support = self._trim_line(lines[1], self.MAX_SUPPORT_LENGTH)
            merged = f"{hook}\n{support}"
            if self._contains_forbidden_claim(merged):
                raise ValueError("forbidden claim detected")
            return merged
        except Exception as exc:
            print(f"  애그로 문구 생성 오류: {exc}")
            return self._build_fallback_first_post(product_title, product_keywords)

    @classmethod
    def _build_second_post_text(cls, original_url: str, title: str, keywords: str) -> str:
        token = cls._select_core_keyword(title, keywords)
        compact_title = cls._trim_line(title or token, 28)
        lines = [
            f"[광고] {compact_title} 정보 정리",
            f"구매 링크: {original_url}",
            f"비슷한 {token} 비교가 필요하면 댓글로 상황 남겨주세요.",
            cls.COUPANG_DISCLOSURE,
        ]
        return "\n".join(lines)

    def generate_product_post(self, product_info: dict, api_key: str = "") -> Dict[str, object]:
        """Build 3-part post payload with media metadata."""
        title = str(product_info.get("title", "") or "")
        keywords = str(product_info.get("search_keywords", "") or "")
        original_url = str(product_info.get("original_url", "") or "")
        image_path: Optional[str] = product_info.get("image_path")
        video_path: Optional[str] = product_info.get("video_path")

        aggro_text = self.generate_aggro_text(title, keywords, api_key=api_key)
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
