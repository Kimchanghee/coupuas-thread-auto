from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import computer_use_agent


def _storage_state(secret: str = "new-secret"):
    return {
        "cookies": [{"name": "sessionid", "value": secret}],
        "origins": [],
    }


def _agent(tmp_path: Path, state=None):
    agent = object.__new__(computer_use_agent.ComputerUseAgent)
    agent.profile_name = "transaction-test"
    agent.profile_path = tmp_path
    agent.profile_dir = str(tmp_path)
    agent.legacy_profile_path = None
    agent.context = SimpleNamespace(
        storage_state=lambda: state or _storage_state()
    )
    agent.browser = None
    agent.playwright = None
    agent.page = None
    agent.headless = True
    agent._load_saved_session_default = True
    return agent


@pytest.fixture
def protected_session(monkeypatch):
    protected_payloads = {}

    def protect(payload, _purpose):
        token = f"fernet:test-{len(protected_payloads)}"
        protected_payloads[token] = payload
        return token

    monkeypatch.setattr(computer_use_agent, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(computer_use_agent, "secure_file_permissions", lambda _path: True)
    monkeypatch.setattr(computer_use_agent, "protect_secret", protect)
    monkeypatch.setattr(
        computer_use_agent,
        "unprotect_secret",
        lambda token: protected_payloads.get(token),
    )
    return protect


def test_profile_directory_acl_failure_is_fatal(tmp_path, monkeypatch):
    acl_results = iter((True, False))
    monkeypatch.setattr(computer_use_agent.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        computer_use_agent,
        "secure_dir_permissions",
        lambda _path: next(acl_results),
    )

    with pytest.raises(PermissionError, match="세션 디렉터리 권한"):
        computer_use_agent.ComputerUseAgent._resolve_profile_path("unsafe-profile")


def test_stage_is_encrypted_sibling_and_discard_preserves_previous_bytes(
    tmp_path,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_bytes(b"previous-session-bytes")

    staged_path = agent.stage_session()

    assert staged_path.parent == tmp_path
    assert staged_path.name.startswith(agent.SESSION_STAGE_PREFIX)
    assert b"new-secret" not in staged_path.read_bytes()
    assert saved_path.read_bytes() == b"previous-session-bytes"

    assert agent.discard_staged_session(staged_path) is True
    assert not staged_path.exists()
    assert saved_path.read_bytes() == b"previous-session-bytes"


def test_successful_commit_atomically_replaces_previous_session(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_bytes(b"previous-session-bytes")
    staged_path = agent.stage_session()
    expected_bytes = staged_path.read_bytes()
    real_replace = computer_use_agent.os.replace
    replacements = []

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    monkeypatch.setattr(computer_use_agent.os, "replace", record_replace)

    assert agent.commit_staged_session(staged_path) is True
    assert saved_path.read_bytes() == expected_bytes
    assert not staged_path.exists()
    assert any(source == staged_path and destination == saved_path for source, destination in replacements)
    assert list(tmp_path.glob(f"{agent.SESSION_BACKUP_PREFIX}*")) == []


def test_final_acl_failure_rolls_back_exact_previous_bytes(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    previous = b"previous-session-bytes"
    saved_path.write_bytes(previous)
    staged_path = agent.stage_session()
    final_checks = 0

    def fail_new_final_once(path):
        nonlocal final_checks
        if Path(path).name == agent.SESSION_FILENAME:
            final_checks += 1
            # Existing final precheck succeeds, new final post-replace fails,
            # and the restored rollback file succeeds.
            return final_checks != 2
        return True

    monkeypatch.setattr(computer_use_agent, "secure_file_permissions", fail_new_final_once)

    assert agent.commit_staged_session(staged_path) is False
    assert saved_path.read_bytes() == previous
    assert list(tmp_path.glob(f"{agent.SESSION_BACKUP_PREFIX}*")) == []


def test_failed_rollback_preserves_the_only_exact_backup(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    previous = b"only-recoverable-previous-session"
    saved_path.write_bytes(previous)
    staged_path = agent.stage_session()
    final_checks = 0

    def fail_new_final_once(path):
        nonlocal final_checks
        if Path(path).name == agent.SESSION_FILENAME:
            final_checks += 1
            return final_checks != 2
        return True

    real_replace = computer_use_agent.os.replace

    def fail_restore_replace(source, destination):
        if ".restore." in Path(source).name:
            raise OSError("simulated rollback replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(computer_use_agent, "secure_file_permissions", fail_new_final_once)
    monkeypatch.setattr(computer_use_agent.os, "replace", fail_restore_replace)

    assert agent.commit_staged_session(staged_path) is False
    backups = list(tmp_path.glob(f"{agent.SESSION_BACKUP_PREFIX}*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == previous


def test_close_attempts_every_resource_after_individual_failures(tmp_path):
    agent = _agent(tmp_path)
    calls = []

    class Resource:
        def __init__(self, name, operation, fail=False):
            self.name = name
            self.operation = operation
            self.fail = fail

        def close(self):
            assert self.operation == "close"
            calls.append(self.name)
            if self.fail:
                raise RuntimeError(self.name)

        def stop(self):
            assert self.operation == "stop"
            calls.append(self.name)
            if self.fail:
                raise RuntimeError(self.name)

    agent.context = Resource("context", "close", fail=True)
    agent.browser = Resource("browser", "close", fail=True)
    agent.playwright = Resource("playwright", "stop")

    agent.close(save_session=False)

    assert calls == ["context", "browser", "playwright"]
    assert agent.context is None
    assert agent.browser is None
    assert agent.playwright is None
    assert agent.page is None


def test_directory_acl_failure_stops_staging_and_preserves_previous_session(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_bytes(b"previous-session-bytes")
    monkeypatch.setattr(computer_use_agent, "secure_dir_permissions", lambda _path: False)

    with pytest.raises(PermissionError, match="디렉터리 권한"):
        agent.stage_session()

    assert saved_path.read_bytes() == b"previous-session-bytes"
    assert list(tmp_path.glob(f"{agent.SESSION_STAGE_PREFIX}*")) == []


def test_candidate_acl_failure_cleans_temp_and_preserves_previous_session(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_bytes(b"previous-session-bytes")
    monkeypatch.setattr(computer_use_agent, "secure_file_permissions", lambda _path: False)

    with pytest.raises(PermissionError, match="후보 브라우저 세션"):
        agent.stage_session()

    assert saved_path.read_bytes() == b"previous-session-bytes"
    assert list(tmp_path.glob(f"{agent.SESSION_STAGE_PREFIX}*")) == []


def test_rollback_backup_acl_failure_blocks_replace_and_preserves_previous_session(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    previous = b"previous-session-bytes"
    saved_path.write_bytes(previous)
    staged_path = agent.stage_session()

    def reject_backup(path):
        return not Path(path).name.startswith(agent.SESSION_BACKUP_PREFIX)

    monkeypatch.setattr(computer_use_agent, "secure_file_permissions", reject_backup)

    assert agent.commit_staged_session(staged_path) is False
    assert saved_path.read_bytes() == previous
    assert staged_path.exists()
    assert agent.discard_staged_session(staged_path) is True
    assert list(tmp_path.glob(f"{agent.SESSION_BACKUP_PREFIX}*")) == []


@pytest.mark.parametrize(
    "candidate_payload",
    (
        "not-an-encrypted-session",
        json.dumps(_storage_state("plaintext-tamper")),
        "encrypted-invalid-shape",
    ),
)
def test_corrupt_or_invalid_candidate_preserves_previous_session(
    tmp_path,
    protected_session,
    candidate_payload,
):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    previous = b"previous-session-bytes"
    saved_path.write_bytes(previous)
    staged_path = agent.stage_session()
    if candidate_payload == "encrypted-invalid-shape":
        candidate_payload = protected_session(
            json.dumps({"cookies": {}, "origins": []}),
            "unused-purpose",
        )
    staged_path.write_text(candidate_payload, encoding="utf-8")

    assert agent.commit_staged_session(staged_path) is False
    assert saved_path.read_bytes() == previous
    assert staged_path.exists()


def test_plaintext_secure_session_file_is_never_loaded(tmp_path, protected_session):
    agent = _agent(tmp_path)
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_text(json.dumps(_storage_state("plaintext")), encoding="utf-8")

    assert agent._load_storage_state() is None


class _BrowserContext:
    def __init__(self):
        self.page = object()
        self.closed = False

    def route(self, _pattern, _handler):
        pass

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class _Browser:
    def __init__(self):
        self.context_kwargs = None
        self.contexts = []

    def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        context = _BrowserContext()
        self.contexts.append(context)
        return context


def test_start_browser_can_skip_saved_session_without_deleting_it(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    agent.context = None
    saved_path = tmp_path / agent.SESSION_FILENAME
    saved_path.write_bytes(b"previous-session-bytes")
    browser = _Browser()
    loaded = []
    fake_playwright = SimpleNamespace(stop=lambda: None)
    monkeypatch.setattr(
        computer_use_agent,
        "sync_playwright",
        lambda: SimpleNamespace(start=lambda: fake_playwright),
    )
    agent._iter_browser_candidates = lambda: [{"label": "fake"}]
    agent._launch_browser = lambda **_kwargs: browser
    agent._load_storage_state = lambda: loaded.append(True) or _storage_state("saved")

    agent.start_browser(load_saved_session=False)

    assert loaded == []
    assert "storage_state" not in browser.context_kwargs
    assert saved_path.read_bytes() == b"previous-session-bytes"


def test_start_browser_loads_saved_session_by_default(
    tmp_path,
    monkeypatch,
    protected_session,
):
    agent = _agent(tmp_path)
    agent.context = None
    browser = _Browser()
    fake_playwright = SimpleNamespace(stop=lambda: None)
    monkeypatch.setattr(
        computer_use_agent,
        "sync_playwright",
        lambda: SimpleNamespace(start=lambda: fake_playwright),
    )
    agent._iter_browser_candidates = lambda: [{"label": "fake"}]
    agent._launch_browser = lambda **_kwargs: browser
    agent._load_storage_state = lambda: _storage_state("saved")

    agent.start_browser()

    assert browser.context_kwargs["storage_state"] == _storage_state("saved")


def test_candidate_identity_is_verified_in_disposable_context(
    tmp_path,
    monkeypatch,
    protected_session,
):
    from src import threads_navigation, threads_playwright_helper

    agent = _agent(tmp_path)
    browser = _Browser()
    agent.browser = browser
    verified = []
    monkeypatch.setattr(
        threads_navigation,
        "goto_threads_with_fallback",
        lambda page, **_kwargs: page,
    )
    monkeypatch.setattr(
        threads_playwright_helper.ThreadsPlaywrightHelper,
        "check_login_status",
        lambda _helper: True,
    )
    monkeypatch.setattr(
        threads_playwright_helper.ThreadsPlaywrightHelper,
        "verify_account",
        lambda _helper, expected: verified.append(expected) or True,
    )
    state = _storage_state()

    assert agent.validate_session_state_identity(state, "expected_user") is True
    assert browser.context_kwargs["storage_state"] == state
    assert verified == ["expected_user"]
    assert browser.contexts[-1].closed is True


def test_candidate_identity_mismatch_fails_and_closes_disposable_context(
    tmp_path,
    monkeypatch,
    protected_session,
):
    from src import threads_navigation, threads_playwright_helper

    agent = _agent(tmp_path)
    browser = _Browser()
    agent.browser = browser
    monkeypatch.setattr(
        threads_navigation,
        "goto_threads_with_fallback",
        lambda page, **_kwargs: page,
    )
    monkeypatch.setattr(
        threads_playwright_helper.ThreadsPlaywrightHelper,
        "check_login_status",
        lambda _helper: True,
    )
    monkeypatch.setattr(
        threads_playwright_helper.ThreadsPlaywrightHelper,
        "verify_account",
        lambda _helper, _expected: False,
    )

    assert agent.validate_session_state_identity(
        _storage_state(),
        "expected_user",
    ) is False
    assert browser.contexts[-1].closed is True
