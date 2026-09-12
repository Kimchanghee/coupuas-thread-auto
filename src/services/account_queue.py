"""Account-scoped, durable upload queues.

This module deliberately contains no Qt or browser objects.  It is safe to use
from worker threads and persists each account independently so one damaged or
blocked account cannot affect another one.
"""

from __future__ import annotations

import copy
import json
import os
import re
import stat
import tempfile
import threading
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.fs_security import secure_dir_permissions, secure_file_permissions

VALID_PHASES = frozenset({"idle", "running", "waiting", "blocked", "stopped"})
_SAFE_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_RECOVERY_BLOCK_REASON = "state_recovery_required"
_PATH_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def _lock_for_path(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


class QueueStateRecoveryRequired(RuntimeError):
    """Raised when the durable queue cannot be trusted or safely mutated."""


class QueuePersistenceError(OSError):
    """Raised when a queue update failed before its atomic publish point."""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


@dataclass(frozen=True)
class AccountQueueState:
    """A detached, UI-safe view of an account queue's persisted state."""

    account_id: str
    pending_items: list[dict[str, Any]]
    processed_urls: list[str]
    phase: str
    next_allowed_at: str | float | None
    stats: dict[str, int]
    current_item: dict[str, Any] | None
    last_error: str | None
    stop_requested: bool
    recovery_required: bool = False
    recovery_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountQueueState:
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
            recovery_required=bool(data.get("recovery_required", False)),
            recovery_reason=(
                str(data.get("recovery_reason") or "") or None
            ),
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
        root: str | Path | None = None,
        *,
        storage_root: str | Path | None = None,
    ):
        normalized_account_id = str(account_id or "").strip()
        if not _SAFE_ACCOUNT_ID_RE.fullmatch(normalized_account_id):
            raise ValueError("account_id contains unsupported characters")
        self.account_id = normalized_account_id
        selected_root = storage_root if storage_root is not None else root
        requested_root = (
            Path(selected_root).expanduser()
            if selected_root
            else Path.home() / ".shorts_thread_maker" / "queues"
        ).absolute()
        self.root = requested_root
        self.path = self.root / (self.account_id + ".json")
        self._lock = threading.RLock()
        self._recovery_required = False
        self._recovery_reason: str | None = None
        self._disk_identity: tuple[int, int, int, int] | None = None
        self._file_was_observed = False

        try:
            root_stat = requested_root.lstat()
        except FileNotFoundError:
            try:
                # Another store may create the same root after our lstat.  The
                # lstat/type/inode checks below still reject unsafe outcomes.
                requested_root.mkdir(parents=True, exist_ok=True)
                root_stat = requested_root.lstat()
            except OSError:
                self._state = self._default_state()
                self._enter_recovery_required("queue_directory_unavailable")
                return
        except OSError:
            self._state = self._default_state()
            self._enter_recovery_required("queue_directory_unavailable")
            return

        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            self._state = self._default_state()
            self._enter_recovery_required("queue_directory_type_invalid")
            return

        try:
            canonical_root = requested_root.resolve(strict=True)
            confirmed_stat = requested_root.lstat()
        except OSError:
            self._state = self._default_state()
            self._enter_recovery_required("queue_directory_unavailable")
            return
        if (
            stat.S_ISLNK(confirmed_stat.st_mode)
            or not stat.S_ISDIR(confirmed_stat.st_mode)
            or (int(confirmed_stat.st_dev), int(confirmed_stat.st_ino))
            != (int(root_stat.st_dev), int(root_stat.st_ino))
        ):
            self._state = self._default_state()
            self._enter_recovery_required("queue_directory_changed")
            return

        self.root = canonical_root
        self.path = canonical_root / (self.account_id + ".json")
        self._lock = _lock_for_path(self.path)
        with self._lock:
            if not secure_dir_permissions(self.root):
                self._state = self._default_state()
                self._enter_recovery_required("queue_directory_permissions_invalid")
            else:
                self._state = self._load(allow_missing=True)

    def _default_state(self) -> dict[str, Any]:
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

    def _load(self, *, allow_missing: bool = False) -> dict[str, Any]:
        state = self._default_state()
        try:
            path_stat = self.path.stat()
        except FileNotFoundError:
            if not allow_missing or self._file_was_observed:
                self._enter_recovery_required("queue_file_disappeared")
                return state
            self._disk_identity = None
            return state
        except OSError:
            self._enter_recovery_required("queue_file_read_failed")
            return state

        self._file_was_observed = True
        self._disk_identity = self._identity_from_stat(path_stat)

        if not stat.S_ISREG(path_stat.st_mode) or self.path.is_symlink():
            self._enter_recovery_required("queue_file_type_invalid")
            return state
        if not secure_file_permissions(self.path):
            self._enter_recovery_required("queue_file_permissions_invalid")
            return state
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            self._enter_recovery_required("queue_file_read_failed")
            return state

        if not self._is_valid_state(loaded):
            self._enter_recovery_required("queue_schema_invalid")
            return state
        return loaded

    @staticmethod
    def _identity_from_stat(path_stat: os.stat_result) -> tuple[int, int, int, int]:
        return (
            int(path_stat.st_dev),
            int(path_stat.st_ino),
            int(path_stat.st_mtime_ns),
            int(path_stat.st_size),
        )

    def _current_disk_identity(self) -> tuple[int, int, int, int] | None:
        try:
            return self._identity_from_stat(self.path.stat())
        except FileNotFoundError:
            return None
        except OSError as exc:
            self._enter_recovery_required("queue_file_read_failed")
            raise QueueStateRecoveryRequired(
                f"{_RECOVERY_BLOCK_REASON}: queue_file_read_failed"
            ) from exc

    def _prepare_mutation(self) -> None:
        """Refresh a concurrently replaced file before applying a mutation."""
        self.assert_mutable()
        current_identity = self._current_disk_identity()
        if current_identity == self._disk_identity:
            return
        if current_identity is None:
            if self._file_was_observed:
                self._enter_recovery_required("queue_file_disappeared")
                raise QueueStateRecoveryRequired(
                    f"{_RECOVERY_BLOCK_REASON}: queue_file_disappeared"
                )
            return

        self._state = self._load(allow_missing=False)
        self.assert_mutable()

    def _is_valid_state(self, loaded: Any) -> bool:
        """Validate persisted state without repairing or discarding any fields."""
        if not isinstance(loaded, dict):
            return False
        required = {
            "version",
            "account_id",
            "pending_items",
            "processed_urls",
            "phase",
            "next_allowed_at",
            "stats",
            "current_item",
            "last_error",
            "stop_requested",
        }
        if not required.issubset(loaded):
            return False
        if loaded.get("version") != self.VERSION:
            return False
        if loaded.get("account_id") != self.account_id:
            return False
        if loaded.get("phase") not in VALID_PHASES:
            return False
        if not isinstance(loaded.get("stop_requested"), bool):
            return False
        if loaded.get("next_allowed_at") is not None and not isinstance(
            loaded.get("next_allowed_at"), (str, int, float)
        ):
            return False
        if loaded.get("last_error") is not None and not isinstance(
            loaded.get("last_error"), str
        ):
            return False

        pending_items = loaded.get("pending_items")
        current_item = loaded.get("current_item")
        if not isinstance(pending_items, list):
            return False
        if current_item is not None and not isinstance(current_item, dict):
            return False
        if not all(self._is_valid_item(item) for item in pending_items):
            return False
        if current_item is not None and not self._is_valid_item(current_item):
            return False

        processed_urls = loaded.get("processed_urls")
        if not isinstance(processed_urls, list) or not all(
            isinstance(url, str) and bool(url.strip()) for url in processed_urls
        ):
            return False

        stats = loaded.get("stats")
        if not isinstance(stats, dict):
            return False
        for key in ("success", "failed", "skipped"):
            value = stats.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return False
        return True

    @staticmethod
    def _is_valid_item(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        return all(
            isinstance(item.get(key), str) and bool(item[key].strip())
            for key in ("item_id", "url", "created_at", "idempotency_key")
        )

    def _enter_recovery_required(self, reason: str) -> None:
        self._recovery_required = True
        self._recovery_reason = str(reason or _RECOVERY_BLOCK_REASON)

    @property
    def recovery_required(self) -> bool:
        with self._lock:
            return self._recovery_required

    @property
    def recovery_reason(self) -> str | None:
        with self._lock:
            return self._recovery_reason

    def assert_mutable(self) -> None:
        with self._lock:
            if self._recovery_required:
                raise QueueStateRecoveryRequired(
                    f"{_RECOVERY_BLOCK_REASON}: {self._recovery_reason or 'unknown'}"
                )

    @staticmethod
    def _fsync_parent_directory(path: Path) -> None:
        """Persist a directory entry where the platform supports directory fsync."""
        if os.name == "nt":
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _save(self) -> None:
        self.assert_mutable()
        if not secure_dir_permissions(self.root):
            raise QueuePersistenceError("queue directory permissions could not be secured")

        temp_path: Path | None = None
        published = False
        try:
            descriptor, temp_name = tempfile.mkstemp(
                dir=self.root,
                prefix=self.account_id + ".",
                suffix=".tmp",
            )
            temp_path = Path(temp_name)
            os.close(descriptor)
            if not secure_file_permissions(temp_path):
                raise QueuePersistenceError(
                    "temporary queue file permissions could not be secured"
                )
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(self._state, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.replace(temp_path, self.path)
                published = True
            except Exception as exc:
                # A replacement error is treated as an uncertain publication
                # boundary.  Never allow another mutation over that ambiguity.
                self._enter_recovery_required("queue_publish_outcome_unknown")
                raise QueueStateRecoveryRequired(
                    f"{_RECOVERY_BLOCK_REASON}: queue_publish_outcome_unknown"
                ) from exc

            try:
                if not secure_file_permissions(self.path):
                    raise QueuePersistenceError(
                        "published queue file permissions could not be secured"
                    )
                # Windows requires a writable descriptor for ``os.fsync``.
                # ``r+b`` does not modify content and works on both platforms.
                with self.path.open("r+b") as handle:
                    os.fsync(handle.fileno())
                self._fsync_parent_directory(self.root)
                self._disk_identity = self._identity_from_stat(self.path.stat())
                self._file_was_observed = True
            except Exception as exc:
                self._enter_recovery_required("queue_publish_durability_unknown")
                raise QueueStateRecoveryRequired(
                    f"{_RECOVERY_BLOCK_REASON}: queue_publish_durability_unknown"
                ) from exc
        finally:
            if not published and temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    # The temp file was ACL-restricted before content was
                    # written, so cleanup failure must not hide the root cause.
                    pass

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._state)
            snapshot["recovery_required"] = self._recovery_required
            snapshot["recovery_reason"] = self._recovery_reason
            if self._recovery_required:
                snapshot["phase"] = "blocked"
                snapshot["last_error"] = _RECOVERY_BLOCK_REASON
                snapshot["stop_requested"] = True
                snapshot["blocked_reason"] = _RECOVERY_BLOCK_REASON
            return snapshot

    def get_state(self) -> AccountQueueState:
        with self._lock:
            return AccountQueueState.from_dict(self.snapshot())

    # Alias useful to consumers that call their serialized state a restore.
    restore = snapshot

    def enqueue(self, url: str, **payload: Any) -> dict[str, Any]:
        """Append a stable queue item and return its copy."""
        text = str(url or "").strip()
        if not text:
            raise ValueError("url is required")
        with self._lock:
            self._prepare_mutation()
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
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def enqueue_many(self, urls: Iterable[str]) -> list[dict[str, Any]]:
        return [self.enqueue(url) for url in urls]

    def reserve_next(self) -> dict[str, Any] | None:
        """Mark the next pending item current without removing it (crash safe)."""
        with self._lock:
            self._prepare_mutation()
            if self._state["stop_requested"] or self._state["current_item"]:
                return None
            previous = copy.deepcopy(self._state)
            if not self._state["pending_items"]:
                self._state["phase"] = "idle"
                try:
                    self._save()
                except QueueStateRecoveryRequired:
                    raise
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
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def update_current(self, **changes: Any) -> dict[str, Any] | None:
        """Atomically persist transaction metadata for the current item."""
        protected = {"item_id", "url", "created_at"}
        if protected.intersection(changes):
            raise ValueError("stable current item fields cannot be changed")
        with self._lock:
            self._prepare_mutation()
            item = self._state["current_item"]
            if item is None:
                return None
            previous = copy.deepcopy(self._state)
            item.update(copy.deepcopy(changes))
            try:
                self._save()
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def complete_current(self, outcome: str = "success", error: str | None = None) -> dict[str, Any] | None:
        if outcome not in {"success", "failed", "skipped"}:
            raise ValueError("outcome must be success, failed, or skipped")
        with self._lock:
            self._prepare_mutation()
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
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def requeue_current(self) -> dict[str, Any] | None:
        with self._lock:
            self._prepare_mutation()
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
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
            return copy.deepcopy(item)

    def set_phase(
        self,
        phase: str,
        *,
        next_allowed_at: str | float | None = None,
        last_error: str | None = None,
    ) -> None:
        if phase not in VALID_PHASES:
            raise ValueError("invalid queue phase")
        with self._lock:
            self._prepare_mutation()
            previous = copy.deepcopy(self._state)
            self._state["phase"] = phase
            self._state["next_allowed_at"] = next_allowed_at
            self._state["last_error"] = last_error
            try:
                self._save()
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise

    def request_stop(self, requested: bool = True) -> None:
        with self._lock:
            self._prepare_mutation()
            previous = copy.deepcopy(self._state)
            self._state["stop_requested"] = bool(requested)
            if requested:
                self._state["phase"] = "stopped"
            try:
                self._save()
            except QueueStateRecoveryRequired:
                raise
            except Exception:
                self._state = previous
                raise
