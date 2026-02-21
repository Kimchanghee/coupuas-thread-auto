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

    def __init__(self, api_key: str = "") -> None:
        self._client = None
        self._model_name = os.environ.get("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash")
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

    def generate_aggro_text(
        self, product_title: str, product_keywords: str = "", api_key: str = ""
    ) -> str:
        """Generate one short hook sentence for Threads."""
        if api_key:
            self.set_api_key(api_key)

        seed_text = str(product_title or product_keywords or "").strip()
        if not seed_text:
            seed_text = "추천 상품"

        if self._client is None:
            return f"이거 보고 안 사면 손해일 수도 있음 {seed_text[:15]}"

        try:
            prompt = (
                f"상품명: {seed_text}\n\n"
                "Threads용 한 줄 훅 문장을 작성해줘.\n"
                "규칙:\n"
                "- 25~40자\n"
                "- 과장된 후기체/충동구매 유도 톤\n"
                "- 해시태그 금지\n"
                "- 한국어만 사용\n"
                "- 문장 하나만 출력\n"
            )
            result = self._generate_text(prompt).strip()
            if not result:
                raise ValueError("empty response")

            result = result.strip("\"'")
            result = result.replace("\n", " ").strip()
            result = re.sub(r"[\u4e00-\u9fff]+", "", result)
            result = re.sub(r"#\S+", "", result).strip()
            return result
        except Exception as exc:
            print(f"  애그로 문구 생성 오류: {exc}")
            return "이거 보고 안 사면 손해일 수도 있음"

    def generate_product_post(self, product_info: dict, api_key: str = "") -> Dict[str, object]:
        """Build 3-part post payload with media metadata."""
        title = str(product_info.get("title", "") or "")
        keywords = str(product_info.get("search_keywords", "") or "")
        original_url = str(product_info.get("original_url", "") or "")
        image_path: Optional[str] = product_info.get("image_path")
        video_path: Optional[str] = product_info.get("video_path")

        aggro_text = self.generate_aggro_text(title, keywords, api_key=api_key)
        media_path = video_path if video_path else image_path

        second_text = f"상품 구경하기\n{original_url}\n\n{self.COUPANG_DISCLOSURE}"

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
