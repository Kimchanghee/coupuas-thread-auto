"""Auto-updater with release checksum verification."""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from packaging import version
from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.system_process import popen_process, run_process


class AutoUpdater:
    """Manage auto update flow via GitHub Releases."""

    GITHUB_OWNER = "Kimchanghee"
    GITHUB_OWNER_ID = 9594198
    GITHUB_ACTIONS_BOT_ID = 41898282
    GITHUB_REPO = "coupuas-thread-auto"
    TRUSTED_RELEASE_AUTHORS = {
        (GITHUB_OWNER_ID, GITHUB_OWNER.lower()),
        (GITHUB_ACTIONS_BOT_ID, "github-actions[bot]"),
    }

    API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    RELEASES_URL = f"{API_BASE}/releases/latest"
    ALLOWED_DOWNLOAD_HOSTS = {
        "github.com",
        "objects.githubusercontent.com",
        "github-releases.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
    INSTALLER_ASSET_NAME = "CoupangThreadAutoSetup.exe"
    STANDALONE_EXE_NAME = "CoupangThreadAuto.exe"
    EXPECTED_EXE_NAME = STANDALONE_EXE_NAME
    PREFERRED_UPDATE_ASSET_NAMES = (INSTALLER_ASSET_NAME, STANDALONE_EXE_NAME)
    INSTALLER_ARGS = ("/SP-", "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART")
    REQUIRE_SIGNED_UPDATES = True
    MAX_UPDATE_SIZE_BYTES = 200 * 1024 * 1024
    MINIMUM_SAFE_VERSION = "2.2.3"
    # Release CI injects the production signer thumbprint into this constant at build time.
    DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = set()
    DEFAULT_TRUSTED_PUBLISHERS = {"ym"}

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
        self.last_update_asset_name: str = ""

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

    @classmethod
    def _find_release_asset(cls, assets, names):
        ordered_names = [str(name or "").lower() for name in names if str(name or "").strip()]
        for wanted_name in ordered_names:
            for asset in assets:
                name = str(asset.get("name", ""))
                if name.lower() == wanted_name:
                    return asset
        return None

    @staticmethod
    def _secure_update_temp_dir() -> Path:
        update_dir = Path.home() / ".shorts_thread_maker" / "updates"
        update_dir.mkdir(parents=True, exist_ok=True)
        if not secure_dir_permissions(update_dir):
            raise PermissionError("Unable to secure the update directory")
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
        if not author_id or not author_login:
            return False
        return (author_id, author_login) in self.TRUSTED_RELEASE_AUTHORS

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
            "StatusMessage=$sig.StatusMessage;"
            "Subject=($(if($cert){$cert.Subject}else{''}));"
            "Thumbprint=($(if($cert){$cert.Thumbprint}else{''}))"
            "};"
            "$obj | ConvertTo-Json -Compress"
        )
        try:
            completed = run_process(
                ["powershell", "-NoProfile", "-Command", ps_script],
                system_command=True,
                operation="updater.verify_authenticode",
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            data = json.loads((completed.stdout or "").strip() or "{}")
            status = str(data.get("Status", "")).strip().lower()
            status_message = str(data.get("StatusMessage", "")).strip().lower()
            subject = str(data.get("Subject", "")).strip()
            thumbprint = str(data.get("Thumbprint", "")).strip().upper()

            if self.trusted_thumbprints and thumbprint not in self.trusted_thumbprints:
                return False
            subject_identities = self._extract_subject_identities(subject)
            if self.trusted_publishers and not subject_identities.intersection(self.trusted_publishers):
                return False
            if status != "valid":
                trust_chain_only_error = status == "nottrusted" or (
                    status == "unknownerror"
                    and (
                        "not trusted" in status_message
                        or "root certificate" in status_message
                        or "trust provider" in status_message
                    )
                )
                if not (self.trusted_thumbprints and trust_chain_only_error):
                    return False
            return bool(subject)
        except Exception:
            return False

    def check_for_updates(self) -> Optional[Dict]:
        if not self.is_dev_mode and not self.trusted_thumbprints:
            # A frozen build without a baked-in signer pin cannot safely install
            # releases. Keep local/test builds from repeatedly offering an update
            # that signature verification must reject later.
            return None

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
        exe_asset = self._find_release_asset(assets, self.PREFERRED_UPDATE_ASSET_NAMES)

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
            "asset_kind": (
                "installer"
                if str(exe_asset.get("name", "")).lower() == self.INSTALLER_ASSET_NAME.lower()
                else "standalone"
            ),
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
            self.last_update_asset_name = str(update_info.get("asset_name", "") or "")
            update_info["expected_sha256"] = expected_sha256

            with tempfile.NamedTemporaryFile(
                prefix="coupuas_update_",
                suffix=".exe",
                dir=str(self._secure_update_temp_dir()),
                delete=False,
            ) as tmp:
                temp_file = tmp.name
            if not secure_file_permissions(temp_file):
                Path(temp_file).unlink(missing_ok=True)
                raise PermissionError("Unable to secure the downloaded update")

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
                        raise ValueError("업데이트 다운로드가 허용된 최대 크기를 초과했습니다.")
                    if progress_callback and total_size > 0:
                        progress_callback((downloaded / total_size) * 100)

            actual_sha256 = self._compute_sha256(temp_file)
            if actual_sha256 != expected_sha256:
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                raise ValueError("다운로드된 업데이트 체크섬이 일치하지 않습니다.")
            if not self._verify_authenticode_signature(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                raise ValueError("다운로드된 업데이트 서명 검증에 실패했습니다.")

            return temp_file

        except Exception as e:
            if "temp_file" in locals():
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            print(f"다운로드 오류: {e}")
            return None

    def install_update(self, update_file: str, expected_sha256: str = "", asset_name: str = "") -> bool:
        try:
            if not self._verify_authenticode_signature(update_file):
                print("업데이트 서명 검증에 실패했습니다.")
                return False

            expected_sha = str(expected_sha256 or self.last_expected_sha256 or "").strip().lower()
            if not expected_sha:
                print("예상 업데이트 체크섬 정보가 없습니다.")
                return False
            actual_sha = self._compute_sha256(update_file)
            if actual_sha != expected_sha:
                print("업데이트 체크섬 검증에 실패했습니다.")
                return False

            if not getattr(sys, "frozen", False):
                print("자동 업데이트는 패키징된 실행 파일 모드에서만 지원됩니다.")
                return False

            update_asset_name = str(asset_name or self.last_update_asset_name or "").strip()
            if update_asset_name.lower() == self.INSTALLER_ASSET_NAME.lower():
                return self._run_installer_update(update_file, expected_sha)

            current_exe = sys.executable

            backup_exe = current_exe + ".backup"
            if os.path.exists(backup_exe):
                try:
                    os.remove(backup_exe)
                except OSError:
                    pass

            shutil.copy2(current_exe, backup_exe)
            update_script = self._create_update_script()

            popen_process(
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
                system_command=True,
                operation="updater.install_standalone",
            )
            return True

        except Exception as e:
            print(f"업데이트 설치 오류: {e}")
            return False

    def _run_installer_update(self, installer_path: str, expected_sha256: str) -> bool:
        if os.name != "nt":
            print("설치형 업데이트는 Windows에서만 지원됩니다.")
            return False
        if not Path(installer_path).exists():
            print("설치 파일을 찾을 수 없습니다.")
            return False

        update_script = self._create_installer_update_script()
        popen_process(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "RemoteSigned",
                "-File",
                update_script,
                "-Installer",
                str(installer_path),
                "-AppExe",
                str(sys.executable),
                "-ParentPid",
                str(os.getpid()),
                "-ExpectedSha256",
                str(expected_sha256),
                "-TrustedThumbprints",
                ",".join(sorted(self.trusted_thumbprints)),
                "-TrustedPublishers",
                ",".join(sorted(self.trusted_publishers)),
            ],
            system_command=True,
            operation="updater.install_package",
            close_fds=True,
        )
        return True

    def _create_installer_update_script(self) -> str:
        """Create a detached installer runner that relaunches the updated app."""
        installer_args = ", ".join(
            "'" + value.replace("'", "''") + "'" for value in self.INSTALLER_ARGS
        )
        script_content = f"""param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$AppExe,
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256,
    [string]$TrustedThumbprints = '',
    [string]$TrustedPublishers = ''
)
$ErrorActionPreference = 'Stop'
$installerLock = $null

function Normalize-Identity([string]$value) {{
    if (-not $value) {{ return '' }}
    return [regex]::Replace($value.ToLowerInvariant(), '[^a-z0-9]+', '')
}}

function Parse-TrustedList([string]$value, [bool]$normalize) {{
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    if (-not $value) {{ return $set }}
    foreach ($item in $value.Split(',')) {{
        $candidate = $item.Trim()
        if ($normalize) {{ $candidate = Normalize-Identity($candidate) }}
        else {{ $candidate = $candidate.ToUpperInvariant() }}
        if ($candidate) {{ [void]$set.Add($candidate) }}
    }}
    return $set
}}

function Get-SubjectIdentities([string]$subject) {{
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    if (-not $subject) {{ return $set }}
    $matches = [regex]::Matches($subject, '(?:^|,\\s*)(CN|O|OU)\\s*=\\s*([^,]+)')
    foreach ($match in $matches) {{
        $normalized = Normalize-Identity($match.Groups[2].Value)
        if ($normalized) {{ [void]$set.Add($normalized) }}
    }}
    return $set
}}

try {{
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {{
        Start-Sleep -Milliseconds 250
    }}
    if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {{
        throw 'Application did not stop before update deadline.'
    }}

    # Hold a read handle that denies write/delete sharing from verification through setup exit.
    $installerLock = [System.IO.File]::Open(
        $Installer,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    $actualHash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedSha256.ToLowerInvariant()) {{
        throw 'Installer checksum mismatch.'
    }}

    $signature = Get-AuthenticodeSignature -FilePath $Installer
    $certificate = $signature.SignerCertificate
    if (-not $certificate) {{ throw 'Installer signer certificate is missing.' }}
    $thumbprint = $certificate.Thumbprint.ToUpperInvariant()
    $trustedThumbSet = Parse-TrustedList $TrustedThumbprints $false
    if ($trustedThumbSet.Count -eq 0 -or -not $trustedThumbSet.Contains($thumbprint)) {{
        throw 'Installer signer thumbprint is not trusted.'
    }}
    $trustedPublisherSet = Parse-TrustedList $TrustedPublishers $true
    if ($trustedPublisherSet.Count -gt 0) {{
        $publisherMatch = $false
        foreach ($subjectId in (Get-SubjectIdentities $certificate.Subject)) {{
            if ($trustedPublisherSet.Contains($subjectId)) {{
                $publisherMatch = $true
                break
            }}
        }}
        if (-not $publisherMatch) {{ throw 'Installer signer publisher is not trusted.' }}
    }}

    $status = $signature.Status.ToString()
    if ($status -ne 'Valid') {{
        $statusMessage = [string]$signature.StatusMessage
        $chainOnly = $status -eq 'NotTrusted' -or (
            $status -eq 'UnknownError' -and
            $statusMessage -match '(?i)not trusted|root certificate|trust provider'
        )
        if (-not $chainOnly) {{
            throw ('Installer signature status is not allowed: ' + $status)
        }}
    }}

    $arguments = @({installer_args})
    $process = Start-Process -FilePath $Installer -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {{
        throw "Installer failed with exit code $($process.ExitCode)."
    }}
    if (Test-Path -LiteralPath $AppExe) {{ Start-Process -FilePath $AppExe }}
}} catch {{
    # If setup fails, reopen the existing binary so saved work can resume.
    if (Test-Path -LiteralPath $AppExe) {{ Start-Process -FilePath $AppExe }}
}} finally {{
    if ($installerLock) {{ $installerLock.Dispose() }}
    Remove-Item -LiteralPath $Installer -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""
        fd, script_path = tempfile.mkstemp(
            suffix=".ps1",
            prefix="install_coupuas_",
            dir=str(self._secure_update_temp_dir()),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as script_file:
                script_file.write(script_content)
            if not secure_file_permissions(script_path):
                raise PermissionError("Unable to secure the installer update script")
            return script_path
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            Path(script_path).unlink(missing_ok=True)
            raise

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
$updateLock = $null

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
    $updateLock = [System.IO.File]::Open(
        $UpdateFile,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
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
    if ($updateLock) {
        $updateLock.Dispose()
    }
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
            if not secure_file_permissions(script_path):
                raise PermissionError("Unable to secure the update script")
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
    print(f"현재 버전: {VERSION}")
    print("업데이트 확인 중...")

    update_info = updater.check_for_updates()
    if update_info:
        print(f"\n새 버전 발견: v{update_info['version']}")
        print(f"크기: {update_info['size_mb']:.1f} MB")
        print("\n변경 내역:")
        print(AutoUpdater.get_changelog_summary(update_info["changelog"]))

        response = input("\n지금 다운로드할까요? (y/n): ").strip().lower()
        if response == "y":
            def progress(percent):
                print(f"\r진행률: {percent:.1f}%", end="")

            file_path = updater.download_update(update_info, progress)
            if file_path:
                print(f"\n\n다운로드 완료: {file_path}")
                print("업데이트 설치를 위해 앱을 다시 시작해주세요.")
            else:
                print("\n다운로드에 실패했습니다.")
    else:
        print("\n이미 최신 버전입니다.")
