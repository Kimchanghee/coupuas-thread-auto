import os

import pytest

from src import config, secure_storage
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


def test_config_directory_acl_failure_is_fatal(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(config, "secure_dir_permissions", lambda _path: False)

    with pytest.raises(PermissionError):
        Config()


def test_config_save_fails_closed_when_temp_acl_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = Config()
    cfg.config_file.unlink(missing_ok=True)
    monkeypatch.setattr(config, "secure_file_permissions", lambda _path: False)

    assert cfg.save() is False
    assert not cfg.config_file.exists()
    assert list(cfg.config_dir.glob("config_*.tmp")) == []


def test_fernet_key_is_not_published_when_acl_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(secure_storage, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(secure_storage, "secure_file_permissions", lambda _path: False)

    assert secure_storage._load_or_create_fernet_key() is None
    key_path = tmp_path / ".shorts_thread_maker" / ".secure_storage.key"
    assert not key_path.exists()


def test_secret_protection_failure_preserves_last_good_secret_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = Config()
    cfg.secrets_file.write_text('{"instagram_password":"stale"}', encoding="utf-8")
    cfg.instagram_password = "replacement"
    monkeypatch.setattr(config, "protect_secret", lambda *_args: None)

    assert cfg._save_secrets() is False
    assert cfg.secrets_file.read_text(encoding="utf-8") == '{"instagram_password":"stale"}'


def test_config_save_rolls_back_both_files_when_secret_write_fails(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = Config()
    cfg.instagram_password = "last-good-password"
    cfg.upload_interval = 111
    assert cfg.save() is True
    old_config = cfg.config_file.read_bytes()
    old_secrets = cfg.secrets_file.read_bytes()

    cfg.instagram_password = "replacement-password"
    cfg.upload_interval = 222

    def fail_after_partial_secret_write():
        cfg.secrets_file.write_text('{"partial":"write"}', encoding="utf-8")
        return False

    monkeypatch.setattr(cfg, "_save_secrets", fail_after_partial_secret_write)

    assert cfg.save() is False
    assert cfg.config_file.read_bytes() == old_config
    assert cfg.secrets_file.read_bytes() == old_secrets


@pytest.mark.parametrize(
    ("stored_value", "expected"),
    [("not-a-number", 60), (-10, 30), (0, 60)],
)
def test_malformed_upload_interval_falls_back_safely(
    monkeypatch,
    tmp_path,
    stored_value,
    expected,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = Config()

    cfg._load_from_dict({"upload_interval": stored_value})

    assert cfg.upload_interval == expected

