import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication

from src.ai_provider import AI_PROVIDER_GEMINI
from src.config import config
from src.main_window import MainWindow


def test_settings_page_uses_four_category_tabs(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "ai_provider", AI_PROVIDER_GEMINI)

    window = MainWindow()
    tab_bar = window._settings_tab_bar

    assert [tab_bar.tabText(index) for index in range(tab_bar.count())] == [
        "계정 · 연결",
        "작성 · AI",
        "앱 설정",
        "구독 · 지원",
    ]
    assert not window._settings_account_sec.isHidden()
    assert not window._settings_threads_sec.isHidden()
    assert window._settings_concept_sec.isHidden()
    assert window._settings_api_sec.isHidden()

    tab_bar.setCurrentIndex(1)
    app.processEvents()
    assert not window._settings_concept_sec.isHidden()
    assert not window._settings_api_sec.isHidden()
    assert window._settings_account_sec.isHidden()

    tab_bar.setCurrentIndex(2)
    app.processEvents()
    assert not window._settings_startup_sec.isHidden()
    assert not window._settings_info_sec.isHidden()
    assert window._settings_payment_sec.isHidden()

    tab_bar.setCurrentIndex(3)
    app.processEvents()
    assert not window._settings_payment_sec.isHidden()
    assert not window._settings_tutorial_sec.isHidden()
    assert not window._settings_contact_sec.isHidden()
    assert window._settings_startup_sec.isHidden()

    assert window._settings_save_btn.parent() is window._pages[2]
    assert window._settings_scroll.geometry().bottom() < window._settings_save_btn.y()

    window.deleteLater()
    app.processEvents()
