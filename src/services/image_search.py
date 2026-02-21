"""Search and download product images from 1688 with guarded network I/O."""

from __future__ import annotations

import hashlib
import os
import random
import re
import time
from typing import List, Optional
from urllib.parse import quote, urlparse

import requests


class ImageSearchService:
    """1688 image search service with retry and fallback query generation."""

    CACHE_DIR = "media/cache"
    MAX_RETRIES = 10
    TARGET_IMAGES = 2
    MAX_IMAGE_BYTES = 8 * 1024 * 1024
    MIN_IMAGE_BYTES = 5 * 1024
    DOWNLOAD_CHUNK_SIZE = 64 * 1024
    ALLOWED_IMAGE_HOST_SUFFIXES = ("alicdn.com",)

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._gemini_model = None

    def _get_gemini_model(self, api_key: str):
        """Lazily initialize Gemini model for translation/query variation."""
        if self._gemini_model is None and api_key:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")
        return self._gemini_model

    def search_product_images(self, product_info: dict, api_key: str = "") -> List[str]:
        """Return up to TARGET_IMAGES local image paths for the given product."""
        title = str(product_info.get("title", "") or "")
        keywords = str(product_info.get("search_keywords", "") or "")

        if not title and not keywords:
            print("  상품명/키워드가 없습니다.")
            return []

        images: List[str] = []
        tried_keywords = set()
        retry_count = 0
        search_variants = self._generate_search_variants(title, keywords, api_key)

        print(
            f"  1688 이미지 검색 시작 (목표: {self.TARGET_IMAGES}개, 최대 {self.MAX_RETRIES}회 시도)"
        )

        while len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
            retry_count += 1

            search_term = None
            for variant in search_variants:
                if variant not in tried_keywords:
                    search_term = variant
                    tried_keywords.add(variant)
                    break

            if search_term is None:
                search_term = self._generate_random_variant(title, keywords, api_key, retry_count)
                tried_keywords.add(search_term)

            print(f"  [{retry_count}/{self.MAX_RETRIES}] 검색: {search_term[:30]}...")
            found_urls = self._search_1688_multiple(search_term)

            for url in found_urls:
                if len(images) >= self.TARGET_IMAGES:
                    break

                url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
                if any(url_hash in img for img in images):
                    continue

                local_path = self._download_image(url, title)
                if local_path:
                    images.append(local_path)
                    print(f"  이미지 {len(images)}개 확보: {local_path}")

            if len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
                time.sleep(random.uniform(0.5, 1.5))

        if images:
            print(f"  1688 이미지 검색 완료: {len(images)}개 확보")
        else:
            print(f"  1688 이미지 검색 실패 ({self.MAX_RETRIES}회 시도)")

        return images

    def search_product_image(self, product_info: dict, api_key: str = "") -> Optional[str]:
        """Compatibility helper: return a single image path."""
        images = self.search_product_images(product_info, api_key)
        return images[0] if images else None

    def _generate_search_variants(self, title: str, keywords: str, api_key: str) -> List[str]:
        """Generate prioritized query variants."""
        variants: List[str] = []

        chinese = self._translate_to_chinese(title or keywords, api_key)
        if chinese:
            variants.append(chinese)

        if keywords and keywords != title:
            chinese_kw = self._translate_to_chinese(keywords, api_key)
            if chinese_kw and chinese_kw not in variants:
                variants.append(chinese_kw)

        words = (title or keywords).split()
        if len(words) > 2:
            core_words = " ".join(words[:3])
            chinese_core = self._translate_to_chinese(core_words, api_key)
            if chinese_core and chinese_core not in variants:
                variants.append(chinese_core)

        english = self._translate_to_english(title or keywords, api_key)
        if english and english not in variants:
            variants.append(english)

        if title and title not in variants:
            variants.append(title)
        if keywords and keywords not in variants:
            variants.append(keywords)

        return variants

    def _generate_random_variant(self, title: str, keywords: str, api_key: str, attempt: int) -> str:
        """Generate additional variant for retries."""
        base = (title or keywords or "").strip()
        model = self._get_gemini_model(api_key)

        if model and base and attempt <= 5:
            try:
                prompt = (
                    f"Return one short 1688 Chinese search keyword phrase for: {base}. "
                    "Output phrase only."
                )
                response = model.generate_content(prompt)
                result = str(getattr(response, "text", "") or "").strip().strip("\"'")
                if result:
                    return result
            except Exception:
                pass

        words = base.split()
        if len(words) > 1:
            random.shuffle(words)
            return " ".join(words[: min(3, len(words))])
        return base or "product"

    def _translate_to_chinese(self, text: str, api_key: str) -> Optional[str]:
        """Translate product keyword to Chinese for 1688 search."""
        model = self._get_gemini_model(api_key)
        if not model or not text:
            return None

        try:
            prompt = (
                f"Translate this into concise Chinese search terms for 1688: {text}. "
                "Output terms only."
            )
            response = model.generate_content(prompt)
            result = str(getattr(response, "text", "") or "").strip()
            result = re.sub(r"[\"'\n]", "", result)
            if re.search(r"[\u4e00-\u9fff]", result):
                return result
            return None
        except Exception as exc:
            print(f"  번역 오류: {exc}")
            return None

    def _translate_to_english(self, text: str, api_key: str) -> Optional[str]:
        """Translate product keyword to English fallback query."""
        model = self._get_gemini_model(api_key)
        if not model or not text:
            return None

        try:
            prompt = (
                f"Translate this into concise English product search terms: {text}. "
                "Output terms only."
            )
            response = model.generate_content(prompt)
            result = str(getattr(response, "text", "") or "").strip().strip("\"'")
            return result if result else None
        except Exception:
            return None

    def _search_1688_multiple(self, keyword: str) -> List[str]:
        """Search 1688 pages and extract candidate image URLs."""
        urls: List[str] = []

        try:
            encoded_keyword = quote(keyword)
            search_urls = [
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}",
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}&sortType=va",
                f"https://s.1688.com/pic/offer_search.htm?keywords={encoded_keyword}",
            ]

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,ko;q=0.8,en;q=0.7",
                "Referer": "https://www.1688.com/",
            }

            patterns = [
                r"(https://cbu01\.alicdn\.com/img/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://img\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://cbu\d+\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://gw\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
            ]

            for search_url in search_urls:
                if len(urls) >= 5:
                    break
                try:
                    response = requests.get(search_url, headers=headers, timeout=10)
                    response.encoding = "utf-8"
                    text = response.text
                    for pattern in patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            clean_url = re.sub(r"_\d+x\d+\.", ".", match)
                            clean_url = re.sub(r"\?.+$", "", clean_url)
                            if "_60x60" in match or "_80x80" in match or "avatar" in match.lower():
                                continue
                            if clean_url not in urls:
                                urls.append(clean_url)
                            if len(urls) >= 10:
                                break
                        if len(urls) >= 10:
                            break
                except Exception:
                    continue
        except Exception as exc:
            print(f"  1688 검색 오류: {exc}")

        return urls

    @classmethod
    def _is_allowed_image_url(cls, url: str) -> bool:
        try:
            parsed = urlparse(str(url or ""))
            if parsed.scheme != "https":
                return False
            host = (parsed.hostname or "").lower().strip()
            if not host:
                return False
            return any(
                host == suffix or host.endswith(f".{suffix}")
                for suffix in cls.ALLOWED_IMAGE_HOST_SUFFIXES
            )
        except Exception:
            return False

    def _download_image(self, url: str, product_name: str) -> Optional[str]:
        """Download candidate image to local cache with size/domain checks."""
        try:
            if not self._is_allowed_image_url(url):
                return None

            hash_name = hashlib.sha256(url.encode()).hexdigest()[:12]
            ext = url.split(".")[-1].split("?")[0][:4].lower()
            if ext not in ["jpg", "jpeg", "png", "webp", "gif"]:
                ext = "jpg"

            filename = f"{hash_name}.{ext}"
            filepath = os.path.join(self.CACHE_DIR, filename)
            if os.path.exists(filepath):
                return filepath

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.1688.com/",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            }
            response = requests.get(url, headers=headers, timeout=15, stream=True)
            if response.status_code != 200:
                return None

            if not self._is_allowed_image_url(response.url):
                return None

            content_type = response.headers.get("content-type", "").lower()
            if "image" not in content_type and ext not in ["jpg", "jpeg", "png", "webp", "gif"]:
                return None

            content_length = response.headers.get("content-length", "").strip()
            if content_length.isdigit() and int(content_length) > self.MAX_IMAGE_BYTES:
                return None

            total_written = 0
            with open(filepath, "wb") as handle:
                for chunk in response.iter_content(chunk_size=self.DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    total_written += len(chunk)
                    if total_written > self.MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds maximum allowed size")
                    handle.write(chunk)

            if total_written < self.MIN_IMAGE_BYTES:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None

            return filepath
        except Exception:
            try:
                if "filepath" in locals() and os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            return None


_instance: Optional[ImageSearchService] = None


def get_image_search() -> ImageSearchService:
    """Return singleton ImageSearchService instance."""
    global _instance
    if _instance is None:
        _instance = ImageSearchService()
    return _instance
