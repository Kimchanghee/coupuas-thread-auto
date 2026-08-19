# -*- coding: utf-8 -*-
"""
쿠팡 파트너스 링크 파싱 서비스
쿠팡 링크에서 상품 정보를 추출합니다.
스크린샷 + Gemini Vision 방식으로 봇 탐지를 우회합니다.
"""
import re
import requests
import base64
import json
import time
import html as html_lib
from html.parser import HTMLParser
from typing import Callable, Optional, Dict
from urllib.parse import urlparse, urljoin

from src.gemini_keys import (
    generate_content_with_model_fallback,
    get_gemini_model_candidates,
    is_retryable_gemini_model_error,
)
from src.services.cancellation import check_cancelled, is_cancelled_exception
from src.services.marketplaces import (
    MARKETPLACES_BY_ID,
    marketplace_for_url,
    marketplace_for_redirect_url,
    normalize_product_url,
)

# Gemini API 재시도 설정
MAX_RETRIES = 5
RETRY_DELAY = 60  # 1분
PARTNER_LINK_HOST = "link.coupang.com"
ALLOWED_COUPANG_DOMAINS = ("coupang.com",)
MAX_REDIRECT_HOPS = 8
MAX_BRIDGE_HOPS = 2
MAX_PRODUCT_HTML_BYTES = 2_000_000


class _ProductMetadataParser(HTMLParser):
    """Small dependency-free parser for public product-page metadata."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.json_ld_parts: list[str] = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        lowered = str(tag or "").lower()
        if lowered == "title":
            self._in_title = True
        elif lowered == "meta":
            key = (
                values.get("property")
                or values.get("name")
                or values.get("itemprop")
                or ""
            ).strip().lower()
            content = values.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif lowered == "script" and "ld+json" in values.get("type", "").lower():
            self._in_json_ld = True

    def handle_endtag(self, tag: str) -> None:
        lowered = str(tag or "").lower()
        if lowered == "title":
            self._in_title = False
        elif lowered == "script":
            self._in_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif self._in_json_ld:
            self.json_ld_parts.append(data)


def _find_product_json(value: object) -> dict:
    if isinstance(value, dict):
        raw_type = value.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        if any(str(item or "").lower() == "product" for item in types):
            return value
        for child in value.values():
            found = _find_product_json(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_product_json(child)
            if found:
                return found
    return {}


def _redact_api_key(value: object) -> str:
    text = str(value or "")
    return re.sub(r"(key=)[^&\s]+", r"\1[REDACTED]", text)


class CoupangParser:
    """상품 링크 파서.

    기존 클래스 이름은 호환성을 위해 유지하며 등록된 제휴 쇼핑몰
    상품 링크를 공통 결과 형식으로 반환합니다.
    """

    def __init__(self, google_api_key: str = None):
        self.google_api_key = google_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            # requests always decodes gzip/deflate. Advertising Brotli without
            # a Brotli decoder can leave compressed bytes masquerading as HTML.
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    @staticmethod
    def _normalize_url(url: str) -> str:
        return normalize_product_url(url)

    @staticmethod
    def _is_allowed_coupang_host(host: str) -> bool:
        host = str(host or "").strip().lower()
        if not host:
            return False
        return any(
            host == domain or host.endswith(f".{domain}")
            for domain in ALLOWED_COUPANG_DOMAINS
        )

    @classmethod
    def _is_allowed_coupang_url(cls, url: str) -> bool:
        try:
            parsed = urlparse(cls._normalize_url(url))
            if parsed.scheme != "https":
                return False
            return cls._is_allowed_coupang_host(parsed.hostname or "")
        except Exception:
            return False

    @classmethod
    def _is_partner_link_url(cls, url: str) -> bool:
        try:
            parsed = urlparse(cls._normalize_url(url))
            if parsed.scheme != "https":
                return False
            if (parsed.hostname or "").strip().lower() != PARTNER_LINK_HOST:
                return False
            return bool(re.match(r"^/a/[A-Za-z0-9]+/?$", parsed.path or ""))
        except Exception:
            return False

    def parse_link(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[Dict]:
        """지원 쇼핑몰 상품 링크에서 공개 상품 정보를 추출합니다."""
        try:
            check_cancelled(cancel_check)
            url = normalize_product_url(url)
            marketplace = marketplace_for_url(url)
            if not url or marketplace is None:
                print("  [!] 지원하지 않는 상품 URL")
                return None

            print(f"  [Parse] {marketplace.label} 상품 링크 분석 중...")

            if marketplace.marketplace_id == "coupang" and self._is_partner_link_url(url):
                result = self._parse_with_playwright(url, cancel_check=cancel_check)
            else:
                result = self._parse_marketplace_page(
                    url,
                    marketplace.marketplace_id,
                    cancel_check=cancel_check,
                )
            if result:
                result['original_url'] = url
                result['affiliate_url'] = url
                result['resolved_product_url'] = str(result.get('final_url') or url)
                result['marketplace'] = marketplace.marketplace_id
                result['marketplace_label'] = marketplace.label
                result['affiliate_disclosure'] = marketplace.disclosure

                if result.get('image_url'):
                    print("  [Parse] Successfully extracted image URL")
                elif result.get('product_id'):
                    print("  [Parse] Only product_id available, will use 1688 search")

                return result

            print("  [!] Could not parse link")
            return None

        except Exception as e:
            if is_cancelled_exception(e):
                raise
            print(f"  [!] Parse error: {e}")
            return None

    def _parse_marketplace_page(
        self,
        url: str,
        marketplace_id: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[Dict]:
        """Extract public metadata, then use URL Context as an optional fallback."""
        final_url, html = self._fetch_supported_html(url, cancel_check=cancel_check)
        info = self._metadata_from_html(html, final_url) if html else {}
        info["final_url"] = final_url or url

        product_id = self._product_id_from_url(final_url or url, marketplace_id)
        if product_id:
            info["product_id"] = product_id

        if self.google_api_key and not (info.get("title") and info.get("image_url")):
            ai_result = self._fetch_with_gemini_url_context(
                final_url or url,
                cancel_check=cancel_check,
                marketplace_id=marketplace_id,
            )
            if ai_result:
                for key in ("title", "keywords", "image_url", "price"):
                    if ai_result.get(key) and not info.get(
                        "search_keywords" if key == "keywords" else key
                    ):
                        info["search_keywords" if key == "keywords" else key] = ai_result[key]

        title = str(info.get("title") or "").strip()
        if title and not info.get("search_keywords"):
            info["search_keywords"] = self._extract_keywords(title)
        return info if title or info.get("image_url") or info.get("product_id") else None

    def _fetch_supported_html(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> tuple[str, str]:
        """Fetch a supported public page while validating every redirect hop."""
        initial_marketplace = marketplace_for_url(url)
        if initial_marketplace is None:
            return "", ""

        current_url = normalize_product_url(url)
        visited: set[str] = set()
        redirect_hops = 0
        bridge_hops = 0
        try:
            while redirect_hops <= MAX_REDIRECT_HOPS:
                check_cancelled(cancel_check)
                if current_url in visited:
                    return current_url, ""
                visited.add(current_url)
                response = self.session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=15,
                    stream=True,
                )
                status = int(response.status_code or 0)
                if 300 <= status < 400:
                    location = str(response.headers.get("Location", "") or "").strip()
                    self._close_response(response)
                    next_url = normalize_product_url(urljoin(current_url, location))
                    if (
                        not next_url
                        or marketplace_for_redirect_url(
                            next_url,
                            initial_marketplace.marketplace_id,
                        ) is None
                    ):
                        return current_url, ""
                    current_url = next_url
                    redirect_hops += 1
                    continue
                if status < 200 or status >= 400:
                    self._close_response(response)
                    return current_url, ""
                content_type = str(response.headers.get("Content-Type", "") or "").lower()
                if content_type and not any(
                    allowed in content_type
                    for allowed in ("text/html", "application/xhtml+xml")
                ):
                    self._close_response(response)
                    return current_url, ""
                content = self._read_limited_content(response)
                encoding = str(getattr(response, "encoding", "") or "utf-8")
                try:
                    page_html = content.decode(encoding, errors="replace")
                except LookupError:
                    page_html = content.decode("utf-8", errors="replace")

                embedded_target = self._embedded_bridge_target(
                    initial_marketplace.marketplace_id,
                    current_url,
                    page_html,
                )
                if embedded_target:
                    next_url = normalize_product_url(urljoin(current_url, embedded_target))
                    if (
                        bridge_hops >= MAX_BRIDGE_HOPS
                        or not next_url
                        or marketplace_for_redirect_url(
                            next_url,
                            initial_marketplace.marketplace_id,
                        ) is None
                    ):
                        return current_url, page_html
                    bridge_hops += 1
                    current_url = next_url
                    continue
                return current_url, page_html
            return current_url, ""
        except Exception as exc:
            if is_cancelled_exception(exc):
                raise
            print(f"  [!] 상품 페이지 메타데이터 요청 실패: {exc}")
            return current_url, ""

    @staticmethod
    def _close_response(response) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    @classmethod
    def _read_limited_content(cls, response) -> bytes:
        """Stream at most the configured HTML budget, then close the response."""
        chunks: list[bytes] = []
        remaining = MAX_PRODUCT_HTML_BYTES
        try:
            iterator = getattr(response, "iter_content", None)
            if not callable(iterator):
                return bytes(getattr(response, "content", b"") or b"")[:remaining]
            for chunk in iterator(chunk_size=64 * 1024):
                value = bytes(chunk or b"")
                if not value:
                    continue
                chunks.append(value[:remaining])
                remaining -= min(len(value), remaining)
                if remaining <= 0:
                    break
            return b"".join(chunks)
        finally:
            cls._close_response(response)

    @staticmethod
    def _embedded_bridge_target(marketplace_id: str, current_url: str, page_html: str) -> str:
        """Read only explicitly supported, inert bridge bootstrap fields."""
        if str(marketplace_id or "") != "oliveyoung":
            return ""
        try:
            if (urlparse(current_url).hostname or "").lower() != "oy.run":
                return ""
            html_text = str(page_html or "")
            match = re.search(r"window\.__SERVER_DATA__\s*=\s*", html_text)
            if not match:
                return ""
            payload, _ = json.JSONDecoder().raw_decode(html_text[match.end():].lstrip())
            if not isinstance(payload, dict):
                return ""
            return html_lib.unescape(str(payload.get("targetUrl") or "").strip())
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _metadata_from_html(cls, html: str, final_url: str) -> Dict:
        parser = _ProductMetadataParser()
        try:
            parser.feed(str(html or ""))
        except Exception:
            return {}

        product_json: dict = {}
        for raw in parser.json_ld_parts:
            try:
                product_json = _find_product_json(json.loads(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if product_json:
                break

        title = str(
            parser.meta.get("og:title")
            or parser.meta.get("twitter:title")
            or product_json.get("name")
            or " ".join(parser.title_parts)
            or ""
        ).strip()
        image_value = (
            parser.meta.get("og:image")
            or parser.meta.get("twitter:image")
            or product_json.get("image")
            or ""
        )
        if isinstance(image_value, list):
            image_value = image_value[0] if image_value else ""
        if isinstance(image_value, dict):
            image_value = image_value.get("url") or image_value.get("contentUrl") or ""
        image_url = str(image_value or "").strip()
        if image_url:
            image_url = urljoin(final_url, image_url)
            if not image_url.startswith("https://"):
                image_url = ""

        offers = product_json.get("offers") if isinstance(product_json, dict) else None
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = (
            parser.meta.get("product:price:amount")
            or parser.meta.get("og:price:amount")
            or (offers.get("price") if isinstance(offers, dict) else None)
        )
        return {
            "title": title[:300],
            "image_url": image_url,
            "price": price,
        }

    @staticmethod
    def _product_id_from_url(url: str, marketplace_id: str) -> str:
        marketplace = MARKETPLACES_BY_ID.get(str(marketplace_id or ""))
        return marketplace.product_id_from_url(url) if marketplace else ""

    def _parse_with_playwright(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[Dict]:
        """쿠팡 상품 정보를 추출 (Gemini URL Context 사용)"""
        try:
            check_cancelled(cancel_check)
            # 1. 먼저 리다이렉트로 최종 URL과 product_id 추출
            final_url = self._follow_redirect(url, cancel_check=cancel_check)
            if not final_url:
                return None

            info = {'final_url': final_url}

            # 상품 ID 추출
            product_id_match = re.search(r'/products/(\d+)', final_url)
            if product_id_match:
                info['product_id'] = product_id_match.group(1)
                print(f"  [Parse] Product ID: {info['product_id']}")

            # 2. Gemini URL Context로 상품 정보 추출 시도
            if self.google_api_key:
                gemini_result = self._fetch_with_gemini_url_context(
                    final_url,
                    cancel_check=cancel_check,
                )
                if gemini_result:
                    if gemini_result.get('title'):
                        info['title'] = gemini_result['title']
                        print(f"  [Parse] Title: {info['title'][:40]}...")
                    if gemini_result.get('keywords'):
                        info['search_keywords'] = gemini_result['keywords']
                    if gemini_result.get('image_url'):
                        info['image_url'] = gemini_result['image_url']
                        print("  [Parse] Image URL found")

            # 제목이 없으면 빈 값으로
            if not info.get('title'):
                info['title'] = ''
            if not info.get('search_keywords'):
                info['search_keywords'] = ''

            return info if info.get('product_id') else None

        except Exception as e:
            if is_cancelled_exception(e):
                raise
            print(f"  [!] Parse error: {e}")
            return None

    def _fetch_with_gemini_url_context(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
        marketplace_id: str = "coupang",
    ) -> Optional[Dict]:
        """Gemini URL Context API로 공개 상품 정보를 보완합니다."""
        if not self.google_api_key:
            return None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                check_cancelled(cancel_check)
                from google import genai
                from google.genai.types import GenerateContentConfig

                if attempt == 1:
                    print("  [Parse] Using Gemini URL Context...")
                else:
                    print(f"  [Parse] Gemini 재시도 {attempt}/{MAX_RETRIES}...")

                client = genai.Client(api_key=self.google_api_key)

                # URL Context 도구 설정
                tools = [{"url_context": {}}]

                marketplace = marketplace_for_url(url)
                marketplace_label = marketplace.label if marketplace else marketplace_id
                prompt = f"""다음 {marketplace_label} 상품 페이지에서 공개된 정보를 추출해주세요: {url}

다음 JSON 형식으로 응답해주세요:
{{
  "title": "상품명",
  "keywords": "1688.com 검색용 중국어 키워드",
  "image_url": "상품 대표 이미지 URL",
  "price": 가격(숫자)
}}

규칙:
1. title: 정확한 상품명
2. keywords: 상품의 핵심 특징만 중국어로 (브랜드명 제외, 2-4단어)
3. image_url: og:image 또는 상품 대표 이미지 URL (https://로 시작)
4. price: 판매가격 (숫자만)

Access Denied이거나 정보를 찾을 수 없으면 빈 객체 {{}}를 반환하세요.
JSON만 출력하세요."""

                response, _model = generate_content_with_model_fallback(
                    client,
                    contents=prompt,
                    config=GenerateContentConfig(tools=tools),
                )

                # 응답 텍스트 추출
                text = ""
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text'):
                        text += part.text

                # JSON 파싱
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if data.get('title') or data.get('image_url'):
                        return data

                return None

            except ImportError:
                print("  [!] google-genai not installed, trying REST API...")
                return self._fetch_with_gemini_rest_api(
                    url,
                    cancel_check=cancel_check,
                    marketplace_id=marketplace_id,
                )
            except Exception as e:
                if is_cancelled_exception(e):
                    raise
                error_str = str(e).lower()

                if is_retryable_gemini_model_error(e):
                    print(f"  [!] Gemini URL Context model error: {e}")
                    return self._fetch_with_gemini_rest_api(
                        url,
                        cancel_check=cancel_check,
                        marketplace_id=marketplace_id,
                    )

                # 서버 오류인 경우에만 재시도
                if any(err in error_str for err in ['500', '503', 'server', 'overloaded', 'rate', 'quota', 'timeout']):
                    if attempt < MAX_RETRIES:
                        print(f"  [!] Gemini 서버 오류: {e}")
                        print(f"  [!] {RETRY_DELAY}초 후 재시도합니다...")
                        for _ in range(RETRY_DELAY):
                            check_cancelled(cancel_check)
                            time.sleep(1)
                        continue
                else:
                    # 서버 오류가 아니면 바로 REST API 시도
                    print(f"  [!] Gemini URL Context error: {e}")
                    return self._fetch_with_gemini_rest_api(
                        url,
                        cancel_check=cancel_check,
                        marketplace_id=marketplace_id,
                    )

        # 모든 재시도 실패
        print(f"  [!] Gemini {MAX_RETRIES}회 재시도 모두 실패")
        return self._fetch_with_gemini_rest_api(
            url,
            cancel_check=cancel_check,
            marketplace_id=marketplace_id,
        )

    def _fetch_with_gemini_rest_api(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
        marketplace_id: str = "coupang",
    ) -> Optional[Dict]:
        """Gemini REST API로 URL Context 사용 (SDK 없이)"""
        if not self.google_api_key:
            return None

        try:
            check_cancelled(cancel_check)
            print("  [Parse] Using Gemini REST API with URL Context...")

            marketplace = marketplace_for_url(url)
            marketplace_label = marketplace.label if marketplace else marketplace_id
            prompt = f"""다음 {marketplace_label} 상품 페이지에서 공개된 정보를 추출해주세요: {url}

다음 JSON 형식으로 응답해주세요:
{{
  "title": "상품명",
  "keywords": "1688.com 검색용 중국어 키워드",
  "image_url": "상품 대표 이미지 URL",
  "price": 가격(숫자)
}}

규칙:
1. title: 정확한 상품명
2. keywords: 상품의 핵심 특징만 중국어로 (브랜드명 제외, 2-4단어)
3. image_url: og:image 또는 상품 대표 이미지 URL
4. price: 판매가격 (숫자만)

Access Denied이거나 정보를 찾을 수 없으면 빈 객체 {{}}를 반환하세요.
JSON만 출력하세요."""

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"url_context": {}}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1000
                }
            }

            response = None
            last_error = None
            for model in get_gemini_model_candidates():
                check_cancelled(cancel_check)
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                try:
                    response = requests.post(
                        api_url,
                        json=payload,
                        headers={"x-goog-api-key": self.google_api_key},
                        timeout=60,
                    )
                    response.raise_for_status()
                    break
                except Exception as exc:
                    last_error = exc
                    if is_retryable_gemini_model_error(exc):
                        print(f"  [!] Gemini REST model {model} failed, trying fallback: {_redact_api_key(exc)}")
                        continue
                    raise

            if response is None:
                if last_error is not None:
                    raise last_error
                return None
            check_cancelled(cancel_check)

            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            # JSON 파싱
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if data.get('title') or data.get('image_url'):
                    return data

            return None

        except Exception as e:
            if is_cancelled_exception(e):
                raise
            print(f"  [!] Gemini REST API error: {_redact_api_key(e)}")
            return None

    def _analyze_screenshot_with_gemini(self, screenshot_bytes: bytes) -> Optional[Dict]:
        """Gemini Vision API로 스크린샷에서 상품 정보 추출"""
        if not self.google_api_key:
            return None

        try:
            # 이미지를 base64로 인코딩
            image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            prompt = """이 쿠팡 상품 페이지 스크린샷을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. title: 상품명 (정확하게)
2. keywords: 1688.com에서 검색할 수 있는 중국어 키워드 (핵심 상품명만, 브랜드/수량/용량 제외)
3. price: 판매가격 (숫자만)

JSON 형식으로만 응답하세요. 예시:
{"title": "삼성 갤럭시 버즈2 프로", "keywords": "蓝牙耳机 无线耳机", "price": 159000}

Access Denied 페이지이거나 상품 정보를 찾을 수 없으면 빈 객체 {}를 반환하세요."""

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_base64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 500
                }
            }

            response = None
            last_error = None
            for model in get_gemini_model_candidates():
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers={"x-goog-api-key": self.google_api_key},
                        timeout=30,
                    )
                    response.raise_for_status()
                    break
                except Exception as exc:
                    last_error = exc
                    if is_retryable_gemini_model_error(exc):
                        print(f"  [!] Gemini Vision model {model} failed, trying fallback: {_redact_api_key(exc)}")
                        continue
                    raise

            if response is None:
                if last_error is not None:
                    raise last_error
                return None

            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            # JSON 추출
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return None

        except Exception as e:
            print(f"  [!] Gemini Vision error: {_redact_api_key(e)}")
            return None

    def _follow_redirect(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """리다이렉트를 따라가서 최종 URL 반환"""
        normalized = self._normalize_url(url)
        if not self._is_allowed_coupang_url(normalized):
            return None

        current_url = normalized
        try:
            for _ in range(MAX_REDIRECT_HOPS):
                check_cancelled(cancel_check)
                response = self.session.head(current_url, allow_redirects=False, timeout=10)
                status = int(response.status_code or 0)
                if 300 <= status < 400:
                    location = str(response.headers.get("Location", "")).strip()
                    if not location:
                        return None
                    next_url = self._normalize_url(urljoin(current_url, location))
                    if not self._is_allowed_coupang_url(next_url):
                        return None
                    current_url = next_url
                    continue
                if status >= 400:
                    raise RuntimeError(f"HEAD redirect check failed with status {status}")
                if not re.search(r"/products/\d+", current_url):
                    raise RuntimeError("HEAD redirect check did not resolve a product page")
                return current_url if self._is_allowed_coupang_url(current_url) else None
            return None
        except Exception as e:
            if is_cancelled_exception(e):
                raise
            try:
                current_url = normalized
                for _ in range(MAX_REDIRECT_HOPS):
                    check_cancelled(cancel_check)
                    response = self.session.get(current_url, allow_redirects=False, timeout=10)
                    status = int(response.status_code or 0)
                    if 300 <= status < 400:
                        location = str(response.headers.get("Location", "")).strip()
                        if not location:
                            return None
                        next_url = self._normalize_url(urljoin(current_url, location))
                        if not self._is_allowed_coupang_url(next_url):
                            return None
                        current_url = next_url
                        continue
                    return current_url if self._is_allowed_coupang_url(current_url) else None
                return None
            except Exception as e:
                if is_cancelled_exception(e):
                    raise
                print(f"  [!] Redirect error: {e}")
                return None

    def _extract_keywords(self, title: str) -> str:
        """상품명에서 검색 키워드 추출"""
        # 불필요한 문자 제거
        keywords = re.sub(r'[\[\]()（）\d+개입\d+ml\d+g\d+kg\d+팩]', ' ', title)
        keywords = re.sub(r'[^\w\s]', ' ', keywords)

        # 중복 공백 제거
        keywords = re.sub(r'\s+', ' ', keywords).strip()

        # 핵심 단어만 추출 (2글자 이상)
        words = [w for w in keywords.split() if len(w) >= 2]

        # 최대 5개 단어만 사용
        return ' '.join(words[:5])

    def validate_link(self, url: str) -> bool:
        """쿠팡 파트너스 링크 유효성 검사"""
        try:
            return self._is_partner_link_url(url)
        except Exception:
            return False

    def extract_links_from_text(self, text: str) -> list:
        """텍스트에서 쿠팡 링크 추출"""
        pattern1 = r'https://link\.coupang\.com/[^\s<>\"\']+'

        links = []
        links.extend(re.findall(pattern1, text))

        return list(dict.fromkeys(links))


# 테스트
if __name__ == "__main__":
    import sys
    import os
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 50)
    print("쿠팡 파트너스 링크 파서 테스트")
    print("  (Gemini URL Context 사용)")
    print("=" * 50)

    # 명령줄 인자로 API 키 받기
    api_key = None
    test_url = "https://link.coupang.com/a/daLtlY"

    if len(sys.argv) > 1:
        api_key = sys.argv[1]
        print("API Key: 명령줄에서 제공됨")
    if len(sys.argv) > 2:
        test_url = sys.argv[2]

    # 환경변수에서 시도
    if not api_key:
        api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if api_key:
            print("API Key: 환경변수에서 로드됨")

    # config에서 시도
    if not api_key:
        try:
            from src.config import config
            api_key = config.gemini_api_key
            if api_key:
                print("API Key: config에서 로드됨")
        except Exception:
            pass

    if not api_key:
        print("\n⚠️ API Key가 설정되지 않았습니다!")
        print("   Gemini URL Context 기능을 사용하려면 API 키가 필요합니다.")
        print("\n사용법:")
        print("   python -m src.services.coupang_parser <API_KEY> [URL]")
        print("\n또는:")
        print("   set GOOGLE_API_KEY=your_api_key")
        print("   python -m src.services.coupang_parser")
        sys.exit(1)

    parser = CoupangParser(google_api_key=api_key)

    if parser.validate_link(test_url):
        print(f"\n테스트 링크: {test_url}")
        info = parser.parse_link(test_url)

        if info:
            print("\n결과:")
            print(f"  Product ID: {info.get('product_id', 'N/A')}")
            print(f"  Title: {info.get('title') or '(추출 불가)'}")
            print(f"  Keywords: {info.get('search_keywords') or '(추출 불가)'}")
            print(f"  Image URL: {info.get('image_url') or '(추출 불가)'}")

            if info.get('title'):
                print("\n✅ Gemini URL Context로 상품 정보 추출 성공!")
            else:
                print("\n⚠️ 상품 정보 추출 실패")
                print("   → UI에서 'URL | 키워드' 형식으로 직접 입력 필요")
        else:
            print("파싱 실패")
    else:
        print(f"유효하지 않은 링크: {test_url}")
