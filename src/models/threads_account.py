"""Persistent model for a Threads upload account.

Account and profile identifiers deliberately do not derive from a username.  A
username can be corrected later without losing its browser session or history.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import re
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import UUID, uuid4


_USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")


def normalize_threads_username(value: object) -> str:
    """Return a canonical Threads username, accepting handles and profile URLs.

    Invalid input is rejected instead of silently changing it: accepting
    ``a!b`` as ``ab`` could connect an account to the wrong profile.
    """
    candidate = str(value or "").strip()
    if not candidate:
        return ""

    if "://" in candidate:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        if host not in {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}:
            raise ValueError("expected_username must be a Threads username or profile URL")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("Threads profile URL does not contain a username")
        candidate = parts[-1]

    if candidate.startswith("@"):
        candidate = candidate[1:]
    candidate = candidate.strip().lower()
    if not _USERNAME_RE.fullmatch(candidate):
        raise ValueError("expected_username must contain only letters, numbers, periods, or underscores")
    return candidate


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_account_id() -> str:
    return str(uuid4())


def _new_profile_id(account_id: str) -> str:
    return "threads_" + str(UUID(account_id))


@dataclass(frozen=True, slots=True)
class ThreadsAccount:
    """An account's persistent, non-secret configuration.

    ``account_id`` and ``profile_id`` are frozen identifiers.  Use
    :meth:`updated` for mutable account settings; attempts to replace either
    stable identifier are rejected.
    """

    account_id: str
    profile_id: str
    expected_username: str
    display_name: str = ""
    enabled: bool = True
    upload_interval: int = 60
    created_at: str = ""
    updated_at: str = ""
    last_verified_username: str = ""
    last_verified_at: str = ""

    def __post_init__(self) -> None:
        try:
            account_id = str(UUID(str(self.account_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("account_id must be a UUID") from exc
        if not str(self.profile_id or "").strip():
            raise ValueError("profile_id is required")

        expected_username = normalize_threads_username(self.expected_username)
        if not expected_username:
            raise ValueError("expected_username is required")
        verified = str(self.last_verified_username or "").strip()
        if verified:
            verified = normalize_threads_username(verified)

        interval = int(self.upload_interval)
        if interval < 30:
            raise ValueError("upload_interval must be at least 30 seconds")

        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "profile_id", str(self.profile_id).strip())
        object.__setattr__(self, "expected_username", expected_username)
        object.__setattr__(self, "display_name", str(self.display_name or "").strip())
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "upload_interval", interval)
        object.__setattr__(self, "last_verified_username", verified)

    @classmethod
    def create(cls, expected_username: object, **values: Any) -> "ThreadsAccount":
        account_id = str(values.pop("account_id", "") or _new_account_id())
        profile_id = str(values.pop("profile_id", "") or _new_profile_id(account_id))
        now = _utc_now()
        return cls(
            account_id=account_id,
            profile_id=profile_id,
            expected_username=expected_username,
            created_at=str(values.pop("created_at", "") or now),
            updated_at=str(values.pop("updated_at", "") or now),
            **values,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "ThreadsAccount":
        if not isinstance(values, Mapping):
            raise ValueError("Threads account must be an object")
        return cls.create(**dict(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "expected_username": self.expected_username,
            "enabled": self.enabled,
            "upload_interval": self.upload_interval,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_verified_username": self.last_verified_username,
            "last_verified_at": self.last_verified_at,
        }

    def updated(self, **changes: Any) -> "ThreadsAccount":
        forbidden = {"account_id", "profile_id"}.intersection(changes)
        if forbidden:
            raise ValueError("account_id and profile_id are immutable")
        changes["updated_at"] = _utc_now()
        return replace(self, **changes)
