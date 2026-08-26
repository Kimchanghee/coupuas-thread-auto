"""Safe reporting links for inappropriate AI-generated content."""

from __future__ import annotations

from urllib.parse import urlencode


AI_CONTENT_REPORT_EMAIL = "support@fitshot.ai"
AI_CONTENT_REPORT_SUBJECT = "Thread Auto AI 생성 결과 신고"


def build_ai_content_report_url(*, app_version: object = "", provider: object = "") -> str:
    """Return a mailto link that never includes generated content automatically."""

    version_text = str(app_version or "확인 필요").strip() or "확인 필요"
    provider_text = str(provider or "확인 필요").strip() or "확인 필요"
    body = "\n".join(
        (
            "AI 생성 결과 신고",
            "",
            "문제 유형: 부적절함 / 유해함 / 사실과 다름 / 기타",
            "발견한 화면 또는 작업:",
            "문제 설명:",
            "",
            "문제된 문안(개인정보와 비밀값을 지운 뒤 필요한 부분만 붙여넣어 주세요):",
            "",
            f"앱 버전: {version_text}",
            f"AI 방식: {provider_text}",
            "",
            "안내: 게시물 내용과 개인정보는 앱에서 자동으로 전송되지 않습니다.",
        )
    )
    query = urlencode({"subject": AI_CONTENT_REPORT_SUBJECT, "body": body})
    return f"mailto:{AI_CONTENT_REPORT_EMAIL}?{query}"
