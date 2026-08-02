from pathlib import Path


def test_periodic_network_tasks_run_outside_the_qt_event_loop():
    source = (Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert 'name="server-heartbeat-worker"' in source
    assert 'name="update-check-worker"' in source
    assert "def _heartbeat_worker" in source
    assert "def _update_check_worker" in source
    assert "heartbeat_complete = pyqtSignal(object)" in source
    assert "update_check_complete = pyqtSignal(object)" in source


def test_normal_close_quits_but_update_close_preserves_login():
    source = (Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )
    close_event = source[source.index("    def closeEvent(self, event):") :]

    assert "forced_update" in close_event
    assert "if not (forced_relogin or forced_update):" in close_event
    assert "auth_client.logout()" in close_event
    assert "app = QApplication.instance()" in close_event
    assert "app.quit()" in close_event


def test_stale_grok_check_does_not_overwrite_active_oauth_login():
    from src.main_window import MainWindow

    class FakeWindow:
        _grok_status_check_running = True
        _grok_login_running = True

        def _set_grok_buttons_enabled(self, _enabled):
            raise AssertionError("active login controls must remain disabled")

    window = FakeWindow()

    MainWindow._apply_grok_status(
        window,
        "not_logged_in",
        "Grok 로그인이 필요합니다.",
        "check",
    )

    assert window._grok_status_check_running is False
    assert window._grok_login_running is True
