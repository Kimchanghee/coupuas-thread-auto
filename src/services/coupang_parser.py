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
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs

# Gemini API 재시도 설정
MAX_RETRIES = 5
RETRY_DELAY = 60  # 1분
ALLOWED_COUPANG_DOMAINS = ("coupang.com",)


class CoupangParser:
    """쿠팡 파트너스 링크 파서 (스크린샷 + AI Vision 방식)"""

    def __init__(self, google_api_key: str = None):
        self.google_api_key = google_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
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
        value = str(url or "").strip()
        if not value:
            return ""
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value

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
            if parsed.scheme not in ("http", "https"):
                return False
            return cls._is_allowed_coupang_host(parsed.hostname or "")
        except Exception:
            return False

    def parse_link(self, url: str) -> Optional[Dict]:
        """
        쿠팡 파트너스 링크에서 상품 정보 추출

        쿠팡 봇 탐지 우회를 위해 리다이렉트와 이미지 URL만 추출합니다.
        상품명/키워드는 1688 이미지 검색에서 처리합니다.

        Args:
            url: 쿠팡 파트너스 링크 (link.coupang.com/a/xxx 형식)

        Returns:
            상품 정보 딕셔너리 또는 None
        """
        try:
            url = self._normalize_url(url)
            if not self._is_allowed_coupang_url(url):
                print("  [!] Invalid or disallowed URL")
                return None

            print(f"  [Parse] Parsing Coupang link...")

            # 파서로 정보 추출 시도
            result = self._parse_with_playwright(url)
            if result:
                result['original_url'] = url

                # 이미지 URL이 있으면 성공으로 간주
                if result.get('image_url'):
                    print(f"  [Parse] Successfully extracted image URL")
                elif result.get('product_id'):
                    print(f"  [Parse] Only product_id available, will use 1688 search")

                return result

            print(f"  [!] Could not parse link")
            return None

        except Exception as e:
            print(f"  [!] Parse error: {e}")
            return None

    def _parse_with_playwright(self, url: str) -> Optional[Dict]:
        """쿠팡 상품 정보를 추출 (Gemini URL Context 사용)"""
        try:
            # 1. 먼저 리다이렉트로 최종 URL과 product_id 추출
            final_url = self._follow_redirect(url)
            if not final_url:
                return None

            info = {'final_url': final_url}

            # 상품 ID 추출
            product_id_match = re.search(r'/products/(\d+)', final_url)
            if product_id_match:
                info['product_id'] = product_id_match.group(1)
                print(f"  [Parse] Product ID: {info['product_id']}")

            # 2. Gemini URL Context로 상품 정보 추출 시도
            print(f"  [Parse] API Key: {'Yes' if self.google_api_key else 'No'}")
            if self.google_api_key:
                gemini_result = self._fetch_with_gemini_url_context(final_url)
                if gemini_result:
                    if gemini_result.get('title'):
                        info['title'] = gemini_result['title']
                        print(f"  [Parse] Title: {info['title'][:40]}...")
                    if gemini_result.get('keywords'):
                        info['search_keywords'] = gemini_result['keywords']
                    if gemini_result.get('image_url'):
                        info['image_url'] = gemini_result['image_url']
                        print(f"  [Parse] Image URL found")

            # 제목이 없으면 빈 값으로
            if not info.get('title'):
                info['title'] = ''
            if not info.get('search_keywords'):
                info['search_keywords'] = ''

            return info if info.get('product_id') else None

        except Exception as e:
            print(f"  [!] Parse error: {e}")
            return None

    def _fetch_with_gemini_url_context(self, url: str) -> Optional[Dict]:
        """Gemini URL Context API로 웹페이지 내용 가져오기 (재시도 로직 포함)"""
        if not self.google_api_key:
            return None

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                from google import genai
                from google.genai.types import GenerateContentConfig

                if attempt == 1:
                    print(f"  [Parse] Using Gemini URL Context...")
                else:
                    print(f"  [Parse] Gemini 재시도 {attempt}/{MAX_RETRIES}...")

                client = genai.Client(api_key=self.google_api_key)

                # URL Context 도구 설정
                tools = [{"url_context": {}}]

                prompt = f"""다음 쿠팡 상품 페이지에서 정보를 추출해주세요: {url}

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

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=GenerateContentConfig(tools=tools)
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
                print(f"  [!] google-genai not installed, trying REST API...")
                return self._fetch_with_gemini_rest_api(url)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # 서버 오류인 경우에만 재시도
                if any(err in error_str for err in ['500', '503', 'server', 'overloaded', 'rate', 'quota', 'timeout']):
                    if attempt < MAX_RETRIES:
                        print(f"  [!] Gemini 서버 오류: {e}")
                        print(f"  [!] {RETRY_DELAY}초 후 재시도합니다...")
                        time.sleep(RETRY_DELAY)
                        continue
                else:
                    # 서버 오류가 아니면 바로 REST API 시도
                    print(f"  [!] Gemini URL Context error: {e}")
                    return self._fetch_with_gemini_rest_api(url)

        # 모든 재시도 실패
        print(f"  [!] Gemini {MAX_RETRIES}회 재시도 모두 실패")
        return self._fetch_with_gemini_rest_api(url)

    def _fetch_with_gemini_rest_api(self, url: str) -> Optional[Dict]:
        """Gemini REST API로 URL Context 사용 (SDK 없이)"""
        if not self.google_api_key:
            return None

        try:
            print(f"  [Parse] Using Gemini REST API with URL Context...")

            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.google_api_key}"

            prompt = f"""다음 쿠팡 상품 페이지에서 정보를 추출해주세요: {url}

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

            response = requests.post(api_url, json=payload, timeout=60)
            response.raise_for_status()

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
            print(f"  [!] Gemini REST API error: {e}")
            return None

    def _analyze_screenshot_with_gemini(self, screenshot_bytes: bytes) -> Optional[Dict]:
        """Gemini Vision API로 스크린샷에서 상품 정보 추출"""
        if not self.google_api_key:
            return None

        try:
            # 이미지를 base64로 인코딩
            image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            # Gemini API 호출
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.google_api_key}"

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

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            # JSON 추출
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return None

        except Exception as e:
            print(f"  [!] Gemini Vision error: {e}")
            return None

    def _follow_redirect(self, url: str) -> Optional[str]:
        """리다이렉트를 따라가서 최종 URL 반환"""
        try:
            normalized = self._normalize_url(url)
            if not self._is_allowed_coupang_url(normalized):
                return None

            response = self.session.head(normalized, allow_redirects=True, timeout=10)
            final_url = self._normalize_url(response.url)
            return final_url if self._is_allowed_coupang_url(final_url) else None
        except:
            try:
                response = self.session.get(normalized, allow_redirects=True, timeout=10)
                final_url = self._normalize_url(response.url)
                return final_url if self._is_allowed_coupang_url(final_url) else None
            except Exception as e:
                print(f"  [!] Redirect error: {e}")
                return None

    def _extract_keywords(self, title: str) -> str:
        """상품명에서 검색 키워드 추출"""
        # 불필요한 문자 제거
        keywords = re.sub(r'[\[\]()（）\d+개입\d+ml\d+g\d+kg\d+팩]', ' ', title)
        keywords = re.sub(r'[^\w\s가-힣a-zA-Z]', ' ', keywords)

        # 중복 공백 제거
        keywords = re.sub(r'\s+', ' ', keywords).strip()

        # 핵심 단어만 추출 (2글자 이상)
        words = [w for w in keywords.split() if len(w) >= 2]

        # 최대 5개 단어만 사용
        return ' '.join(words[:5])

    def validate_link(self, url: str) -> bool:
        """쿠팡 파트너스 링크 유효성 검사"""
        try:
            return self._is_allowed_coupang_url(url)
        except:
            return False

    def extract_links_from_text(self, text: str) -> list:
        """텍스트에서 쿠팡 링크 추출"""
        pattern1 = r'https?://link\.coupang\.com/[^\s<>\"\']+'
        pattern2 = r'https?://(?:www\.)?coupang\.com/vp/products/\d+[^\s<>\"\']+'

        links = []
        links.extend(re.findall(pattern1, text))
        links.extend(re.findall(pattern2, text))

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
        print(f"API Key: 명령줄에서 제공됨")
    if len(sys.argv) > 2:
        test_url = sys.argv[2]

    # 환경변수에서 시도
    if not api_key:
        api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if api_key:
            print(f"API Key: 환경변수에서 로드됨")

    # config에서 시도
    if not api_key:
        try:
            from src.config import config
            api_key = config.gemini_api_key
            if api_key:
                print(f"API Key: config에서 로드됨")
        except:
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
            print(f"\n결과:")
            print(f"  Product ID: {info.get('product_id', 'N/A')}")
            print(f"  Title: {info.get('title') or '(추출 불가)'}")
            print(f"  Keywords: {info.get('search_keywords') or '(추출 불가)'}")
            print(f"  Image URL: {info.get('image_url') or '(추출 불가)'}")

            if info.get('title'):
                print(f"\n✅ Gemini URL Context로 상품 정보 추출 성공!")
            else:
                print(f"\n⚠️ 상품 정보 추출 실패")
                print("   → UI에서 'URL | 키워드' 형식으로 직접 입력 필요")
        else:
            print("파싱 실패")
    else:
        print(f"유효하지 않은 링크: {test_url}")
