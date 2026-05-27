# -*- coding: utf-8 -*-
"""Shared cancellation helpers for long-running service calls."""

from __future__ import annotations

from typing import Callable, Optional


class OperationCancelled(Exception):
    """Raised when a long-running service operation should stop."""


def is_cancelled_exception(exc: BaseException) -> bool:
    """Return True for local and app-level cancellation exceptions."""
    return isinstance(exc, OperationCancelled) or exc.__class__.__name__ in {
        "CancelledException",
    }


def check_cancelled(cancel_check: Optional[Callable[[], bool]]) -> None:
    """Raise OperationCancelled when the provided callback reports cancellation."""
    if cancel_check is None:
        return
    if cancel_check():
        raise OperationCancelled("사용자에 의해 취소됨")
