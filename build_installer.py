"""Build helper for creating a Windows installer via Inno Setup."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from src.version import VERSION

REPO_ROOT = Path(__file__).resolve().parent
APP_EXE_PATH = REPO_ROOT / "dist" / "CoupangThreadAuto.exe"
INSTALLER_SCRIPT = REPO_ROOT / "installer" / "CoupangThreadAuto.iss"
INSTALLER_OUTPUT = REPO_ROOT / "dist" / "CoupangThreadAutoSetup.exe"
_VERSION_PATTERN = re.compile(r"[0-9]{1,5}(?:\.[0-9]{1,5}){2}")


def _validated_version(value: str) -> str:
    normalized = str(value or "").strip().lstrip("v")
    if not _VERSION_PATTERN.fullmatch(normalized):
        raise ValueError("Application version must use major.minor.patch digits")
    return normalized


def _resolve_app_version() -> str:
    canonical_version = _validated_version(VERSION)
    env_version = str(os.getenv("COUPUAS_APP_VERSION", "")).strip()
    if env_version:
        requested_version = _validated_version(env_version)
        if requested_version != canonical_version:
            raise ValueError(
                "COUPUAS_APP_VERSION must exactly match src/version.py "
                f"({canonical_version})"
            )
        return requested_version

    return canonical_version


def _find_iscc_path() -> str:
    env_path = str(os.getenv("ISCC_PATH", "")).strip()
    local_programs = Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
    candidates = [
        env_path,
        str(local_programs),
        r"C:\InnoSetup\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        shutil.which("ISCC") or "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return str(path.resolve())
    raise FileNotFoundError(
        "ISCC.exe not found. Install Inno Setup 6 or set ISCC_PATH."
    )


def build_installer() -> bool:
    print("=" * 60)
    print("CoupangThreadAuto - Installer build")
    print("=" * 60)

    if not APP_EXE_PATH.exists():
        print(f"ERROR: missing EXE. Build executable first. ({APP_EXE_PATH})")
        return False
    if not INSTALLER_SCRIPT.exists():
        print(f"ERROR: missing installer script. ({INSTALLER_SCRIPT})")
        return False

    app_version = _resolve_app_version()
    iscc_path = _find_iscc_path()

    print(f"  - Version: {app_version}")
    print(f"  - ISCC: {iscc_path}")

    cmd = [
        iscc_path,
        f"/DMyAppVersion={app_version}",
        str(INSTALLER_SCRIPT.resolve()),
    ]

    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: installer build failed ({exc})")
        return False

    if not INSTALLER_OUTPUT.exists():
        print(f"ERROR: installer output not found ({INSTALLER_OUTPUT})")
        return False

    size_mb = INSTALLER_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: installer created ({INSTALLER_OUTPUT}, {size_mb:.1f} MB)")
    return True


if __name__ == "__main__":
    if not build_installer():
        sys.exit(1)
