"""Shared retry classification for short-lived external service failures."""

from __future__ import annotations

import re


MAX_TRANSIENT_RETRIES = 3

_TRANSIENT_MARKERS = re.compile(
    r"(?:timed?\s*out|timeout|temporar(?:y|ily)|connection|network|dns|tls|"
    r"rate[ _-]?limit|too many requests|overloaded|service unavailable|"
    r"\b(?:429|500|502|503|504)\b)",
    re.IGNORECASE,
)


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return bool(_TRANSIENT_MARKERS.search(str(exc or "")))


def retry_delay_seconds(attempt: int) -> int:
    normalized = max(1, int(attempt or 1))
    return min(300, 15 * (2 ** (normalized - 1)))
