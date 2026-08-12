"""Filesystem permission hardening helpers."""

from __future__ import annotations

import ctypes
import getpass
import logging
import os
import re
import json
import threading
import time
from collections import OrderedDict
from ctypes import wintypes
from pathlib import Path
from typing import Optional, Tuple, Union

from src.system_process import run_system_command

PathLike = Union[str, Path]
FileIdentity = Tuple[bool, int, int]

logger = logging.getLogger(__name__)

_CACHE_LIMIT = 256
_BACKOFF_INITIAL_SECONDS = 5.0
_BACKOFF_MAX_SECONDS = 300.0

_principal: Optional[str] = None
_principal_resolved = False
_principal_lock = threading.Lock()
_state_lock = threading.Lock()
_successful: "OrderedDict[FileIdentity, None]" = OrderedDict()
_failures: "OrderedDict[FileIdentity, Tuple[int, float]]" = OrderedDict()
_inflight: dict[FileIdentity, threading.Event] = {}
_SID_PRINCIPAL_PATTERN = re.compile(r"^\*S-\d+(?:-\d+)+$")


def _to_path(value: PathLike) -> Path:
    return value if isinstance(value, Path) else Path(str(value))


def _native_current_user_sid() -> Optional[str]:
    """Resolve the process token SID without spawning a console process."""
    if os.name != "nt":
        return None

    token = wintypes.HANDLE()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    TOKEN_QUERY = 0x0008
    TOKEN_USER = 1
    ERROR_INSUFFICIENT_BUFFER = 122

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        return None
    try:
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(needed))
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not needed.value:
            return None
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token, TOKEN_USER, buffer, needed.value, ctypes.byref(needed)
        ):
            return None

        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_text)):
            return None
        try:
            value = sid_text.value
            return f"*{value}" if value and value.startswith("S-1-") else None
        finally:
            kernel32.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))
    finally:
        kernel32.CloseHandle(token)


def _resolve_current_user_principal() -> str:
    global _principal, _principal_resolved
    if _principal_resolved:
        return _principal or ""
    with _principal_lock:
        if _principal_resolved:
            return _principal or ""
        principal: Optional[str] = None
        try:
            principal = _native_current_user_sid()
        except Exception:
            logger.debug("filesystem_acl_sid_native_failed", exc_info=True)
        if not principal:
            try:
                completed = run_system_command(
                    "whoami.exe",
                    ["/user", "/fo", "csv", "/nh"],
                    operation="resolve_current_user_sid",
                    timeout=5,
                )
                text = (completed.stdout or "").strip()
                if text:
                    parts = [item.strip().strip('"') for item in text.split(",")]
                    if len(parts) >= 2 and parts[1].startswith("S-1-"):
                        principal = f"*{parts[1]}"
            except Exception:
                logger.warning("filesystem_acl_sid_command_failed", exc_info=True)
        if not principal:
            principal = str(os.environ.get("USERNAME") or getpass.getuser() or "").strip()
        _principal = principal
        _principal_resolved = True
        return principal


def _file_identity(path: Path, is_dir: bool) -> Optional[FileIdentity]:
    try:
        stat = path.stat()
        return (is_dir, int(stat.st_dev), int(stat.st_ino))
    except OSError:
        return None


def _remember_bounded(cache: OrderedDict, key, value) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


def _apply_windows_acl_native(path: Path, is_dir: bool, principal: str) -> bool:
    """Apply a protected DACL through Win32, avoiding an external process."""
    if os.name != "nt" or not _SID_PRINCIPAL_PATTERN.fullmatch(principal):
        return False

    class TRUSTEE_W(ctypes.Structure):
        _fields_ = [
            ("pMultipleTrustee", ctypes.c_void_p),
            ("MultipleTrusteeOperation", wintypes.DWORD),
            ("TrusteeForm", wintypes.DWORD),
            ("TrusteeType", wintypes.DWORD),
            ("ptstrName", wintypes.LPWSTR),
        ]

    class EXPLICIT_ACCESS_W(ctypes.Structure):
        _fields_ = [
            ("grfAccessPermissions", wintypes.DWORD),
            ("grfAccessMode", wintypes.DWORD),
            ("grfInheritance", wintypes.DWORD),
            ("Trustee", TRUSTEE_W),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.SetEntriesInAclW.argtypes = [
        wintypes.ULONG,
        ctypes.POINTER(EXPLICIT_ACCESS_W),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.SetEntriesInAclW.restype = wintypes.DWORD
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    sid_strings = [principal[1:], "S-1-5-18", "S-1-5-32-544"]
    sid_pointers: list[ctypes.c_void_p] = []
    acl = ctypes.c_void_p()
    try:
        for sid_string in sid_strings:
            sid = ctypes.c_void_p()
            if not advapi32.ConvertStringSidToSidW(sid_string, ctypes.byref(sid)):
                return False
            sid_pointers.append(sid)

        entries = (EXPLICIT_ACCESS_W * len(sid_pointers))()
        inheritance = 0x3 if is_dir else 0  # container + object inheritance
        for index, sid in enumerate(sid_pointers):
            entries[index].grfAccessPermissions = 0x001F01FF  # FILE_ALL_ACCESS
            entries[index].grfAccessMode = 2  # SET_ACCESS
            entries[index].grfInheritance = inheritance
            entries[index].Trustee.TrusteeForm = 0  # TRUSTEE_IS_SID
            entries[index].Trustee.TrusteeType = 0  # TRUSTEE_IS_UNKNOWN
            entries[index].Trustee.ptstrName = ctypes.cast(sid, wintypes.LPWSTR)

        if advapi32.SetEntriesInAclW(len(entries), entries, None, ctypes.byref(acl)):
            return False
        status = advapi32.SetNamedSecurityInfoW(
            str(path),
            1,  # SE_FILE_OBJECT
            0x4 | 0x80000000,  # DACL + protected DACL
            None,
            None,
            acl,
            None,
        )
        return status == 0
    except Exception:
        logger.debug("filesystem_acl_native_failed", exc_info=True)
        return False
    finally:
        if acl.value:
            kernel32.LocalFree(acl)
        for sid in sid_pointers:
            if sid.value:
                kernel32.LocalFree(sid)


def _apply_windows_acl(path: Path, is_dir: bool) -> bool:
    identity = _file_identity(path, is_dir)
    if identity is None:
        return False

    # Only one thread applies permissions to a particular filesystem object.
    attempt = 1
    while True:
        with _state_lock:
            if identity in _successful:
                _successful.move_to_end(identity)
                return True
            failure = _failures.get(identity)
            if failure and time.monotonic() < failure[1]:
                return False
            if failure:
                attempt = min(failure[0] + 1, 16)
            pending = _inflight.get(identity)
            if pending is None:
                pending = threading.Event()
                _inflight[identity] = pending
                break
        pending.wait()

    success = False
    returncode: Optional[int] = None
    correlation_id = f"acl-{identity[1]:x}-{identity[2]:x}-{attempt}"
    try:
        principal = _resolve_current_user_principal()
        if not principal:
            return False
        success = _apply_windows_acl_native(path, is_dir, principal)
        if not success:
            user_acl = f"{principal}:(OI)(CI)F" if is_dir else f"{principal}:(F)"
            completed = run_system_command(
                "icacls.exe",
                [
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    user_acl,
                    "/grant:r",
                    "*S-1-5-18:(F)",
                    "/grant:r",
                    "*S-1-5-32-544:(F)",
                ],
                operation="apply_filesystem_acl",
                timeout=15,
                process_attempt=attempt,
                correlation_id=correlation_id,
            )
            returncode = completed.returncode
            success = returncode == 0
        return success
    except Exception:
        logger.warning(
            "filesystem_acl_command_failed %s",
            json.dumps(
                {
                    "target": str(path),
                    "target_kind": "directory" if is_dir else "file",
                    "attempt": attempt,
                    "correlation_id": correlation_id,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            extra={"target_kind": "directory" if is_dir else "file"},
            exc_info=True,
        )
        return False
    finally:
        with _state_lock:
            if success:
                _remember_bounded(_successful, identity, None)
                _failures.pop(identity, None)
            else:
                delay = min(
                    _BACKOFF_INITIAL_SECONDS * (2 ** (attempt - 1)),
                    _BACKOFF_MAX_SECONDS,
                )
                _remember_bounded(_failures, identity, (attempt, time.monotonic() + delay))
            event = _inflight.pop(identity)
            event.set()
        logger.log(
            logging.DEBUG if success else logging.WARNING,
            "filesystem_acl_result %s",
            json.dumps(
                {
                    "target": str(path),
                    "target_kind": "directory" if is_dir else "file",
                    "returncode": returncode,
                    "attempt": attempt,
                    "correlation_id": correlation_id,
                    "success": success,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            extra={
                "target_kind": "directory" if is_dir else "file",
                "returncode": returncode,
                "attempt": attempt,
                "success": success,
            },
        )


def secure_dir_permissions(path: PathLike) -> bool:
    target = _to_path(path)
    if not target.exists():
        return False
    try:
        if os.name == "nt":
            return _apply_windows_acl(target, is_dir=True)
        os.chmod(target, 0o700)
        return True
    except Exception:
        return False


def secure_file_permissions(path: PathLike) -> bool:
    target = _to_path(path)
    if not target.exists():
        return False
    try:
        if os.name == "nt":
            return _apply_windows_acl(target, is_dir=False)
        os.chmod(target, 0o600)
        return True
    except Exception:
        return False
