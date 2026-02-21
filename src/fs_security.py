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


def _resolve_current_user_principal() -> str:
    try:
        completed = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        text = (completed.stdout or "").strip()
        if text:
            parts = [item.strip().strip('"') for item in text.split(",")]
            if len(parts) >= 2 and parts[1].startswith("S-1-"):
                # icacls requires SID principals with * prefix.
                return f"*{parts[1]}"
    except Exception:
        pass

    username = str(os.environ.get("USERNAME") or getpass.getuser() or "").strip()
    return username


def _apply_windows_acl(path: Path, is_dir: bool) -> None:
    if not path.exists():
        return

    principal = _resolve_current_user_principal()
    if not principal:
        return

    user_acl = f"{principal}:(OI)(CI)F" if is_dir else f"{principal}:(F)"
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
