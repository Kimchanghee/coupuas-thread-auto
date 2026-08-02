"""Persist the small amount of state needed to resume work after an app update."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from packaging.version import InvalidVersion, Version

from src.fs_security import secure_dir_permissions, secure_file_permissions


def _version(value: str) -> Version | None:
    try:
        return Version(str(value or "").strip().lstrip("vV"))
    except InvalidVersion:
        return None


def update_completed(current_version: str, target_version: str) -> bool:
    """Return true only when the running binary reached the requested version."""
    current = _version(current_version)
    target = _version(target_version)
    return bool(current is not None and target is not None and current >= target)


def active_account_ids(snapshots: dict) -> list[str]:
    """Extract enabled/running account queues that still contain work."""
    result: list[str] = []
    for account_id, snapshot in (snapshots or {}).items():
        if not isinstance(snapshot, dict):
            continue
        pending = len(snapshot.get("pending_items") or []) + bool(snapshot.get("current_item"))
        schedule = snapshot.get("schedule")
        enabled = bool(
            getattr(schedule, "enabled", False)
            or getattr(schedule, "running", False)
            or (isinstance(schedule, dict) and (schedule.get("enabled") or schedule.get("running")))
        )
        if pending and enabled:
            normalized = str(account_id or "").strip()
            if normalized and normalized not in result:
                result.append(normalized)
    return result


class UpdateResumeStore:
    """Atomic, user-only update handoff marker."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(
        self,
        target_version: str,
        account_ids: Iterable[str],
        *,
        legacy_running: bool = False,
    ) -> dict:
        unique_ids = []
        for value in account_ids:
            normalized = str(value or "").strip()
            if normalized and normalized not in unique_ids:
                unique_ids.append(normalized)
        payload = {
            "schema": 1,
            "target_version": str(target_version or "").strip(),
            "account_ids": unique_ids,
            "legacy_running": bool(legacy_running),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if _version(payload["target_version"]) is None:
            raise ValueError("target_version must be a semantic version")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(self.path.parent)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            secure_file_permissions(temp_name)
            os.replace(temp_name, self.path)
            secure_file_permissions(self.path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        return payload

    def load(self) -> dict | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("schema") != 1:
            return None
        if _version(payload.get("target_version")) is None:
            return None
        account_ids = payload.get("account_ids")
        if not isinstance(account_ids, list):
            return None
        payload["account_ids"] = [
            value.strip() for value in account_ids if isinstance(value, str) and value.strip()
        ]
        payload["legacy_running"] = bool(payload.get("legacy_running"))
        return payload

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
