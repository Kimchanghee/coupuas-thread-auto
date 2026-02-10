"""
1688 상품 이미지 검색 서비스
상품명으로 1688에서 관련 이미지를 최대한 가져옵니다.
최대 10번 재시도하여 최소 1개 이상 이미지를 확보합니다.
"""
import os
import re
import time
import random
import requests
import hashlib
from typing import Optional, List, Tuple
from urllib.parse import quote


class ImageSearchService:
    """1688 이미지 검색 서비스 - 적극적 검색"""

    CACHE_DIR = "media/cache"
    MAX_RETRIES = 10  # 최대 재시도 횟수
    TARGET_IMAGES = 2  # 목표 이미지 개수 (영상 있으면 1개)

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._gemini_model = None

    def _get_gemini_model(self, api_key: str):
        """Gemini 모델 가져오기"""
        if self._gemini_model is None and api_key:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        return self._gemini_model

    def search_product_images(self, product_info: dict, api_key: str = "") -> List[str]:
        """
        상품 이미지 적극 검색 - 최대 10번 재시도

        Args:
            product_info: 상품 정보
            api_key: Gemini API 키

        Returns:
            이미지 경로 리스트 (1~2개)
        """
        title = product_info.get('title', '')
        keywords = product_info.get('search_keywords', '')

        if not title and not keywords:
            print("  상품명/키워드 없음")
            return []

        images = []
        tried_keywords = set()
        retry_count = 0

        # 검색 키워드 변형 생성
        search_variants = self._generate_search_variants(title, keywords, api_key)

        print(f"  1688 이미지 검색 시작 (목표: {self.TARGET_IMAGES}개, 최대 {self.MAX_RETRIES}회 시도)")

        while len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
            retry_count += 1

            # 다음 검색어 선택
            search_term = None
            for variant in search_variants:
                if variant not in tried_keywords:
                    search_term = variant
                    tried_keywords.add(variant)
                    break

            # 모든 변형 시도했으면 랜덤 변형 생성
            if search_term is None:
                search_term = self._generate_random_variant(title, keywords, api_key, retry_count)
                tried_keywords.add(search_term)

            print(f"  [{retry_count}/{self.MAX_RETRIES}] 검색: {search_term[:30]}...")

            # 1688 검색
            found_urls = self._search_1688_multiple(search_term)

            for url in found_urls:
                if len(images) >= self.TARGET_IMAGES:
                    break

                # 중복 체크 (URL 해시로)
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                if any(url_hash in img for img in images):
                    continue

                # 다운로드
                local_path = self._download_image(url, title)
                if local_path:
                    images.append(local_path)
                    print(f"  ✅ 이미지 {len(images)}개 확보: {local_path}")

            # 잠시 대기 (봇 탐지 방지)
            if len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
                time.sleep(random.uniform(0.5, 1.5))

        if images:
            print(f"  1688 이미지 검색 완료: {len(images)}개 확보")
        else:
            print(f"  1688 이미지 검색 실패 ({self.MAX_RETRIES}회 시도)")

        return images

    def search_product_image(self, product_info: dict, api_key: str = "") -> Optional[str]:
        """
        단일 이미지 검색 (기존 호환용)

        Returns:
            이미지 경로 또는 None
        """
        images = self.search_product_images(product_info, api_key)
        return images[0] if images else None

    def _generate_search_variants(self, title: str, keywords: str, api_key: str) -> List[str]:
        """검색어 변형 생성"""
        variants = []

        # 1. 중국어 번역 (가장 중요)
        chinese = self._translate_to_chinese(title or keywords, api_key)
        if chinese:
            variants.append(chinese)

        # 2. 키워드 기반 중국어
        if keywords and keywords != title:
            chinese_kw = self._translate_to_chinese(keywords, api_key)
            if chinese_kw and chinese_kw not in variants:
                variants.append(chinese_kw)

        # 3. 단어별 번역
        words = (title or keywords).split()
        if len(words) > 2:
            # 핵심 단어만 번역
            core_words = ' '.join(words[:3])
            chinese_core = self._translate_to_chinese(core_words, api_key)
            if chinese_core and chinese_core not in variants:
                variants.append(chinese_core)

        # 4. 영어 키워드
        english = self._translate_to_english(title or keywords, api_key)
        if english:
            variants.append(english)

        # 5. 원본 (한국어)
        if title:
            variants.append(title)
        if keywords and keywords not in variants:
            variants.append(keywords)

        return variants

    def _generate_random_variant(self, title: str, keywords: str, api_key: str, attempt: int) -> str:
        """랜덤 변형 생성 (재시도용)"""
        base = title or keywords
        model = self._get_gemini_model(api_key)

        if model and attempt <= 5:
            try:
                prompts = [
                    f"'{base}'를 1688.com에서 검색하기 좋은 중국어 키워드로 변환. 다른 표현 사용. 결과만 출력:",
                    f"'{base}'의 중국어 동의어나 유사 제품명. 결과만:",
                    f"'{base}' 관련 중국 쇼핑몰 검색 키워드 (중국어). 결과만:",
                    f"'{base}'를 타오바오 스타일 중국어 키워드로. 결과만:",
                    f"'{base}'의 핵심 기능을 중국어로. 결과만:",
                ]
                prompt = prompts[attempt % len(prompts)]
                response = model.generate_content(prompt)
                result = response.text.strip().strip('"\'')
                if result:
                    return result
            except:
                pass

        # 폴백: 단순 변형
        words = base.split()
        if len(words) > 1:
            random.shuffle(words)
            return ' '.join(words[:min(3, len(words))])
        return base

    def _translate_to_chinese(self, text: str, api_key: str) -> Optional[str]:
        """중국어 번역"""
        model = self._get_gemini_model(api_key)
        if not model:
            return None

        try:
            prompt = f"""'{text}'를 중국어(简体中文)로 번역.
1688.com 검색에 적합한 상품 키워드로.
번역 결과만 출력 (따옴표, 설명 없이):"""

            response = model.generate_content(prompt)
            result = response.text.strip()
            result = re.sub(r'["\'\n]', '', result)
            # 중국어가 포함되어 있는지 확인
            if re.search(r'[\u4e00-\u9fff]', result):
                return result
            return None
        except Exception as e:
            print(f"  번역 오류: {e}")
            return None

    def _translate_to_english(self, text: str, api_key: str) -> Optional[str]:
        """영어 번역 (대안 검색용)"""
        model = self._get_gemini_model(api_key)
        if not model:
            return None

        try:
            prompt = f"""'{text}'를 영어 상품 키워드로 번역.
AliExpress 검색에 적합하게.
결과만 출력:"""

            response = model.generate_content(prompt)
            result = response.text.strip().strip('"\'')
            return result if result else None
        except:
            return None

    def _search_1688_multiple(self, keyword: str) -> List[str]:
        """1688에서 여러 이미지 URL 검색"""
        urls = []

        try:
            encoded_keyword = quote(keyword)

            # 여러 검색 URL 시도
            search_urls = [
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}",
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}&sortType=va",
                f"https://s.1688.com/pic/offer_search.htm?keywords={encoded_keyword}",
            ]

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,ko;q=0.8,en;q=0.7',
                'Referer': 'https://www.1688.com/',
            }

            for search_url in search_urls:
                if len(urls) >= 5:  # 충분히 모았으면 중단
                    break

                try:
                    response = requests.get(search_url, headers=headers, timeout=10)
                    response.encoding = 'utf-8'

                    # 이미지 URL 추출
                    patterns = [
                        r'(https?://cbu01\.alicdn\.com/img/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
                        r'(https?://img\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
                        r'(https?://cbu\d+\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
                        r'(https?://gw\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
                    ]

                    for pattern in patterns:
                        matches = re.findall(pattern, response.text, re.IGNORECASE)
                        for match in matches:
                            # 크기 파라미터 제거
                            clean_url = re.sub(r'_\d+x\d+\.', '.', match)
                            clean_url = re.sub(r'\?.+$', '', clean_url)

                            # 작은 이미지 제외 (아이콘 등)
                            if '_60x60' in match or '_80x80' in match or 'avatar' in match.lower():
                                continue

                            if clean_url not in urls:
                                urls.append(clean_url)

                            if len(urls) >= 10:
                                break
                        if len(urls) >= 10:
                            break

                except Exception as e:
                    continue

        except Exception as e:
            print(f"  1688 검색 오류: {e}")

        return urls

    def _download_image(self, url: str, product_name: str) -> Optional[str]:
        """이미지 다운로드"""
        try:
            hash_name = hashlib.md5(url.encode()).hexdigest()[:12]
            ext = url.split('.')[-1].split('?')[0][:4].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                ext = 'jpg'

            filename = f"{hash_name}.{ext}"
            filepath = os.path.join(self.CACHE_DIR, filename)

            # 이미 존재하면 재사용
            if os.path.exists(filepath):
                return filepath

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.1688.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            }

            response = requests.get(url, headers=headers, timeout=15)

            # 이미지 유효성 검사
            if response.status_code == 200 and len(response.content) > 5000:  # 5KB 이상
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type or ext in ['jpg', 'jpeg', 'png', 'webp']:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    return filepath

            return None

        except Exception as e:
            return None


# 싱글톤
_instance: Optional[ImageSearchService] = None

def get_image_search() -> ImageSearchService:
    """ImageSearchService 싱글톤 인스턴스"""
    global _instance
    if _instance is None:
        _instance = ImageSearchService()
    return _instance
