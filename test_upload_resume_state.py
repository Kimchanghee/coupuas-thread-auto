import json
import queue
import threading
from types import SimpleNamespace

import pytest

import src.main_window as main_window
from src.main_window import MainWindow, ResumeStatePersistenceError
from src.services.managed_ai_client import ManagedAiClientError


def _make_resume_fake(tmp_path):
    fake = SimpleNamespace(
        _resume_state_path=tmp_path / "upload_resume_queue.json",
        _resume_state_lock=threading.RLock(),
        _resume_items=[],
        _resume_interval=60,
        _resume_next_allowed_at=None,
        _resume_recovered_idempotency_keys={},
    )
    for name in (
        "_normalize_link_data",
        "_save_resume_state",
        "_initialize_resume_state",
        "_mark_resume_item",
        "_resume_item_idempotency_key",
        "_set_resume_next_allowed_at",
        "_resume_pending_link_data",
        "_load_resume_state_file",
        "_archive_legacy_resume_state",
        "_ask_ambiguous_post_result",
        "_reconcile_ambiguous_post_items",
        "_reconcile_history_write_items",
        "_reconcile_reservation_release_items",
        "_handle_managed_ai_reconciliation_error",
    ):
        setattr(fake, name, getattr(MainWindow, name).__get__(fake, type(fake)))
    fake._reserved_replay_id = MainWindow._reserved_replay_id
    fake._is_resume_unfinished = MainWindow._is_resume_unfinished
    fake._is_work_allowed = MainWindow._is_work_allowed
    return fake


class _Emitter:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values)


class _Button:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


def test_resume_state_persists_only_unfinished_items(tmp_path):
    fake = _make_resume_fake(tmp_path)

    fake._initialize_resume_state(
        [
            ("https://link.coupang.com/a/item1", "summer fan"),
            ("https://link.coupang.com/a/item2", "cool mat"),
        ],
        14400,
        source="test",
    )
    fake._mark_resume_item("https://link.coupang.com/a/item1", "completed", "done")
    fake._mark_resume_item("https://link.coupang.com/a/item2", "running", "active")
    fake._set_resume_next_allowed_at(12345.0)

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["interval"] == 14400
    assert payload["next_allowed_at"] == 12345.0
    assert fake._resume_pending_link_data(payload) == [
        ("https://link.coupang.com/a/item2", "cool mat")
    ]

    fake._mark_resume_item("https://link.coupang.com/a/item2", "failed", "active")
    assert not fake._resume_state_path.exists()


def test_resume_items_receive_and_reuse_generation_idempotency_keys(tmp_path):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/idempotent-generation"
    fake._initialize_resume_state([(url, "item")], 60, source="test")

    first = fake._resume_item_idempotency_key(url)
    persisted = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    second = fake._resume_item_idempotency_key(url)

    assert first
    assert second == first
    assert persisted["items"][0]["idempotency_key"] == first


@pytest.mark.parametrize("failure_point", ["write", "replace"])
def test_resume_state_save_failure_is_observable_and_preserves_previous_file(
    monkeypatch,
    tmp_path,
    failure_point,
):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/atomic-resume"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    previous_bytes = fake._resume_state_path.read_bytes()
    fake._resume_items[0]["status"] = "running"

    if failure_point == "write":
        monkeypatch.setattr(
            main_window.json,
            "dump",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("write failed")),
        )
    else:
        monkeypatch.setattr(
            main_window.os,
            "replace",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("replace failed")),
        )

    with pytest.raises(RuntimeError, match="업로드 대기열"):
        fake._save_resume_state("failure_injection")

    assert fake._resume_state_path.read_bytes() == previous_bytes
    assert list(tmp_path.glob("upload_resume_queue_*.tmp")) == []


def test_idempotency_key_save_failure_rolls_back_and_prevents_ai_call(
    monkeypatch,
    tmp_path,
):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/idempotency-disk-failure"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    fake._resume_items[0].pop("idempotency_key", None)
    fake._resume_recovered_idempotency_keys.clear()
    fake._save_resume_state("remove_key_for_test")
    previous_bytes = fake._resume_state_path.read_bytes()
    ai_calls = []
    monkeypatch.setattr(
        main_window.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("replace failed")),
    )

    with pytest.raises(RuntimeError, match="업로드 대기열"):
        ai_calls.append(fake._resume_item_idempotency_key(url))

    assert ai_calls == []
    assert "idempotency_key" not in fake._resume_items[0]
    assert fake._resume_recovered_idempotency_keys == {}
    assert fake._resume_state_path.read_bytes() == previous_bytes


def test_posting_stage_save_failure_rolls_back_before_external_post(
    monkeypatch,
    tmp_path,
):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/posting-disk-failure"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    previous_bytes = fake._resume_state_path.read_bytes()
    post_calls = []
    monkeypatch.setattr(
        main_window.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("replace failed")),
    )

    with pytest.raises(RuntimeError, match="업로드 대기열"):
        fake._mark_resume_item(url, "posting", "item")
        post_calls.append("external-post")

    assert post_calls == []
    assert fake._resume_items[0]["status"] == "pending"
    assert fake._resume_state_path.read_bytes() == previous_bytes


def test_legacy_resume_file_is_archived_after_account_import(tmp_path):
    fake = _make_resume_fake(tmp_path)
    fake._resume_state_path.write_text('{"items":[]}', encoding="utf-8")

    fake._archive_legacy_resume_state()

    assert not fake._resume_state_path.exists()
    assert (
        tmp_path / "upload_resume_queue.migrated.json"
    ).read_text(encoding="utf-8") == '{"items":[]}'


def test_posted_commit_pending_is_persisted_but_never_reuploaded(tmp_path):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item1"
    fake._initialize_resume_state([(url, "item")], 60, source="test")

    fake._mark_resume_item(
        url,
        "posted_commit_pending",
        "posted item",
        reservation_id="reservation-1",
        idempotency_key="request-1",
    )

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["reservation_id"] == "reservation-1"
    assert fake._resume_pending_link_data(payload) == []


def test_ambiguous_posting_state_is_persisted_but_never_reuploaded(tmp_path):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item2"
    fake._initialize_resume_state([(url, "item")], 60, source="test")

    fake._mark_resume_item(
        url,
        "posting_unknown",
        "possibly posted item",
        reservation_id="reservation-2",
        idempotency_key="request-2",
    )

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["status"] == "posting_unknown"
    assert fake._resume_pending_link_data(payload) == []


def test_confirmed_not_posted_releases_and_rotates_idempotency_key(tmp_path, monkeypatch):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item3"
    state = {
        "interval": 60,
        "items": [
            {
                "url": url,
                "status": "posting_unknown",
                "reservation_id": "reservation-3",
                "idempotency_key": "old-request-key",
            }
        ],
    }
    fake._resume_items = [dict(state["items"][0])]
    fake._ask_ambiguous_post_result = lambda _title: "not_posted"
    released = []
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    fake._reconcile_ambiguous_post_items(state)

    assert released == ["reservation-3"]
    assert state["items"][0]["status"] == "pending"
    assert "reservation_id" not in state["items"][0]
    assert "idempotency_key" not in state["items"][0]


def test_history_write_pending_recovers_without_returning_item_to_upload(tmp_path):
    fake = _make_resume_fake(tmp_path)
    recorded = []
    fake.pipeline = SimpleNamespace(
        link_history=SimpleNamespace(
            add_link=lambda *args, **kwargs: recorded.append((args, kwargs))
        )
    )
    url = "https://link.coupang.com/a/history-pending"
    state = {
        "interval": 60,
        "items": [
            {
                "url": url,
                "product_title": "게시된 상품",
                "status": "history_write_pending",
                "idempotency_key": "stable-key",
            }
        ],
    }

    fake._reconcile_history_write_items(state)

    assert recorded == [((url, "게시된 상품"), {"success": True})]
    assert state["items"][0]["status"] == "completed"
    assert fake._resume_pending_link_data(state) == []
    assert not fake._resume_state_path.exists()


def test_legacy_managed_ai_error_persists_release_before_rotating_key(
    monkeypatch,
    tmp_path,
):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/legacy-managed-error"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    original_key = fake._resume_items[0]["idempotency_key"]
    observed = []

    def release(reservation_id):
        payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
        observed.append((reservation_id, payload["items"][0].copy()))
        return {"success": True}

    monkeypatch.setattr(auth_client, "release_reserved_work", release)
    outcome = fake._handle_managed_ai_reconciliation_error(
        url,
        "상품",
        ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "잠시 후 다시 시도해주세요.",
            status_code=503,
            reservation_release_pending=True,
            reservation_id="legacy-reservation-1",
            ai_job_id="legacy-job-1",
        ),
    )

    assert outcome == "requeued"
    assert observed[0][0] == "legacy-reservation-1"
    assert observed[0][1]["status"] == "reservation_release_pending"
    assert observed[0][1]["reservation_id"] == "legacy-reservation-1"
    item = fake._resume_items[0]
    assert item["status"] == "pending"
    assert item["idempotency_key"] != original_key
    assert "reservation_id" not in item
    assert "ai_job_id" not in item


def test_legacy_release_pending_restart_recovers_and_rotates_key(
    monkeypatch,
    tmp_path,
):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/legacy-release-restart"
    state = {
        "interval": 60,
        "items": [
            {
                "url": url,
                "status": "reservation_release_pending",
                "reservation_id": "legacy-reservation-restart",
                "ai_job_id": "legacy-job-restart",
                "idempotency_key": "old-key",
            }
        ],
    }
    released = []
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    recovered = fake._reconcile_reservation_release_items(state)

    item = recovered["items"][0]
    assert released == ["legacy-reservation-restart"]
    assert item["status"] == "pending"
    assert item["idempotency_key"] != "old-key"
    assert "reservation_id" not in item
    assert fake._resume_pending_link_data(recovered) == [(url, None)]


def test_legacy_missing_reservation_uses_exact_replay_before_release(
    monkeypatch,
    tmp_path,
):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/legacy-replay"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    original_key = fake._resume_items[0]["idempotency_key"]
    replayed = []
    released = []
    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda key: replayed.append(key)
        or {
            "success": True,
            "allowed": True,
            "code": "IDEMPOTENCY_REPLAY",
            "reservation_status": "reserved",
            "reservation_id": "legacy-replayed-reservation",
        },
    )
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    outcome = fake._handle_managed_ai_reconciliation_error(
        url,
        "상품",
        ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "잠시 후 다시 시도해주세요.",
            status_code=503,
            reservation_release_pending=True,
            ai_job_id="legacy-job-replay",
        ),
    )

    assert outcome == "requeued"
    assert replayed == [original_key]
    assert released == ["legacy-replayed-reservation"]
    assert fake._resume_items[0]["idempotency_key"] != original_key


def test_legacy_missing_reservation_releases_fresh_reconciliation_reservation(
    monkeypatch,
    tmp_path,
):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/legacy-fresh-reconciliation"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    original_key = fake._resume_items[0]["idempotency_key"]
    queried = []
    released = []
    monkeypatch.setattr(
        auth_client,
        "reserve_work",
        lambda key: queried.append(key)
        or {
            "success": True,
            "allowed": True,
            "reservation_id": "legacy-fresh-reservation",
        },
    )
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    outcome = fake._handle_managed_ai_reconciliation_error(
        url,
        "상품",
        ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "응답 전달 여부를 확인할 수 없습니다.",
            reservation_release_pending=True,
            ai_job_id=original_key,
        ),
    )

    assert outcome == "requeued"
    assert queried == [original_key]
    assert released == ["legacy-fresh-reservation"]
    assert fake._resume_items[0]["idempotency_key"] != original_key


@pytest.mark.parametrize("reservation_status", ["committed", "released", "unknown"])
def test_legacy_recovery_never_releases_non_reserved_replay(
    monkeypatch,
    tmp_path,
    reservation_status,
):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/non-reserved-replay"
    fake._initialize_resume_state([(url, "item")], 60, source="test")
    released = []
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
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    outcome = fake._handle_managed_ai_reconciliation_error(
        url,
        "상품",
        ManagedAiClientError(
            "AI_TEMPORARILY_UNAVAILABLE",
            "응답 결과를 확인할 수 없습니다.",
            reservation_release_pending=True,
        ),
    )

    assert outcome == "blocked"
    assert released == []


def test_start_queue_persistence_failure_is_reported_without_starting(monkeypatch):
    errors = []
    starts = []
    account = SimpleNamespace(account_id="account-a", expected_username="tester")
    runtime = SimpleNamespace(
        refresh_accounts=lambda: None,
        enqueue=lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
        start_account=lambda account_id: starts.append(account_id),
    )
    window = SimpleNamespace(
        selected_threads_account=lambda: account,
        _ensure_threads_account_allowed=lambda *_args: True,
        _multi_account_runtime=runtime,
        _configure_multi_account_pipeline=lambda *_args: None,
        _init_multi_account_runtime=lambda: None,
        is_running=False,
    )
    monkeypatch.setattr(main_window, "show_error", lambda *args: errors.append(args))

    result = MainWindow._start_selected_account_batch(
        window,
        [("https://example.test/a", None)],
        interval=60,
        selected_provider="managed",
        api_key="",
    )

    assert result is False
    assert starts == []
    assert window.is_running is False
    assert errors and errors[0][1] == "대기열 저장 실패"


def test_add_queue_persistence_failure_is_reported_without_starting(monkeypatch):
    errors = []
    starts = []
    account = SimpleNamespace(account_id="account-a", expected_username="tester")
    runtime = SimpleNamespace(
        enqueue=lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
        start_account=lambda account_id: starts.append(account_id),
    )
    window = SimpleNamespace(
        _log_user_activity=lambda *_args, **_kwargs: None,
        _ensure_threads_account_allowed=lambda: True,
        links_text=SimpleNamespace(toPlainText=lambda: "https://example.test/a"),
        _extract_links=lambda _text: [("https://example.test/a", None)],
        _ensure_marketplace_links_allowed=lambda _items: True,
        _multi_account_runtime=runtime,
        selected_threads_account=lambda: account,
    )
    monkeypatch.setattr(main_window, "show_error", lambda *args: errors.append(args))

    MainWindow.add_links_to_queue(window)

    assert starts == []
    assert errors and errors[0][1] == "대기열 저장 실패"


def test_stop_persistence_failure_keeps_worker_running_and_reports(monkeypatch):
    warnings = []
    cancellations = []
    window = SimpleNamespace(
        _multi_account_runtime=None,
        selected_threads_account_id=lambda: "",
        is_running=True,
        _save_resume_state=lambda *_args: (_ for _ in ()).throw(
            ResumeStatePersistenceError("save failed")
        ),
        pipeline=SimpleNamespace(cancel=lambda: cancellations.append("cancel")),
        _active_pipeline=None,
        signals=SimpleNamespace(log=_Emitter(), status=_Emitter()),
        status_badge=SimpleNamespace(update_style=lambda *_args: None),
        _relayout_header_account_card=lambda: None,
        _sidebar_status_label=SimpleNamespace(setText=lambda *_args: None),
        _set_run_state=lambda *_args: None,
    )
    monkeypatch.setattr(main_window, "show_warning", lambda *args: warnings.append(args))

    MainWindow.stop_upload(window)

    assert window.is_running is True
    assert cancellations == []
    assert warnings and warnings[0][1] == "중지 준비 실패"


def test_finished_persistence_failure_keeps_recovery_queue_and_reports(monkeypatch):
    warnings = []
    run_states = []
    link_queue = queue.Queue()
    link_queue.put(("https://example.test/a", None))
    window = SimpleNamespace(
        _log_user_activity=lambda *_args, **_kwargs: None,
        _active_pipeline=object(),
        is_running=True,
        start_btn=_Button(),
        add_btn=_Button(),
        stop_btn=_Button(),
        start_all_btn=_Button(),
        stop_all_btn=_Button(),
        status_badge=SimpleNamespace(update_style=lambda *_args: None),
        _relayout_header_account_card=lambda: None,
        _sidebar_status_label=SimpleNamespace(setText=lambda *_args: None),
        _save_resume_state=lambda *_args: (_ for _ in ()).throw(
            ResumeStatePersistenceError("save failed")
        ),
        link_queue=link_queue,
        _set_run_state=lambda state: run_states.append(state),
        signals=SimpleNamespace(log=_Emitter()),
    )
    monkeypatch.setattr(main_window, "show_warning", lambda *args: warnings.append(args))

    MainWindow._on_finished(window, {"cancelled": True})

    assert link_queue.qsize() == 1
    assert run_states[-1]["phase"] == "blocked"
    assert warnings and warnings[0][1] == "복구 상태 저장 실패"


def test_update_prepare_persistence_failure_precedes_marker_stop_and_cancel():
    events = []
    window = SimpleNamespace(
        _multi_account_runtime=SimpleNamespace(
            snapshots=lambda: {},
            stop_all=lambda: events.append("stop"),
        ),
        _update_resume_store=SimpleNamespace(
            save=lambda *_args, **_kwargs: events.append("marker") or {}
        ),
        _save_resume_state=lambda *_args: (_ for _ in ()).throw(
            ResumeStatePersistenceError("save failed")
        ),
        pipeline=SimpleNamespace(cancel=lambda: events.append("cancel")),
        is_running=True,
        signals=SimpleNamespace(status=_Emitter(), log=_Emitter()),
    )

    with pytest.raises(ResumeStatePersistenceError):
        MainWindow._prepare_update_resume(window, {"version": "3.1.0"})

    assert events == []


def test_close_persistence_failure_ignores_event_without_logout(monkeypatch):
    warnings = []
    logout = []
    event = SimpleNamespace(
        ignored=False,
        accepted=False,
        ignore=lambda: setattr(event, "ignored", True),
        accept=lambda: setattr(event, "accepted", True),
    )
    window = SimpleNamespace(
        is_running=False,
        _force_close_for_relogin=False,
        _force_close_for_update=False,
        _log_user_activity=lambda *_args, **_kwargs: None,
        _active_pipeline=None,
        pipeline=None,
        _multi_account_runtime=None,
        _save_resume_state=lambda *_args: (_ for _ in ()).throw(
            ResumeStatePersistenceError("save failed")
        ),
    )
    monkeypatch.setattr(main_window, "show_warning", lambda *args: warnings.append(args))
    from src import auth_client

    monkeypatch.setattr(auth_client, "logout", lambda: logout.append("logout"))

    MainWindow.closeEvent(window, event)

    assert event.ignored is True
    assert event.accepted is False
    assert logout == []
    assert warnings and warnings[0][1] == "종료 준비 실패"


def test_resume_prompt_persistence_failure_is_reported_without_starting(monkeypatch):
    warnings = []
    starts = []
    monkeypatch.delenv("THREAD_AUTO_DISABLE_RESUME_PROMPT", raising=False)
    window = SimpleNamespace(
        is_running=False,
        _load_resume_state_file=lambda: {"items": []},
        _reconcile_reservation_release_items=lambda _state: (_ for _ in ()).throw(
            ResumeStatePersistenceError("save failed")
        ),
        _reconcile_posted_commit_items=lambda state: state,
        _reconcile_ambiguous_post_items=lambda state: state,
        _reconcile_history_write_items=lambda state: state,
        _resume_pending_link_data=lambda _state: [],
        start_link_data_batch=lambda *_args, **_kwargs: starts.append("start"),
    )
    monkeypatch.setattr(main_window, "show_warning", lambda *args: warnings.append(args))

    MainWindow._prompt_resume_queue_if_needed(window)

    assert starts == []
    assert warnings and warnings[0][1] == "복구 상태 저장 실패"
