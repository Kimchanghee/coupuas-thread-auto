# -*- coding: utf-8 -*-
"""Runtime security hardening for packaged (frozen) builds."""

from __future__ import annotations

import csv
import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


class RuntimeSecurityError(RuntimeError):
    """Raised when runtime security policy validation fails."""


_SUSPICIOUS_ENV_VARS = (
    "PYTHONINSPECT",
    "PYTHONBREAKPOINT",
    "PYTHONDEBUG",
    "PYTHONVERBOSE",
    "THREAD_AUTO_ALLOW_CLIENT_IP_OVERRIDE",
    "THREAD_AUTO_LOAD_EXTERNAL_ENV",
    "THREAD_AUTO_TRUST_EXTERNAL_ENV",
    "COUPUAS_ALLOW_UNPINNED_UPDATER_SIGNER",
    "THREAD_AUTO_SECURITY_BYPASS",
)

_SUSPICIOUS_PROCESS_NAMES = {
    "x64dbg.exe",
    "x32dbg.exe",
    "ida64.exe",
    "ida.exe",
    "idaq64.exe",
    "idaq.exe",
    "ollydbg.exe",
    "dnspy.exe",
    "procmon.exe",
    "procexp.exe",
    "wireshark.exe",
    "fiddler.exe",
}


def _is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False))


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _is_debugger_attached() -> bool:
    if not _is_windows():
        return False

    try:
        if bool(ctypes.windll.kernel32.IsDebuggerPresent()):
            return True
    except Exception:
        pass

    try:
        kernel32 = ctypes.windll.kernel32
        current_process = kernel32.GetCurrentProcess()
        debug_flag = ctypes.c_int(0)
        success = kernel32.CheckRemoteDebuggerPresent(
            current_process,
            ctypes.byref(debug_flag),
        )
        if success and bool(debug_flag.value):
            return True
    except Exception:
        pass

    return False


def _find_suspicious_env_var() -> str:
    for key in _SUSPICIOUS_ENV_VARS:
        value = str(os.getenv(key, "")).strip()
        if not value:
            continue
        if value.lower() in {"0", "false", "no", "off"}:
            continue
        return key
    return ""


def _list_process_names() -> set[str]:
    if not _is_windows():
        return set()

    try:
        completed = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except Exception:
        return set()

    names: set[str] = set()
    reader = csv.reader(line for line in completed.stdout.splitlines() if line.strip())
    for row in reader:
        if not row:
            continue
        raw_name = str(row[0] or "").strip().strip('"')
        if not raw_name:
            continue
        names.add(Path(raw_name).name.lower())
    return names


def _find_suspicious_process_name() -> str:
    names = _list_process_names()
    for proc_name in sorted(_SUSPICIOUS_PROCESS_NAMES):
        if proc_name in names:
            return proc_name
    return ""


def assess_runtime_security() -> Tuple[bool, str]:
    """
    Return (is_safe, reason).

    For development/source mode, checks are bypassed.
    """
    if not _is_frozen_build():
        return True, ""

    # Emergency override for support scenarios.
    if str(os.getenv("THREAD_AUTO_ALLOW_ANALYSIS_MODE", "")).strip() == "1":
        return True, ""

    if _is_debugger_attached():
        return False, "디버거가 감지되었습니다."

    env_key = _find_suspicious_env_var()
    if env_key:
        return False, f"보안 우회 환경변수가 감지되었습니다: {env_key}"

    proc_name = _find_suspicious_process_name()
    if proc_name:
        return False, f"분석 도구 프로세스가 감지되었습니다: {proc_name}"

    return True, ""


def enforce_runtime_security() -> None:
    safe, reason = assess_runtime_security()
    if safe:
        return
    raise RuntimeSecurityError(f"실행 환경 보안 점검 실패: {reason}")
