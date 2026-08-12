"""Exercise packaged Windows child-process and ACL paths without user interaction."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.fs_security import secure_file_permissions  # noqa: E402
from src.system_process import run_system_command  # noqa: E402


def _run_failure_diagnostic() -> dict:
    """Prove packaged failures are hidden, structured, and secret-safe."""
    handle, raw_log_path = tempfile.mkstemp(prefix="coupuas_process_smoke_", suffix=".log")
    os.close(handle)
    log_path = Path(raw_log_path)
    process_logger = logging.getLogger("src.system_process")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter("%(message)s"))
    previous_level = process_logger.level
    process_logger.setLevel(logging.WARNING)
    process_logger.addHandler(handler)
    try:
        completed = run_system_command(
            "cmd.exe",
            [
                "/d",
                "/s",
                "/c",
                "echo token=packaged-smoke-secret 1>&2 & exit /b 7",
            ],
            operation="packaged_smoke.expected_failure",
            timeout=10,
        )
    finally:
        process_logger.removeHandler(handler)
        process_logger.setLevel(previous_level)
        handler.close()

    try:
        log_text = log_path.read_text(encoding="utf-8")
    finally:
        log_path.unlink(missing_ok=True)

    executable = str(completed.args[0])
    diagnostic_fields = {}
    for line in log_text.splitlines():
        marker = "external_process_failed "
        if marker in line:
            try:
                diagnostic_fields = json.loads(line.split(marker, 1)[1])
            except (ValueError, TypeError):
                diagnostic_fields = {}
    return {
        "returncode": completed.returncode,
        "absolute": Path(executable).is_absolute(),
        "has_operation": (
            diagnostic_fields.get("operation") == "packaged_smoke.expected_failure"
        ),
        "has_executable": diagnostic_fields.get("executable") == executable,
        "has_return_code": diagnostic_fields.get("return_code") == 7,
        "has_return_code_hex": (
            diagnostic_fields.get("return_code_hex") == "0x00000007"
        ),
        "secret_redacted": (
            "[REDACTED]" in log_text and "packaged-smoke-secret" not in log_text
        ),
    }


def _write_result(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)


def _run_windows_smoke() -> dict:
    """Return machine-readable assertions; never show a GUI error dialog."""
    handle, raw_path = tempfile.mkstemp(prefix="coupuas_acl_smoke_", suffix=".tmp")
    os.close(handle)
    target = Path(raw_path)
    try:
        results = {}
        for executable, args in (
            ("whoami.exe", ["/user", "/fo", "csv", "/nh"]),
            ("tasklist.exe", ["/fo", "csv", "/nh"]),
            ("icacls.exe", [str(target), "/verify"]),
        ):
            completed = run_system_command(
                executable,
                args,
                operation=f"packaged_smoke.{executable}",
                timeout=10,
            )
            results[executable] = {
                "returncode": completed.returncode,
                "absolute": Path(completed.args[0]).is_absolute(),
            }
        results["acl"] = secure_file_permissions(target)
        results["diagnostics"] = _run_failure_diagnostic()
        return results
    finally:
        target.unlink(missing_ok=True)


def main() -> int:
    if os.name != "nt":
        _write_result({"skipped": "Windows only"})
        return 0

    try:
        results = _run_windows_smoke()
    except Exception as exc:
        _write_result(
            {
                "frozen": bool(getattr(sys, "frozen", False)),
                "passed": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
        )
        return 1

    passed = all(
        item["returncode"] == 0 and item["absolute"]
        for key, item in results.items()
        if key.endswith(".exe")
    ) and results["acl"] is True and all(
        value is True
        for key, value in results["diagnostics"].items()
        if key not in {"returncode"}
    ) and results["diagnostics"]["returncode"] == 7
    results["frozen"] = bool(getattr(sys, "frozen", False))
    results["passed"] = passed
    _write_result(results)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
