"""Build helper for creating the Windows executable with PyInstaller."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "CoupangThreadAuto"
MAIN_SCRIPT = "main.py"
ICON_PATH = str((Path(__file__).resolve().parent / "images" / "app_icon.ico").resolve())

HIDDEN_IMPORTS = [
    # Google AI
    "google.generativeai",
    "google.ai.generativelanguage",
    "google.api_core",
    "google.auth",
    "google.protobuf",
    "grpc",
    # PyQt6
    "PyQt6",
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.sip",
    # Playwright
    "playwright",
    "playwright.sync_api",
    "playwright.async_api",
    "playwright._impl",
    # Images/network
    "PIL",
    "PIL.Image",
    "requests",
    "urllib3",
    # Misc
    "json",
    "hashlib",
    "re",
    "asyncio",
    "packaging",
    "packaging.version",
    "packaging.specifiers",
    # Project modules
    "src",
    "src.main_window",
    "src.config",
    "src.coupang_uploader",
    "src.settings_dialog",
    "src.threads_playwright_helper",
    "src.computer_use_agent",
    "src.auto_updater",
    "src.update_dialog",
    "src.login_window",
    "src.auth_client",
    "src.runtime_security",
    "src.theme",
    "src.events",
    "src.tutorial",
    "src.services",
    "src.services.aggro_generator",
    "src.services.image_search",
    "src.services.link_history",
    "src.services.coupang_parser",
]

DATAS = [
    ("fonts", "fonts"),
    (str(Path("images") / "app_icon.ico"), "images"),
]

EXCLUDES = [
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "tkinter",
    "test",
    "unittest",
]


def _normalize_thumbprint(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = re.sub(r"[^a-fA-F0-9]", "", raw).upper()
    if len(normalized) != 40:
        return ""
    return normalized


def pin_updater_signer_thumbprint():
    """
    Temporarily pin update signer thumbprint in src/auto_updater.py for this build.
    Returns a restore callback or None.
    """
    thumb = _normalize_thumbprint(
        os.getenv("COUPUAS_TRUSTED_SIGNER_THUMBPRINT")
        or os.getenv("CODE_SIGN_CERT_THUMBPRINT")
    )
    if not thumb:
        allow_unpinned = os.getenv("COUPUAS_ALLOW_UNPINNED_UPDATER_SIGNER", "").strip() == "1"
        if allow_unpinned:
            print("  - WARNING: unpinned updater signer is allowed by override env.")
            return None
        raise RuntimeError(
            "Trusted signer thumbprint is required. "
            "Set COUPUAS_TRUSTED_SIGNER_THUMBPRINT (or CODE_SIGN_CERT_THUMBPRINT). "
            "For local test builds only, set COUPUAS_ALLOW_UNPINNED_UPDATER_SIGNER=1."
        )

    updater_path = Path("src") / "auto_updater.py"
    if not updater_path.exists():
        print("  - auto_updater.py not found; skipping thumbprint pin.")
        return None

    original = updater_path.read_text(encoding="utf-8")
    pattern = r"DEFAULT_TRUSTED_SIGNER_THUMBPRINTS\s*=\s*(?:set\(\)|\{[^}]*\})"
    replacement = f"DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = {{'{thumb}'}}"
    updated, count = re.subn(pattern, replacement, original, count=1)
    if count != 1:
        print("  - Failed to patch trusted signer thumbprint line; skipping.")
        return None
    if updated == original:
        print(f"  - Trusted signer thumbprint already pinned: {thumb}")
        return None

    updater_path.write_text(updated, encoding="utf-8")
    print(f"  - Pinned updater trusted signer thumbprint: {thumb}")

    def _restore():
        try:
            updater_path.write_text(original, encoding="utf-8")
            print("  - Restored auto_updater.py thumbprint pin source state.")
        except Exception as exc:
            print(f"  - Failed to restore auto_updater.py after build: {exc}")

    return _restore


def get_playwright_driver_path() -> str | None:
    try:
        import playwright

        playwright_path = os.path.dirname(playwright.__file__)
        driver_path = os.path.join(playwright_path, "driver")
        if os.path.exists(driver_path):
            return driver_path
    except Exception:
        return None
    return None


def build_exe() -> bool:
    print("=" * 60)
    print("Coupang Partners Thread Auto - EXE build")
    print("=" * 60)

    print("\n[1/6] Cleaning previous build artifacts...")
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  - Removed {folder}")

    print("\n[2/6] Preparing updater signer pin...")
    restore_updater_pin = pin_updater_signer_thumbprint()

    print("\n[3/6] Building PyInstaller command...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--noupx",
        "--optimize",
        "2",
        "--specpath",
        "build",
    ]

    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])

    for hidden in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])

    for src, dst in DATAS:
        abs_src = os.path.abspath(src)
        if os.path.exists(abs_src):
            cmd.extend(["--add-data", f"{abs_src};{dst}"])

    for exclude in EXCLUDES:
        cmd.extend(["--exclude-module", exclude])

    playwright_driver = get_playwright_driver_path()
    if playwright_driver:
        cmd.extend(["--add-data", f"{playwright_driver};playwright/driver"])
        print(f"  - Included Playwright driver: {playwright_driver}")

    cmd.append(os.path.abspath(MAIN_SCRIPT))

    print("\n[4/6] Running PyInstaller...")
    print(f"  Command preview: {' '.join(cmd[:10])} ...")
    try:
        subprocess.run(cmd, check=True)
        print("  - Build completed")
    except subprocess.CalledProcessError as exc:
        print(f"  - Build failed: {exc}")
        return False
    finally:
        if restore_updater_pin:
            restore_updater_pin()

    print("\n[5/6] Preparing runtime folders...")
    dist_folder = "dist"
    os.makedirs(os.path.join(dist_folder, "media", "cache"), exist_ok=True)
    os.makedirs(os.path.join(dist_folder, "user_data"), exist_ok=True)
    print("  - Created dist/media/cache")
    print("  - Created dist/user_data")

    print("\n[6/6] Verifying build output...")
    exe_path = os.path.join(dist_folder, f"{APP_NAME}.exe")
    if not os.path.exists(exe_path):
        print("  - EXE file not found.")
        return False

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    try:
        with open("main.py", "r", encoding="utf-8") as handle:
            for line in handle:
                if "VERSION =" in line:
                    app_version = line.split("=")[1].strip().strip('"').strip("'")
                    print(f"  - Version: {app_version}")
                    break
    except Exception:
        pass

    print(f"  - EXE file: {exe_path}")
    print(f"  - File size: {size_mb:.1f} MB")
    print("\n" + "=" * 60)
    print("Build completed.")
    print(f"Run file: {os.path.abspath(exe_path)}")
    print("\nNext steps:")
    print("1. Test the generated EXE")
    print("2. Create and push a release tag")
    print("   git tag vX.Y.Z")
    print("   git push origin vX.Y.Z")
    print("=" * 60)
    return True


def install_playwright_browsers() -> None:
    print("\n[Preparation] Installing Playwright Chromium...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("  - Chromium installed")
    except Exception as exc:
        print(f"  - Chromium install failed: {exc}")


if __name__ == "__main__":
    install_playwright_browsers()
    if not build_exe():
        print("\nBuild failed. Check logs above.")
        sys.exit(1)
