import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from src.login_window import LoginWindow
from src.main_window import MainWindow
from src.settings_dialog import SettingsDialog
from src.theme import Colors


def _app():
    return QApplication.instance() or QApplication([])


def _assert_button_text_fits(button: QPushButton, horizontal_padding=12, vertical_padding=8):
    lines = (button.text() or "").splitlines() or [""]
    metrics = button.fontMetrics()
    assert max(metrics.horizontalAdvance(line) for line in lines) <= (
        button.width() - horizontal_padding * 2
    )
    assert metrics.lineSpacing() * len(lines) <= button.height() - vertical_padding * 2


def _assert_wrapped_label_fits(label: QLabel):
    metrics = label.fontMetrics()
    bounds = metrics.boundingRect(
        QRect(0, 0, max(1, label.width()), 10000),
        int(Qt.TextFlag.TextWordWrap),
        label.text(),
    )
    assert bounds.height() <= label.height()


def test_nordic_bento_preserves_the_complete_ui_contract():
    app = _app()
    window = MainWindow()
    try:
        required_attributes = (
            "logout_btn", "tutorial_btn", "update_btn", "_work_label",
            "_header_username_label", "_online_dot", "_connection_label",
            "status_badge", "_plan_badge", "_sidebar", "_sidebar_buttons",
            "_progress_queue_label", "_step_dots", "_step_labels",
            "_sidebar_status_label", "_sidebar_success_label",
            "_sidebar_failed_label", "_sidebar_total_label", "log_text",
            "_upload_account_tabs", "_page_help_btn", "_link_help_panel",
            "_coupang_link", "link_count_badge", "_links_hint", "links_text",
            "start_btn", "add_btn", "stop_btn", "start_all_btn", "stop_all_btn",
            "_run_state_frame", "_run_state_title", "_run_state_main",
            "_run_state_detail", "_run_state_next", "_link_table_label", "link_table",
            "_settings_tab_bar", "_settings_help_panel", "_settings_scroll",
            "_settings_content", "_settings_save_btn", "_settings_account_sec",
            "_acct_username_label", "_acct_status_label", "_acct_plan_badge",
            "_acct_work_label", "_settings_threads_sec", "threads_account_combo",
            "threads_account_add_btn", "threads_account_remove_btn", "username_edit",
            "login_status_label", "threads_login_btn", "check_login_btn",
            "_threads_hint_label", "_settings_automation_sec", "hour_spin",
            "min_spin", "sec_spin", "video_check", "settings_post_concept_combo",
            "_concept_desc", "_settings_api_sec", "_ai_provider_combo",
            "_settings_api_guide", "_grok_status_label", "_gemini_key_rows",
            "_add_gemini_key_btn", "_settings_info_sec", "_version_label",
            "_settings_payment_sec", "_pay_phone_edit", "_pay_weekly_btn",
            "_pay_monthly_btn", "_pay_shopping_weekly_btn",
            "_pay_shopping_monthly_btn", "_pay_status_label", "_pay_cancel_btn",
            "_pay_refresh_btn", "_settings_startup_sec", "_auto_start_check",
            "_settings_tutorial_sec", "_tutorial_settings_btn",
            "_settings_contact_sec", "_contact_btn", "_status_bar_frame",
            "_statusbar_dot", "status_label", "_server_label", "progress_label",
        )
        missing = [name for name in required_attributes if not hasattr(window, name)]
        assert missing == []
        assert len(window._sidebar_buttons) == 2
        assert len(window._step_dots) == len(window._step_labels) == 4
        assert len(window._gemini_key_rows) == 10
        assert [window._settings_tab_bar.tabText(i) for i in range(4)] == [
            "업로드 · 글쓰기", "계정 · 연결", "AI · 앱", "구독 · 지원"
        ]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_nordic_bento_reflows_without_dropping_automation_actions():
    app = _app()
    window = MainWindow()
    window.show()
    try:
        window.resize(1360, 900)
        window._switch_page(0)
        app.processEvents()
        assert window._link_input_card.y() == window._run_state_frame.y()
        assert window._link_input_card.geometry().right() < window._run_state_frame.x()
        assert window.link_table.y() > window._run_state_frame.geometry().bottom()

        window.resize(900, 620)
        app.processEvents()
        assert window._run_state_frame.y() > window._link_input_card.geometry().bottom()
        for button in (
            window.start_btn,
            window.add_btn,
            window.stop_btn,
            window.start_all_btn,
            window.stop_all_btn,
        ):
            assert button.isVisible()
            assert button.geometry().right() <= window._link_input_card.geometry().right()
            assert button.geometry().bottom() <= window._link_input_card.geometry().bottom()
        assert window.link_table.height() >= 42
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_nordic_bento_settings_use_twelve_column_pairings():
    app = _app()
    window = MainWindow()
    window.resize(1360, 900)
    window.show()
    window._switch_page(1)
    try:
        pairings = (
            (1, window._settings_account_sec, window._settings_threads_sec),
            (2, window._settings_api_sec, window._settings_startup_sec),
            (3, window._settings_payment_sec, window._settings_tutorial_sec),
        )
        for tab_index, primary, secondary in pairings:
            window._settings_tab_bar.setCurrentIndex(tab_index)
            app.processEvents()
            assert primary.isVisible() and secondary.isVisible()
            assert primary.geometry().right() < secondary.x() or secondary.geometry().right() < primary.x()
            assert primary.geometry().right() < window._settings_content.width()
            assert secondary.geometry().right() < window._settings_content.width()

        assert Colors.BG_DARK == "#EDF1F3"
        assert Colors.BG_CARD == "#FFFFFF"
        assert Colors.ACCENT == "#176B87"
        assert Colors.TEXT_PRIMARY == "#17272F"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_text_metrics_fit_payment_header_sidebar_and_dynamic_run_state():
    app = _app()
    window = MainWindow()
    window.resize(900, 620)
    window.show()
    try:
        window._switch_page(1)
        window._settings_tab_bar.setCurrentIndex(3)
        window._pay_shopping_monthly_btn.setText(
            "월간 쇼핑 프로  69,000원\n10개 Threads 계정 · 정기결제"
        )
        app.processEvents()

        for button in (
            window._pay_weekly_btn,
            window._pay_monthly_btn,
            window._pay_shopping_weekly_btn,
            window._pay_shopping_monthly_btn,
        ):
            _assert_button_text_fits(button)
            assert button.height() >= 56
        assert window._pay_phone_edit.textMargins().left() >= 12
        for label in (
            window._payment_desc,
            window._shopping_offer_label,
            window._pay_hint_label,
            window._pay_status_label,
            window._contact_desc,
        ):
            _assert_wrapped_label_fits(label)

        for button in (window.logout_btn, window.tutorial_btn, window._work_label, window._plan_badge):
            assert button.height() >= button.sizeHint().height()
        for label in (
            window._sidebar_success_label,
            window._sidebar_failed_label,
            window._sidebar_total_label,
        ):
            assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()

        window._switch_page(0)
        window._run_state_main.setText("2번 계정에서 상품 정보를 확인하는 중입니다.")
        window._run_state_detail.setText(
            "현재 링크를 분석하고 Threads 게시물을 준비하고 있습니다. 잠시만 기다려주세요."
        )
        window._run_state_next.setText("다음 작업: Threads 업로드 상태 확인")
        app.processEvents()
        for label in (window._run_state_main, window._run_state_detail, window._run_state_next):
            _assert_wrapped_label_fits(label)
        assert window._link_scroll.verticalScrollBar().maximum() > 0
        assert window.link_table.height() >= 140
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_login_registration_and_legacy_dialog_controls_keep_text_room():
    app = _app()
    login = LoginWindow()
    dialog = SettingsDialog()
    try:
        login.resize(600, 600)
        login.show()
        app.processEvents()
        assert login.login_id.height() >= 48
        assert login.login_pw.height() >= 48
        assert login.remember_cb.height() >= 30
        assert login.auto_login_cb.height() >= 30
        assert login.btn_go_register.height() >= 46
        assert login.login_status.height() >= 2 * login.login_status.fontMetrics().lineSpacing()

        login.stack.setCurrentIndex(1)
        app.processEvents()
        assert login._form_scroll.verticalScrollBar().maximum() > 0
        for field in (
            login.reg_name,
            login.reg_email,
            login.reg_username,
            login.reg_pw,
            login.reg_pw_confirm,
            login.reg_contact,
        ):
            assert field.height() >= 48
        assert login.btn_check_user.width() >= login.btn_check_user.sizeHint().width()
        assert login.btn_check_user.height() >= login.btn_check_user.sizeHint().height()
        assert login.reg_news_opt_in.height() >= 2 * login.reg_news_opt_in.fontMetrics().lineSpacing()
        assert login.reg_legal_consent.height() >= 2 * login.reg_legal_consent.fontMetrics().lineSpacing()

        dialog.resize(460, 560)
        dialog.show()
        app.processEvents()
        assert dialog.save_btn.height() >= 44
        assert dialog.cancel_btn.height() >= 44
        assert dialog.gemini_key_edit.height() >= 48
        assert dialog.username_edit.height() >= 48
        assert dialog.threads_login_btn.height() >= 44
        assert dialog.check_login_btn.height() >= 44
    finally:
        login.close()
        dialog.close()
        login.deleteLater()
        dialog.deleteLater()
        app.processEvents()
