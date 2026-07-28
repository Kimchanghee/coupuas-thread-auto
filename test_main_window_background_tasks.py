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


def test_normal_main_window_close_ends_the_qt_event_loop():
    source = (Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )
    close_event = source[source.index("    def closeEvent(self, event):") :]

    assert "if not forced_relogin:" in close_event
    assert "app = QApplication.instance()" in close_event
    assert "app.quit()" in close_event
