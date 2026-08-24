import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QBoxLayout, QDialog, QWidget

from src.config import config
from src.main_window import MainWindow
from src.onboarding_dialog import OnboardingDialog
from src.theme import ControlHeight


def _app():
    return QApplication.instance() or QApplication([])


def _close(*widgets):
    app = _app()
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    app.processEvents()


def test_parent_relative_compact_size_and_wide_reflow_have_no_horizontal_scroll():
    app = _app()
    parent = QWidget()
    parent.resize(760, 560)
    parent.show()
    dialog = OnboardingDialog(parent)
    dialog.show()
    app.processEvents()
    try:
        assert dialog.minimumWidth() <= 640
        assert dialog.minimumHeight() <= 500
        assert dialog.width() <= int(parent.width() * 0.9)
        assert dialog.height() <= int(parent.height() * 0.9)
        assert dialog.is_compact
        assert dialog.step_layout.direction() == QBoxLayout.Direction.LeftToRight
        assert len(dialog.step_buttons) == len(dialog.step_scroll_areas) == 4
        assert all(
            button.height() >= ControlHeight.INPUT for button in dialog.step_buttons
        )
        assert dialog.back_btn.height() >= ControlHeight.PRIMARY
        assert dialog.next_btn.height() >= ControlHeight.PRIMARY
        for index, scroll_area in enumerate(dialog.step_scroll_areas):
            dialog.set_current_step(index)
            app.processEvents()
            assert (
                scroll_area.horizontalScrollBarPolicy()
                == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            assert scroll_area.horizontalScrollBar().maximum() == 0

        parent.resize(1400, 1000)
        dialog.setMaximumSize(16777215, 16777215)
        dialog.resize(1040, 720)
        app.processEvents()
        assert not dialog.is_compact
        assert dialog.step_layout.direction() == QBoxLayout.Direction.TopToBottom
        assert dialog.width() == 1040
        assert dialog.height() == 720
    finally:
        _close(dialog, parent)


def test_step_api_updates_navigation_status_and_accessibility():
    app = _app()
    dialog = OnboardingDialog()
    dialog.show()
    app.processEvents()
    try:
        assert dialog.current_step == 0
        assert dialog.step_stack.currentIndex() == 0
        assert dialog.step_buttons[0].isChecked()

        dialog.set_current_step(2)
        app.processEvents()
        assert dialog.current_step == 2
        assert dialog.step_stack.currentIndex() == 2
        assert dialog.step_buttons[2].isChecked()
        assert dialog.back_btn.isEnabled()
        assert dialog.next_btn.text() == "다음"

        dialog.set_step_status(1, "complete", "Threads 연결을 확인했습니다.")
        assert "완료" in dialog.step_buttons[1].accessibleDescription()
        assert (
            "Threads 연결을 확인했습니다."
            in dialog.step_buttons[1].accessibleDescription()
        )
        assert dialog.step_status_pills[1].status == "success"
        assert dialog.step_detail_labels[1].text() == "Threads 연결을 확인했습니다."

        dialog.set_step_status(2, "error", "기본값을 다시 확인해 주세요.")
        assert dialog.step_status_pills[2].status == "error"
        assert "오류" in dialog.step_buttons[2].accessibleDescription()

        with pytest.raises(IndexError):
            dialog.set_current_step(4)
        with pytest.raises(IndexError):
            dialog.set_step_status(-1, "pending")
        with pytest.raises(ValueError):
            dialog.set_step_status(0, "pretend-success")
    finally:
        _close(dialog)


def test_step_actions_emit_intent_only_and_never_fake_success():
    app = _app()
    dialog = OnboardingDialog()
    dialog.show()
    app.processEvents()
    subscription_spy = QSignalSpy(dialog.open_subscription_requested)
    accounts_spy = QSignalSpy(dialog.open_accounts_requested)
    settings_spy = QSignalSpy(dialog.open_settings_requested)
    sample_spy = QSignalSpy(dialog.sample_link_requested)
    try:
        QTest.mouseClick(dialog.subscription_btn, Qt.MouseButton.LeftButton)
        QTest.mouseClick(dialog.accounts_btn, Qt.MouseButton.LeftButton)
        QTest.mouseClick(dialog.settings_btn, Qt.MouseButton.LeftButton)
        assert len(subscription_spy) == len(accounts_spy) == len(settings_spy) == 1
        assert all(pill.status != "success" for pill in dialog.step_status_pills)

        dialog.set_current_step(3)
        app.processEvents()
        dialog.sample_link_edit.clear()
        QTest.mouseClick(dialog.sample_link_btn, Qt.MouseButton.LeftButton)
        assert len(sample_spy) == 0
        assert dialog.sample_link_error.isVisible()
        assert dialog.sample_link_edit.hasFocus()

        sample_url = "https://link.coupang.com/a/test-item"
        dialog.sample_link_edit.setText(sample_url)
        QTest.mouseClick(dialog.sample_link_btn, Qt.MouseButton.LeftButton)
        assert len(sample_spy) == 1
        assert sample_spy[0][0] == sample_url
        assert not dialog.sample_link_error.isVisible()
        assert dialog.step_status_pills[3].status != "success"
    finally:
        _close(dialog)


def test_keyboard_back_next_finish_and_escape_emit_terminal_signal_once():
    app = _app()
    dialog = OnboardingDialog()
    dialog.show()
    app.processEvents()
    finished_spy = QSignalSpy(dialog.finished)
    skipped_spy = QSignalSpy(dialog.skipped)
    try:
        QTest.keyClick(
            dialog,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.AltModifier,
        )
        assert dialog.current_step == 1
        QTest.keyClick(
            dialog,
            Qt.Key.Key_Left,
            Qt.KeyboardModifier.AltModifier,
        )
        assert dialog.current_step == 0

        dialog.set_current_step(3)
        assert dialog.next_btn.text() == "온보딩 완료"
        QTest.mouseClick(dialog.next_btn, Qt.MouseButton.LeftButton)
        assert len(finished_spy) == 1
        assert len(skipped_spy) == 0
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        _close(dialog)

    escape_dialog = OnboardingDialog()
    escape_dialog.show()
    app.processEvents()
    escape_finished_spy = QSignalSpy(escape_dialog.finished)
    escape_skipped_spy = QSignalSpy(escape_dialog.skipped)
    try:
        QTest.keyClick(escape_dialog, Qt.Key.Key_Escape)
        assert len(escape_skipped_spy) == 1
        assert len(escape_finished_spy) == 0
        assert escape_dialog.result() == QDialog.DialogCode.Rejected
    finally:
        _close(escape_dialog)


def test_main_window_connects_authenticated_onboarding_to_real_routes(monkeypatch):
    app = _app()
    monkeypatch.setattr(config, "onboarding_completed", False)
    monkeypatch.setattr(config, "tutorial_shown", False)
    monkeypatch.setattr(config, "save", lambda: True)
    window = MainWindow()
    window._auth_data = {"id": "qa-user", "username": "qa-user", "work_count": 5}
    window.show()
    app.processEvents()
    try:
        window._show_onboarding_if_needed()
        app.processEvents()
        dialog = window._onboarding_dialog
        assert dialog is not None
        assert dialog.isVisible()
        assert dialog.step_status_pills[0].status == "success"

        sample_url = "https://link.coupang.com/a/manual-qa-item"
        dialog.sample_link_requested.emit(sample_url)
        app.processEvents()
        assert window._page_stack.currentIndex() == 0
        assert window.links_text.toPlainText() == sample_url
        assert dialog.step_status_pills[3].status == "success"
        assert not dialog.isVisible()
        assert window._onboarding_resume_btn.isVisible()
        button_top_left = window._onboarding_resume_btn.mapTo(
            window.centralWidget(), window._onboarding_resume_btn.rect().topLeft()
        )
        footer_top_left = window._automation_footer.mapTo(
            window.centralWidget(), window._automation_footer.rect().topLeft()
        )
        button_rect = window._onboarding_resume_btn.rect().translated(button_top_left)
        footer_rect = window._automation_footer.rect().translated(footer_top_left)
        assert not button_rect.intersects(footer_rect)

        window._onboarding_resume_btn.click()
        app.processEvents()
        assert dialog.isVisible()

        dialog.reject()
        app.processEvents()
        assert config.onboarding_completed is False
        assert window._onboarding_dismissed_for_session is True
        assert not window._onboarding_resume_btn.isVisible()

        window._complete_onboarding()
        assert config.onboarding_completed is True
        assert config.tutorial_shown is True
    finally:
        window._closed = True
        _close(window)
