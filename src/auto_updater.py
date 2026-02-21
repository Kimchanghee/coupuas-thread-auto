"""Auto-updater with release checksum verification."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from packaging import version
from src.fs_security import secure_dir_permissions, secure_file_permissions


class AutoUpdater:
    """Manage auto update flow via GitHub Releases."""

    GITHUB_OWNER = "Kimchanghee"
    GITHUB_OWNER_ID = 9594198
    GITHUB_REPO = "coupuas-thread-auto"

    API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    RELEASES_URL = f"{API_BASE}/releases/latest"
    ALLOWED_DOWNLOAD_HOSTS = {
        "github.com",
        "objects.githubusercontent.com",
        "github-releases.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
    EXPECTED_EXE_NAME = "CoupangThreadAuto.exe"
    REQUIRE_SIGNED_UPDATES = True
    MAX_UPDATE_SIZE_BYTES = 200 * 1024 * 1024
    MINIMUM_SAFE_VERSION = "2.2.3"
    # Release CI injects the production signer thumbprint into this constant at build time.
    DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = set()
    DEFAULT_TRUSTED_PUBLISHERS = {"paro partners"}

    def __init__(self, current_version: str):
        self.current_version = str(current_version or "").lstrip("v")
        self.is_dev_mode = not getattr(sys, "frozen", False)

        default_thumbprints = {
            item.strip().upper()
            for item in self.DEFAULT_TRUSTED_SIGNER_THUMBPRINTS
            if str(item).strip()
        }
        if self.is_dev_mode:
            env_thumbprints = os.getenv("COUPUAS_TRUSTED_SIGNER_THUMBPRINTS", "")
            env_thumbprint_set = {
                item.strip().upper()
                for item in env_thumbprints.split(",")
                if item.strip()
            }
            self.trusted_thumbprints = env_thumbprint_set or default_thumbprints
        else:
            # Production builds use signer pins baked into the binary.
            self.trusted_thumbprints = default_thumbprints

        publishers = set()
        if self.is_dev_mode:
            publishers = {
                self._normalize_identity(item)
                for item in os.getenv("COUPUAS_TRUSTED_PUBLISHERS", "").split(",")
                if item.strip()
            }
            legacy_publisher = self._normalize_identity(
                os.getenv("COUPUAS_TRUSTED_PUBLISHER", "").strip()
            )
            if legacy_publisher:
                publishers.add(legacy_publisher)
        self.trusted_publishers = publishers or {
            self._normalize_identity(item) for item in self.DEFAULT_TRUSTED_PUBLISHERS
        }

        # Unsigned updates are not allowed in production builds.
        self.allow_unsigned_updates = False

        self.last_expected_sha256: Optional[str] = None

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
    def _normalize_identity(value: str) -> str:
        text = str(value or "").strip().lower()
        return re.sub(r"[^a-z0-9]+", "", text)

    @classmethod
    def _extract_subject_identities(cls, subject: str) -> set:
        identities = set()
        text = str(subject or "").strip()
        if not text:
            return identities

        for field in re.finditer(r"(?:^|,\s*)(CN|O|OU)\s*=\s*([^,]+)", text, re.IGNORECASE):
            normalized = cls._normalize_identity(field.group(2))
            if normalized:
                identities.add(normalized)
        return identities

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
    def _secure_update_temp_dir() -> Path:
        update_dir = Path.home() / ".shorts_thread_maker" / "updates"
        update_dir.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(update_dir)
        return update_dir

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

    def _verify_release_author(self, release_data: Dict) -> bool:
        author = release_data.get("author") or {}
        try:
            author_id = int(author.get("id"))
        except (TypeError, ValueError):
            author_id = 0
        author_login = str(author.get("login", "")).strip().lower()
        if not author_id and not author_login:
            return False
        if author_id and author_id != int(self.GITHUB_OWNER_ID):
            return False
        if author_login and author_login != self.GITHUB_OWNER.lower():
            return False
        return True

    def _is_version_allowed(self, latest_version: str) -> bool:
        latest = str(latest_version or "").lstrip("v").strip()
        if not latest:
            return False
        minimum_safe = str(self.MINIMUM_SAFE_VERSION or "").lstrip("v").strip()
        if minimum_safe and version.parse(latest) < version.parse(minimum_safe):
            return False
        return True

    def _verify_authenticode_signature(self, file_path: str) -> bool:
        if os.name != "nt":
            return True
        if self.allow_unsigned_updates:
            return True
        if not self.REQUIRE_SIGNED_UPDATES:
            return True
        if not self.is_dev_mode and not self.trusted_thumbprints:
            # Fail closed: production updates require pinned signer thumbprints.
            return False

        escaped_file_path = str(file_path).replace("'", "''")
        ps_script = (
            "$ErrorActionPreference='Stop';"
            f"$sig=Get-AuthenticodeSignature -FilePath '{escaped_file_path}';"
            "$cert=$sig.SignerCertificate;"
            "$obj=[PSCustomObject]@{"
            "Status=$sig.Status.ToString();"
            "Subject=($(if($cert){$cert.Subject}else{''}));"
            "Thumbprint=($(if($cert){$cert.Thumbprint}else{''}))"
            "};"
            "$obj | ConvertTo-Json -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            data = json.loads((completed.stdout or "").strip() or "{}")
            status = str(data.get("Status", "")).strip().lower()
            subject = str(data.get("Subject", "")).strip()
            thumbprint = str(data.get("Thumbprint", "")).strip().upper()

            if status != "valid":
                return False
            if self.trusted_thumbprints and thumbprint not in self.trusted_thumbprints:
                return False
            subject_identities = self._extract_subject_identities(subject)
            if self.trusted_publishers and not subject_identities.intersection(self.trusted_publishers):
                return False
            return bool(subject)
        except Exception:
            return False

    def check_for_updates(self) -> Optional[Dict]:
        response = self.session.get(self.RELEASES_URL, timeout=10)
        if response.status_code == 404:
            return None

        response.raise_for_status()
        release_data = response.json()
        if not self._verify_release_author(release_data):
            return None

        latest_version = str(release_data.get("tag_name", "")).lstrip("v")
        if not latest_version:
            return None
        if not self._is_version_allowed(latest_version):
            return None

        if version.parse(latest_version) <= version.parse(self.current_version or "0"):
            return None

        assets = release_data.get("assets", []) or []
        exe_asset = None
        for asset in assets:
            name = str(asset.get("name", ""))
            if name.lower() == self.EXPECTED_EXE_NAME.lower():
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
        if isinstance(size, int) and size > self.MAX_UPDATE_SIZE_BYTES:
            return None
        return {
            "version": latest_version,
            "download_url": download_url,
            "checksum_download_url": checksum_url,
            "changelog": release_data.get("body", ""),
            "published_at": release_data.get("published_at", ""),
            "size_mb": size / (1024 * 1024),
            "size_bytes": size,
            "asset_name": str(exe_asset.get("name", "")),
            "checksum_asset_name": str(checksum_asset.get("name", "")),
        }

    def download_update(self, update_info: Dict, progress_callback=None) -> Optional[str]:
        try:
            download_url = str(update_info.get("download_url", ""))
            checksum_url = str(update_info.get("checksum_download_url", ""))
            declared_size = int(update_info.get("size_bytes") or 0)
            if declared_size > self.MAX_UPDATE_SIZE_BYTES:
                raise ValueError("Update file is too large")
            if not self._is_allowed_download_url(download_url):
                raise ValueError("Disallowed update download URL")
            if not self._is_allowed_download_url(checksum_url):
                raise ValueError("Disallowed checksum download URL")

            checksum_resp = self.session.get(checksum_url, timeout=20)
            checksum_resp.raise_for_status()
            expected_sha256 = self._parse_sha256_text(checksum_resp.text)
            if not expected_sha256:
                raise ValueError("Checksum file does not contain SHA-256 hash")
            self.last_expected_sha256 = expected_sha256
            update_info["expected_sha256"] = expected_sha256

            with tempfile.NamedTemporaryFile(
                prefix="coupuas_update_",
                suffix=".exe",
                dir=str(self._secure_update_temp_dir()),
                delete=False,
            ) as tmp:
                temp_file = tmp.name
            secure_file_permissions(temp_file)

            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            if total_size > self.MAX_UPDATE_SIZE_BYTES:
                raise ValueError("Update file exceeds maximum allowed size")
            downloaded = 0

            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > self.MAX_UPDATE_SIZE_BYTES:
                        raise ValueError("Update download exceeded maximum allowed size")
                    if progress_callback and total_size > 0:
                        progress_callback((downloaded / total_size) * 100)

            actual_sha256 = self._compute_sha256(temp_file)
            if actual_sha256 != expected_sha256:
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                raise ValueError("Downloaded update checksum mismatch")
            if not self._verify_authenticode_signature(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                raise ValueError("Downloaded update signature validation failed")

            return temp_file

        except Exception as e:
            if "temp_file" in locals():
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            print(f"Download error: {e}")
            return None

    def install_update(self, update_file: str, expected_sha256: str = "") -> bool:
        try:
            if not self._verify_authenticode_signature(update_file):
                print("Update signature validation failed.")
                return False

            expected_sha = str(expected_sha256 or self.last_expected_sha256 or "").strip().lower()
            if not expected_sha:
                print("Expected update checksum is missing.")
                return False
            actual_sha = self._compute_sha256(update_file)
            if actual_sha != expected_sha:
                print("Update checksum validation failed.")
                return False

            current_exe = sys.executable
            if not getattr(sys, "frozen", False):
                print("Auto-update is only supported in packaged executable mode.")
                return False

            backup_exe = current_exe + ".backup"
            if os.path.exists(backup_exe):
                try:
                    os.remove(backup_exe)
                except OSError:
                    pass

            shutil.copy2(current_exe, backup_exe)
            update_script = self._create_update_script()

            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "RemoteSigned",
                    "-File",
                    update_script,
                    "-CurrentExe",
                    current_exe,
                    "-UpdateFile",
                    update_file,
                    "-BackupExe",
                    backup_exe,
                    "-ExpectedSha256",
                    expected_sha,
                    "-TrustedThumbprints",
                    ",".join(sorted(self.trusted_thumbprints)),
                    "-TrustedPublishers",
                    ",".join(sorted(self.trusted_publishers)),
                ],
                shell=False,
            )
            return True

        except Exception as e:
            print(f"Update installation error: {e}")
            return False

    def _create_update_script(self) -> str:
        script_content = """param(
    [Parameter(Mandatory=$true)][string]$CurrentExe,
    [Parameter(Mandatory=$true)][string]$UpdateFile,
    [Parameter(Mandatory=$true)][string]$BackupExe,
    [string]$ExpectedSha256 = '',
    [string]$TrustedThumbprints = '',
    [string]$TrustedPublishers = ''
)
$ErrorActionPreference = 'Stop'

function Normalize-Identity([string]$value) {
    if (-not $value) { return '' }
    return [regex]::Replace($value.ToLowerInvariant(), '[^a-z0-9]+', '')
}

function Parse-TrustedList([string]$value) {
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    if (-not $value) { return $set }
    foreach ($item in $value.Split(',')) {
        $trimmed = $item.Trim()
        if ($trimmed) {
            [void]$set.Add($trimmed.ToUpperInvariant())
        }
    }
    return $set
}

function Get-SubjectIdentities([string]$subject) {
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    if (-not $subject) { return $set }
    $matches = [regex]::Matches($subject, '(?:^|,\\s*)(CN|O|OU)\\s*=\\s*([^,]+)')
    foreach ($m in $matches) {
        $normalized = Normalize-Identity($m.Groups[2].Value)
        if ($normalized) {
            [void]$set.Add($normalized)
        }
    }
    return $set
}

try {
    Start-Sleep -Seconds 2
    if (-not (Test-Path -LiteralPath $UpdateFile)) {
        throw 'Update file is missing.'
    }
    if ($ExpectedSha256) {
        $actualHash = (Get-FileHash -LiteralPath $UpdateFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $ExpectedSha256.ToLowerInvariant()) {
            throw 'Update checksum mismatch.'
        }
    }
    $sig = Get-AuthenticodeSignature -FilePath $UpdateFile
    $status = $sig.Status.ToString()
    if ($status -ne 'Valid') {
        throw ('Update signature status is not allowed: ' + $status)
    }
    $cert = $sig.SignerCertificate
    if (-not $cert) {
        throw 'Update signer certificate is missing.'
    }

    $thumb = ''
    if ($cert.Thumbprint) {
        $thumb = $cert.Thumbprint.ToUpperInvariant()
    }
    $trustedThumbSet = Parse-TrustedList($TrustedThumbprints)
    if ($trustedThumbSet.Count -gt 0 -and -not $trustedThumbSet.Contains($thumb)) {
        throw 'Update signer thumbprint is not trusted.'
    }

    $trustedPublisherSet = New-Object 'System.Collections.Generic.HashSet[string]'
    if ($TrustedPublishers) {
        foreach ($item in $TrustedPublishers.Split(',')) {
            $normalized = Normalize-Identity($item.Trim())
            if ($normalized) {
                [void]$trustedPublisherSet.Add($normalized)
            }
        }
    }
    if ($trustedPublisherSet.Count -gt 0) {
        $subjectIds = Get-SubjectIdentities($cert.Subject)
        $publisherMatch = $false
        foreach ($subjectId in $subjectIds) {
            if ($trustedPublisherSet.Contains($subjectId)) {
                $publisherMatch = $true
                break
            }
        }
        if (-not $publisherMatch) {
            throw 'Update signer publisher is not trusted.'
        }
    }

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            if (-not (Test-Path -LiteralPath $CurrentExe)) {
                throw 'Current executable is missing.'
            }
            $stream = [System.IO.File]::Open(
                $CurrentExe,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $stream.Close()
            $ready = $true
            break
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) {
        throw 'Failed to acquire executable lock for replacement.'
    }

    $targetDir = Split-Path -Parent $CurrentExe
    $tempReplacement = Join-Path $targetDir ([System.IO.Path]::GetRandomFileName() + '.exe')
    Copy-Item -LiteralPath $UpdateFile -Destination $tempReplacement -Force
    [System.IO.File]::Replace($tempReplacement, $CurrentExe, $BackupExe, $true)
    Remove-Item -LiteralPath $UpdateFile -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $CurrentExe
} catch {
    try {
        if (Test-Path -LiteralPath $BackupExe) {
            Copy-Item -LiteralPath $BackupExe -Destination $CurrentExe -Force
        }
    } catch {
    }
} finally {
    if ($tempReplacement -and (Test-Path -LiteralPath $tempReplacement)) {
        Remove-Item -LiteralPath $tempReplacement -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
"""

        fd, script_path = tempfile.mkstemp(
            suffix=".ps1",
            prefix="update_coupuas_",
            dir=str(self._secure_update_temp_dir()),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as script_file:
                script_file.write(script_content)
            secure_file_permissions(script_path)
            return script_path
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.remove(script_path)
            except OSError:
                pass
            raise

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
