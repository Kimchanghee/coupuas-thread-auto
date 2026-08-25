import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QFrame, QWidget

from src import auth_client
import src.login_window as login_window_module
from src.login_window import LoginWindow, WEBSITE_BASE_URL
from src.tutorial import OVERLAY_STEPS, TutorialOverlay
from src.update_dialog import UpdateDialog


def _app():
    return QApplication.instance() or QApplication([])


def test_compact_login_has_no_scroll_and_keeps_48_dip_controls(monkeypatch):
    app = _app()
    monkeypatch.setattr(auth_client, "get_saved_credentials", dict)
    window = LoginWindow()
    try:
        window.resize(420, 560)
        window.show()
        app.processEvents()

        assert window.compact_brand_bar.isVisible()
        assert not window.left_panel.isVisible()
        assert window._form_scroll.verticalScrollBar().maximum() == 0
        assert window.login_id.height() >= 48
        assert window.login_pw.height() >= 48
        assert window.btn_login.height() >= 48
        assert window.btn_close.width() >= 40
        assert window.btn_close.height() >= 40
        assert window.login_status.geometry().bottom() < window._form_scroll.height()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_saved_login_credentials_are_loaded_before_auto_login_is_scheduled(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        auth_client,
        "get_saved_credentials",
        lambda: {
            "username": "saved_user",
            "password": "saved_password",
            "auto_login": True,
        },
    )
    window = LoginWindow()
    try:
        assert window.login_id.text() == "saved_user"
        assert window.login_pw.text() == "saved_password"
        assert window.remember_cb.isChecked()
        assert window.auto_login_cb.isChecked()
        assert window._auto_login_pending is True
        assert window.stack.currentIndex() == 0
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_password_reset_opens_live_route_and_reports_browser_failure(monkeypatch):
    app = _app()
    monkeypatch.setattr(auth_client, "get_saved_credentials", dict)
    opened = []
    warnings = []
    monkeypatch.setattr(
        login_window_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or False,
    )
    monkeypatch.setattr(
        login_window_module,
        "show_warning",
        lambda parent, title, message: warnings.append((title, message)),
    )
    window = LoginWindow()
    try:
        window._password_reset_btn.click()
        app.processEvents()
        assert opened == [f"{WEBSITE_BASE_URL}/forgot-password"]
        assert warnings
        assert warnings[0][0] == "비밀번호 재설정"
        assert "브라우저를 열 수 없습니다" in warnings[0][1]
        assert window._password_reset_btn.height() >= 40
        assert window._password_reset_btn.accessibleName()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_registration_uses_two_local_steps_without_recreating_public_fields(monkeypatch):
    app = _app()
    monkeypatch.setattr(auth_client, "get_saved_credentials", dict)
    window = LoginWindow()
    try:
        window.resize(720, 760)
        window.show()
        window.btn_go_register.click()
        app.processEvents()

        required = (
            "reg_name",
            "reg_email",
            "reg_username",
            "reg_pw",
            "reg_pw_confirm",
            "reg_contact",
            "reg_legal_consent",
            "btn_check_user",
            "btn_register",
            "btn_go_register",
        )
        assert all(hasattr(window, name) for name in required)
        assert window.stack.currentIndex() == 1
        assert window._register_steps.count() == 2

        window.reg_name.setText("테스트 사용자")
        window.reg_email.setText("user@example.com")
        window.reg_username.setText("test_user")
        window.reg_pw.setText("password8")
        window.reg_pw_confirm.setText("password8")
        window._username_available = True
        window._username_available_for = "test_user"
        window._go_register_step_two()
        app.processEvents()

        assert window._register_steps.currentIndex() == 1
        assert window._register_step_text.text() == "2 / 2"
        assert window.reg_name.text() == "테스트 사용자"
        assert window.reg_username.text() == "test_user"
        assert window.btn_register.height() >= 48
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


class _OverlayHost(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(760, 560)
        fixtures = {
            "_sidebar": (0, 0, 72, 560),
            "_run_state_frame": (402, 84, 320, 180),
            "links_text": (92, 106, 280, 156),
            "start_btn": (92, 310, 180, 48),
            "_settings_tab_bar": (92, 42, 500, 44),
        }
        for name, geometry in fixtures.items():
            widget = QFrame(self)
            widget.setGeometry(*geometry)
            setattr(self, name, widget)


def test_context_help_is_five_steps_clamped_and_keyboard_operable():
    app = _app()
    host = _OverlayHost()
    overlay = TutorialOverlay(host)
    try:
        host.show()
        for target in (
            host._sidebar,
            host._run_state_frame,
            host.links_text,
            host.start_btn,
            host._settings_tab_bar,
        ):
            target.show()
        overlay.show_overlay()
        app.processEvents()

        assert len(OVERLAY_STEPS) == 5
        for index in range(5):
            overlay._step_index = index
            overlay._update_step()
            app.processEvents()
            card = overlay.tooltip_card.geometry()
            assert overlay.rect().contains(card)
            assert card.width() <= min(340, overlay.width() - 40)
            assert card.height() <= overlay.TOOLTIP_H_MAX

        overlay._step_index = 2
        overlay._update_step()
        overlay.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
        )
        assert overlay._step_index == 1
        overlay.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        )
        assert overlay._step_index == 2
        overlay.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        assert not overlay.isVisible()
    finally:
        host.close()
        host.deleteLater()
        app.processEvents()


def test_update_dialog_exposes_six_states_without_clipping_ctas():
    app = _app()
    info = {
        "version": "4.0.0",
        "size_mb": 112.4,
        "changelog": "작업 흐름과 상태 화면 개선",
    }
    dialog = UpdateDialog("3.1.0", update_info=info)
    try:
        dialog.resize(560, 520)
        dialog.show()
        app.processEvents()

        seen = {dialog.state}
        dialog.set_download_progress(43)
        seen.add(dialog.state)
        assert not dialog.install_btn.isEnabled()
        assert dialog.install_btn.text() == "다운로드 중"
        dialog.set_installing()
        seen.add(dialog.state)
        assert not dialog.install_btn.isEnabled()
        assert dialog.install_btn.text() == "설치 중"
        assert not dialog.close_btn.isEnabled()
        dialog.set_install_error("네트워크 연결을 확인해 주세요.")
        seen.add(dialog.state)
        dialog._on_no_update()
        seen.add(dialog.state)
        dialog.set_checking()
        seen.add(dialog.state)
        assert not dialog.install_btn.isEnabled()
        assert dialog.install_btn.text() == "확인 중"
        app.processEvents()

        assert seen == UpdateDialog.VALID_STATES
        for button in (
            dialog.manual_download_btn,
            dialog.close_btn,
            dialog.install_btn,
        ):
            if button.isVisible():
                assert button.geometry().right() < dialog.width()
                assert button.geometry().bottom() < dialog.height()
                assert button.height() >= 46
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
