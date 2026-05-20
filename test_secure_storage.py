import os

from src.config import Config
from src.secure_storage import protect_secret, unprotect_secret


def test_protect_unprotect_secret_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    plain = "unit-test-secret-value"
    protected = protect_secret(plain, "shorts_thread_maker.test")

    assert isinstance(protected, str)
    assert protected
    assert protected != plain
    assert unprotect_secret(protected) == plain

    if os.name != "nt":
        key_path = tmp_path / ".shorts_thread_maker" / ".secure_storage.key"
        assert key_path.exists()


def test_config_persists_gemini_keys_across_reload(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    keys = [
        "AIzaSyA_test_key_1_1234567890",
        "AIzaSyA_test_key_2_1234567890",
    ]

    cfg = Config()
    cfg.set_gemini_api_keys(keys)
    cfg.save()

    reloaded = Config()
    assert reloaded.get_gemini_api_keys() == keys
    assert reloaded.gemini_api_key == keys[0]

