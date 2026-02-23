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
        "ISCC.exe를 찾을 수 없습니다. Inno Setup 6 설치 또는 ISCC_PATH 환경변수를 설정해주세요."
    )


def build_installer() -> bool:
    print("=" * 60)
    print("CoupangThreadAuto - 설치형 인스톨러 빌드")
    print("=" * 60)

    if not APP_EXE_PATH.exists():
        print(f"오류: EXE 파일이 없습니다. 먼저 EXE를 빌드해주세요. ({APP_EXE_PATH})")
        return False
    if not INSTALLER_SCRIPT.exists():
        print(f"오류: 인스톨러 스크립트가 없습니다. ({INSTALLER_SCRIPT})")
        return False

    app_version = _resolve_app_version()
    iscc_path = _find_iscc_path()

    print(f"  - 버전: {app_version}")
    print(f"  - ISCC: {iscc_path}")

    cmd = [
        iscc_path,
        f"/DMyAppVersion={app_version}",
        str(INSTALLER_SCRIPT.resolve()),
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"오류: 인스톨러 빌드 실패 ({exc})")
        return False

    if not INSTALLER_OUTPUT.exists():
        print(f"오류: 설치 파일이 생성되지 않았습니다. ({INSTALLER_OUTPUT})")
        return False

    size_mb = INSTALLER_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"성공: 설치 파일 생성 완료 ({INSTALLER_OUTPUT}, {size_mb:.1f} MB)")
    return True


if __name__ == "__main__":
    if not build_installer():
        sys.exit(1)
