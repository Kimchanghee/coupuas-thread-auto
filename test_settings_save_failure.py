import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication

from src.ai_provider import AI_PROVIDER_MANAGED
from src.config import config
from src.models.threads_account import ThreadsAccount
import src.main_window as main_window_module


class _ValueWidget:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class _TextWidget:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


class _CheckWidget:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


def _minimal_settings_window(username=""):
    return SimpleNamespace(
        _log_user_activity=lambda *_args, **_kwargs: None,
        hour_spin=_ValueWidget(0),
        min_spin=_ValueWidget(2),
        sec_spin=_ValueWidget(0),
        _selected_ai_provider=lambda: AI_PROVIDER_MANAGED,
        _gemini_key_rows=[{"edit": _TextWidget("")}],
        _visible_gemini_key_rows=1,
        username_edit=_TextWidget(username),
        _normalize_threads_username=main_window_module.MainWindow._normalize_threads_username,
        selected_threads_account_id=lambda: "",
        video_check=_CheckWidget(False),
        _auto_start_check=_CheckWidget(False),
        settings_post_concept_combo=SimpleNamespace(currentData=lambda: "review"),
        _load_settings=lambda: None,
        _refresh_threads_account_ui=lambda *_args: None,
    )


def test_settings_save_failure_does_not_show_false_success(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    account = ThreadsAccount.create("save_test")
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")
    monkeypatch.setattr(config, "threads_accounts", [account])
    monkeypatch.setattr(config, "active_threads_account_id", account.account_id)
    monkeypatch.setattr(config, "instagram_username", account.expected_username)
    monkeypatch.setattr(config, "ai_provider", AI_PROVIDER_MANAGED)
    monkeypatch.setattr(config, "save", lambda: False)
    monkeypatch.setattr(config, "load", lambda: None)

    infos = []
    errors = []
    monkeypatch.setattr(
        main_window_module,
        "show_info",
        lambda _parent, title, message: infos.append((title, message)),
    )
    monkeypatch.setattr(
        main_window_module,
        "show_error",
        lambda _parent, title, message: errors.append((title, message)),
    )

    window = main_window_module.MainWindow()
    try:
        window.username_edit.setText(account.expected_username)
        window._save_settings()

        assert not any(title == "저장 완료" for title, _message in infos)
        assert errors == [
            (
                "설정 저장 실패",
                "설정을 저장하지 못했습니다. 저장 폴더 권한과 디스크 공간을 확인한 뒤 다시 시도해주세요.",
            )
        ]
    finally:
        window._closed = True
        window.close()
        app.processEvents()


def test_invalid_username_does_not_mutate_other_settings(monkeypatch):
    monkeypatch.setattr(config, "upload_interval", 75)
    monkeypatch.setattr(config, "prefer_video", True)
    monkeypatch.setattr(config, "auto_start_enabled", True)
    monkeypatch.setattr(config, "post_concept", "benefit")
    monkeypatch.setattr(config, "instagram_username", "valid_user")
    save_calls = []
    monkeypatch.setattr(config, "save", lambda: save_calls.append(True) or True)
    warnings = []
    monkeypatch.setattr(
        main_window_module,
        "show_warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    fake_window = _minimal_settings_window("bad-user")

    main_window_module.MainWindow._save_settings(fake_window)

    assert config.upload_interval == 75
    assert config.prefer_video is True
    assert config.auto_start_enabled is True
    assert config.post_concept == "benefit"
    assert config.instagram_username == "valid_user"
    assert save_calls == []
    assert warnings and warnings[0][0] == "계정 설정"


def test_clearing_all_gemini_key_rows_clears_saved_keys(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_keys", ["old-key"])
    monkeypatch.setattr(config, "gemini_api_key", "old-key")
    monkeypatch.setattr(config, "upload_interval", 75)
    monkeypatch.setattr(config, "ai_provider", AI_PROVIDER_MANAGED)
    monkeypatch.setattr(config, "prefer_video", True)
    monkeypatch.setattr(config, "auto_start_enabled", False)
    monkeypatch.setattr(config, "post_concept", "benefit")
    monkeypatch.setattr(config, "instagram_username", "")
    monkeypatch.setattr(config, "save", lambda: False)
    monkeypatch.setattr(config, "load", lambda: None)
    monkeypatch.setattr(main_window_module, "show_error", lambda *_args: None)
    fake_window = _minimal_settings_window("")

    main_window_module.MainWindow._save_settings(fake_window)

    assert config.get_gemini_api_keys() == []
    assert config.gemini_api_key == ""
