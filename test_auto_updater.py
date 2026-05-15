import json

from src import auto_updater


class _Completed:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)


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
