"""Account-scoped, durable upload queues.

This module deliberately contains no Qt or browser objects.  It is safe to use
from worker threads and persists each account independently so one damaged or
blocked account cannot affect another one.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.fs_security import secure_dir_permissions, secure_file_permissions


VALID_PHASES = frozenset({"idle", "running", "waiting", "blocked", "stopped"})
_SAFE_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _now() -> str:
    return datetime.now().isoformat()


@dataclass(frozen=True)
class AccountQueueState:
    """A detached, UI-safe view of an account queue's persisted state."""

    account_id: str
    pending_items: list[Dict[str, Any]]
    processed_urls: list[str]
    phase: str
    next_allowed_at: Optional[str]
    stats: Dict[str, int]
    current_item: Optional[Dict[str, Any]]
    last_error: Optional[str]
    stop_requested: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountQueueState":
        return cls(
            account_id=data["account_id"],
            pending_items=copy.deepcopy(data["pending_items"]),
            processed_urls=list(data["processed_urls"]),
            phase=data["phase"],
            next_allowed_at=data["next_allowed_at"],
            stats=copy.deepcopy(data["stats"]),
            current_item=copy.deepcopy(data["current_item"]),
            last_error=data["last_error"],
            stop_requested=bool(data["stop_requested"]),
        )


class AccountQueueStore:
    """Persist and mutate one account's queue atomically.

    ``root`` is injectable for tests; by default files live below
    ``~/.shorts_thread_maker/queues/<account_id>.json``.
    """

    VERSION = 2

    def __init__(
        self,
        account_id: str,
        root: Optional[str | Path] = None,
        *,
        storage_root: Optional[str | Path] = None,
    ):
        normalized_account_id = str(account_id or "").strip()
        if not _SAFE_ACCOUNT_ID_RE.fullmatch(normalized_account_id):
            raise ValueError("account_id contains unsupported characters")
        self.account_id = normalized_account_id
        selected_root = storage_root if storage_root is not None else root
        self.root = Path(selected_root).expanduser() if selected_root else Path.home() / ".shorts_thread_maker" / "queues"
        self.root.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(self.root)
        self.path = self.root / (self.account_id + ".json")
        self._lock = threading.RLock()
        self._state = self._load()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "account_id": self.account_id,
            "pending_items": [],
            "processed_urls": [],
            "phase": "idle",
            "next_allowed_at": None,
            "stats": {"success": 0, "failed": 0, "skipped": 0},
            "current_item": None,
            "last_error": None,
            "stop_requested": False,
        }

    def _load(self) -> Dict[str, Any]:
        state = self._default_state()
        if not self.path.exists():
            return state
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict) or loaded.get("account_id") not in (None, self.account_id):
                return state
            for key, value in state.items():
                loaded.setdefault(key, copy.deepcopy(value))
            loaded["version"] = self.VERSION
            loaded["account_id"] = self.account_id
            loaded["pending_items"] = [item for item in loaded["pending_items"] if isinstance(item, dict)]
            if not isinstance(loaded.get("current_item"), dict):
                loaded["current_item"] = None
            loaded["processed_urls"] = list(dict.fromkeys(str(url) for url in loaded["processed_urls"] if url))
            if loaded["phase"] not in VALID_PHASES:
                loaded["phase"] = "idle"
            if not isinstance(loaded["stats"], dict):
                loaded["stats"] = state["stats"]
            for key in state["stats"]:
                loaded["stats"][key] = max(0, int(loaded["stats"].get(key, 0) or 0))
            return loaded
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return state

    def _save(self) -> None:
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, prefix=self.account_id + ".", suffix=".tmp", delete=False) as handle:
                json.dump(self._state, handle, ensure_ascii=False, indent=2)
                temp_name = handle.name
            secure_file_permissions(temp_name)
            os.replace(temp_name, self.path)
            secure_file_permissions(self.path)
        finally:
            if temp_name and Path(temp_name).exists():
                Path(temp_name).unlink(missing_ok=True)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def get_state(self) -> AccountQueueState:
        with self._lock:
            return AccountQueueState.from_dict(self._state)

    # Alias useful to consumers that call their serialized state a restore.
    restore = snapshot

    def enqueue(self, url: str, **payload: Any) -> Dict[str, Any]:
        """Append a stable queue item and return its copy."""
        text = str(url or "").strip()
        if not text:
            raise ValueError("url is required")
        with self._lock:
            previous = copy.deepcopy(self._state)
            item_id = uuid.uuid4().hex
            item = {
                **payload,
                "item_id": item_id,
                "url": text,
                "created_at": _now(),
                # Created with the durable queue item so every retry of one
                # logical generation/reservation request reuses the same key.
                "idempotency_key": str(
                    payload.get("idempotency_key") or uuid.uuid4().hex
                ),
            }
            self._state["pending_items"].append(item)
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def enqueue_many(self, urls: Iterable[str]) -> list[Dict[str, Any]]:
        return [self.enqueue(url) for url in urls]

    def reserve_next(self) -> Optional[Dict[str, Any]]:
        """Mark the next pending item current without removing it (crash safe)."""
        with self._lock:
            if self._state["stop_requested"] or self._state["current_item"]:
                return None
            previous = copy.deepcopy(self._state)
            if not self._state["pending_items"]:
                self._state["phase"] = "idle"
                try:
                    self._save()
                except Exception:
                    self._state = previous
                    raise
                return None
            item = self._state["pending_items"].pop(0)
            item["stage"] = "parsing"
            self._state["current_item"] = item
            self._state["phase"] = "running"
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def update_current(self, **changes: Any) -> Optional[Dict[str, Any]]:
        """Atomically persist transaction metadata for the current item."""
        protected = {"item_id", "url", "created_at"}
        if protected.intersection(changes):
            raise ValueError("stable current item fields cannot be changed")
        with self._lock:
            item = self._state["current_item"]
            if item is None:
                return None
            previous = copy.deepcopy(self._state)
            item.update(copy.deepcopy(changes))
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def complete_current(self, outcome: str = "success", error: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if outcome not in {"success", "failed", "skipped"}:
            raise ValueError("outcome must be success, failed, or skipped")
        with self._lock:
            item = self._state["current_item"]
            if item is None:
                return None
            previous = copy.deepcopy(self._state)
            self._state["current_item"] = None
            self._state["stats"][outcome] += 1
            if outcome == "success":
                self._state["processed_urls"].append(item.get("url", ""))
            self._state["last_error"] = str(error) if error else None
            self._state["phase"] = "stopped" if self._state["stop_requested"] else ("idle" if not self._state["pending_items"] else "running")
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def requeue_current(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._state["current_item"]
            if item is None:
                return None
            previous = copy.deepcopy(self._state)
            for key in (
                "stage",
                "reservation_id",
                "reservation_legacy",
                "reservation_bypass",
                "resolution",
                "next_idempotency_key",
                "reconciliation_lookup_pending",
                "ai_job_id",
            ):
                item.pop(key, None)
            self._state["pending_items"].insert(0, item)
            self._state["current_item"] = None
            self._state["phase"] = "stopped" if self._state["stop_requested"] else "idle"
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def set_phase(self, phase: str, *, next_allowed_at: Optional[str] = None, last_error: Optional[str] = None) -> None:
        if phase not in VALID_PHASES:
            raise ValueError("invalid queue phase")
        with self._lock:
            previous = copy.deepcopy(self._state)
            self._state["phase"] = phase
            self._state["next_allowed_at"] = next_allowed_at
            self._state["last_error"] = last_error
            try:
                self._save()
            except Exception:
                self._state = previous
                raise

    def request_stop(self, requested: bool = True) -> None:
        with self._lock:
            previous = copy.deepcopy(self._state)
            self._state["stop_requested"] = bool(requested)
            if requested:
                self._state["phase"] = "stopped"
            try:
                self._save()
            except Exception:
                self._state = previous
                raise
