"""Auto-updater with release checksum verification."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from packaging import version


class AutoUpdater:
    """Manage auto update flow via GitHub Releases."""

    GITHUB_OWNER = "Kimchanghee"
    GITHUB_REPO = "coupuas-thread-auto"

    API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    RELEASES_URL = f"{API_BASE}/releases/latest"
    ALLOWED_DOWNLOAD_HOSTS = {
        "github.com",
        "objects.githubusercontent.com",
        "github-releases.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }

    def __init__(self, current_version: str):
        self.current_version = str(current_version or "").lstrip("v")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": f"CoupangThreadAuto/{self.current_version or 'unknown'}",
                "Accept": "application/vnd.github.v3+json",
            }
        )

    @staticmethod
    def _is_allowed_download_url(download_url: str) -> bool:
        try:
            parsed = urlparse(str(download_url or ""))
            if parsed.scheme != "https":
                return False
            host = (parsed.hostname or "").lower()
            return host in AutoUpdater.ALLOWED_DOWNLOAD_HOSTS
        except Exception:
            return False

    @staticmethod
    def _parse_sha256_text(content: str) -> Optional[str]:
        if not isinstance(content, str):
            return None
        match = re.search(r"\b[a-fA-F0-9]{64}\b", content)
        return match.group(0).lower() if match else None

    @staticmethod
    def _compute_sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest().lower()

    @staticmethod
    def _find_checksum_asset(assets, exe_name: str):
        names = {
            f"{exe_name}.sha256",
            f"{exe_name}.sha256.txt",
        }
        for asset in assets:
            name = str(asset.get("name", ""))
            lower_name = name.lower()
            if name in names:
                return asset
            if lower_name.endswith(".sha256") and exe_name.lower() in lower_name:
                return asset
            if lower_name.endswith(".sha256.txt") and exe_name.lower() in lower_name:
                return asset
        return None

    def check_for_updates(self) -> Optional[Dict]:
        response = self.session.get(self.RELEASES_URL, timeout=10)
        if response.status_code == 404:
            return None

        response.raise_for_status()
        release_data = response.json()

        latest_version = str(release_data.get("tag_name", "")).lstrip("v")
        if not latest_version:
            return None

        if version.parse(latest_version) <= version.parse(self.current_version or "0"):
            return None

        assets = release_data.get("assets", []) or []
        exe_asset = None
        for asset in assets:
            name = str(asset.get("name", ""))
            if name.lower().endswith(".exe"):
                exe_asset = asset
                break

        if not exe_asset:
            return None

        checksum_asset = self._find_checksum_asset(assets, str(exe_asset.get("name", "")))
        if not checksum_asset:
            return None

        download_url = str(exe_asset.get("browser_download_url", ""))
        checksum_url = str(checksum_asset.get("browser_download_url", ""))
        if not self._is_allowed_download_url(download_url):
            return None
        if not self._is_allowed_download_url(checksum_url):
            return None

        size = exe_asset.get("size") or 0
        return {
            "version": latest_version,
            "download_url": download_url,
            "checksum_download_url": checksum_url,
            "changelog": release_data.get("body", ""),
            "published_at": release_data.get("published_at", ""),
            "size_mb": size / (1024 * 1024),
            "asset_name": str(exe_asset.get("name", "")),
            "checksum_asset_name": str(checksum_asset.get("name", "")),
        }

    def download_update(self, update_info: Dict, progress_callback=None) -> Optional[str]:
        try:
            download_url = str(update_info.get("download_url", ""))
            checksum_url = str(update_info.get("checksum_download_url", ""))
            if not self._is_allowed_download_url(download_url):
                raise ValueError("Disallowed update download URL")
            if not self._is_allowed_download_url(checksum_url):
                raise ValueError("Disallowed checksum download URL")

            checksum_resp = self.session.get(checksum_url, timeout=20)
            checksum_resp.raise_for_status()
            expected_sha256 = self._parse_sha256_text(checksum_resp.text)
            if not expected_sha256:
                raise ValueError("Checksum file does not contain SHA-256 hash")

            safe_name = os.path.basename(str(update_info.get("asset_name", "update.exe")))
            if not safe_name.lower().endswith(".exe"):
                safe_name = f"{safe_name}.exe"

            with tempfile.NamedTemporaryFile(
                prefix="coupuas_update_",
                suffix=".exe",
                delete=False,
            ) as tmp:
                temp_file = tmp.name

            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback((downloaded / total_size) * 100)

            actual_sha256 = self._compute_sha256(temp_file)
            if actual_sha256 != expected_sha256:
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                raise ValueError("Downloaded update checksum mismatch")

            return temp_file

        except Exception as e:
            print(f"다운로드 중 오류: {e}")
            return None

    def install_update(self, update_file: str) -> bool:
        try:
            current_exe = sys.executable
            if not getattr(sys, "frozen", False):
                print("개발 모드에서는 자동 업데이트를 지원하지 않습니다.")
                return False

            backup_exe = current_exe + ".backup"
            if os.path.exists(backup_exe):
                try:
                    os.remove(backup_exe)
                except OSError:
                    pass

            shutil.copy2(current_exe, backup_exe)
            update_script = self._create_update_script(current_exe, update_file, backup_exe)

            subprocess.Popen(["cmd", "/c", update_script], shell=False)
            return True

        except Exception as e:
            print(f"업데이트 설치 중 오류: {e}")
            return False

    def _create_update_script(self, current_exe: str, update_file: str, backup_exe: str) -> str:
        current_exe_q = current_exe.replace('"', '""')
        update_file_q = update_file.replace('"', '""')
        backup_exe_q = backup_exe.replace('"', '""')

        script_content = f"""@echo off
setlocal

echo Update install in progress...
timeout /t 5 /nobreak >nul

set retry=0
:delete_loop
del /f \"{current_exe_q}\" 2>nul
if exist \"{current_exe_q}\" (
    set /a retry+=1
    if %retry% lss 10 (
        timeout /t 1 /nobreak >nul
        goto delete_loop
    ) else (
        copy /y \"{backup_exe_q}\" \"{current_exe_q}\" >nul
        goto cleanup
    )
)

copy /y \"{update_file_q}\" \"{current_exe_q}\" >nul
if errorlevel 1 (
    copy /y \"{backup_exe_q}\" \"{current_exe_q}\" >nul
    goto cleanup
)

del /f \"{backup_exe_q}\" 2>nul
del /f \"{update_file_q}\" 2>nul
start \"\" \"{current_exe_q}\"
goto end

:cleanup
del /f \"{update_file_q}\" 2>nul
echo Update failed and previous version was restored.
pause

:end
del /f \"%~f0\"
endlocal
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".bat",
            prefix="update_coupuas_",
            delete=False,
        ) as script_file:
            script_file.write(script_content)
            return script_file.name

    @staticmethod
    def get_changelog_summary(changelog: str, max_lines: int = 10) -> str:
        lines = str(changelog or "").split("\n")
        if len(lines) <= max_lines:
            return changelog

        summary_lines = lines[:max_lines]
        summary_lines.append(f"\n... (remaining {len(lines) - max_lines} lines omitted)")
        return "\n".join(summary_lines)


if __name__ == "__main__":
    from main import VERSION

    updater = AutoUpdater(VERSION)
    print(f"Current version: {VERSION}")
    print("Checking for updates...")

    update_info = updater.check_for_updates()
    if update_info:
        print(f"\nNew version found: v{update_info['version']}")
        print(f"Size: {update_info['size_mb']:.1f} MB")
        print("\nChangelog:")
        print(AutoUpdater.get_changelog_summary(update_info["changelog"]))

        response = input("\nDownload now? (y/n): ").strip().lower()
        if response == "y":
            def progress(percent):
                print(f"\rProgress: {percent:.1f}%", end="")

            file_path = updater.download_update(update_info, progress)
            if file_path:
                print(f"\n\nDownloaded: {file_path}")
                print("Restart app to install the update.")
            else:
                print("\nDownload failed")
    else:
        print("\nAlready on latest version.")
