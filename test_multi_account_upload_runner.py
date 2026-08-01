from types import SimpleNamespace

from src.services.account_queue import AccountQueueStore
from src.services.link_history import LinkHistory
from src.services.multi_account_upload_runner import (
    AccountBlockedError,
    AuthQuotaAdapter,
    MultiAccountUploadRunner,
    QuotaReservation,
)
import pytest


class FakePipeline:
    def __init__(self):
        self.calls = []
        self.managed_reservation_id = ""
        self.managed_quota_mode = "reservation"

    def process_link(self, url, user_keywords=None):
        self.calls.append((url, user_keywords))
        result = {
            "product_title": "테스트 상품",
            "first_post": {"text": "첫 게시글"},
            "second_post": {"text": "두 번째 게시글"},
        }
        if self.managed_reservation_id:
            result["managed_ai_reservation_id"] = self.managed_reservation_id
            result["managed_ai_quota_mode"] = self.managed_quota_mode
        return result


class FakeAgent:
    def __init__(self, profile_id, events):
        self.profile_id = profile_id
        self.events = events
        self.page = object()

    def start_browser(self):
        self.events.append(("browser", self.profile_id))

    def save_session(self):
        self.events.append(("save", self.profile_id))

    def close(self):
        self.events.append(("close", self.profile_id))


class FakeHelper:
    def __init__(self, *, login=True, matches=True, upload=True):
        self.login = login
        self.matches = matches
        self.upload = upload
        self.expected = ""
        self.last_error = ""

    def check_login_status(self):
        return self.login

    def verify_account(self, expected_username):
        self.expected = expected_username
        return self.matches

    def create_thread_direct(self, _payload):
        return self.upload


class FakeQuota:
    def __init__(self, commit=True, release=True):
        self.commit_result = commit
        self.release_result = release
        self.reserved = 0
        self.committed = 0
        self.released = 0

    def reserve(self):
        self.reserved += 1
        return QuotaReservation(reservation_id=f"reservation-{self.reserved}")

    def commit(self, _reservation):
        self.committed += 1
        return self.commit_result

    def release(self, _reservation):
        self.released += 1
        return self.release_result


def test_auth_quota_adapter_passes_stable_key_and_fails_closed(monkeypatch):
    from src import auth_client

    monkeypatch.delenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", raising=False)
    captured = []
    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda key: captured.append(key) or {"success": True, "reservation_id": "r-1"},
    )
    adapter = AuthQuotaAdapter()
    assert adapter.reserve("queue-key").reservation_id == "r-1"
    assert captured == ["queue-key"]

    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda _key: {"success": False, "unsupported": True},
    )
    with pytest.raises(AccountBlockedError, match="안전한 작업 예약"):
        adapter.reserve("queue-key")


def _build_runner(tmp_path, helper, quota=None):
    account = SimpleNamespace(
        account_id="account-a",
        profile_id="profile-a",
        expected_username="expected_user",
    )
    queue = AccountQueueStore("account-a", tmp_path / "queues")
    history = LinkHistory(
        account_id="account-a",
        history_root=str(tmp_path / "history"),
    )
    pipeline = FakePipeline()
    events = []
    quota = quota or FakeQuota()
    runner = MultiAccountUploadRunner(
        account_resolver=lambda _account_id: account,
        queue_resolver=lambda _account_id: queue,
        history_resolver=lambda _account_id: history,
        pipeline=pipeline,
        browser_factory=lambda profile_id: FakeAgent(profile_id, events),
        helper_factory=lambda _page: helper,
        navigator=lambda _page: None,
        quota_adapter=quota,
    )
    return runner, queue, history, pipeline, events, quota


def test_runner_uses_expected_account_profile_and_completes_queue(tmp_path):
    helper = FakeHelper()
    runner, queue, history, pipeline, events, quota = _build_runner(
        tmp_path,
        helper,
    )
    queue.enqueue("https://link.coupang.com/a/test", keyword="키워드")

    result = runner.process_one("account-a")

    assert result.success
    assert result.pending_count == 0
    assert helper.expected == "expected_user"
    assert pipeline.calls == [
        ("https://link.coupang.com/a/test", "키워드"),
    ]
    assert history.is_uploaded("https://link.coupang.com/a/test")
    assert events == [
        ("browser", "profile-a"),
        ("save", "profile-a"),
        ("close", "profile-a"),
    ]
    assert quota.reserved == quota.committed == 1


def test_runner_reuses_managed_ai_reservation_without_double_reserving(tmp_path):
    helper = FakeHelper()
    runner, queue, _history, pipeline, _events, quota = _build_runner(
        tmp_path,
        helper,
    )
    pipeline.managed_reservation_id = "managed-reservation-1"
    queue.enqueue("https://link.coupang.com/a/managed")

    result = runner.process_one("account-a")

    assert result.success
    assert quota.reserved == 0
    assert quota.committed == 1


def test_account_mismatch_requeues_item_and_blocks_only_that_account(tmp_path):
    helper = FakeHelper(matches=False)
    runner, queue, history, _pipeline, _events, quota = _build_runner(
        tmp_path,
        helper,
    )
    item = queue.enqueue("https://link.coupang.com/a/test")

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == "account_mismatch"
    assert state["phase"] == "blocked"
    assert state["pending_items"][0]["item_id"] == item["item_id"]
    assert not history.is_uploaded(item["url"])
    assert quota.reserved == 0


def test_duplicate_is_skipped_without_opening_browser(tmp_path):
    helper = FakeHelper()
    runner, queue, history, _pipeline, events, quota = _build_runner(
        tmp_path,
        helper,
    )
    url = "https://link.coupang.com/a/test"
    history.add_link(url, "기존 상품", success=True)
    queue.enqueue(url)

    result = runner.process_one("account-a")

    assert result.success
    assert events == []
    assert queue.snapshot()["stats"]["skipped"] == 1
    assert quota.reserved == 0


def test_quota_commit_failure_does_not_requeue_already_published_item(tmp_path):
    helper = FakeHelper()
    quota = FakeQuota(commit=False)
    runner, queue, history, _pipeline, _events, _quota = _build_runner(
        tmp_path,
        helper,
        quota,
    )
    url = "https://link.coupang.com/a/test"
    queue.enqueue(url)

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == "quota_commit_failed"
    assert state["pending_items"] == []
    assert state["current_item"]["stage"] == "posted_commit_pending"
    assert history.is_uploaded(url)


def test_uncertain_post_is_blocked_instead_of_requeued(tmp_path):
    helper = FakeHelper(upload=False)
    runner, queue, history, _pipeline, _events, quota = _build_runner(
        tmp_path,
        helper,
    )
    url = "https://link.coupang.com/a/test"
    queue.enqueue(url)

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == "uncertain_external_post"
    assert state["pending_items"] == []
    assert state["current_item"]["stage"] == "posting_unknown"
    assert not history.is_uploaded(url)
    assert quota.released == 0


def test_failed_reservation_release_stays_blocked_without_new_reservation(
    tmp_path,
):
    quota = FakeQuota(release=False)
    runner, queue, _history, pipeline, _events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )
    item = queue.enqueue("https://link.coupang.com/a/test")
    queue.reserve_next()
    queue.update_current(
        stage="reserved",
        reservation_id="existing-reservation",
    )

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == "reservation_release_pending"
    assert state["current_item"]["item_id"] == item["item_id"]
    assert state["current_item"]["reservation_id"] == "existing-reservation"
    assert state["current_item"]["stage"] == "reservation_release_pending"
    assert state["pending_items"] == []
    assert quota.released == 1
    assert quota.reserved == 0
    assert pipeline.calls == []
