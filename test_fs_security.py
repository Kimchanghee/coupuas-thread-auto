from types import SimpleNamespace

from src import fs_security


def test_windows_acl_uses_stable_sid_principals(monkeypatch, tmp_path):
    target = tmp_path / "update.exe"
    target.write_bytes(b"placeholder")
    calls = []
    monkeypatch.setattr(
        fs_security,
        "_resolve_current_user_principal",
        lambda: "*S-1-5-21-123",
    )
    monkeypatch.setattr(
        fs_security.subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or SimpleNamespace(returncode=0),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is True
    assert "*S-1-5-18:(F)" in calls[0]
    assert "*S-1-5-32-544:(F)" in calls[0]


def test_windows_acl_reports_hardening_failure(monkeypatch, tmp_path):
    target = tmp_path / "update.exe"
    target.write_bytes(b"placeholder")
    monkeypatch.setattr(
        fs_security,
        "_resolve_current_user_principal",
        lambda: "*S-1-5-21-123",
    )
    monkeypatch.setattr(
        fs_security.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=5),
    )

    assert fs_security._apply_windows_acl(target, is_dir=False) is False
