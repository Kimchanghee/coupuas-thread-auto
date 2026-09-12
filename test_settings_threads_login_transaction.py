from types import SimpleNamespace

from src import settings_dialog
from src.threads_login_transaction import ThreadsLoginTransactionResult


class _Agent:
    def __init__(self, commit=True):
        self.commit = commit
        self.committed = []
        self.discarded = []

    def commit_staged_session(self, path):
        self.committed.append(path)
        return self.commit

    def discard_staged_session(self, path):
        self.discarded.append(path)
        return True


class _Config:
    def __init__(self, save_results=(True,)):
        self.instagram_username = "old_user"
        self.active_threads_account_id = "account-1"
        self.account = SimpleNamespace(expected_username="old_user")
        self.results = list(save_results)
        self.loaded = 0

    def get_threads_account(self, account_id):
        return self.account if account_id == "account-1" else None

    def update_threads_account(self, account_id, *, expected_username):
        assert account_id == "account-1"
        self.account.expected_username = expected_username

    def save(self):
        return self.results.pop(0) if self.results else True

    def load(self):
        self.loaded += 1


class _LineEdit:
    def __init__(self):
        self.value = ""

    def setText(self, value):
        self.value = value


class _Dialog:
    def __init__(self):
        self._closed = False
        self.username_edit = _LineEdit()
        self.statuses = []
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = enabled

    def _restore_login_btn(self):
        return None

    def _update_login_status(self, state, text):
        self.statuses.append((state, text))


def _payload(agent):
    return {
        "success": True,
        "reason": "verified",
        "verified_username": "new_user",
        "staged_path": "candidate.stage",
        "agent": agent,
    }


def test_settings_login_commits_only_verified_candidate(monkeypatch):
    config = _Config()
    monkeypatch.setattr(settings_dialog, "config", config)
    agent = _Agent(commit=True)
    dialog = _Dialog()

    def commit_transaction(config, target_agent, staged_path, **values):
        config.instagram_username = values["verified_username"]
        config.update_threads_account(
            values["account_id"],
            expected_username=values["verified_username"],
        )
        return target_agent.commit_staged_session(staged_path)

    monkeypatch.setattr(settings_dialog, "commit_threads_login_transaction", commit_transaction)

    settings_dialog.SettingsDialog._apply_threads_login_result(dialog, _payload(agent))

    assert config.instagram_username == "new_user"
    assert config.account.expected_username == "new_user"
    assert agent.committed == ["candidate.stage"]
    assert dialog.username_edit.value == "new_user"
    assert dialog.statuses[-1][0] == "success"


def test_settings_login_commit_failure_restores_config(monkeypatch):
    config = _Config(save_results=(True, True))
    monkeypatch.setattr(settings_dialog, "config", config)
    monkeypatch.setattr(settings_dialog, "show_error", lambda *_args, **_kwargs: None)
    agent = _Agent(commit=False)
    dialog = _Dialog()
    monkeypatch.setattr(
        settings_dialog,
        "commit_threads_login_transaction",
        lambda *_args, **_kwargs: False,
    )

    settings_dialog.SettingsDialog._apply_threads_login_result(dialog, _payload(agent))

    assert config.instagram_username == "old_user"
    assert config.account.expected_username == "old_user"
    assert agent.discarded == ["candidate.stage"]
    assert dialog.statuses[-1][0] == "error"


def test_settings_recovery_required_prompts_restart_without_old_state_claim(monkeypatch):
    config = _Config()
    monkeypatch.setattr(settings_dialog, "config", config)
    monkeypatch.setattr(
        settings_dialog,
        "commit_threads_login_transaction",
        lambda *_args, **_kwargs: ThreadsLoginTransactionResult("recovery_required"),
    )
    shown = []
    monkeypatch.setattr(
        settings_dialog,
        "show_error",
        lambda _parent, _title, message: shown.append(message),
    )
    quit_calls = []
    fake_app = SimpleNamespace(quit=lambda: quit_calls.append(True))
    monkeypatch.setattr(
        settings_dialog,
        "QApplication",
        SimpleNamespace(instance=lambda: fake_app),
    )
    monkeypatch.setattr(
        settings_dialog,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )
    agent = _Agent(commit=False)
    dialog = _Dialog()

    settings_dialog.SettingsDialog._apply_threads_login_result(dialog, _payload(agent))

    assert "재시작" in dialog.statuses[-1][1]
    assert "기존 로그인은 유지" not in dialog.statuses[-1][1]
    assert "재시작" in shown[-1]
    assert dialog.enabled is False
    assert quit_calls == [True]


def test_settings_login_worker_uses_fresh_staged_session_contract():
    source = open(settings_dialog.__file__, encoding="utf-8").read()
    flow = source[
        source.index("    def _open_threads_login(self):") :
        source.index("    def _restore_login_btn(self):")
    ]

    assert "load_saved_session=False" in flow
    assert "candidate_state = agent.capture_session_state()" in flow
    assert "agent.validate_session_state_identity(" in flow
    assert "agent.stage_session(candidate_state)" in flow
    assert "agent.close(save_session=False)" in flow
    assert "agent.clear_saved_session()" not in flow
    assert "agent.save_session()" not in flow
