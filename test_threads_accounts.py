import json

import pytest

from src.config import Config
from src.models.threads_account import ThreadsAccount, normalize_threads_username


def _use_config_home(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.Path.home", lambda: tmp_path)


def test_threads_account_normalizes_username_and_keeps_ids_stable():
    account = ThreadsAccount.create("https://www.threads.com/@Example_User", display_name="Primary")

    changed = account.updated(expected_username="@new.name", display_name="Renamed")

    assert account.expected_username == "example_user"
    assert changed.expected_username == "new.name"
    assert changed.account_id == account.account_id
    assert changed.profile_id == account.profile_id
    with pytest.raises(ValueError, match="변경할 수 없습니다"):
        account.updated(profile_id="other")


@pytest.mark.parametrize(
    "value",
    [
        "bad name",
        "@",
        "a!b",
        "https://example.com/@name",
        "https://www.threads.com/@name/post/example",
        "https://www.threads.net/@name/post/example",
    ],
)
def test_threads_username_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_threads_username(value)


def test_config_migrates_legacy_username_and_preserves_legacy_reads(monkeypatch, tmp_path):
    _use_config_home(monkeypatch, tmp_path)
    config_dir = tmp_path / ".shorts_thread_maker"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"instagram_username": "@Legacy_User"}), encoding="utf-8")

    cfg = Config()

    account = cfg.get_active_threads_account()
    assert cfg.instagram_username == "@Legacy_User"
    assert account.expected_username == "legacy_user"
    assert account.profile_id == ".threads_profile_Legacy_User"
    assert json.loads(cfg.config_file.read_text(encoding="utf-8"))["active_threads_account_id"] == account.account_id


def test_config_account_crud_persists_and_enforces_limit(monkeypatch, tmp_path):
    _use_config_home(monkeypatch, tmp_path)
    cfg = Config()
    first = cfg.add_threads_account("@first")
    cfg.update_threads_account(first.account_id, expected_username="second")
    cfg.set_active_threads_account(first.account_id)
    cfg.save()

    restored = Config()
    assert restored.get_active_threads_account().expected_username == "second"
    for number in range(9):
        restored.add_threads_account(f"user{number}")
    with pytest.raises(ValueError, match="최대 10개"):
        restored.add_threads_account("overflow")
    restored.remove_threads_account(first.account_id)
    assert restored.get_threads_account(first.account_id) is None
