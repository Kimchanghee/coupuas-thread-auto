import json
import queue
import threading
from types import SimpleNamespace

from src.main_window import MainWindow
from src.services.link_history import LinkHistory


class _Emitter:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _Signals:
    def __init__(self):
        self.log = _Emitter()
        self.status = _Emitter()
        self.progress = _Emitter()
        self.results = _Emitter()
        self.finished = _Emitter()
        self.step_update = _Emitter()
        self.link_status = _Emitter()
        self.queue_progress = _Emitter()
        self.reset_steps = _Emitter()
        self.run_state = _Emitter()


class _OneItemQueue:
    def __init__(self, item):
        self._item = item
        self._used = False
        self.empty_reads = 0

    def qsize(self):
        return 0 if self._used else 1

    def get(self, timeout=None):
        if not self._used:
            self._used = True
            return self._item
        self.empty_reads += 1
        raise queue.Empty


class _FakeAgent:
    page = object()

    def __init__(self, *args, **kwargs):
        pass

    def start_browser(self):
        pass

    def save_session(self):
        pass

    def close(self):
        pass


class _FakeHelper:
    def __init__(self, page):
        self.page = page

    def check_login_status(self):
        return True

    def create_thread_direct(self, posts_data):
        raise AssertionError("duplicate links must not reach upload")


class _History:
    def __init__(self):
        self.added = []

    def is_uploaded(self, url):
        return True

    def add_link(self, *args, **kwargs):
        self.added.append((args, kwargs))


class _Pipeline:
    def __init__(self):
        self.link_history = _History()

    def process_link(self, *args, **kwargs):
        raise AssertionError("duplicate links must not be processed")


def test_upload_queue_skips_links_already_in_history(monkeypatch):
    import src.computer_use_agent as computer_use_agent
    import src.threads_playwright_helper as threads_playwright_helper
    import src.main_window as main_window

    monkeypatch.setattr(computer_use_agent, "ComputerUseAgent", _FakeAgent)
    monkeypatch.setattr(threads_playwright_helper, "ThreadsPlaywrightHelper", _FakeHelper)
    monkeypatch.setattr(main_window, "goto_threads_with_fallback", lambda *args, **kwargs: "")
    monkeypatch.setattr(main_window.time, "sleep", lambda *_args, **_kwargs: None)

    signals = _Signals()
    pipeline = _Pipeline()
    fake_self = SimpleNamespace(
        link_queue=_OneItemQueue(("https://link.coupang.com/a/dup", None)),
        _stop_event=threading.Event(),
        signals=signals,
        _log_user_activity=lambda *args, **kwargs: None,
        _is_dev_quota_bypass_enabled=lambda: True,
        _is_work_allowed=MainWindow._is_work_allowed,
        _wait_for_resume_interval_if_needed=lambda log, total_links=None: None,
        _mark_resume_item=lambda *args, **kwargs: None,
        _set_resume_next_allowed_at=lambda *args, **kwargs: None,
    )

    MainWindow._run_upload_queue(fake_self, 30, {"api_key": "", "profile_dir": "test"}, pipeline)

    assert signals.finished.calls
    results = signals.finished.calls[-1][0]
    assert results["skipped"] == 1
    assert results["uploaded"] == 0
    assert results["failed"] == 0
    assert pipeline.link_history.added == []
    assert ("https://link.coupang.com/a/dup", "중복", "이미 업로드됨") in signals.link_status.calls


def test_failed_history_records_do_not_count_as_uploaded(tmp_path):
    history = LinkHistory(str(tmp_path / "uploaded_links.json"))

    history.add_link("https://example.com/product/1?track=failed", "failed attempt", success=False)

    assert not history.is_uploaded("https://example.com/product/1")

    history.add_link("https://example.com/product/1", "successful upload", success=True)

    assert history.is_uploaded("https://example.com/product/1")
    assert not history.is_uploaded("https://example.com/product/1?other=value")
    assert history.get_stats() == {"total": 2, "success": 1, "failed": 1}


def test_validated_api_key_resolution_does_not_fallback_to_failed_key(monkeypatch):
    import src.main_window as main_window

    monkeypatch.setattr(main_window, "select_working_gemini_api_key", lambda validate=True: "")
    monkeypatch.setattr(main_window.config, "get_gemini_api_keys", lambda: ["expired-key-value"], raising=False)
    monkeypatch.setattr(main_window.config, "gemini_api_key", "legacy-expired-key", raising=False)

    assert MainWindow._resolve_runtime_gemini_api_key(object(), validate=True) == ""
    assert MainWindow._resolve_runtime_gemini_api_key(object(), validate=False) == "expired-key-value"
