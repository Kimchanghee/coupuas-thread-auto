import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QAbstractSpinBox, QApplication

from src.ai_provider import AI_PROVIDER_MANAGED
from src.config import config
from src.main_window import MainWindow


def test_settings_page_uses_four_category_tabs(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.delenv("THREAD_AUTO_ALLOW_LOCAL_AI_PROVIDERS", raising=False)
    monkeypatch.setattr(config, "ai_provider", AI_PROVIDER_MANAGED)

    window = MainWindow()
    tab_bar = window._settings_tab_bar

    assert window._nav_button_by_page[2].shortcut().toString() == "Alt+1"
    assert window._nav_button_by_page[0].shortcut().toString() == "Alt+2"
    assert window._nav_button_by_page[1].shortcut().toString() == "Alt+5"
    assert window.tutorial_btn.shortcut().toString() == "F1"
    assert window.log_text.tabChangesFocus()

    assert window._ai_provider_combo.count() == 1
    assert window._ai_provider_combo.currentData() == AI_PROVIDER_MANAGED

    assert [tab_bar.tabText(index) for index in range(tab_bar.count())] == [
        "업로드 · 글쓰기",
        "계정 · 연결",
        "AI · 앱",
        "구독 · 지원",
    ]
    assert not window._settings_automation_sec.isHidden()
    assert window._settings_account_sec.isHidden()
    assert window._settings_threads_sec.isHidden()
    assert window._settings_api_sec.isHidden()
    assert not hasattr(window, "post_concept_combo")
    assert window.hour_spin.parent() is window._settings_automation_sec
    assert all(
        spin.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.PlusMinus
        for spin in (window.hour_spin, window.min_spin, window.sec_spin)
    )
    assert window.video_check.parent() is window._settings_automation_sec
    assert window.settings_post_concept_combo.parent() is window._settings_automation_sec

    tab_bar.setCurrentIndex(1)
    app.processEvents()
    assert not window._settings_account_sec.isHidden()
    assert not window._settings_threads_sec.isHidden()
    assert window._settings_automation_sec.isHidden()

    tab_bar.setCurrentIndex(2)
    app.processEvents()
    assert not window._settings_api_sec.isHidden()
    assert not window._settings_startup_sec.isHidden()
    assert not window._settings_info_sec.isHidden()
    assert window._settings_payment_sec.isHidden()

    tab_bar.setCurrentIndex(3)
    app.processEvents()
    assert not window._settings_payment_sec.isHidden()
    assert not window._settings_tutorial_sec.isHidden()
    assert not window._settings_contact_sec.isHidden()
    assert window._settings_startup_sec.isHidden()

    assert window._pay_phone_edit.accessibleName() == "결제 휴대폰 번호"
    assert window._pay_phone_edit.maxLength() == 11
    assert "19,000원" in window._pay_weekly_btn.text()
    assert "49,000원" in window._pay_monthly_btn.text()
    assert "29,000원" in window._pay_shopping_weekly_btn.text()
    assert "69,000원" in window._pay_shopping_monthly_btn.text()
    assert window._pay_shopping_weekly_btn.accessibleName() == "7일 쇼핑 프로 이용권 결제"
    assert window._pay_shopping_monthly_btn.accessibleName() == "월간 쇼핑 프로 이용권 결제"
    assert window._settings_payment_sec.height() >= 360

    assert window._settings_footer.parent() is window._pages[1]
    assert window._settings_save_btn.parent() is window._settings_footer
    assert window._settings_scroll.geometry().bottom() < window._settings_footer.y()

    window._switch_page(0)
    window.open_tutorial()
    app.processEvents()
    assert window._tutorial_overlay.isVisible() is window.isVisible()
    assert window._tutorial_overlay.accessibleName() == "현재 화면 도움말"
    assert window.tutorial_btn.text() in {"?", "도움말"}
    window._tutorial_overlay._close_overlay()

    window.deleteLater()
    app.processEvents()
