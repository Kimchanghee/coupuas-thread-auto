import json

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
