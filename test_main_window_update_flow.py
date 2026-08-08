from src import main_window
from src.update_resume import UpdateResumeStore


class _Button:
    def __init__(self):
        self.enabled = True
        self.visible = False
        self.text = ""

    def setEnabled(self, value):
        self.enabled = bool(value)

    def setVisible(self, value):
        self.visible = bool(value)

    def setText(self, value):
        self.text = str(value)


def test_background_update_check_only_offers_update_until_user_clicks():
    class FakeWindow:
        _closed = False
        _update_check_in_flight = True
        _update_installing = False
        _update_notice_version = None
        _pending_update_info = None
        update_btn = _Button()

        def _relayout_header_account_card(self):
            pass

        def _has_active_update_work(self):
            return False

        def _run_auto_update_flow(self, *_args, **_kwargs):
            raise AssertionError("background checks must not start installation")

        def _maybe_show_update_notice(self):
            self.notice_offered = True

    window = FakeWindow()
    main_window.MainWindow._apply_update_check_result(
        window,
        {"update_info": {"version": "3.1.0", "download_url": "https://example.test"}},
    )

    assert window._update_check_in_flight is False
    assert window._pending_update_info["version"] == "3.1.0"
    assert window.update_btn.visible is True
    assert window.update_btn.enabled is True
    assert window.update_btn.text.endswith("3.1.0")
    assert window.notice_offered is True


def test_update_notice_is_deferred_during_work_and_shown_once_when_idle():
    shown = []

    class FakeWindow:
        _pending_update_info = {"version": "3.1.0"}
        _update_notice_version = ""

        def _has_active_update_work(self):
            return self.active

        def _show_update_dialog(self, update_info):
            shown.append(update_info["version"])

    window = FakeWindow()
    window.active = True
    main_window.MainWindow._maybe_show_update_notice(window)
    assert shown == []
    assert window._update_notice_version == ""

    window.active = False
    main_window.MainWindow._maybe_show_update_notice(window)
    main_window.MainWindow._maybe_show_update_notice(window)
    assert shown == ["3.1.0"]
    assert window._update_notice_version == "3.1.0"


def test_always_on_update_check_has_a_periodic_timer():
    source = (main_window.Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert "UPDATE_CHECK_INTERVAL_MS" in source
    assert "self._update_timer.timeout.connect(self._check_for_updates_silent)" in source
    assert "self._update_timer.start(UPDATE_CHECK_INTERVAL_MS)" in source


def test_update_does_not_start_when_resume_state_cannot_be_saved(monkeypatch, tmp_path):
    errors = []

    class FakeWindow:
        _update_installing = False
        update_btn = _Button()
        _update_resume_store = UpdateResumeStore(tmp_path / "missing.json")

        def _prepare_update_resume(self, _update_info):
            raise OSError("disk unavailable")

        def _resume_update_work(self, _marker):
            raise AssertionError("no marker should exist")

    monkeypatch.setattr(main_window, "show_error", lambda *args: errors.append(args))
    window = FakeWindow()
    main_window.MainWindow._run_auto_update_flow(
        window,
        {"version": "3.1.0"},
        resume_after=True,
    )

    assert window._update_installing is False
    assert window.update_btn.enabled is True
    assert errors and errors[0][1] == "업데이트 준비 실패"


def test_failed_resume_keeps_marker_for_next_start(monkeypatch, tmp_path):
    warnings = []
    store = UpdateResumeStore(tmp_path / "update_resume.json")
    marker = store.save("v3.1.0", ["account-1"])

    class BrokenRuntime:
        def refresh_accounts(self):
            raise RuntimeError("runtime unavailable")

    class FakeWindow:
        _update_resume_store = store
        _multi_account_runtime = BrokenRuntime()

    monkeypatch.setattr(main_window, "show_warning", lambda *args: warnings.append(args))
    window = FakeWindow()
    resumed = main_window.MainWindow._resume_update_work(window, marker)

    assert resumed is False
    assert store.load() is not None
    assert warnings and warnings[0][1] == "작업 재개 확인"


def test_empty_resume_marker_is_consumed(monkeypatch, tmp_path):
    store = UpdateResumeStore(tmp_path / "update_resume.json")
    marker = store.save("v3.1.0", [])

    class FakeWindow:
        _update_resume_store = store
        _multi_account_runtime = None

    window = FakeWindow()
    assert main_window.MainWindow._resume_update_work(window, marker) is True
    assert store.load() is None


def test_resume_waits_for_previous_runtime_worker(monkeypatch):
    callbacks = []

    class Runtime:
        is_running = True

    class FakeWindow:
        _multi_account_runtime = Runtime()

        def __init__(self):
            self.resumed = []

        def _resume_update_work(self, marker):
            self.resumed.append(marker)
            return True

        def _resume_update_work_when_ready(self, marker, retries=120):
            return main_window.MainWindow._resume_update_work_when_ready(
                self, marker, retries
            )

    monkeypatch.setattr(
        main_window.QTimer,
        "singleShot",
        lambda _delay, callback: callbacks.append(callback),
    )
    window = FakeWindow()
    marker = {"account_ids": ["account-1"]}

    assert window._resume_update_work_when_ready(marker) is False
    assert window.resumed == []
    assert len(callbacks) == 1

    window._multi_account_runtime.is_running = False
    callbacks.pop()()
    assert window.resumed == [marker]
