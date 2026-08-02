"""Application-facing runtime for account-scoped queues and uploads."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from src.services.account_queue import AccountQueueStore
from src.services.link_history import LinkHistory
from src.services.multi_account_coordinator import MultiAccountCoordinator
from src.services.multi_account_upload_runner import MultiAccountUploadRunner


class MultiAccountRuntime:
    """Own account stores, the single upload worker, and UI-safe callbacks."""

    def __init__(
        self,
        *,
        config,
        pipeline,
        queue_root: Optional[str | Path] = None,
        history_root: Optional[str | Path] = None,
        on_state: Optional[Callable[[str, dict], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        browser_factory=None,
        helper_factory=None,
        navigator=None,
        quota_adapter=None,
    ):
        self._config = config
        self._pipeline = pipeline
        self._queue_root = queue_root
        self._history_root = history_root
        self._on_state = on_state
        self._on_log = on_log
        self._browser_factory = browser_factory
        self._helper_factory = helper_factory
        self._navigator = navigator
        self._quota_adapter = quota_adapter
        self._lock = threading.RLock()
        self._stores: Dict[str, AccountQueueStore] = {}
        self._histories: Dict[str, LinkHistory] = {}
        self._worker_thread: Optional[threading.Thread] = None
        self._runner = self._build_runner()
        self._coordinator = MultiAccountCoordinator(
            self._runner.process_one,
            on_state=self._handle_schedule_state,
        )
        self.refresh_accounts()

    def _build_runner(self) -> MultiAccountUploadRunner:
        kwargs = {
            "account_resolver": self._config.get_threads_account,
            "queue_resolver": self.queue_store,
            "history_resolver": self.link_history,
            "pipeline": self._pipeline,
            "log": self._emit_log,
        }
        for key, value in (
            ("browser_factory", self._browser_factory),
            ("helper_factory", self._helper_factory),
            ("navigator", self._navigator),
            ("quota_adapter", self._quota_adapter),
        ):
            if value is not None:
                kwargs[key] = value
        return MultiAccountUploadRunner(**kwargs)

    def set_pipeline(self, pipeline) -> None:
        with self._lock:
            if self.is_running:
                raise RuntimeError("cannot replace pipeline while uploads are running")
            self._pipeline = pipeline
            self._runner = self._build_runner()
            self._coordinator.set_process_one(self._runner.process_one)

    @property
    def is_running(self) -> bool:
        thread = self._worker_thread
        return bool(thread is not None and thread.is_alive())

    def _emit_log(self, account_id: str, message: str) -> None:
        if self._on_log is not None:
            self._on_log(account_id, str(message or ""))

    def _emit_state(self, account_id: str) -> None:
        if self._on_state is not None:
            self._on_state(account_id, self.snapshot(account_id))

    def _handle_schedule_state(self, state) -> None:
        store = self._stores.get(state.account_id)
        if store is not None:
            phase = "blocked" if state.blocked else (
                "running" if state.running else (
                    "waiting"
                    if state.enabled and state.pending_count > 0 and state.next_allowed_at > 0
                    else ("idle" if state.pending_count == 0 else "stopped")
                )
            )
            try:
                store.set_phase(
                    phase,
                    next_allowed_at=state.next_allowed_at or None,
                    last_error=state.last_error or state.blocked_reason or None,
                )
            except Exception:
                pass
        self._emit_state(state.account_id)

    def queue_store(self, account_id: str) -> AccountQueueStore:
        account_id = str(account_id or "").strip()
        if not account_id:
            raise ValueError("account_id is required")
        with self._lock:
            store = self._stores.get(account_id)
            if store is None:
                store = AccountQueueStore(account_id, root=self._queue_root)
                self._stores[account_id] = store
            return store

    def link_history(self, account_id: str) -> LinkHistory:
        account_id = str(account_id or "").strip()
        if not account_id:
            raise ValueError("account_id is required")
        with self._lock:
            history = self._histories.get(account_id)
            if history is None:
                account = self._config.get_threads_account(account_id)
                active_account_id = str(
                    getattr(self._config, "active_threads_account_id", "") or ""
                )
                history_path = (
                    Path(self._history_root) / f"{account_id}.json"
                    if self._history_root is not None
                    else LinkHistory.DEFAULT_HISTORY_FILE.parent
                    / "history"
                    / f"{account_id}.json"
                )
                should_import_legacy = bool(
                    not history_path.exists()
                    and account is not None
                    and account_id == active_account_id
                    and str(getattr(account, "profile_id", "")).startswith(
                        ".threads_profile"
                    )
                    and LinkHistory.DEFAULT_HISTORY_FILE.exists()
                )
                history = LinkHistory(
                    account_id=account_id,
                    history_root=(
                        str(self._history_root)
                        if self._history_root is not None
                        else None
                    ),
                )
                if should_import_legacy:
                    legacy_history = LinkHistory()
                    for url in legacy_history.get_uploaded_urls():
                        history.add_link(url, success=True)
                self._histories[account_id] = history
            return history

    def refresh_accounts(self) -> None:
        accounts = list(self._config.get_threads_accounts())
        account_ids = {account.account_id for account in accounts}
        existing = set(self._coordinator.snapshots())

        for account in accounts:
            store = self.queue_store(account.account_id)
            snapshot = store.snapshot()
            existing_state = (
                self._coordinator.snapshot(account.account_id)
                if account.account_id in existing
                else None
            )
            current_item = snapshot.get("current_item")
            if (
                isinstance(current_item, dict)
                and str(current_item.get("stage") or "") in {"", "parsing"}
                and not (existing_state is not None and existing_state.running)
            ):
                store.requeue_current()
                snapshot = store.snapshot()
            pending_count = len(snapshot.get("pending_items") or []) + (
                1 if snapshot.get("current_item") else 0
            )
            next_allowed_at = snapshot.get("next_allowed_at")
            try:
                next_allowed_at = float(next_allowed_at or 0.0)
            except (TypeError, ValueError):
                next_allowed_at = 0.0
            if account.account_id in existing:
                self._coordinator.update_account(
                    account.account_id,
                    interval_seconds=account.upload_interval,
                    pending_count=pending_count,
                    next_allowed_at=next_allowed_at,
                )
            else:
                self._coordinator.register_account(
                    account.account_id,
                    interval_seconds=account.upload_interval,
                    pending_count=pending_count,
                    next_allowed_at=next_allowed_at,
                )

        for account_id in existing - account_ids:
            state = self._coordinator.snapshot(account_id)
            if state.running:
                continue
            self._coordinator.remove_account(account_id)
            self._stores.pop(account_id, None)
            self._histories.pop(account_id, None)

    def enqueue(self, account_id: str, items: Iterable) -> int:
        store = self.queue_store(account_id)
        history = self.link_history(account_id)
        initial_state = store.snapshot()
        known_urls = {
            self._normalize_url(item.get("url"))
            for item in (initial_state.get("pending_items") or [])
            if isinstance(item, dict)
        }
        current_item = initial_state.get("current_item")
        if isinstance(current_item, dict):
            known_urls.add(self._normalize_url(current_item.get("url")))
        known_urls.update(
            self._normalize_url(url)
            for url in (initial_state.get("processed_urls") or [])
        )
        known_urls.update(
            self._normalize_url(url)
            for url in history.get_uploaded_urls()
        )
        added = 0
        for item in items:
            if isinstance(item, dict):
                url = str(item.get("url") or "").strip()
                keyword = str(item.get("keyword") or item.get("title") or "").strip()
            elif isinstance(item, (tuple, list)):
                url = str(item[0] if item else "").strip()
                keyword = str(item[1] if len(item) > 1 and item[1] else "").strip()
            else:
                url = str(item or "").strip()
                keyword = ""
            normalized_url = self._normalize_url(url)
            if not normalized_url or normalized_url in known_urls:
                continue
            store.enqueue(url, keyword=keyword)
            known_urls.add(normalized_url)
            added += 1

        queue_state = store.snapshot()
        pending_count = len(queue_state.get("pending_items") or []) + (
            1 if queue_state.get("current_item") else 0
        )
        self._coordinator.update_account(
            account_id,
            pending_count=pending_count,
        )
        self._emit_state(account_id)
        return added

    @staticmethod
    def _normalize_url(url) -> str:
        return str(url or "").strip().split("?", 1)[0].lower()

    def snapshot(self, account_id: str) -> dict:
        store_state = self.queue_store(account_id).snapshot()
        try:
            schedule = self._coordinator.snapshot(account_id)
        except KeyError:
            schedule = None
        store_state["schedule"] = schedule
        return store_state

    def snapshots(self) -> Dict[str, dict]:
        return {
            account.account_id: self.snapshot(account.account_id)
            for account in self._config.get_threads_accounts()
        }

    def start_account(self, account_id: str) -> None:
        store = self.queue_store(account_id)
        store.request_stop(False)
        state = store.snapshot()
        pending_count = len(state.get("pending_items") or []) + (
            1 if state.get("current_item") else 0
        )
        if pending_count <= 0:
            return
        self._coordinator.update_account(
            account_id,
            pending_count=pending_count,
        )
        self._coordinator.start_account(account_id)
        self._ensure_worker()

    def start_all(self) -> None:
        for account in self._config.get_threads_accounts():
            self.queue_store(account.account_id).request_stop(False)
        self._coordinator.start_all()
        self._ensure_worker()

    def stop_account(self, account_id: str) -> None:
        self.queue_store(account_id).request_stop(True)
        self._coordinator.stop_account(account_id)
        self._emit_state(account_id)

    def stop_all(self) -> None:
        for store in list(self._stores.values()):
            store.request_stop(True)
        self._coordinator.request_stop()

    def wait_until_stopped(self, timeout: float) -> bool:
        """Wait for the active worker without holding the runtime lock."""
        with self._lock:
            worker = self._worker_thread
        if worker is None:
            return True
        if worker is threading.current_thread():
            return False
        worker.join(max(float(timeout), 0.0))
        return not worker.is_alive()

    def stop_and_join(self, timeout: float) -> bool:
        """Request a cooperative stop and confirm the worker has exited."""
        self.stop_all()
        return self.wait_until_stopped(timeout)

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._coordinator.reset_stop()

            def run():
                try:
                    self._coordinator.run_until_idle(poll_seconds=0.25)
                finally:
                    with self._lock:
                        self._worker_thread = None

            self._worker_thread = threading.Thread(
                target=run,
                daemon=True,
                name="multi-account-upload-coordinator",
            )
            self._worker_thread.start()
