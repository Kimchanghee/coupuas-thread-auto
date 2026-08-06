# -*- coding: utf-8 -*-
"""Process-wide single instance guard for the desktop app."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import Optional, Tuple


_MUTEX_NAME = "Local\\CoupuasThreadAutoSingleInstance"
_ERROR_ALREADY_EXISTS = 183
_APP_WINDOW_TITLE_PARTS = (
    "Coupang Partners Thread Automation",
    "스레드 쇼핑 자동화 - 로그인",
    "쇼츠스레드메이커 - 로그인",
)


def _is_app_window_title(title: str) -> bool:
    text = str(title or "").strip()
    return any(part in text for part in _APP_WINDOW_TITLE_PARTS)


@dataclass
class SingleInstanceGuard:
    """Keep the acquired mutex handle alive for the process lifetime."""

    already_running: bool
    reason: str = ""
    existing_hwnd: Optional[int] = None
    _mutex_handle: Optional[int] = None

    def activate_existing_window(self) -> bool:
        if os.name != "nt" or not self.existing_hwnd:
            return False

        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.existing_hwnd)
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            return bool(user32.SetForegroundWindow(hwnd))
        except Exception:
            return False

    def release(self) -> None:
        if os.name == "nt" and self._mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(int(self._mutex_handle))
            except Exception:
                pass
            self._mutex_handle = None

    def __del__(self) -> None:
        self.release()


def _find_existing_app_window() -> Optional[Tuple[int, str]]:
    if os.name != "nt":
        return None

    current_pid = os.getpid()
    matches = []

    try:
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            proc_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == current_pid:
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if _is_app_window_title(title):
                matches.append((int(hwnd), title))
                return False
            return True

        user32.EnumWindows(enum_proc(callback), 0)
    except Exception:
        return None

    return matches[0] if matches else None


def _create_windows_mutex() -> Tuple[bool, Optional[int]]:
    if os.name != "nt":
        return True, None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return True, None

    last_error = ctypes.get_last_error()
    if last_error == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False, None

    return True, int(handle)


def acquire_single_instance_guard() -> SingleInstanceGuard:
    existing = _find_existing_app_window()
    if existing:
        hwnd, title = existing
        return SingleInstanceGuard(
            already_running=True,
            reason=f"window:{title}",
            existing_hwnd=hwnd,
        )

    acquired, handle = _create_windows_mutex()
    if not acquired:
        existing = _find_existing_app_window()
        return SingleInstanceGuard(
            already_running=True,
            reason="mutex",
            existing_hwnd=existing[0] if existing else None,
        )

    return SingleInstanceGuard(already_running=False, _mutex_handle=handle)
