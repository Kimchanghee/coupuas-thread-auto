"""Build helper for creating a Windows installer via Inno Setup."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

APP_EXE_PATH = Path("dist") / "CoupangThreadAuto.exe"
INSTALLER_SCRIPT = Path("installer") / "CoupangThreadAuto.iss"
INSTALLER_OUTPUT = Path("dist") / "CoupangThreadAutoSetup.exe"


def _resolve_app_version() -> str:
    env_version = str(os.getenv("COUPUAS_APP_VERSION", "")).strip()
    if env_version:
        return env_version.lstrip("v")

    try:
        main_py = Path("main.py").read_text(encoding="utf-8")
        match = re.search(r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']', main_py, re.MULTILINE)
        if match:
            return str(match.group(1)).strip().lstrip("v")
    except Exception:
        pass

    return "0.0.0"


def _find_iscc_path() -> str:
    env_path = str(os.getenv("ISCC_PATH", "")).strip()
    candidates = [
        env_path,
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
        subprocess.run(cmd, check=True)
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
