"""Build helper for creating the Windows executable with PyInstaller."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_NAME = "CoupangThreadAuto"
REPO_ROOT = Path(__file__).resolve().parent
MAIN_SCRIPT = REPO_ROOT / "login_main.py"
BUILD_DIR = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"
ICON_PATH = str((REPO_ROOT / "images" / "app_icon.ico").resolve())

HIDDEN_IMPORTS = [
    # Google GenAI
    "google.genai",
    "google.genai.types",
    "google.genai.client",
    "google.genai.models",
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
    "src.ai_provider",
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
    "src.services.grok_cli_provider",
    "src.services.account_queue",
    "src.services.multi_account_coordinator",
    "src.services.multi_account_runtime",
    "src.services.multi_account_upload_runner",
    "src.services.image_search",
    "src.services.link_history",
    "src.services.coupang_parser",
    "src.services.cancellation",
    "src.models",
    "src.models.threads_account",
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


def _normalize_thumbprints(value: str) -> tuple[str, ...]:
    """Validate a current/next exact signer pin bridge from CI configuration."""
    tokens = [item for item in re.split(r"[,;\s]+", str(value or "").strip()) if item]
    normalized: list[str] = []
    for token in tokens:
        thumbprint = re.sub(r"[^a-fA-F0-9]", "", token).upper()
        if len(thumbprint) != 40:
            raise RuntimeError(f"Invalid SHA-1 certificate thumbprint: {token!r}")
        if thumbprint not in normalized:
            normalized.append(thumbprint)
    if len(normalized) > 2:
        raise RuntimeError("At most two signer thumbprints are allowed during rotation")
    return tuple(normalized)


def _atomic_replace_text(path: Path, content: str) -> None:
    """Atomically replace a source file and verify its exact durable contents."""
    temp_path: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, temp_path)
        os.replace(temp_path, path)
        temp_path = None
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"Atomic source verification failed for {path}")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def pin_updater_signer_thumbprint():
    """
    Temporarily pin update signer thumbprint in src/auto_updater.py for this build.
    Returns a restore callback or None.
    """
    thumbprints = _normalize_thumbprints(
        os.getenv("AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS")
        or os.getenv("COUPUAS_TRUSTED_SIGNER_THUMBPRINTS")
    )
    if not thumbprints:
        allow_unpinned = os.getenv("COUPUAS_ALLOW_UNPINNED_UPDATER_SIGNER", "").strip() == "1"
        if allow_unpinned:
            print("  - WARNING: unpinned updater signer is allowed by override env.")
            return None
        raise RuntimeError(
            "Managed signing thumbprints are required. "
            "Set AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS to the current signer "
            "thumbprint, or current,next during a rotation bridge. "
            "For local test builds only, set COUPUAS_ALLOW_UNPINNED_UPDATER_SIGNER=1."
        )

    updater_path = REPO_ROOT / "src" / "auto_updater.py"
    if not updater_path.exists():
        raise RuntimeError("auto_updater.py is missing; refusing an unpinned updater build")

    original = updater_path.read_text(encoding="utf-8")
    pattern = r"DEFAULT_TRUSTED_SIGNER_THUMBPRINTS\s*=\s*(?:set\(\)|\{[^}]*\})"
    pin_values = ", ".join(repr(item) for item in thumbprints)
    replacement = f"DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = {{{pin_values}}}"
    updated, count = re.subn(pattern, replacement, original, count=1)
    if count != 1:
        raise RuntimeError(
            "Could not inject the exact updater signer pins; refusing to build"
        )
    if updated == original:
        print(f"  - Trusted signer thumbprints already pinned: {', '.join(thumbprints)}")
        return None

    try:
        _atomic_replace_text(updater_path, updated)
    except BaseException:
        try:
            _atomic_replace_text(updater_path, original)
        except BaseException as restore_exc:
            raise RuntimeError(
                "Updater signer pin injection failed and the original source could not be restored"
            ) from restore_exc
        raise
    print(f"  - Pinned updater trusted signer thumbprints: {', '.join(thumbprints)}")

    def _restore():
        try:
            _atomic_replace_text(updater_path, original)
        except Exception as exc:
            raise RuntimeError(
                "Failed to restore auto_updater.py after injecting signer pins"
            ) from exc
        print("  - Restored auto_updater.py thumbprint pin source state.")

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


def _build_executable_with_pinned_updater() -> bool:
    """Build and verify the executable while the updater source is pinned."""
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
        str(BUILD_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller"),
        "--distpath",
        str(DIST_DIR),
    ]

    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])

    for hidden in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])

    for src, dst in DATAS:
        abs_src = str((REPO_ROOT / src).resolve())
        if os.path.exists(abs_src):
            cmd.extend(["--add-data", f"{abs_src};{dst}"])

    for exclude in EXCLUDES:
        cmd.extend(["--exclude-module", exclude])

    playwright_driver = get_playwright_driver_path()
    if playwright_driver:
        cmd.extend(["--add-data", f"{playwright_driver};playwright/driver"])
        print(f"  - Included Playwright driver: {playwright_driver}")

    cmd.append(str(MAIN_SCRIPT))

    print("\n[4/6] Running PyInstaller...")
    print(f"  Command preview: {' '.join(cmd[:10])} ...")
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
        print("  - Build completed")
    except subprocess.CalledProcessError as exc:
        print(f"  - Build failed: {exc}")
        return False

    print("\n[5/6] Preparing runtime folders...")
    dist_folder = DIST_DIR
    (dist_folder / "media" / "cache").mkdir(parents=True, exist_ok=True)
    (dist_folder / "user_data").mkdir(parents=True, exist_ok=True)
    print("  - Created dist/media/cache")
    print("  - Created dist/user_data")

    print("\n[6/6] Verifying build output...")
    exe_path = dist_folder / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print("  - EXE file not found.")
        return False

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    try:
        from src.version import VERSION_TAG

        print(f"  - Version: {VERSION_TAG}")
    except Exception:
        pass

    print(f"  - EXE file: {exe_path}")
    print(f"  - File size: {size_mb:.1f} MB")
    print("\n" + "=" * 60)
    print("Build completed.")
    print(f"Run file: {exe_path.resolve()}")
    print("\nNext steps:")
    print("1. Test the generated EXE")
    print("2. Create and push a release tag")
    print("   git tag vX.Y.Z")
    print("   git push origin vX.Y.Z")
    print("=" * 60)
    return True


def build_exe() -> bool:
    print("=" * 60)
    print("Coupang Partners Thread Auto - EXE build")
    print("=" * 60)

    print("\n[1/6] Cleaning previous build artifacts...")
    for folder in (BUILD_DIR, DIST_DIR):
        resolved = folder.resolve()
        if resolved.parent != REPO_ROOT or resolved.name not in {"build", "dist"}:
            raise RuntimeError(f"Refusing to remove build output outside repository: {resolved}")
        if resolved.exists():
            shutil.rmtree(resolved)
            print(f"  - Removed {resolved}")

    print("\n[2/6] Preparing updater signer pin...")
    restore_updater_pin = pin_updater_signer_thumbprint()
    try:
        return _build_executable_with_pinned_updater()
    finally:
        if restore_updater_pin:
            restore_updater_pin()


def install_playwright_browsers() -> None:
    print("\n[Preparation] Installing Playwright Chromium...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=REPO_ROOT,
            check=True,
        )
        print("  - Chromium installed")
    except Exception as exc:
        print(f"  - Chromium install failed: {exc}")


if __name__ == "__main__":
    install_playwright_browsers()
    if not build_exe():
        print("\nBuild failed. Check logs above.")
        sys.exit(1)
