from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import logging
import threading

import pytest

from src import fs_security


@pytest.fixture(autouse=True)
def reset_fs_security_caches():
    fs_security._principal = None
    fs_security._principal_resolved = False
    fs_security._successful.clear()
    fs_security._failures.clear()
    fs_security._inflight.clear()


def test_principal_is_resolved_once_with_hidden_system_command(monkeypatch):
    calls = []
    monkeypatch.setattr(fs_security, "_native_current_user_sid", lambda: None)

    def run(executable, args, **kwargs):
        calls.append((executable, args, kwargs))
        return SimpleNamespace(stdout='"desktop\\user","S-1-5-21-123"', returncode=0)

    monkeypatch.setattr(fs_security, "run_system_command", run)

    assert fs_security._resolve_current_user_principal() == "*S-1-5-21-123"
    assert fs_security._resolve_current_user_principal() == "*S-1-5-21-123"
    assert calls == [
        (
            "whoami.exe",
            ["/user", "/fo", "csv", "/nh"],
            {"operation": "resolve_current_user_sid", "timeout": 5},
        )
    ]


def test_windows_acl_uses_system_runner_and_stable_sid_principals(monkeypatch, tmp_path):
    target = tmp_path / "update.exe"
    target.write_bytes(b"placeholder")
    calls = []
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda executable, args, **kwargs: calls.append((executable, args, kwargs))
        or SimpleNamespace(returncode=0),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    executable, args, kwargs = calls[0]
    assert executable == "icacls.exe"
    assert kwargs["operation"] == "apply_filesystem_acl"
    assert kwargs["timeout"] == 15
    assert kwargs["process_attempt"] == 1
    assert kwargs["correlation_id"].startswith("acl-")
    assert "*S-1-5-18:(F)" in args
    assert "*S-1-5-32-544:(F)" in args


def test_native_acl_success_avoids_external_process(monkeypatch, tmp_path):
    target = tmp_path / "credentials.json"
    target.write_bytes(b"protected")
    calls = []
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: True)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda *args, **kwargs: calls.append(args),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    assert calls == []


def test_success_cache_follows_same_file_across_rename(monkeypatch, tmp_path):
    target = tmp_path / "before"
    target.write_bytes(b"same object")
    calls = []
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda *args, **kwargs: calls.append(args) or SimpleNamespace(returncode=0),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    renamed = target.rename(tmp_path / "after")
    assert fs_security._apply_windows_acl(renamed, is_dir=False) is True
    assert len(calls) == 1


def test_concurrent_requests_are_single_flight(monkeypatch, tmp_path):
    target = tmp_path / "credentials.json"
    target.write_bytes(b"same object")
    entered = threading.Event()
    release = threading.Event()
    calls = []
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)

    def run(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert release.wait(timeout=2)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(fs_security, "run_system_command", run)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fs_security._apply_windows_acl, target, False) for _ in range(4)]
        assert entered.wait(timeout=2)
        release.set()
        assert [future.result(timeout=2) for future in futures] == [True] * 4
    assert len(calls) == 1


def test_replacement_at_same_path_is_hardened_again(monkeypatch, tmp_path):
    target = tmp_path / "credentials.json"
    target.write_bytes(b"old")
    calls = []
    identities = iter([(False, 1, 10), (False, 1, 20)])
    monkeypatch.setattr(fs_security, "_file_identity", lambda path, is_dir: next(identities))
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda *args, **kwargs: calls.append(args) or SimpleNamespace(returncode=0),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    target.write_bytes(b"replacement")
    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    assert len(calls) == 2


def test_failure_backoff_skips_immediate_retry_then_retries(
    monkeypatch, tmp_path, caplog
):
    target = tmp_path / "update.exe"
    target.write_bytes(b"placeholder")
    now = [100.0]
    calls = []
    monkeypatch.setattr(fs_security.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or SimpleNamespace(returncode=5),
    )

    with caplog.at_level(logging.WARNING):
        assert fs_security._apply_windows_acl(target, is_dir=False) is False
        assert fs_security._apply_windows_acl(target, is_dir=False) is False
        assert len(calls) == 1
        now[0] += fs_security._BACKOFF_INITIAL_SECONDS
        assert fs_security._apply_windows_acl(target, is_dir=False) is False
    assert len(calls) == 2
    assert calls[0][1]["process_attempt"] == 1
    assert calls[1][1]["process_attempt"] == 2
    assert str(target).replace("\\", "\\\\") in caplog.text
    assert '"attempt":1' in caplog.text
    assert '"correlation_id":"acl-' in caplog.text


def test_windows_acl_reports_hardening_failure(monkeypatch, tmp_path):
    target = tmp_path / "update.exe"
    target.write_bytes(b"placeholder")
    monkeypatch.setattr(
        fs_security, "_resolve_current_user_principal", lambda: "*S-1-5-21-123"
    )
    monkeypatch.setattr(fs_security, "_apply_windows_acl_native", lambda *args: False)
    monkeypatch.setattr(
        fs_security,
        "run_system_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=5),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is False
