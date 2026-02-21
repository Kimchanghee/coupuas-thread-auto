"""
어그로 문구 생성 서비스
상품에 대한 재미있고 어그로성 있는 한줄 문구를 Gemini로 생성합니다.
"""
import google.generativeai as genai
from typing import Optional


class AggroGenerator:
    """어그로 문구 생성기"""

    # 쿠팡 파트너스 규정 문구
    COUPANG_DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

    # 활동 시 주의사항
    ACTIVITY_WARNING = """*활동 시 주의 사항

1. 게시글 작성 시, 아래 문구를 반드시 기재해 주세요.
"이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

쿠팡 파트너스의 활동은 공정거래위원회의 심사지침에 따라 추천, 보증인인 파트너스 회원과 당사의 경제적 이해관계에 대하여 공개하여야 합니다.

2. 바로가기 아이콘 이용 시, 수신자의 사전 동의를 얻지 않은 메신저, SNS 등으로 메시지를 발송하는 행위는 불법 스팸 전송 행위로 간주되어 규제기관의 행정제재 또는 형사 처벌의 대상이 될 수 있으니 이 점 유의하시기 바랍니다."""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Google Gemini API 키
        """
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None

    def set_api_key(self, api_key: str):
        """API 키 설정"""
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None

    def generate_aggro_text(self, product_title: str, product_keywords: str = "") -> str:
        """
        상품에 대한 어그로성 한줄 문구 생성

        Args:
            product_title: 상품명
            product_keywords: 추가 키워드 (사용하지 않음 - 한국어만 사용)

        Returns:
            어그로성 한줄 문구
        """
        if not self.model:
            return f"이거 보고 충동구매 했는데 후회 1도 없음 {product_title[:15]}"

        try:
            prompt = f"""상품명: {product_title}

Threads에 올릴 클릭을 유도하는 한줄 문구를 작성해.

규칙:
- 25~40자 정도로 작성
- 궁금해서 클릭할 수밖에 없는 문장
- 충격/반전/궁금증 유발
- 과장되고 재미있게
- 이모지 1~2개 사용
- 해시태그 금지
- 한국어만

좋은 예시:
"친구가 이거 사고 인생 바뀌었다는데 실화냐"
"우리 엄마한테 보여줬더니 왜 이제 알려줬냐고 화냄"
"이거 보고 충동구매 했는데 후회 1도 없음"
"솔직히 이 가격에 이게 된다고? 사기 아님?"
"3일 써보고 소름돋아서 가족한테도 사줌"
"이거 왜 아무도 안알려줬어 진짜 억울해"

나쁜 예시:
"좋은 상품입니다" (재미없음)
"추천드려요" (광고느낌)
"이거 실화냐?!" (너무 짧음)

한줄만 출력:"""
            response = self.model.generate_content(prompt)
            result = response.text.strip()

            # 따옴표 제거
            result = result.strip('"\'')

            # 줄바꿈 제거
            result = result.replace('\n', ' ').strip()

            # 중국어 문자 제거 (혹시 포함되어 있다면)
            import re
            result = re.sub(r'[\u4e00-\u9fff]+', '', result)

            # 해시태그 제거 (혹시 포함되어 있다면)
            result = re.sub(r'#\S+', '', result).strip()

            return result

        except Exception as e:
            print(f"  ⚠️ 어그로 문구 생성 오류: {e}")
            return f"이거 뭐야?! ㅋㅋ"

    def generate_product_post(self, product_info: dict) -> dict:
        """
        상품 정보로 스레드 포스트 데이터 생성

        Args:
            product_info: 상품 정보 딕셔너리
                - title: 상품명
                - original_url: 쿠팡 파트너스 링크
                - search_keywords: 검색 키워드
                - image_path: 이미지 경로 (선택)
                - video_path: 영상 경로 (선택)

        Returns:
            포스트 데이터 딕셔너리
            {
                'first_post': {'text': 어그로문구, 'media_path': 이미지/영상},
                'second_post': {'text': 링크+규정문구},
                'third_post': {'text': 주의사항}
            }
        """
        title = product_info.get('title', '')
        keywords = product_info.get('search_keywords', '')
        original_url = product_info.get('original_url', '')
        image_path = product_info.get('image_path')
        video_path = product_info.get('video_path')

        # 어그로 문구 생성
        aggro_text = self.generate_aggro_text(title, keywords)

        # 미디어 선택 (영상 우선)
        media_path = video_path if video_path else image_path

        # 두 번째 포스트 (링크 + 규정 문구)
        second_text = f"👆제품 구경하기\n{original_url}\n\n{self.COUPANG_DISCLOSURE}"

        # 세 번째 포스트 (주의사항)
        third_text = self.ACTIVITY_WARNING

        return {
            'first_post': {
                'text': aggro_text,
                'media_path': media_path,
                'media_type': 'video' if video_path else 'image'
            },
            'second_post': {
                'text': second_text,
                'media_path': None,
                'media_type': None
            },
            'third_post': {
                'text': third_text,
                'media_path': None,
                'media_type': None
            },
            'product_title': title,
            'original_url': original_url
        }

    def generate_batch(self, products: list) -> list:
        """
        여러 상품에 대해 일괄 포스트 생성

        Args:
            products: 상품 정보 리스트

        Returns:
            포스트 데이터 리스트
        """
        results = []
        for i, product in enumerate(products, 1):
            print(f"  📝 [{i}/{len(products)}] 어그로 문구 생성: {product.get('title', '')[:30]}...")
            post_data = self.generate_product_post(product)
            results.append(post_data)

        return results


# 테스트
if __name__ == "__main__":
    import os

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    generator = AggroGenerator(api_key)

    # 테스트 상품
    test_product = {
        'title': '동전 먹는 가오나시 저금통',
        'original_url': 'https://link.coupang.com/a/test123',
        'search_keywords': '가오나시 저금통 동전',
        'image_path': 'media/test.jpg',
        'video_path': None
    }

    result = generator.generate_product_post(test_product)
    print(f"\n첫 번째 포스트: {result['first_post']['text']}")
    print(f"두 번째 포스트: {result['second_post']['text'][:100]}...")
