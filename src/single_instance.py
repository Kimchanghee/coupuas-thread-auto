# -*- coding: utf-8 -*-
"""Process-wide single instance guard for the desktop app."""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple


_MUTEX_NAME = "Local\\CoupuasThreadAutoSingleInstance"
_ERROR_ALREADY_EXISTS = 183
_APP_WINDOW_TITLE_PARTS = (
    "Coupang Partners Thread Automation",
    "스레드 쇼핑 자동화 - 로그인",
    "쇼츠스레드메이커 - 로그인",
    "Thread Auto - 멀티 쇼핑 자동화",
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
            user32.BringWindowToTop(hwnd)
            foreground = user32.GetForegroundWindow()
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            foreground_thread = (
                user32.GetWindowThreadProcessId(foreground, None)
                if foreground
                else 0
            )
            attached_target = bool(
                target_thread
                and target_thread != current_thread
                and user32.AttachThreadInput(current_thread, target_thread, True)
            )
            attached_foreground = bool(
                foreground_thread
                and foreground_thread not in {current_thread, target_thread}
                and user32.AttachThreadInput(
                    current_thread,
                    foreground_thread,
                    True,
                )
            )
            try:
                activated = bool(user32.SetForegroundWindow(hwnd))
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)
                return activated or int(user32.GetForegroundWindow() or 0) == hwnd
            finally:
                if attached_foreground:
                    user32.AttachThreadInput(
                        current_thread,
                        foreground_thread,
                        False,
                    )
                if attached_target:
                    user32.AttachThreadInput(current_thread, target_thread, False)
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


def _process_image_path(process_id: int) -> str:
    """Best-effort executable path lookup for a foreign Windows process."""
    if os.name != "nt" or not process_id:
        return ""
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.OpenProcess(0x1000, False, int(process_id))
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return ""
        return os.path.normcase(os.path.abspath(buffer.value))
    except Exception:
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _find_existing_app_window(
    *,
    allow_process_match: bool = False,
) -> Optional[Tuple[int, str]]:
    if os.name != "nt":
        return None

    current_pid = os.getpid()
    matches = []
    current_image = os.path.normcase(os.path.abspath(sys.executable))

    try:
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd) and not allow_process_match:
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
                matches.append((2, int(hwnd), title))
                return True
            if (
                allow_process_match
                and _process_image_path(proc_id.value) == current_image
            ):
                matches.append((1, int(hwnd), title))
            return True

        user32.EnumWindows(enum_proc(callback), 0)
    except Exception:
        return None

    if not matches:
        return None
    _score, hwnd, title = max(matches, key=lambda item: item[0])
    return hwnd, title


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
        existing = _find_existing_app_window(allow_process_match=True)
        return SingleInstanceGuard(
            already_running=True,
            reason="mutex",
            existing_hwnd=existing[0] if existing else None,
        )

    return SingleInstanceGuard(already_running=False, _mutex_handle=handle)
