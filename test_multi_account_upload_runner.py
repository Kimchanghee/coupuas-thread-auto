from types import SimpleNamespace
from unittest.mock import Mock

from src.services.account_queue import AccountQueueStore
from src.services.link_history import LinkHistory
from src.services.managed_ai_client import (
    DEFAULT_MANAGED_AI_URL,
    ManagedAiClient,
    ManagedAiClientError,
)
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
        self.idempotency_keys = []
        self.managed_reservation_id = ""
        self.managed_quota_mode = "reservation"

    def process_link(self, url, user_keywords=None, *, idempotency_key=""):
        self.calls.append((url, user_keywords))
        self.idempotency_keys.append(idempotency_key)
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
    def __init__(self, *, login=True, matches=True, upload=True, on_verify=None):
        self.login = login
        self.matches = matches
        self.upload = upload
        self.on_verify = on_verify
        self.expected = ""
        self.last_error = ""

    def check_login_status(self):
        return self.login

    def verify_account(self, expected_username):
        self.expected = expected_username
        if self.on_verify is not None:
            self.on_verify()
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

    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda _reservation_id: {"success": False, "unsupported": True},
    )
    assert adapter.release(QuotaReservation(reservation_id="r-1")) is False


def test_auth_quota_recovery_returns_fresh_reservation_for_immediate_release(
    monkeypatch,
):
    from src import auth_client

    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda _key: {
            "success": True,
            "allowed": True,
            "reservation_id": "fresh-reconciliation-reservation",
        },
    )

    recovered = AuthQuotaAdapter().recover("durable-key")

    assert recovered == QuotaReservation(
        reservation_id="fresh-reconciliation-reservation"
    )


@pytest.mark.parametrize("reservation_status", ["committed", "released", "unknown"])
def test_auth_quota_recovery_rejects_non_reserved_replay_ids(
    monkeypatch,
    reservation_status,
):
    from src import auth_client

    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda _key: {
            "success": False,
            "code": "IDEMPOTENCY_REPLAY",
            "reservation_status": reservation_status,
            "reservation_id": f"must-not-release-{reservation_status}",
        },
    )

    assert AuthQuotaAdapter().recover("durable-key") is None


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


def test_stop_after_login_releases_managed_reservation_before_requeue(tmp_path):
    helper = FakeHelper()
    runner, queue, _history, pipeline, _events, quota = _build_runner(
        tmp_path,
        helper,
    )
    helper.on_verify = lambda: queue.request_stop(True)
    pipeline.managed_reservation_id = "managed-reservation-stop"
    item = queue.enqueue("https://link.coupang.com/a/managed-stop")

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.processed is False
    assert quota.reserved == 0
    assert quota.released == 1
    assert state["current_item"] is None
    assert state["pending_items"][0]["item_id"] == item["item_id"]
    assert "reservation_id" not in state["pending_items"][0]


def test_failed_managed_release_persists_recovery_metadata(tmp_path):
    helper = FakeHelper()
    quota = FakeQuota(release=False)
    runner, queue, _history, pipeline, _events, _quota = _build_runner(
        tmp_path,
        helper,
        quota,
    )
    helper.on_verify = lambda: queue.request_stop(True)
    pipeline.managed_reservation_id = "managed-reservation-pending"
    item = queue.enqueue("https://link.coupang.com/a/managed-pending")

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == "reservation_release_pending"
    assert state["current_item"]["item_id"] == item["item_id"]
    assert state["current_item"]["stage"] == "reservation_release_pending"
    assert state["current_item"]["reservation_id"] == "managed-reservation-pending"
    assert state["pending_items"] == []
    assert quota.released == 1


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
    assert result.block_reason == "quota_commit_pending"
    assert state["pending_items"] == []
    assert state["current_item"]["stage"] == "posted_commit_pending"
    assert not history.is_uploaded(url)


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


def test_transient_analysis_failure_is_requeued_with_backoff(tmp_path):
    helper = FakeHelper()
    runner, queue, _history, pipeline, events, quota = _build_runner(
        tmp_path,
        helper,
    )
    pipeline.process_link = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        TimeoutError("provider timeout")
    )
    item = queue.enqueue("https://link.coupang.com/a/retry")

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.processed is False
    assert result.pending_count == 1
    assert result.next_allowed_at is not None
    assert state["stats"]["failed"] == 0
    assert state["pending_items"][0]["item_id"] == item["item_id"]
    assert state["pending_items"][0]["retry_count"] == 1
    assert events == []
    assert quota.reserved == 0


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


def test_posting_unknown_posted_resolution_commits_history_then_completes(tmp_path):
    runner, queue, history, _pipeline, _events, quota = _build_runner(
        tmp_path,
        FakeHelper(upload=False),
    )
    url = "https://link.coupang.com/a/confirmed-posted"
    queue.enqueue(url)
    assert runner.process_one("account-a").block_reason == "uncertain_external_post"

    result = runner.resolve_posting_unknown("account-a", "posted")

    state = queue.snapshot()
    assert result.success is True
    assert result.pending_count == 0
    assert state["current_item"] is None
    assert state["stats"]["success"] == 1
    assert history.is_uploaded(url)
    assert quota.committed == 1
    assert quota.released == 0


def test_posting_unknown_not_posted_releases_rotates_key_and_requeues(tmp_path):
    runner, queue, history, _pipeline, _events, quota = _build_runner(
        tmp_path,
        FakeHelper(upload=False),
    )
    url = "https://link.coupang.com/a/confirmed-not-posted"
    original = queue.enqueue(url)
    original_key = original["idempotency_key"]
    assert runner.process_one("account-a").block_reason == "uncertain_external_post"

    result = runner.resolve_posting_unknown("account-a", "not_posted")

    state = queue.snapshot()
    requeued = state["pending_items"][0]
    assert result.processed is False
    assert result.block_reason == ""
    assert state["current_item"] is None
    assert requeued["item_id"] == original["item_id"]
    assert requeued["idempotency_key"] != original_key
    assert "reservation_id" not in requeued
    assert "next_idempotency_key" not in requeued
    assert not history.is_uploaded(url)
    assert quota.released == 1


def test_posting_unknown_later_keeps_durable_block_without_remote_calls(tmp_path):
    runner, queue, _history, _pipeline, _events, quota = _build_runner(
        tmp_path,
        FakeHelper(upload=False),
    )
    queue.enqueue("https://link.coupang.com/a/review-later")
    runner.process_one("account-a")

    result = runner.resolve_posting_unknown("account-a", "later")

    assert result.block_reason == "uncertain_external_post"
    assert queue.snapshot()["current_item"]["stage"] == "posting_unknown"
    assert quota.committed == 0
    assert quota.released == 0


def test_posted_resolution_recovers_history_failure_without_reposting(
    monkeypatch,
    tmp_path,
):
    helper = FakeHelper(upload=False)
    runner, queue, history, pipeline, events, quota = _build_runner(
        tmp_path,
        helper,
    )
    url = "https://link.coupang.com/a/history-recovery"
    queue.enqueue(url)
    runner.process_one("account-a")
    original_save = history._save
    monkeypatch.setattr(
        history,
        "_save",
        lambda: (_ for _ in ()).throw(OSError("history disk full")),
    )

    blocked = runner.resolve_posting_unknown("account-a", "posted")

    assert blocked.block_reason == "history_write_pending"
    assert queue.snapshot()["current_item"]["stage"] == "history_write_pending"
    assert not history.is_uploaded(url)
    assert quota.committed == 1

    monkeypatch.setattr(history, "_save", original_save)
    recovered = runner.process_one("account-a")

    assert recovered.success is True
    assert history.is_uploaded(url)
    assert queue.snapshot()["current_item"] is None
    assert quota.committed == 1
    assert pipeline.calls == [(url, None)]
    assert len([event for event in events if event[0] == "browser"]) == 1


def test_posted_resolution_recovers_queue_completion_failure_without_reposting(
    monkeypatch,
    tmp_path,
):
    runner, queue, history, pipeline, events, quota = _build_runner(
        tmp_path,
        FakeHelper(upload=False),
    )
    url = "https://link.coupang.com/a/completion-recovery"
    queue.enqueue(url)
    runner.process_one("account-a")
    original_complete = queue.complete_current
    monkeypatch.setattr(
        queue,
        "complete_current",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("queue disk full")),
    )

    blocked = runner.resolve_posting_unknown("account-a", "posted")

    assert blocked.block_reason == "history_write_pending"
    assert queue.snapshot()["current_item"]["stage"] == "history_write_pending"
    assert history.is_uploaded(url)
    assert quota.committed == 1

    monkeypatch.setattr(queue, "complete_current", original_complete)
    recovered = runner.process_one("account-a")

    assert recovered.success is True
    assert queue.snapshot()["current_item"] is None
    assert quota.committed == 1
    assert pipeline.calls == [(url, None)]
    assert len([event for event in events if event[0] == "browser"]) == 1


def test_not_posted_resolution_retries_failed_release_with_same_next_key(
    tmp_path,
):
    quota = FakeQuota(release=False)
    runner, queue, history, _pipeline, _events, _quota = _build_runner(
        tmp_path,
        FakeHelper(upload=False),
        quota,
    )
    url = "https://link.coupang.com/a/release-recovery"
    queue.enqueue(url)
    runner.process_one("account-a")

    blocked = runner.resolve_posting_unknown("account-a", "not_posted")
    pending_item = queue.snapshot()["current_item"]
    next_key = pending_item["next_idempotency_key"]
    assert blocked.block_reason == "reservation_release_pending"

    quota.release_result = True
    recovery = runner._recover_interrupted_current(
        queue,
        history,
        queue.snapshot()["current_item"],
    )

    assert recovery is None
    requeued = queue.snapshot()["pending_items"][0]
    assert requeued["idempotency_key"] == next_key
    assert quota.released == 2


def test_transient_generation_retry_reuses_persisted_queue_key(tmp_path):
    runner, queue, _history, pipeline, _events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
    )
    url = "https://link.coupang.com/a/stable-generation"
    item = queue.enqueue(url)
    original_process = pipeline.process_link
    attempts = []

    def flaky_process(link, user_keywords=None, *, idempotency_key=""):
        attempts.append(idempotency_key)
        if len(attempts) == 1:
            raise TimeoutError("temporary provider timeout")
        return original_process(
            link,
            user_keywords=user_keywords,
            idempotency_key=idempotency_key,
        )

    pipeline.process_link = flaky_process

    assert runner.process_one("account-a").processed is False
    assert runner.process_one("account-a").success is True

    assert attempts == [item["idempotency_key"], item["idempotency_key"]]


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("AI_TEMPORARILY_UNAVAILABLE", 503),
        ("INVALID_SERVER_RESPONSE", 200),
        ("MANAGED_AI_POSTPROCESSING_FAILED", 0),
    ],
)
def test_managed_ai_reservation_error_persists_release_then_rotates_requeue_key(
    tmp_path,
    code,
    status_code,
):
    quota = FakeQuota(release=False)
    runner, queue, history, pipeline, events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )
    pipeline.process_link = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        ManagedAiClientError(
            code,
            "안전한 재시도가 필요합니다.",
            status_code=status_code,
            reservation_release_pending=True,
            reservation_id="managed-reservation-error",
            ai_job_id="managed-job-error",
        )
    )
    original = queue.enqueue("https://link.coupang.com/a/managed-error")

    blocked = runner.process_one("account-a")

    persisted = queue.snapshot()["current_item"]
    assert blocked.block_reason == "reservation_release_pending"
    assert persisted["stage"] == "reservation_release_pending"
    assert persisted["reservation_id"] == "managed-reservation-error"
    assert persisted["ai_job_id"] == "managed-job-error"
    assert persisted["idempotency_key"] == original["idempotency_key"]
    assert events == []

    quota.release_result = True
    recovery = runner._recover_interrupted_current(queue, history, persisted)

    assert recovery is None
    requeued = queue.snapshot()["pending_items"][0]
    assert requeued["idempotency_key"] != original["idempotency_key"]
    assert "reservation_id" not in requeued
    assert "ai_job_id" not in requeued
    assert quota.released == 2


def test_managed_ai_reconciliation_stops_after_fourth_failed_generation(tmp_path):
    quota = FakeQuota(release=True)
    runner, queue, _history, pipeline, events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )
    calls = []

    def fail_with_reservation(*_args, idempotency_key="", **_kwargs):
        calls.append(idempotency_key)
        raise ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "안전한 재시도가 필요합니다.",
            status_code=503,
            reservation_release_pending=True,
            reservation_id=f"managed-reservation-{len(calls)}",
        )

    pipeline.process_link = fail_with_reservation
    queue.enqueue("https://link.coupang.com/a/managed-retry-ceiling")

    results = [runner.process_one("account-a") for _ in range(4)]
    after_exhaustion = runner.process_one("account-a")

    assert len(calls) == 4
    assert len(set(calls)) == 4
    assert quota.released == 4
    assert results[-1].processed is True
    assert queue.snapshot()["current_item"] is None
    assert queue.snapshot()["pending_items"] == []
    assert after_exhaustion.processed is False
    assert events == []


def test_released_replay_rotates_keys_and_stops_after_fourth_retry(tmp_path):
    quota = FakeQuota(release=True)
    runner, queue, _history, pipeline, events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )
    calls = []

    def fail_with_released_replay(*_args, idempotency_key="", **_kwargs):
        calls.append(idempotency_key)
        raise ManagedAiClientError(
            "DUPLICATE_REQUEST",
            "새 요청 키로 다시 시도해주세요.",
            status_code=409,
            retry_with_new_idempotency_key=True,
            ai_job_id=idempotency_key,
        )

    pipeline.process_link = fail_with_released_replay
    queue.enqueue("https://link.coupang.com/a/released-replay-retry")

    results = [runner.process_one("account-a") for _ in range(4)]
    after_exhaustion = runner.process_one("account-a")

    assert len(calls) == 4
    assert len(set(calls)) == 4
    assert quota.released == 0
    assert results[-1].processed is True
    assert queue.snapshot()["current_item"] is None
    assert queue.snapshot()["pending_items"] == []
    assert after_exhaustion.processed is False
    assert events == []


def test_lost_success_response_replay_rotates_key_then_generation_succeeds(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        ManagedAiClient,
        "_auth_state",
        staticmethod(lambda: {"token": "token", "user_id": "42"}),
    )
    replay_response = Mock(ok=False, status_code=409)
    replay_response.json.return_value = {
        "success": False,
        "code": "DUPLICATE_REQUEST",
        "message": "새 요청 키로 다시 시도해주세요.",
        "retry_with_new_idempotency_key": True,
        "ai_job_id": "lost-response-key",
    }
    success_response = Mock(ok=True, status_code=200)
    success_response.json.return_value = {
        "success": True,
        "ai_job_id": "replacement-key",
        "reservation_id": "replacement-reservation",
        "quota_mode": "reservation",
        "variants": [
            {
                "variant_id": variant_id,
                "root_text": f"{variant_id} 첫 글",
                "product_comment_text": "상품 댓글",
            }
            for variant_id in (
                "target_direct",
                "convenience_contrast",
                "fun_reveal",
                "use_scene_story",
            )
        ],
    }
    session = Mock(post=Mock(side_effect=[replay_response, success_response]))
    client = ManagedAiClient(DEFAULT_MANAGED_AI_URL, session=session)
    quota = FakeQuota(release=True)
    runner, queue, _history, pipeline, events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )

    def managed_process(url, user_keywords=None, *, idempotency_key=""):
        del user_keywords
        generation = client.generate_variants(
            {"title": "상품", "original_url": url},
            idempotency_key=idempotency_key,
        )
        variant = generation.variants[0]
        return {
            "product_title": "상품",
            "first_post": {"text": variant.root_text},
            "second_post": {"text": variant.product_comment_text},
            "managed_ai_reservation_id": generation.reservation_id,
            "managed_ai_quota_mode": generation.quota_mode,
            "managed_ai_job_id": generation.ai_job_id,
        }

    pipeline.process_link = managed_process
    queued = queue.enqueue("https://link.coupang.com/a/lost-response-replay")

    first = runner.process_one("account-a")
    second = runner.process_one("account-a")

    request_keys = [
        call.kwargs["headers"]["Idempotency-Key"]
        for call in session.post.call_args_list
    ]
    assert first.processed is False
    assert second.success is True
    assert request_keys[0] == queued["idempotency_key"]
    assert request_keys[1] != request_keys[0]
    assert quota.released == 0
    assert quota.committed == 1
    assert events == [
        ("browser", "profile-a"),
        ("save", "profile-a"),
        ("close", "profile-a"),
    ]


def test_managed_ai_missing_reservation_uses_safe_idempotency_replay_recovery(
    tmp_path,
):
    class ReplayQuota(FakeQuota):
        def __init__(self):
            super().__init__(release=True)
            self.recovered_keys = []

        def recover(self, idempotency_key):
            self.recovered_keys.append(idempotency_key)
            return QuotaReservation(reservation_id="replayed-reservation")

    quota = ReplayQuota()
    runner, queue, _history, pipeline, events, _quota = _build_runner(
        tmp_path,
        FakeHelper(),
        quota,
    )
    pipeline.process_link = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "안전한 재시도가 필요합니다.",
            status_code=503,
            reservation_release_pending=True,
            ai_job_id="managed-job-replay",
        )
    )
    original = queue.enqueue("https://link.coupang.com/a/managed-replay")

    result = runner.process_one("account-a")

    state = queue.snapshot()
    assert result.block_reason == ""
    assert state["current_item"] is None
    assert state["pending_items"][0]["idempotency_key"] != original["idempotency_key"]
    assert quota.recovered_keys == [original["idempotency_key"]]
    assert quota.released == 1
    assert events == []
