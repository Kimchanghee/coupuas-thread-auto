import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication

from src.ai_content_report import (
    AI_CONTENT_REPORT_EMAIL,
    AI_CONTENT_REPORT_SUBJECT,
    build_ai_content_report_url,
)
from src.main_window import MainWindow


ROOT = Path(__file__).resolve().parent


def _app():
    return QApplication.instance() or QApplication([])


def test_ai_content_report_url_contains_guidance_but_no_generated_content():
    url = build_ai_content_report_url(app_version="v3.2.3", provider="AI 자동 작성")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "mailto"
    assert parsed.path == AI_CONTENT_REPORT_EMAIL
    assert query["subject"] == [AI_CONTENT_REPORT_SUBJECT]
    body = query["body"][0]
    assert "문제 유형" in body
    assert "개인정보" in body
    assert "자동으로 전송되지 않습니다" in body
    assert "v3.2.3" in body
    assert "AI 자동 작성" in body


def test_main_window_exposes_dedicated_ai_report_action(monkeypatch):
    app = _app()
    window = MainWindow()
    opened = []
    monkeypatch.setattr(
        window,
        "_open_external_link",
        lambda url, event: opened.append((url, event)) or True,
    )
    try:
        assert window._settings_ai_report_sec is not None
        assert window._ai_report_btn.text() == "부적절한 AI 결과 신고하기"
        assert window._ai_report_btn.accessibleName() == "부적절한 AI 생성 결과 신고"

        window._ai_report_btn.click()
        app.processEvents()

        assert len(opened) == 1
        assert opened[0][0].startswith(f"mailto:{AI_CONTENT_REPORT_EMAIL}?")
        assert opened[0][1] == "settings_ai_content_report"
    finally:
        window._closed = True
        window.close()
        window.deleteLater()
        app.processEvents()


def test_store_listing_discloses_every_free_tier_limit_and_report_path():
    listing = (ROOT / "docs" / "MICROSOFT_STORE_FIRST_SUBMISSION.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "매월 자동화 작업 5회",
        "Threads 계정 1개",
        "첫 번째 성공 작업 1회",
        "남은 무료 작업 4회는 쿠팡 링크만",
        "부적절한 AI 결과 신고하기",
    ):
        assert required in listing


def test_public_support_page_has_ai_report_mechanism_and_privacy_notice():
    support = (ROOT / "public" / "support.html").read_text(encoding="utf-8")
    assert 'id="ai-report"' in support
    assert "AI 생성 결과 신고" in support
    assert f"mailto:{AI_CONTENT_REPORT_EMAIL}" in support
    assert "자동으로 전송되지 않습니다" in support
