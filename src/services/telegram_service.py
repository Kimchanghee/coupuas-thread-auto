"""
텔레그램 알림 서비스
업로드 완료 시 텔레그램으로 알림을 보냅니다.
"""
import requests
from typing import Optional, Dict
from src.config import config


class TelegramService:
    """텔레그램 알림 서비스"""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        """
        Args:
            bot_token: 텔레그램 봇 토큰
            chat_id: 알림 받을 채팅 ID
        """
        self.bot_token = bot_token or config.telegram_bot_token
        self.chat_id = chat_id or config.telegram_chat_id
        self.enabled = config.telegram_enabled

    def is_configured(self) -> bool:
        """텔레그램 설정 여부 확인"""
        return bool(self.enabled and self.bot_token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """
        텔레그램 메시지 전송

        Args:
            message: 전송할 메시지

        Returns:
            성공 여부
        """
        if not self.is_configured():
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200

        except Exception as e:
            print(f"  ⚠️ 텔레그램 전송 오류: {e}")
            return False

    def send_upload_result(self, results: Dict) -> bool:
        """
        업로드 결과 알림 전송

        Args:
            results: 업로드 결과 딕셔너리

        Returns:
            성공 여부
        """
        if not self.is_configured():
            return False

        total = results.get('total', 0)
        processed = results.get('processed', 0)
        uploaded = results.get('uploaded', 0)
        failed = results.get('failed', 0)
        parse_failed = results.get('parse_failed', 0)
        cancelled = results.get('cancelled', False)

        status = "🛑 취소됨" if cancelled else "✅ 완료"

        message = f"""
<b>📊 쿠팡 파트너스 업로드 {status}</b>

🔗 전체 링크: {total}개
📝 파싱 완료: {processed}개
❌ 파싱 실패: {parse_failed}개

📤 <b>업로드 결과</b>
✅ 성공: {uploaded}개
❌ 실패: {failed}개
"""

        # 상세 결과가 있으면 추가
        details = results.get('details', [])
        if details:
            success_items = [d for d in details if d.get('success')]
            if success_items:
                message += "\n<b>📋 업로드 성공 목록</b>\n"
                for item in success_items[:5]:  # 최대 5개만 표시
                    title = item.get('product_title', '')[:30]
                    message += f"• {title}...\n"

                if len(success_items) > 5:
                    message += f"... 외 {len(success_items) - 5}개\n"

        return self.send_message(message.strip())

    def send_error_alert(self, error_message: str) -> bool:
        """
        오류 알림 전송

        Args:
            error_message: 오류 메시지

        Returns:
            성공 여부
        """
        if not self.is_configured():
            return False

        message = f"""
<b>⚠️ 쿠팡 파트너스 오류 발생</b>

{error_message}
"""
        return self.send_message(message.strip())


# 전역 인스턴스
telegram_service = TelegramService()


# 테스트
if __name__ == "__main__":
    service = TelegramService()

    if service.is_configured():
        print("텔레그램 설정됨")
        service.send_message("🧪 테스트 메시지입니다!")
    else:
        print("텔레그램 미설정")
        print(f"  - Enabled: {service.enabled}")
        print(f"  - Token: {'있음' if service.bot_token else '없음'}")
        print(f"  - Chat ID: {'있음' if service.chat_id else '없음'}")
