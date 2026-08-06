import json
from pathlib import Path

from src import auto_updater


class _Completed:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)


class _ReleaseResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _ReleaseSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}

    def get(self, *args, **kwargs):
        return _ReleaseResponse(self.payload)


def test_frozen_build_without_pinned_signer_does_not_offer_updates(monkeypatch):
    monkeypatch.setattr(auto_updater.sys, "frozen", True, raising=False)
    monkeypatch.setattr(auto_updater.AutoUpdater, "DEFAULT_TRUSTED_SIGNER_THUMBPRINTS", set())

    class _NoNetworkSession:
        def get(self, *_args, **_kwargs):
            raise AssertionError("an unpinned frozen build must not contact the updater")

    updater = auto_updater.AutoUpdater("3.0.61")
    updater.session = _NoNetworkSession()

    assert updater.check_for_updates() is None


def test_verify_authenticode_accepts_pinned_self_signed_trust_chain_error(monkeypatch):
    monkeypatch.setattr(auto_updater.os, "name", "nt")
    monkeypatch.setenv("COUPUAS_TRUSTED_SIGNER_THUMBPRINTS", "ABC123")

    def _fake_run(*args, **kwargs):
        return _Completed(
            {
                "Status": "UnknownError",
                "StatusMessage": "A certificate chain processed, but terminated in a root certificate which is not trusted by the trust provider.",
                "Subject": "CN=YM, O=YM",
                "Thumbprint": "ABC123",
            }
        )

    monkeypatch.setattr(auto_updater.subprocess, "run", _fake_run)

    updater = auto_updater.AutoUpdater("3.0.5")

    assert updater._verify_authenticode_signature("update.exe") is True


def test_verify_authenticode_rejects_hash_mismatch_even_when_thumbprint_matches(monkeypatch):
    monkeypatch.setattr(auto_updater.os, "name", "nt")
    monkeypatch.setenv("COUPUAS_TRUSTED_SIGNER_THUMBPRINTS", "ABC123")

    def _fake_run(*args, **kwargs):
        return _Completed(
            {
                "Status": "HashMismatch",
                "StatusMessage": "The hash value is not correct.",
                "Subject": "CN=YM, O=YM",
                "Thumbprint": "ABC123",
            }
        )

    monkeypatch.setattr(auto_updater.subprocess, "run", _fake_run)

    updater = auto_updater.AutoUpdater("3.0.5")

    assert updater._verify_authenticode_signature("update.exe") is False


def test_check_for_updates_prefers_installer_asset(monkeypatch):
    release_payload = {
        "tag_name": "v3.0.6",
        "author": {"id": auto_updater.AutoUpdater.GITHUB_OWNER_ID, "login": "Kimchanghee"},
        "published_at": "2026-05-21T00:00:00Z",
        "assets": [
            {
                "name": "CoupangThreadAuto.exe",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.6/CoupangThreadAuto.exe",
                "size": 100,
            },
            {
                "name": "CoupangThreadAuto.exe.sha256",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.6/CoupangThreadAuto.exe.sha256",
                "size": 64,
            },
            {
                "name": "CoupangThreadAutoSetup.exe",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.6/CoupangThreadAutoSetup.exe",
                "size": 100,
            },
            {
                "name": "CoupangThreadAutoSetup.exe.sha256",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.6/CoupangThreadAutoSetup.exe.sha256",
                "size": 64,
            },
        ],
    }
    updater = auto_updater.AutoUpdater("3.0.5")
    updater.session = _ReleaseSession(release_payload)

    info = updater.check_for_updates()

    assert info["asset_name"] == "CoupangThreadAutoSetup.exe"
    assert info["asset_kind"] == "installer"
    assert info["checksum_asset_name"] == "CoupangThreadAutoSetup.exe.sha256"


def test_check_for_updates_accepts_official_github_actions_release_author():
    release_payload = {
        "tag_name": "v3.0.56",
        "author": {
            "id": auto_updater.AutoUpdater.GITHUB_ACTIONS_BOT_ID,
            "login": "github-actions[bot]",
        },
        "published_at": "2026-08-02T00:00:00Z",
        "assets": [
            {
                "name": "CoupangThreadAutoSetup.exe",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.56/CoupangThreadAutoSetup.exe",
                "size": 100,
            },
            {
                "name": "CoupangThreadAutoSetup.exe.sha256",
                "browser_download_url": "https://github.com/Kimchanghee/coupuas-thread-auto/releases/download/v3.0.56/CoupangThreadAutoSetup.exe.sha256",
                "size": 64,
            },
        ],
    }
    updater = auto_updater.AutoUpdater("3.0.55")
    updater.session = _ReleaseSession(release_payload)

    info = updater.check_for_updates()

    assert info["version"] == "3.0.56"
    assert info["asset_name"] == "CoupangThreadAutoSetup.exe"


def test_release_author_requires_matching_trusted_id_and_login():
    updater = auto_updater.AutoUpdater("3.0.55")
    assert updater._verify_release_author(
        {"author": {"id": auto_updater.AutoUpdater.GITHUB_ACTIONS_BOT_ID, "login": "attacker"}}
    ) is False
    assert updater._verify_release_author(
        {"author": {"id": 123, "login": "github-actions[bot]"}}
    ) is False


def test_installer_update_uses_detached_runner_and_relaunches_app(monkeypatch, tmp_path):
    installer = tmp_path / "CoupangThreadAutoSetup.exe"
    installer.write_bytes(b"signed-installer-placeholder")
    script = tmp_path / "install-update.ps1"
    script.write_text("Start-Process -FilePath $AppExe", encoding="utf-8")
    calls = []

    monkeypatch.setattr(auto_updater.os, "name", "nt")
    monkeypatch.setattr(auto_updater.sys, "executable", r"C:\Program Files\Thread Auto\CoupangThreadAuto.exe")
    monkeypatch.setattr(auto_updater.AutoUpdater, "_create_installer_update_script", lambda self: str(script))
    monkeypatch.setattr(auto_updater.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))

    updater = auto_updater.AutoUpdater("3.0.54")
    expected_sha = "a" * 64
    updater.trusted_thumbprints = {"B" * 40}
    assert updater._run_installer_update(str(installer), expected_sha) is True
    args, kwargs = calls[0]
    assert args[:5] == ["powershell", "-NoProfile", "-ExecutionPolicy", "RemoteSigned", "-File"]
    assert "-AppExe" in args
    assert args[args.index("-ExpectedSha256") + 1] == expected_sha
    assert args[args.index("-TrustedThumbprints") + 1] == "B" * 40
    assert str(installer) in args
    assert kwargs["shell"] is False
    assert "creationflags" in kwargs


def test_installer_runner_waits_installs_relaunches_and_self_cleans(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_updater.AutoUpdater, "_secure_update_temp_dir", staticmethod(lambda: tmp_path))
    updater = auto_updater.AutoUpdater("3.0.54")
    path = Path(updater._create_installer_update_script())
    content = path.read_text(encoding="utf-8")
    assert "Get-Process -Id $ParentPid" in content
    assert "[System.IO.File]::Open" in content
    assert "Get-FileHash -LiteralPath $Installer" in content
    assert "Get-AuthenticodeSignature -FilePath $Installer" in content
    assert "Installer signer thumbprint is not trusted" in content
    assert "Start-Process -FilePath $Installer" in content
    assert "Start-Process -FilePath $AppExe" in content
    assert "If setup fails, reopen the existing binary" in content
    assert "Remove-Item -LiteralPath $PSCommandPath" in content


def test_standalone_runner_locks_update_during_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_updater.AutoUpdater, "_secure_update_temp_dir", staticmethod(lambda: tmp_path))
    updater = auto_updater.AutoUpdater("3.0.54")
    path = Path(updater._create_update_script())
    content = path.read_text(encoding="utf-8")

    assert "$updateLock = [System.IO.File]::Open" in content
    assert "[System.IO.FileShare]::Read" in content
    assert "Get-FileHash -LiteralPath $UpdateFile" in content
    assert "$updateLock.Dispose()" in content
