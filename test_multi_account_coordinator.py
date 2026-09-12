from src.services.multi_account_coordinator import (
    AccountRunResult,
    MultiAccountCoordinator,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def test_coordinator_runs_accounts_round_robin_with_one_callback_at_a_time():
    clock = FakeClock()
    pending = {"a": 2, "b": 2}
    calls = []
    active_callbacks = 0
    max_active_callbacks = 0

    def process_one(account_id):
        nonlocal active_callbacks, max_active_callbacks
        active_callbacks += 1
        max_active_callbacks = max(max_active_callbacks, active_callbacks)
        calls.append(account_id)
        pending[account_id] -= 1
        active_callbacks -= 1
        return AccountRunResult(
            processed=True,
            pending_count=pending[account_id],
            next_allowed_at=clock.now(),
        )

    coordinator = MultiAccountCoordinator(
        process_one,
        clock=clock.now,
        sleeper=clock.sleep,
    )
    coordinator.register_account("a", pending_count=2, enabled=True)
    coordinator.register_account("b", pending_count=2, enabled=True)

    coordinator.run_until_idle()

    assert calls == ["a", "b", "a", "b"]
    assert max_active_callbacks == 1
    assert coordinator.snapshot("a").enabled is False
    assert coordinator.snapshot("b").enabled is False


def test_blocked_account_does_not_stop_other_accounts():
    calls = []

    def process_one(account_id):
        calls.append(account_id)
        if account_id == "a":
            return AccountRunResult(
                processed=False,
                pending_count=1,
                block_reason="login_mismatch",
            )
        return AccountRunResult(processed=True, pending_count=0, success=True)

    coordinator = MultiAccountCoordinator(process_one)
    coordinator.register_account("a", pending_count=1, enabled=True)
    coordinator.register_account("b", pending_count=1, enabled=True)

    coordinator.run_until_idle()

    assert calls == ["a", "b"]
    assert coordinator.snapshot("a").blocked_reason == "login_mismatch"
    assert coordinator.snapshot("b").pending_count == 0


def test_interval_wait_for_one_account_allows_another_account_to_run():
    clock = FakeClock()
    calls = []

    def process_one(account_id):
        calls.append(account_id)
        return AccountRunResult(processed=True, pending_count=0)

    coordinator = MultiAccountCoordinator(
        process_one,
        clock=clock.now,
        sleeper=clock.sleep,
    )
    coordinator.register_account(
        "waiting",
        pending_count=1,
        next_allowed_at=200,
        enabled=True,
    )
    coordinator.register_account(
        "ready",
        pending_count=1,
        next_allowed_at=100,
        enabled=True,
    )

    assert coordinator.run_once()
    assert calls == ["ready"]
    assert not coordinator.run_once()

    clock.value = 200
    assert coordinator.run_once()
    assert calls == ["ready", "waiting"]


def test_account_can_be_stopped_without_disabling_other_accounts():
    calls = []

    def process_one(account_id):
        calls.append(account_id)
        return AccountRunResult(processed=True, pending_count=0)

    coordinator = MultiAccountCoordinator(process_one)
    coordinator.register_account("a", pending_count=1, enabled=True)
    coordinator.register_account("b", pending_count=1, enabled=True)
    coordinator.stop_account("a")

    coordinator.run_until_idle()

    assert calls == ["b"]
    assert coordinator.snapshot("a").pending_count == 1
    assert not coordinator.snapshot("a").enabled


def test_callback_exception_blocks_only_failing_account():
    calls = []

    def process_one(account_id):
        calls.append(account_id)
        if account_id == "a":
            raise RuntimeError("browser failed")
        return AccountRunResult(processed=True, pending_count=0)

    coordinator = MultiAccountCoordinator(process_one)
    coordinator.register_account("a", pending_count=1, enabled=True)
    coordinator.register_account("b", pending_count=1, enabled=True)

    coordinator.run_until_idle()

    assert calls == ["a", "b"]
    assert coordinator.snapshot("a").blocked_reason == "process_error"
    assert "browser failed" in coordinator.snapshot("a").last_error


def test_callback_error_state_persistence_failure_is_reported_and_fails_closed():
    state_errors = []

    def process_one(_account_id):
        raise RuntimeError("browser failed")

    def persist_state(state):
        if not state.running and state.blocked_reason == "process_error":
            raise OSError("failed-state write denied")

    coordinator = MultiAccountCoordinator(
        process_one,
        on_state=persist_state,
        on_state_error=lambda state, exc: state_errors.append((state, exc)),
    )
    coordinator.register_account("a", pending_count=1, enabled=True)

    assert coordinator.run_once() is True
    state = coordinator.snapshot("a")
    assert state.enabled is False
    assert state.running is False
    assert state.blocked_reason == "state_persistence_failed"
    assert "failed-state write denied" in state.last_error
    assert len(state_errors) == 1


def test_state_persistence_failure_blocks_before_process_callback():
    process_calls = []
    state_errors = []

    def persist_state(state):
        if state.account_id == "a" and state.running:
            raise OSError("disk full")

    coordinator = MultiAccountCoordinator(
        lambda account_id: process_calls.append(account_id),
        on_state=persist_state,
        on_state_error=lambda state, exc: state_errors.append((state, exc)),
    )
    coordinator.register_account("a", pending_count=1, enabled=True)

    assert coordinator.run_once() is True
    assert process_calls == []
    state = coordinator.snapshot("a")
    assert state.enabled is False
    assert state.running is False
    assert state.blocked_reason == "state_persistence_failed"
    assert "disk full" in state.last_error
    assert len(state_errors) == 1


def test_result_persistence_failure_blocks_future_items():
    process_calls = []
    state_errors = []

    def process_one(account_id):
        process_calls.append(account_id)
        return AccountRunResult(processed=True, pending_count=1)

    def persist_state(state):
        if not state.running and process_calls:
            raise PermissionError("write denied")

    coordinator = MultiAccountCoordinator(
        process_one,
        on_state=persist_state,
        on_state_error=lambda state, exc: state_errors.append((state, exc)),
    )
    coordinator.register_account("a", pending_count=2, enabled=True)

    assert coordinator.run_once() is True
    assert process_calls == ["a"]
    assert coordinator.run_once() is False
    state = coordinator.snapshot("a")
    assert state.blocked_reason == "state_persistence_failed"
    assert state.pending_count == 1
    assert len(state_errors) == 1


def test_update_persistence_failure_is_returned_as_blocked_state():
    errors = []
    fail_updates = False

    def persist_state(_state):
        if fail_updates:
            raise OSError("read only")

    coordinator = MultiAccountCoordinator(
        lambda _account_id: AccountRunResult(processed=False, pending_count=0),
        on_state=persist_state,
        on_state_error=lambda state, exc: errors.append((state, exc)),
    )
    coordinator.register_account("a", pending_count=1)
    fail_updates = True

    updated = coordinator.update_account("a", enabled=True)

    assert updated.enabled is False
    assert updated.blocked_reason == "state_persistence_failed"
    assert coordinator.snapshot("a") == updated
    assert len(errors) == 1
