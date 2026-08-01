"""Single-worker round-robin scheduling for independent account queues."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class AccountRunResult:
    """Result returned after attempting one queued item for an account."""

    processed: bool
    pending_count: int
    success: bool = False
    block_reason: str = ""
    next_allowed_at: Optional[float] = None


@dataclass(frozen=True)
class AccountScheduleState:
    account_id: str
    interval_seconds: int = 30
    pending_count: int = 0
    next_allowed_at: float = 0.0
    enabled: bool = False
    running: bool = False
    blocked_reason: str = ""
    last_error: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)


class MultiAccountCoordinator:
    """Run at most one account item at a time while preserving queue isolation."""

    def __init__(
        self,
        process_one: Callable[[str], AccountRunResult],
        *,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        on_state: Optional[Callable[[AccountScheduleState], None]] = None,
    ):
        self._process_one = process_one
        self._clock = clock
        self._sleeper = sleeper
        self._on_state = on_state
        self._lock = threading.RLock()
        self._states: Dict[str, AccountScheduleState] = {}
        self._order: list[str] = []
        self._cursor = 0
        self._stop_event = threading.Event()

    @staticmethod
    def _normalize_account_id(account_id: str) -> str:
        normalized = str(account_id or "").strip()
        if not normalized:
            raise ValueError("account_id is required")
        return normalized

    def register_account(
        self,
        account_id: str,
        *,
        interval_seconds: int = 30,
        pending_count: int = 0,
        next_allowed_at: float = 0.0,
        enabled: bool = False,
    ) -> AccountScheduleState:
        account_id = self._normalize_account_id(account_id)
        state = AccountScheduleState(
            account_id=account_id,
            interval_seconds=max(30, int(interval_seconds or 30)),
            pending_count=max(0, int(pending_count or 0)),
            next_allowed_at=max(0.0, float(next_allowed_at or 0.0)),
            enabled=bool(enabled),
        )
        with self._lock:
            existing = self._states.get(account_id)
            if existing is None:
                self._order.append(account_id)
                self._states[account_id] = state
            else:
                state = replace(
                    existing,
                    interval_seconds=state.interval_seconds,
                    pending_count=state.pending_count,
                    next_allowed_at=state.next_allowed_at,
                    enabled=state.enabled,
                )
                self._states[account_id] = state
        self._emit(state)
        return state

    def set_process_one(
        self,
        process_one: Callable[[str], AccountRunResult],
    ) -> None:
        if not callable(process_one):
            raise TypeError("process_one must be callable")
        with self._lock:
            if any(state.running for state in self._states.values()):
                raise RuntimeError("cannot replace process callback while running")
            self._process_one = process_one

    def remove_account(self, account_id: str) -> None:
        account_id = self._normalize_account_id(account_id)
        with self._lock:
            state = self._states.get(account_id)
            if state is not None and state.running:
                raise RuntimeError("running account cannot be removed")
            self._states.pop(account_id, None)
            self._order = [value for value in self._order if value != account_id]
            self._cursor = 0 if not self._order else self._cursor % len(self._order)

    def update_account(self, account_id: str, **changes) -> AccountScheduleState:
        account_id = self._normalize_account_id(account_id)
        allowed = {
            "interval_seconds",
            "pending_count",
            "next_allowed_at",
            "enabled",
            "blocked_reason",
            "last_error",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported state fields: {sorted(unknown)}")
        if "interval_seconds" in changes:
            changes["interval_seconds"] = max(
                30,
                int(changes["interval_seconds"] or 30),
            )
        if "pending_count" in changes:
            changes["pending_count"] = max(0, int(changes["pending_count"] or 0))
        if "next_allowed_at" in changes:
            changes["next_allowed_at"] = max(
                0.0,
                float(changes["next_allowed_at"] or 0.0),
            )
        for text_field in ("blocked_reason", "last_error"):
            if text_field in changes:
                changes[text_field] = str(changes[text_field] or "")

        with self._lock:
            current = self._states.get(account_id)
            if current is None:
                raise KeyError(account_id)
            updated = replace(current, **changes)
            self._states[account_id] = updated
        self._emit(updated)
        return updated

    def start_account(self, account_id: str) -> AccountScheduleState:
        return self.update_account(
            account_id,
            enabled=True,
            blocked_reason="",
            last_error="",
        )

    def stop_account(self, account_id: str) -> AccountScheduleState:
        return self.update_account(account_id, enabled=False)

    def block_account(self, account_id: str, reason: str) -> AccountScheduleState:
        return self.update_account(
            account_id,
            enabled=False,
            blocked_reason=str(reason or "blocked"),
        )

    def start_all(self) -> None:
        with self._lock:
            account_ids = list(self._order)
        self._stop_event.clear()
        for account_id in account_ids:
            state = self.snapshot(account_id)
            if state.pending_count > 0 and not state.blocked:
                self.update_account(account_id, enabled=True)

    def request_stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            account_ids = list(self._order)
        for account_id in account_ids:
            self.update_account(account_id, enabled=False)

    def reset_stop(self) -> None:
        self._stop_event.clear()

    def snapshot(self, account_id: str) -> AccountScheduleState:
        account_id = self._normalize_account_id(account_id)
        with self._lock:
            state = self._states.get(account_id)
            if state is None:
                raise KeyError(account_id)
            return replace(state)

    def snapshots(self) -> Dict[str, AccountScheduleState]:
        with self._lock:
            return {
                account_id: replace(state)
                for account_id, state in self._states.items()
            }

    def _emit(self, state: AccountScheduleState) -> None:
        if self._on_state is not None:
            self._on_state(replace(state))

    def _next_eligible(self) -> Optional[str]:
        now = self._clock()
        with self._lock:
            if not self._order:
                return None
            order_length = len(self._order)
            for offset in range(order_length):
                index = (self._cursor + offset) % order_length
                account_id = self._order[index]
                state = self._states.get(account_id)
                if state is None:
                    continue
                if (
                    state.enabled
                    and not state.running
                    and not state.blocked
                    and state.pending_count > 0
                    and state.next_allowed_at <= now
                ):
                    self._cursor = (index + 1) % order_length
                    return account_id
            return None

    def run_once(self) -> bool:
        """Process one eligible item. Returns whether a callback was invoked."""
        if self._stop_event.is_set():
            return False
        account_id = self._next_eligible()
        if account_id is None:
            return False

        with self._lock:
            state = self._states[account_id]
            running_state = replace(state, running=True, last_error="")
            self._states[account_id] = running_state
        self._emit(running_state)

        try:
            result = self._process_one(account_id)
            if not isinstance(result, AccountRunResult):
                raise TypeError("process_one must return AccountRunResult")
        except Exception as exc:
            with self._lock:
                failed_state = replace(
                    self._states[account_id],
                    running=False,
                    enabled=False,
                    blocked_reason="process_error",
                    last_error=str(exc)[:300],
                )
                self._states[account_id] = failed_state
            self._emit(failed_state)
            return True

        now = self._clock()
        with self._lock:
            current = self._states[account_id]
            block_reason = str(result.block_reason or "")
            next_allowed_at = result.next_allowed_at
            if next_allowed_at is None:
                next_allowed_at = (
                    now + current.interval_seconds
                    if result.processed and result.pending_count > 0
                    else 0.0
                )
            updated = replace(
                current,
                pending_count=max(0, int(result.pending_count or 0)),
                next_allowed_at=max(0.0, float(next_allowed_at or 0.0)),
                enabled=bool(current.enabled and not block_reason),
                running=False,
                blocked_reason=block_reason,
                last_error=block_reason if block_reason else "",
            )
            self._states[account_id] = updated
        self._emit(updated)
        return True

    def run_until_idle(self, *, poll_seconds: float = 0.1) -> None:
        """Run until no enabled account has pending work or stop is requested."""
        self._stop_event.clear()
        while not self._stop_event.is_set():
            if self.run_once():
                continue
            states = self.snapshots().values()
            runnable = [
                state
                for state in states
                if state.enabled and not state.blocked and state.pending_count > 0
            ]
            if not runnable:
                return
            self._sleeper(max(0.01, float(poll_seconds or 0.1)))
