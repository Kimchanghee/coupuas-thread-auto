"""Filesystem permission hardening helpers."""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def _to_path(value: PathLike) -> Path:
    return value if isinstance(value, Path) else Path(str(value))


def _apply_windows_acl(path: Path, is_dir: bool) -> None:
    if not path.exists():
        return

    username = str(os.environ.get("USERNAME") or getpass.getuser() or "").strip()
    if not username:
        return

    user_acl = f"{username}:(OI)(CI)F" if is_dir else f"{username}:(F)"
    cmd = [
        "icacls",
        str(path),
        "/inheritance:r",
        "/grant:r",
        user_acl,
        "/grant:r",
        "SYSTEM:(F)",
        "/grant:r",
        "Administrators:(F)",
    ]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        # Permission hardening is best-effort.
        pass


def secure_dir_permissions(path: PathLike) -> None:
    target = _to_path(path)
    if not target.exists():
        return
    try:
        if os.name == "nt":
            _apply_windows_acl(target, is_dir=True)
        else:
            os.chmod(target, 0o700)
    except Exception:
        pass


def secure_file_permissions(path: PathLike) -> None:
    target = _to_path(path)
    if not target.exists():
        return
    try:
        if os.name == "nt":
            _apply_windows_acl(target, is_dir=False)
        else:
            os.chmod(target, 0o600)
    except Exception:
        pass
