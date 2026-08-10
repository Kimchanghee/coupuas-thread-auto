import time
import threading
from types import SimpleNamespace

from src.coupang_uploader import CancelledException
from src.services.link_history import LinkHistory
from src.services.multi_account_runtime import MultiAccountRuntime


def test_stop_and_join_confirms_worker_exit():
    runtime = object.__new__(MultiAccountRuntime)
    runtime._lock = threading.RLock()
    stopped = threading.Event()
    worker = threading.Thread(target=stopped.wait, daemon=True)
    runtime._worker_thread = worker
    runtime.stop_all = stopped.set
    worker.start()

    assert runtime.stop_and_join(1) is True
    assert runtime.is_running is False


class FakeConfig:
    def __init__(self, accounts):
        self.accounts = list(accounts)

    def get_threads_accounts(self):
        return list(self.accounts)

    def get_threads_account(self, account_id):
        return next(
            (account for account in self.accounts if account.account_id == account_id),
            None,
        )


class FakePipeline:
    def __init__(self):
        self.calls = []

    def process_link(self, url, user_keywords=None):
        self.calls.append(url)
        return {
            "product_title": url.rsplit("/", 1)[-1],
            "first_post": {"text": "본문"},
            "second_post": {"text": "댓글"},
        }


class BlockingCancelablePipeline(FakePipeline):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release_first = threading.Event()
        self.cancelled = False
        self.reset_count = 0

    def reset_cancel(self):
        self.cancelled = False
        self.reset_count += 1

    def cancel(self):
        self.cancelled = True

    def process_link(self, url, user_keywords=None):
        if url.endswith("/a"):
            self.started.set()
            assert self.release_first.wait(2)
        if self.cancelled:
            raise CancelledException("cancelled")
        return super().process_link(url, user_keywords=user_keywords)


class FakeAgent:
    active = 0
    max_active = 0

    def __init__(self, profile_id):
        self.profile_id = profile_id
        self.page = profile_id

    def start_browser(self):
        type(self).active += 1
        type(self).max_active = max(type(self).max_active, type(self).active)

    def save_session(self):
        return None

    def close(self):
        type(self).active -= 1


class FakeHelper:
    def __init__(self, page, mismatch_profile=""):
        self.page = page
        self.mismatch_profile = mismatch_profile
        self.last_error = ""

    def check_login_status(self):
        return True

    def verify_account(self, _expected_username):
        return self.page != self.mismatch_profile

    def create_thread_direct(self, _payload):
        return True


class FakeQuota:
    def reserve(self):
        return object()

    def commit(self, _reservation):
        return True

    def release(self, _reservation):
        return True


def _account(name):
    return SimpleNamespace(
        account_id=f"id-{name}",
        profile_id=f"profile-{name}",
        expected_username=name,
        upload_interval=30,
    )


def _wait_for_runtime(runtime):
    deadline = time.monotonic() + 3
    while runtime.is_running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not runtime.is_running


def test_runtime_processes_independent_account_queues_with_one_browser(tmp_path):
    FakeAgent.active = 0
    FakeAgent.max_active = 0
    config = FakeConfig([_account("a"), _account("b")])
    pipeline = FakePipeline()
    runtime = MultiAccountRuntime(
        config=config,
        pipeline=pipeline,
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )
    runtime.enqueue("id-a", ["https://example.test/a"])
    runtime.enqueue("id-b", ["https://example.test/b"])

    runtime.start_all()
    _wait_for_runtime(runtime)

    assert runtime.snapshot("id-a")["pending_items"] == []
    assert runtime.snapshot("id-b")["pending_items"] == []
    assert sorted(pipeline.calls) == [
        "https://example.test/a",
        "https://example.test/b",
    ]
    assert FakeAgent.max_active == 1


def test_runtime_blocks_mismatched_account_but_continues_other_queue(tmp_path):
    config = FakeConfig([_account("a"), _account("b")])
    runtime = MultiAccountRuntime(
        config=config,
        pipeline=FakePipeline(),
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(
            page,
            mismatch_profile="profile-a",
        ),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )
    runtime.enqueue("id-a", ["https://example.test/a"])
    runtime.enqueue("id-b", ["https://example.test/b"])

    runtime.start_all()
    _wait_for_runtime(runtime)

    assert len(runtime.snapshot("id-a")["pending_items"]) == 1
    assert runtime.snapshot("id-a")["phase"] == "blocked"
    assert runtime.snapshot("id-b")["pending_items"] == []


def test_runtime_deduplicates_urls_within_an_account(tmp_path):
    config = FakeConfig([_account("a")])
    runtime = MultiAccountRuntime(
        config=config,
        pipeline=FakePipeline(),
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )

    assert runtime.enqueue(
        "id-a",
        [
            "https://example.test/a?tracking=1",
            "https://example.test/a?tracking=2",
        ],
    ) == 2
    assert runtime.enqueue("id-a", ["https://example.test/a?tracking=1"]) == 0
    assert runtime.enqueue("id-a", ["https://example.test/a"]) == 1


def test_runtime_recovers_an_item_left_current_by_a_crashed_process(tmp_path):
    config = FakeConfig([_account("a")])
    runtime = MultiAccountRuntime(
        config=config,
        pipeline=FakePipeline(),
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )
    runtime.enqueue("id-a", ["https://example.test/recover"])
    assert runtime.queue_store("id-a").reserve_next() is not None

    recovered = MultiAccountRuntime(
        config=config,
        pipeline=FakePipeline(),
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )

    state = recovered.snapshot("id-a")
    assert state["current_item"] is None
    assert [item["url"] for item in state["pending_items"]] == [
        "https://example.test/recover"
    ]


def test_stopping_one_account_does_not_cancel_the_next_account(tmp_path):
    config = FakeConfig([_account("a"), _account("b")])
    pipeline = BlockingCancelablePipeline()
    runtime = MultiAccountRuntime(
        config=config,
        pipeline=pipeline,
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )
    runtime.enqueue("id-a", ["https://example.test/a"])
    runtime.enqueue("id-b", ["https://example.test/b"])

    runtime.start_all()
    assert pipeline.started.wait(2)
    runtime.stop_account("id-a")
    pipeline.cancel()
    pipeline.release_first.set()
    _wait_for_runtime(runtime)

    assert [item["url"] for item in runtime.snapshot("id-a")["pending_items"]] == [
        "https://example.test/a"
    ]
    assert runtime.snapshot("id-b")["pending_items"] == []
    assert pipeline.calls == ["https://example.test/b"]
    assert pipeline.reset_count >= 2


def test_migrated_first_account_imports_legacy_success_history(
    monkeypatch,
    tmp_path,
):
    legacy_file = tmp_path / "uploaded_links.json"
    monkeypatch.setattr(LinkHistory, "DEFAULT_HISTORY_FILE", legacy_file)
    legacy = LinkHistory()
    legacy.add_link("https://example.test/already-posted", success=True)
    account = SimpleNamespace(
        account_id="id-legacy",
        profile_id=".threads_profile_legacy",
        expected_username="legacy",
        upload_interval=30,
    )
    config = FakeConfig([account])
    config.active_threads_account_id = account.account_id

    runtime = MultiAccountRuntime(
        config=config,
        pipeline=FakePipeline(),
        queue_root=tmp_path / "queues",
        history_root=tmp_path / "history",
        browser_factory=lambda profile_id: FakeAgent(profile_id),
        helper_factory=lambda page: FakeHelper(page),
        navigator=lambda _page: None,
        quota_adapter=FakeQuota(),
    )

    assert runtime.link_history(account.account_id).is_uploaded(
        "https://example.test/already-posted"
    )
