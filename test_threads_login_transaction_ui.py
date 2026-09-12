from types import SimpleNamespace

from src import main_window
from src.threads_login_transaction import ThreadsLoginTransactionResult


class _Signal:
    def __init__(self):
        self.values = []

    def emit(self, value):
        self.values.append(value)


class _Agent:
    def __init__(self, commit_result=True):
        self.commit_result = commit_result
        self.committed = []
        self.discarded = []

    def commit_staged_session(self, path):
        self.committed.append(path)
        return self.commit_result

    def discard_staged_session(self, path):
        self.discarded.append(path)
        return True


class _Config:
    def __init__(self, save_results=(True,)):
        self.account = SimpleNamespace(
            account_id="account-1",
            expected_username="old_user",
        )
        self.active_threads_account_id = "account-1"
        self.instagram_username = "old_user"
        self._save_results = list(save_results)
        self.load_calls = 0

    def get_threads_account(self, account_id):
        return self.account if account_id == self.account.account_id else None

    def update_threads_account(self, account_id, *, expected_username):
        assert account_id == self.account.account_id
        self.account.expected_username = expected_username

    def save(self):
        return self._save_results.pop(0) if self._save_results else True

    def load(self):
        self.load_calls += 1


class _Window:
    def __init__(self):
        self._closed = False
        self._threads_login_account_id = "account-1"
        self._threads_login_browser_open = True
        self.signals = SimpleNamespace(log=_Signal())
        self.checked = []
        self.statuses = []
        self.activities = []
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = enabled

    def _restore_login_btn(self):
        return None

    def _log_user_activity(self, action, content, **kwargs):
        self.activities.append((action, content, kwargs))

    def _update_login_status_for_account(self, account_id, state, text):
        self.statuses.append((account_id, state, text))

    def _check_login_status(self, account_id):
        self.checked.append(account_id)

    def _refresh_threads_account_ui(self, _account_id):
        return None


def _success_payload(agent):
    return {
        "success": True,
        "reason": "verified",
        "account_id": "account-1",
        "verified_username": "new_user",
        "staged_path": "candidate.stage",
        "agent": agent,
    }


def test_verified_login_commits_config_then_session(monkeypatch):
    fake_config = _Config()
    monkeypatch.setattr(main_window, "config", fake_config)
    agent = _Agent(commit_result=True)
    window = _Window()
    calls = []

    def commit_transaction(config, target_agent, staged_path, **values):
        calls.append((config, target_agent, staged_path, values))
        config.instagram_username = values["verified_username"]
        config.update_threads_account(
            values["account_id"],
            expected_username=values["verified_username"],
        )
        return target_agent.commit_staged_session(staged_path)

    monkeypatch.setattr(main_window, "commit_threads_login_transaction", commit_transaction)

    main_window.MainWindow._on_threads_browser_closed(
        window,
        _success_payload(agent),
    )

    assert fake_config.instagram_username == "new_user"
    assert fake_config.account.expected_username == "new_user"
    assert agent.committed == ["candidate.stage"]
    assert calls[0][3] == {
        "account_id": "account-1",
        "verified_username": "new_user",
    }
    assert window.checked == ["account-1"]
    assert window.activities[-1][0] == "threads_login_committed"


def test_failed_session_commit_rolls_back_config_and_preserves_login(monkeypatch):
    fake_config = _Config(save_results=(True, True))
    monkeypatch.setattr(main_window, "config", fake_config)
    monkeypatch.setattr(main_window, "show_error", lambda *_args, **_kwargs: None)
    agent = _Agent(commit_result=False)
    window = _Window()
    monkeypatch.setattr(
        main_window,
        "commit_threads_login_transaction",
        lambda *_args, **_kwargs: False,
    )

    main_window.MainWindow._on_threads_browser_closed(
        window,
        _success_payload(agent),
    )

    assert fake_config.instagram_username == "old_user"
    assert fake_config.account.expected_username == "old_user"
    assert agent.discarded == ["candidate.stage"]
    assert window.checked == []
    assert window.statuses[-1][1] == "error"


def test_recovery_required_does_not_claim_previous_login_is_already_restored(
    monkeypatch,
):
    fake_config = _Config()
    monkeypatch.setattr(main_window, "config", fake_config)
    monkeypatch.setattr(
        main_window,
        "commit_threads_login_transaction",
        lambda *_args, **_kwargs: ThreadsLoginTransactionResult("recovery_required"),
    )
    shown = []
    monkeypatch.setattr(
        main_window,
        "show_error",
        lambda _parent, _title, message: shown.append(message),
    )
    quit_calls = []
    fake_app = SimpleNamespace(quit=lambda: quit_calls.append(True))
    monkeypatch.setattr(
        main_window,
        "QApplication",
        SimpleNamespace(instance=lambda: fake_app),
    )
    monkeypatch.setattr(
        main_window,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )
    agent = _Agent(commit_result=False)
    window = _Window()

    main_window.MainWindow._on_threads_browser_closed(
        window,
        _success_payload(agent),
    )

    assert "재시작" in window.statuses[-1][2]
    assert "기존 로그인은 유지" not in window.statuses[-1][2]
    assert "재시작" in shown[-1]
    assert window.enabled is False
    assert quit_calls == [True]


def test_unverified_login_discards_candidate_without_config_change(monkeypatch):
    fake_config = _Config()
    monkeypatch.setattr(main_window, "config", fake_config)
    agent = _Agent()
    window = _Window()

    main_window.MainWindow._on_threads_browser_closed(
        window,
        {
            "success": False,
            "reason": "account_mismatch",
            "account_id": "account-1",
            "staged_path": "candidate.stage",
            "agent": agent,
        },
    )

    assert fake_config.instagram_username == "old_user"
    assert fake_config.account.expected_username == "old_user"
    assert agent.committed == []
    assert agent.discarded == ["candidate.stage"]
    assert window.checked == []


def test_login_worker_validates_the_exact_captured_candidate_state():
    source = open(main_window.__file__, encoding="utf-8").read()
    flow = source[
        source.index("    def _open_threads_login(self):") :
        source.index("    def _restore_login_btn(self):")
    ]

    capture = flow.index("candidate_state = agent.capture_session_state()")
    validate = flow.index("agent.validate_session_state_identity(")
    stage = flow.index("agent.stage_session(candidate_state)")
    assert capture < validate < stage
    assert "agent.stage_session()" not in flow
