"""Safe subprocess helpers for GUI and frozen application builds."""

from __future__ import annotations

import contextlib
import ctypes
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence


logger = logging.getLogger(__name__)
_DLL_DIRECTORY_LOCK = threading.RLock()
_MAX_LOG_OUTPUT = 2_000
_SEM_NOGPFAULTERRORBOX = 0x0002

_SENSITIVE_PROCESS_PATTERNS = (
    re.compile(r"(\bbearer\s+)([^\s,;]+)", re.IGNORECASE),
    re.compile(
        r"((?:password|passwd|pwd|token|access_token|refresh_token|api[_-]?key|secret|authorization|cookie)\s*[:=]\s*)(?:'[^']*'|\"[^\"]*\"|[^,\s}\]]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(--(?:password|passwd|pwd|token|access-token|refresh-token|api-key|secret|authorization|cookie)(?:=|\s+))([^\s]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(://[^\s/:@]+:)([^\s/@]+)(@)", re.IGNORECASE),
)
_SENSITIVE_ARGUMENT = re.compile(
    r"^--?(?:password|passwd|pwd|token|access-token|refresh-token|api-key|secret|authorization|cookie)$",
    re.IGNORECASE,
)

_PYTHON_ENV_NAMES = {
    "__PYVENV_LAUNCHER__",
    "_MEIPASS2",
    "PYTHONBREAKPOINT",
    "PYTHONDEBUG",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONEXECUTABLE",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUNBUFFERED",
    "PYTHONVERBOSE",
}


def resolve_system_executable(name: str) -> str:
    """Return an absolute path for a Windows system executable."""
    value = str(name or "").strip()
    if not value:
        raise ValueError("System executable name is required")
    if os.name != "nt":
        return value

    basename = Path(value).name
    if basename != value or any(separator in value for separator in ("/", "\\")):
        raise ValueError("System executable must be a basename")
    if basename.lower() in {"powershell", "powershell.exe"}:
        relative = Path("WindowsPowerShell") / "v1.0" / "powershell.exe"
    else:
        relative = Path(basename if Path(basename).suffix else f"{basename}.exe")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetSystemWindowsDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32_768)
    length = kernel32.GetSystemWindowsDirectoryW(buffer, len(buffer))
    if not length or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "Unable to resolve the Windows directory")
    system_root = Path(buffer.value)
    return str((system_root / "System32" / relative).resolve(strict=False))


def sanitized_environment(
    env: Optional[Mapping[str, object]] = None,
) -> dict[str, str]:
    """Copy an environment without Python/PyInstaller loader state."""
    source = os.environ if env is None else env
    cleaned: dict[str, str] = {}
    for raw_key, raw_value in source.items():
        key = str(raw_key)
        upper_key = key.upper()
        if (
            upper_key in _PYTHON_ENV_NAMES
            or upper_key.startswith("_PYI_")
            or upper_key.startswith("PYINSTALLER_")
        ):
            continue
        cleaned[key] = str(raw_value)

    # PyInstaller may save the original loader path on POSIX. External tools
    # must see that value, not the bundle's temporary library directory.
    original_library_path = source.get("LD_LIBRARY_PATH_ORIG")
    if original_library_path is not None:
        cleaned["LD_LIBRARY_PATH"] = str(original_library_path)
    cleaned.pop("LD_LIBRARY_PATH_ORIG", None)

    bundle_dir = str(getattr(sys, "_MEIPASS", "") or "").strip()
    if bundle_dir and "PATH" in cleaned:
        try:
            bundle_path = Path(bundle_dir).resolve(strict=False)
            cleaned["PATH"] = os.pathsep.join(
                entry
                for entry in cleaned["PATH"].split(os.pathsep)
                if entry
                and Path(entry).resolve(strict=False) != bundle_path
            )
        except (OSError, ValueError):
            pass
    return cleaned


def _windows_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


@contextlib.contextmanager
def _clean_windows_dll_directory() -> Iterator[None]:
    """Temporarily isolate Windows loader/error state while spawning."""
    if os.name != "nt":
        yield
        return

    with _DLL_DIRECTORY_LOCK:
        kernel32 = ctypes.windll.kernel32
        previous: Optional[str] = None
        previous_error_mode: Optional[int] = None
        try:
            for function, argtypes, restype in (
                (
                    kernel32.GetDllDirectoryW,
                    [wintypes.DWORD, wintypes.LPWSTR],
                    wintypes.DWORD,
                ),
                (kernel32.SetDllDirectoryW, [wintypes.LPCWSTR], wintypes.BOOL),
                (kernel32.GetErrorMode, [], wintypes.DWORD),
                (kernel32.SetErrorMode, [wintypes.DWORD], wintypes.DWORD),
            ):
                # ctypes functions allow prototypes; lightweight test doubles may not.
                if hasattr(function, "argtypes"):
                    function.argtypes = argtypes
                    function.restype = restype
            if getattr(sys, "frozen", False):
                size = int(kernel32.GetDllDirectoryW(0, None))
                if size:
                    buffer = ctypes.create_unicode_buffer(size + 1)
                    kernel32.GetDllDirectoryW(len(buffer), buffer)
                    previous = buffer.value or None
                if not kernel32.SetDllDirectoryW(None):
                    raise ctypes.WinError()
            previous_error_mode = int(kernel32.GetErrorMode())
            kernel32.SetErrorMode(previous_error_mode | _SEM_NOGPFAULTERRORBOX)
            yield
        finally:
            if previous_error_mode is not None:
                kernel32.SetErrorMode(previous_error_mode)
            if getattr(sys, "frozen", False):
                kernel32.SetDllDirectoryW(previous)


def _prepare_command(
    args: Sequence[object],
    *,
    system_command: bool,
) -> list[str]:
    command = [os.fspath(item) if isinstance(item, os.PathLike) else str(item) for item in args]
    if not command:
        raise ValueError("Process command cannot be empty")
    if system_command:
        command[0] = resolve_system_executable(command[0])
    return command


def _log_failure(
    log: logging.Logger,
    *,
    operation: str,
    command: Sequence[str],
    duration_ms: int,
    return_code: Optional[int],
    stdout: object = "",
    stderr: object = "",
    error: object = "",
    attempt: int = 1,
    correlation_id: str = "",
) -> None:
    def safe_text(value: object) -> str:
        text = str(value or "")
        for pattern in _SENSITIVE_PROCESS_PATTERNS:
            if pattern.groups == 3:
                text = pattern.sub(r"\1[REDACTED]\3", text)
            else:
                text = pattern.sub(r"\1[REDACTED]", text)
        return text[-_MAX_LOG_OUTPUT:]

    redacted_command = []
    redact_next = False
    for item in command:
        raw_item = str(item)
        if redact_next:
            redacted_command.append("[REDACTED]")
            redact_next = False
            continue
        redacted_command.append(safe_text(raw_item))
        redact_next = bool(_SENSITIVE_ARGUMENT.fullmatch(raw_item))

    executable = redacted_command[0] if redacted_command else ""
    safe_operation = safe_text(operation)
    safe_stdout = safe_text(stdout)
    safe_stderr = safe_text(stderr)
    safe_error = safe_text(error)
    return_code_hex = (
        f"0x{(return_code & 0xFFFFFFFF):08X}"
        if isinstance(return_code, int)
        else ""
    )
    fields = {
        "operation": safe_operation,
        "executable": executable,
        "duration_ms": duration_ms,
        "return_code": return_code,
        "return_code_hex": return_code_hex,
        "attempt": max(1, int(attempt)),
        "correlation_id": safe_text(correlation_id),
        "arguments": redacted_command[1:],
        "stdout": safe_stdout,
        "stderr": safe_stderr,
        "error": safe_error,
    }
    log.warning(
        "external_process_failed %s",
        json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
        extra={
            "process_operation": safe_operation,
            "process_executable": executable,
            "process_duration_ms": duration_ms,
            "process_return_code": return_code,
            "process_return_code_hex": return_code_hex,
            "process_attempt": fields["attempt"],
            "process_correlation_id": fields["correlation_id"],
            "process_arguments": fields["arguments"],
            "process_stdout": safe_stdout,
            "process_stderr": safe_stderr,
            "process_error": safe_error,
        },
    )


def run_process(
    args: Sequence[object],
    *,
    system_command: bool = False,
    operation: str = "external_process",
    process_logger: Optional[logging.Logger] = None,
    process_attempt: int = 1,
    correlation_id: Optional[str] = None,
    env: Optional[Mapping[str, object]] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a process without a console window or bundled loader leakage."""
    command = _prepare_command(args, system_command=system_command)
    kwargs.pop("shell", None)
    kwargs.update(_windows_process_kwargs())
    check = bool(kwargs.pop("check", False))
    timeout = kwargs.pop("timeout", None)
    input_data = kwargs.pop("input", None)
    if input_data is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used")
        kwargs["stdin"] = subprocess.PIPE
    if kwargs.pop("capture_output", False):
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout/stderr and capture_output may not both be used")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    started = time.perf_counter()
    log = process_logger or logger
    process_correlation_id = correlation_id or uuid.uuid4().hex
    try:
        with _clean_windows_dll_directory():
            process = subprocess.Popen(
                command,
                shell=False,
                env=sanitized_environment(env),
                **kwargs,
            )
        try:
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            exc.stdout, exc.stderr = process.communicate()
            raise
        except BaseException:
            process.kill()
            process.wait()
            raise
        return_code = process.poll()
        if check and return_code:
            raise subprocess.CalledProcessError(
                return_code,
                command,
                output=stdout,
                stderr=stderr,
            )
        completed = subprocess.CompletedProcess(command, return_code, stdout, stderr)
    except Exception as exc:
        _log_failure(
            log,
            operation=operation,
            command=command,
            duration_ms=round((time.perf_counter() - started) * 1000),
            return_code=getattr(exc, "returncode", None),
            stdout=getattr(exc, "stdout", ""),
            stderr=getattr(exc, "stderr", ""),
            error=exc,
            attempt=process_attempt,
            correlation_id=process_correlation_id,
        )
        raise
    if completed.returncode:
        _log_failure(
            log,
            operation=operation,
            command=command,
            duration_ms=round((time.perf_counter() - started) * 1000),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            attempt=process_attempt,
            correlation_id=process_correlation_id,
        )
    return completed


def run_system_command(
    executable_name: str,
    args: Sequence[object] = (),
    *,
    operation: str = "system_command",
    timeout: Optional[float] = None,
    process_logger: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a System32 executable with captured, decoded output."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("errors", "replace")
    return run_process(
        [executable_name, *args],
        system_command=True,
        operation=operation,
        timeout=timeout,
        process_logger=process_logger,
        **kwargs,
    )


def popen_process(
    args: Sequence[object],
    *,
    system_command: bool = False,
    operation: str = "external_process",
    process_logger: Optional[logging.Logger] = None,
    process_attempt: int = 1,
    correlation_id: Optional[str] = None,
    env: Optional[Mapping[str, object]] = None,
    **kwargs: Any,
) -> subprocess.Popen:
    """Start a process with the same safe Windows spawning policy as run_process."""
    command = _prepare_command(args, system_command=system_command)
    kwargs.pop("shell", None)
    kwargs.update(_windows_process_kwargs())
    started = time.perf_counter()
    try:
        with _clean_windows_dll_directory():
            return subprocess.Popen(
                command,
                shell=False,
                env=sanitized_environment(env),
                **kwargs,
            )
    except Exception as exc:
        _log_failure(
            process_logger or logger,
            operation=operation,
            command=command,
            duration_ms=round((time.perf_counter() - started) * 1000),
            return_code=getattr(exc, "returncode", None),
            error=exc,
            attempt=process_attempt,
            correlation_id=correlation_id or uuid.uuid4().hex,
        )
        raise
