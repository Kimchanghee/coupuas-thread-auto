from types import SimpleNamespace

import pytest

from src import auth_client
from src import main_window


class _LogSignal:
    def __init__(self):
        self.messages = []

    def emit(self, value):
        self.messages.append(value)


def _cancel_auth_context(
    *,
    generation=11,
    user_id="user-1",
    token="token-1",
    email="owner@example.com",
    plan_id="stmaker_pro_month",
):
    snapshot = auth_client.AuthSessionSnapshot(generation, user_id, token)
    state = {
        "user_id": user_id,
        "token": token,
        "email": email,
        "plan_id": plan_id,
    }
    window = SimpleNamespace(_auth_data={"email": email})
    binding = main_window._build_payapp_cancel_binding(
        window,
        snapshot,
        state,
        plan_id,
    )
    assert binding is not None
    return snapshot, state, binding


def test_external_link_opens_original_but_logs_origin_only(monkeypatch):
    opened = []
    events = []

    class FakeWindow:
        def _log_user_activity(self, action, content, **kwargs):
            events.append((action, content, kwargs))

    raw_url = "https://user:pass@m.payapp.kr/pay/order-123?token=secret-value#fragment"
    monkeypatch.setattr(
        main_window.QDesktopServices,
        "openUrl",
        lambda qurl: opened.append(qurl.toString()) or True,
    )

    assert main_window.MainWindow._open_external_link(
        FakeWindow(), raw_url, "settings_payapp_checkout"
    ) is True

    assert opened == [raw_url]
    logged = " ".join(content for _, content, _ in events)
    assert "https://m.payapp.kr" in logged
    assert "user:pass" not in logged
    assert "order-123" not in logged
    assert "secret-value" not in logged
    assert "fragment" not in logged


def test_checkout_handler_only_schedules_background_work():
    scheduled = []
    busy = []
    events = []

    class PhoneEdit:
        def text(self):
            return "010-1234-5678"

    class FakeWindow:
        _payment_in_flight = False
        _pay_phone_edit = PhoneEdit()

        def _log_user_activity(self, action, content, **_kwargs):
            events.append((action, content))

        def _start_payment_worker(self, operation, payload, status):
            scheduled.append((operation, payload, status))
            return True

        def _set_payment_busy(self, value, status=""):
            busy.append((value, status))

    main_window.MainWindow._request_payapp_checkout(FakeWindow(), "stmaker_pro_week")

    assert scheduled == [
        (
            "checkout",
            {"phone": "01012345678", "plan_id": "stmaker_pro_week"},
            "안전한 결제 페이지를 준비하고 있습니다…",
        )
    ]
    assert busy == []
    assert events[0][1] == "phone_present=True; plan_id=stmaker_pro_week"


def test_payment_worker_start_is_non_blocking_and_deduplicated(monkeypatch):
    snapshot = object()
    started = []
    busy = []

    monkeypatch.setattr(auth_client, "capture_auth_session_snapshot", lambda: snapshot)

    class FakeThread:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            started.append(self.kwargs)

    monkeypatch.setattr(main_window.threading, "Thread", FakeThread)

    class FakeWindow:
        _payment_in_flight = False
        _payment_request_seq = 0
        _payment_worker = object()

        def _set_payment_busy(self, value, status=""):
            busy.append((value, status))

    window = FakeWindow()
    assert main_window.MainWindow._start_payment_worker(
        window, "checkout", {"phone": "01012345678"}, "working"
    ) is True
    assert window._payment_in_flight is True
    assert window._payment_request_seq == 1
    assert started[0]["name"] == "payment-checkout-worker"
    assert started[0]["daemon"] is True
    assert busy == [(True, "working")]

    assert main_window.MainWindow._start_payment_worker(
        window, "checkout", {}, "again"
    ) is False
    assert len(started) == 1


def test_payment_worker_start_failure_restores_ui(monkeypatch):
    snapshot = object()
    busy = []
    events = []
    errors = []

    monkeypatch.setattr(auth_client, "capture_auth_session_snapshot", lambda: snapshot)

    class FailingThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("thread resource exhausted")

    monkeypatch.setattr(main_window.threading, "Thread", FailingThread)
    monkeypatch.setattr(
        main_window,
        "show_error",
        lambda _parent, title, message: errors.append((title, message)),
    )

    class FakeWindow:
        _payment_in_flight = False
        _payment_request_seq = 0
        _payment_worker = object()

        def _set_payment_busy(self, value, status=""):
            busy.append((value, status))

        def _log_user_activity(self, action, content, **kwargs):
            events.append((action, content, kwargs))

    window = FakeWindow()
    assert main_window.MainWindow._start_payment_worker(
        window, "checkout", {"phone": "01012345678"}, "working"
    ) is False
    assert window._payment_in_flight is False
    assert window._payment_request_seq == 2
    assert busy[-1][0] is False
    assert events[-1][0] == "payment_worker_start_failed"
    assert errors


def test_stale_payment_completion_is_discarded(monkeypatch):
    events = []
    busy = []

    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda _snapshot: False,
    )

    class FakeWindow:
        _closed = False
        _payment_request_seq = 7
        _payment_in_flight = True

        def _log_user_activity(self, action, content, **kwargs):
            events.append((action, content, kwargs))

        def _set_payment_busy(self, value, status=""):
            busy.append((value, status))

        def _apply_payapp_checkout_result(self, *_args):
            raise AssertionError("stale checkout must not be applied")

        def _apply_payapp_cancel_result(self, *_args):
            raise AssertionError("stale cancellation must not be applied")

    window = FakeWindow()
    main_window.MainWindow._on_payment_complete(
        window,
        7,
        "checkout",
        {"plan_id": "stmaker_pro_week", "result": {"success": True}},
        SimpleNamespace(generation=1),
    )

    assert window._payment_in_flight is False
    assert events[0][0] == "payment_result_discarded"
    assert busy[-1][0] is False


def test_payment_worker_binds_checkout_to_starting_session(monkeypatch):
    snapshot = object()
    calls = []
    emitted = []

    monkeypatch.setattr(
        auth_client,
        "create_payapp_checkout",
        lambda phone, *, plan_id, session_snapshot: calls.append(
            (phone, plan_id, session_snapshot)
        )
        or {"success": True},
    )

    window = SimpleNamespace(
        signals=SimpleNamespace(
            payment_complete=SimpleNamespace(
                emit=lambda *args: emitted.append(args),
            )
        )
    )
    main_window.MainWindow._payment_worker(
        window,
        3,
        "checkout",
        {"phone": "01012345678", "plan_id": "stmaker_pro_week"},
        snapshot,
    )

    assert calls == [("01012345678", "stmaker_pro_week", snapshot)]
    assert emitted[0][0:2] == (3, "checkout")
    assert emitted[0][3] is snapshot


def test_payment_worker_binds_cancel_sequence_to_starting_session(monkeypatch):
    snapshot, state, binding = _cancel_auth_context()
    calls = []
    emitted = []

    def get_status(*, session_snapshot):
        calls.append(("status", session_snapshot))
        return {
            "success": True,
            "subscriptions": [
                {
                    "status": "active",
                    "plan_id": "stmaker_pro_month",
                    "rebill_no": "rb-123",
                }
            ],
        }

    def cancel(rebill_no, *, session_snapshot):
        calls.append(("cancel", rebill_no, session_snapshot))
        return {"success": True}

    monkeypatch.setattr(auth_client, "get_payapp_subscriptions", get_status)
    monkeypatch.setattr(auth_client, "cancel_payapp_subscription", cancel)
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(state))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda candidate: candidate == snapshot,
    )

    window = SimpleNamespace(
        _auth_data={"email": state["email"]},
        signals=SimpleNamespace(
            payment_complete=SimpleNamespace(
                emit=lambda *args: emitted.append(args),
            )
        )
    )
    main_window.MainWindow._payment_worker(
        window,
        4,
        "cancel",
        {
            "expected_plan_id": "stmaker_pro_month",
            "cancel_binding": binding,
        },
        snapshot,
    )

    assert calls == [
        ("status", snapshot),
        ("cancel", "rb-123", snapshot),
    ]
    assert emitted[0][0:2] == (4, "cancel")
    assert emitted[0][3] is snapshot


def test_cancel_candidate_requires_unique_exact_current_recurring_plan():
    current = "stmaker_shopping_pro_month"
    old = {
        "status": "active",
        "plan_id": "stmaker_pro_month",
        "rebill_no": "old-rebill",
    }
    matching = {
        "status": "active",
        "plan_id": current,
        "rebill_no": "current-rebill",
    }

    selected, error = main_window._select_payapp_cancel_candidate(
        [old, matching],
        current,
    )
    assert selected is matching
    assert error == ""

    selected, error = main_window._select_payapp_cancel_candidate(
        [matching, dict(matching, rebill_no="duplicate-rebill")],
        current,
    )
    assert selected is None
    assert error == "subscription_ambiguous"


def test_cancel_candidate_fails_closed_for_missing_or_unknown_plan_identity():
    missing_plan = {"status": "active", "rebill_no": "rb-missing-plan"}
    selected, error = main_window._select_payapp_cancel_candidate(
        [missing_plan],
        "stmaker_pro_month",
    )
    assert selected is None
    assert error == "subscription_identity_unverified"

    selected, error = main_window._select_payapp_cancel_candidate(
        [
            {
                "status": "active",
                "plan_id": "stmaker_pro_month",
                "rebill_no": "rb-1",
            }
        ],
        "unknown-plan",
    )
    assert selected is None
    assert error == "current_plan_unverified"


def test_cancel_worker_does_not_mutate_ambiguous_subscriptions(monkeypatch):
    snapshot, state, binding = _cancel_auth_context()
    cancelled = []
    emitted = []
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(state))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda candidate: candidate == snapshot,
    )
    monkeypatch.setattr(
        auth_client,
        "get_payapp_subscriptions",
        lambda *, session_snapshot: {
            "success": True,
            "subscriptions": [
                {
                    "status": "active",
                    "plan_id": "stmaker_pro_month",
                    "rebill_no": "rb-1",
                },
                {
                    "status": "active",
                    "plan_id": "stmaker_pro_month",
                    "rebill_no": "rb-2",
                },
            ],
        },
    )
    monkeypatch.setattr(
        auth_client,
        "cancel_payapp_subscription",
        lambda *args, **kwargs: cancelled.append((args, kwargs)),
    )
    window = SimpleNamespace(
        _auth_data={"email": state["email"]},
        signals=SimpleNamespace(
            payment_complete=SimpleNamespace(emit=lambda *args: emitted.append(args))
        )
    )

    main_window.MainWindow._payment_worker(
        window,
        5,
        "cancel",
        {
            "expected_plan_id": "stmaker_pro_month",
            "cancel_binding": binding,
        },
        snapshot,
    )

    assert cancelled == []
    assert emitted[0][2]["selection_error"] == "subscription_ambiguous"


@pytest.mark.parametrize(
    ("changed_snapshot", "changed_state", "changed_email"),
    [
        (
            auth_client.AuthSessionSnapshot(12, "user-2", "token-2"),
            {
                "user_id": "user-2",
                "token": "token-2",
                "plan_id": "stmaker_pro_month",
                "email": "other@example.com",
            },
            "other@example.com",
        ),
        (
            auth_client.AuthSessionSnapshot(13, "user-1", "relogin-token"),
            {
                "user_id": "user-1",
                "token": "relogin-token",
                "plan_id": "stmaker_pro_month",
                "email": "owner@example.com",
            },
            "owner@example.com",
        ),
        (
            auth_client.AuthSessionSnapshot(14, "user-1", "token-1"),
            {
                "user_id": "user-1",
                "token": "token-1",
                "plan_id": "stmaker_pro_month",
                "email": "owner@example.com",
            },
            "owner@example.com",
        ),
    ],
    ids=(
        "account-switch-during-confirm",
        "logout-relogin-same-plan",
        "same-user-generation-changed",
    ),
)
def test_cancel_confirmation_auth_change_makes_zero_payapp_calls(
    monkeypatch,
    changed_snapshot,
    changed_state,
    changed_email,
):
    initial_snapshot, initial_state, _binding = _cancel_auth_context()
    current = {"snapshot": initial_snapshot, "state": initial_state}
    network_calls = []
    warnings = []
    scheduled = []

    monkeypatch.setattr(
        auth_client,
        "capture_auth_session_snapshot",
        lambda: current["snapshot"],
    )
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(current["state"]))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda snapshot: snapshot == current["snapshot"],
    )
    monkeypatch.setattr(
        auth_client,
        "get_payapp_subscriptions",
        lambda **kwargs: network_calls.append(("status", kwargs)),
    )
    monkeypatch.setattr(
        auth_client,
        "cancel_payapp_subscription",
        lambda *args, **kwargs: network_calls.append(("cancel", args, kwargs)),
    )
    monkeypatch.setattr(
        main_window,
        "show_warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    class FakeWindow:
        _payment_in_flight = False
        _auth_data = {"email": "owner@example.com"}

        def _log_user_activity(self, *_args, **_kwargs):
            pass

        def _start_payment_worker(self, *args):
            scheduled.append(args)
            return True

    window = FakeWindow()

    def confirm_and_change_auth(*_args, **_kwargs):
        current["snapshot"] = changed_snapshot
        current["state"] = dict(changed_state)
        window._auth_data = {"email": changed_email}
        return True

    monkeypatch.setattr(main_window, "ask_yes_no", confirm_and_change_auth)

    main_window.MainWindow._cancel_payapp_subscription(window)

    assert network_calls == []
    assert scheduled == []
    assert warnings


def test_cancel_worker_start_rejects_changed_binding_before_thread_or_network(
    monkeypatch,
):
    _initial_snapshot, _initial_state, binding = _cancel_auth_context()
    changed_snapshot = auth_client.AuthSessionSnapshot(12, "user-2", "token-2")
    changed_state = {
        "user_id": "user-2",
        "token": "token-2",
        "plan_id": "stmaker_pro_month",
        "email": "other@example.com",
    }
    network_calls = []
    thread_starts = []
    warnings = []
    busy = []

    monkeypatch.setattr(
        auth_client, "capture_auth_session_snapshot", lambda: changed_snapshot
    )
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(changed_state))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda snapshot: snapshot == changed_snapshot,
    )
    monkeypatch.setattr(
        auth_client,
        "get_payapp_subscriptions",
        lambda **kwargs: network_calls.append(("status", kwargs)),
    )
    monkeypatch.setattr(
        auth_client,
        "cancel_payapp_subscription",
        lambda *args, **kwargs: network_calls.append(("cancel", args, kwargs)),
    )
    monkeypatch.setattr(
        main_window.threading,
        "Thread",
        lambda **kwargs: thread_starts.append(kwargs),
    )
    monkeypatch.setattr(
        main_window,
        "show_warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    class FakeWindow:
        _payment_in_flight = False
        _payment_request_seq = 0
        _auth_data = {"email": "other@example.com"}

        def _log_user_activity(self, *_args, **_kwargs):
            pass

        def _set_payment_busy(self, value, status=""):
            busy.append((value, status))

    window = FakeWindow()
    assert (
        main_window.MainWindow._start_payment_worker(
            window,
            "cancel",
            {
                "expected_plan_id": "stmaker_pro_month",
                "cancel_binding": binding,
            },
            "working",
        )
        is False
    )

    assert network_calls == []
    assert thread_starts == []
    assert warnings
    assert busy[-1][0] is False


def test_cancel_worker_rechecks_binding_before_any_payapp_lookup(monkeypatch):
    _initial_snapshot, _initial_state, binding = _cancel_auth_context()
    changed_snapshot = auth_client.AuthSessionSnapshot(15, "user-1", "token-1")
    changed_state = {
        "user_id": "user-1",
        "token": "token-1",
        "plan_id": "stmaker_pro_month",
        "email": "owner@example.com",
    }
    network_calls = []
    emitted = []
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(changed_state))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda snapshot: snapshot == changed_snapshot,
    )
    monkeypatch.setattr(
        auth_client,
        "get_payapp_subscriptions",
        lambda **kwargs: network_calls.append(("status", kwargs)),
    )
    monkeypatch.setattr(
        auth_client,
        "cancel_payapp_subscription",
        lambda *args, **kwargs: network_calls.append(("cancel", args, kwargs)),
    )
    window = SimpleNamespace(
        _auth_data={"email": "owner@example.com"},
        signals=SimpleNamespace(
            payment_complete=SimpleNamespace(emit=lambda *args: emitted.append(args))
        ),
    )

    main_window.MainWindow._payment_worker(
        window,
        6,
        "cancel",
        {
            "expected_plan_id": "stmaker_pro_month",
            "cancel_binding": binding,
        },
        changed_snapshot,
    )

    assert network_calls == []
    assert emitted[0][2]["authorization_error"] == "auth_session_changed"


def test_cancel_worker_rechecks_binding_immediately_before_mutation(monkeypatch):
    initial_snapshot, initial_state, binding = _cancel_auth_context()
    current = {"snapshot": initial_snapshot, "state": initial_state}
    status_calls = []
    cancel_calls = []
    emitted = []

    def get_status(*, session_snapshot):
        status_calls.append(session_snapshot)
        current["snapshot"] = auth_client.AuthSessionSnapshot(
            initial_snapshot.generation + 1,
            initial_snapshot.user_id,
            initial_snapshot.token,
        )
        return {
            "success": True,
            "subscriptions": [
                {
                    "status": "active",
                    "plan_id": "stmaker_pro_month",
                    "rebill_no": "rb-123",
                }
            ],
        }

    monkeypatch.setattr(auth_client, "get_payapp_subscriptions", get_status)
    monkeypatch.setattr(
        auth_client,
        "cancel_payapp_subscription",
        lambda *args, **kwargs: cancel_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(auth_client, "get_auth_state", lambda: dict(current["state"]))
    monkeypatch.setattr(
        auth_client,
        "is_auth_session_snapshot_current",
        lambda snapshot: snapshot == current["snapshot"],
    )
    window = SimpleNamespace(
        _auth_data={"email": "owner@example.com"},
        signals=SimpleNamespace(
            payment_complete=SimpleNamespace(emit=lambda *args: emitted.append(args))
        ),
    )

    main_window.MainWindow._payment_worker(
        window,
        7,
        "cancel",
        {
            "expected_plan_id": "stmaker_pro_month",
            "cancel_binding": binding,
        },
        initial_snapshot,
    )

    assert status_calls == [initial_snapshot]
    assert cancel_calls == []
    assert emitted[0][2]["authorization_error"] == "auth_session_changed"
