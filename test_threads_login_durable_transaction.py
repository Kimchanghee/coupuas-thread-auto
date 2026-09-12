from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import config as config_module
from src import threads_login_transaction as transaction


class _Config:
    def __init__(self, root: Path):
        self.config_dir = root
        self.config_file = root / "config.json"
        self.secrets_file = root / "secrets.json"
        self.instagram_username = "old_user"
        self.active_threads_account_id = "account-1"
        self.account = SimpleNamespace(expected_username="old_user")
        self.save_result = True
        self.load_calls = 0
        self.persistence_quarantine_reason = ""

    def get_threads_account(self, account_id):
        return self.account if account_id == "account-1" else None

    def update_threads_account(self, account_id, *, expected_username):
        if account_id != "account-1":
            raise KeyError(account_id)
        self.account.expected_username = expected_username

    def save(self):
        if self.persistence_quarantine_reason:
            return False
        self.config_file.write_text(
            json.dumps(
                {
                    "instagram_username": self.instagram_username,
                    "threads_accounts": [
                        {
                            "account_id": "account-1",
                            "expected_username": self.account.expected_username,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.secrets_file.write_text(
            json.dumps({"secret": f"secret-for-{self.instagram_username}"}),
            encoding="utf-8",
        )
        return self.save_result

    def quarantine_persistence(self, reason):
        self.persistence_quarantine_reason = str(reason or "state_recovery_required")

    def load(self):
        self.load_calls += 1
        payload = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.instagram_username = payload["instagram_username"]
        self.account.expected_username = self.instagram_username


class _Agent:
    SESSION_FILENAME = "storage_state.sec"
    SESSION_STAGE_PREFIX = f"{SESSION_FILENAME}.stage."
    SESSION_TEMP_SUFFIX = ".tmp"

    def __init__(self, root: Path, *, commit_result=True):
        self.profile_path = root / "sessions" / "profile-1"
        self.profile_path.mkdir(parents=True)
        self.session_path = self.profile_path / self.SESSION_FILENAME
        self.staged_path = (
            self.profile_path / f"{self.SESSION_STAGE_PREFIX}candidate.tmp"
        )
        self.staged_path.write_bytes(b"new-encrypted-session")
        self.commit_result = commit_result

    def _get_storage_state_path(self):
        return str(self.session_path)

    def _is_valid_staged_session_path(self, value):
        return Path(value) == self.staged_path

    def commit_staged_session(self, staged_path):
        if self.commit_result == "replace_then_fail":
            os.replace(staged_path, self.session_path)
            return False
        if not self.commit_result:
            return False
        os.replace(staged_path, self.session_path)
        return True


@pytest.fixture
def durable_fixture(tmp_path, monkeypatch):
    root = tmp_path / ".shorts_thread_maker"
    root.mkdir()
    monkeypatch.setattr(transaction, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(transaction, "secure_file_permissions", lambda _path: True)
    config = _Config(root)
    config.save()
    config.secrets_file.write_text('{"secret":"old-secret"}', encoding="utf-8")
    agent = _Agent(root)
    agent.session_path.write_bytes(b"old-encrypted-session")
    return root, config, agent


def test_common_transaction_commits_all_three_files(durable_fixture):
    root, config, agent = durable_fixture

    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    assert (
        json.loads(config.config_file.read_text(encoding="utf-8"))["instagram_username"]
        == "new_user"
    )
    assert "new_user" in config.secrets_file.read_text(encoding="utf-8")
    assert agent.session_path.read_bytes() == b"new-encrypted-session"
    assert list(root.glob(f"{transaction._TRANSACTION_PREFIX}*")) == []


def test_locked_backup_cleanup_is_retried_from_committed_journal(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_unlink = Path.unlink
    failed_once = False

    def fail_one_backup_unlink(path, *args, **kwargs):
        nonlocal failed_once
        if path.name == "config.backup" and not failed_once:
            failed_once = True
            raise PermissionError("simulated antivirus file lock")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one_backup_unlink)

    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )
    transaction_dirs = list(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert len(transaction_dirs) == 1
    assert (
        json.loads((transaction_dirs[0] / "journal.json").read_text(encoding="utf-8"))[
            "state"
        ]
        == "committed"
    )
    assert (transaction_dirs[0] / "commit.decision").exists()

    later_config = json.loads(config.config_file.read_text(encoding="utf-8"))
    later_config["theme"] = "dark"
    config.config_file.write_text(json.dumps(later_config), encoding="utf-8")
    config.secrets_file.write_text('{"secret":"later-secret"}', encoding="utf-8")
    agent.session_path.write_bytes(b"later-valid-session")
    later_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )

    assert transaction.recover_pending_threads_login_transactions(root)
    assert config.config_file.read_bytes() == later_bytes[0]
    assert json.loads(config.config_file.read_text(encoding="utf-8"))["theme"] == "dark"
    assert config.secrets_file.read_bytes() == later_bytes[1]
    assert agent.session_path.read_bytes() == later_bytes[2]
    assert list(root.glob(f"{transaction._TRANSACTION_PREFIX}*")) == []


def test_partial_backup_cleanup_never_reopens_committed_rollback(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_unlink = Path.unlink
    backup_unlinks = 0
    failed_once = False

    def fail_after_one_backup_was_deleted(path, *args, **kwargs):
        nonlocal backup_unlinks, failed_once
        if path.name.endswith(".backup"):
            backup_unlinks += 1
            if backup_unlinks == 2 and not failed_once:
                failed_once = True
                raise PermissionError("simulated lock after partial cleanup")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_after_one_backup_was_deleted)

    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )
    transaction_dirs = list(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert len(transaction_dirs) == 1
    transaction_dir = transaction_dirs[0]
    assert (transaction_dir / "journal.json").exists()
    assert (transaction_dir / "commit.decision").exists()
    assert len(list(transaction_dir.glob("*.backup"))) == 2

    later_config = json.loads(config.config_file.read_text(encoding="utf-8"))
    later_config["theme"] = "dark"
    config.config_file.write_text(json.dumps(later_config), encoding="utf-8")
    config.secrets_file.write_text('{"secret":"after-partial-cleanup"}', encoding="utf-8")
    agent.session_path.write_bytes(b"session-after-partial-cleanup")
    later_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )

    assert transaction.recover_pending_threads_login_transactions(root)
    assert config.config_file.read_bytes() == later_bytes[0]
    assert config.secrets_file.read_bytes() == later_bytes[1]
    assert agent.session_path.read_bytes() == later_bytes[2]
    assert not transaction_dir.exists()


def test_unverifiable_existing_commit_decision_never_reopens_rollback(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_unlink = Path.unlink
    failed_once = False

    def retain_committed_artifacts(path, *args, **kwargs):
        nonlocal failed_once
        if path.name == "config.backup" and not failed_once:
            failed_once = True
            raise PermissionError("simulated cleanup lock")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", retain_committed_artifacts)
    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )
    transaction_dir = next(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert (transaction_dir / "journal.json").exists()
    assert (transaction_dir / "commit.decision").exists()

    later_config = json.loads(config.config_file.read_text(encoding="utf-8"))
    later_config["theme"] = "dark"
    config.config_file.write_text(json.dumps(later_config), encoding="utf-8")
    config.secrets_file.write_text('{"secret":"later"}', encoding="utf-8")
    agent.session_path.write_bytes(b"later-session")
    later_targets = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )
    artifacts = {
        child.name: child.read_bytes()
        for child in transaction_dir.iterdir()
        if child.is_file()
    }

    real_fsync_file = transaction._fsync_file
    monkeypatch.setattr(
        transaction,
        "_fsync_file",
        lambda path: (
            False
            if Path(path).name == "commit.decision"
            else real_fsync_file(Path(path))
        ),
    )

    assert not transaction.recover_pending_threads_login_transactions(root)
    assert config.config_file.read_bytes() == later_targets[0]
    assert config.secrets_file.read_bytes() == later_targets[1]
    assert agent.session_path.read_bytes() == later_targets[2]
    assert {
        child.name: child.read_bytes()
        for child in transaction_dir.iterdir()
        if child.is_file()
    } == artifacts


def test_decision_only_cleanup_remnant_preserves_later_config(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_unlink = Path.unlink
    failed_once = False

    def lock_decision_once(path, *args, **kwargs):
        nonlocal failed_once
        if path.name == "commit.decision" and not failed_once:
            failed_once = True
            raise PermissionError("simulated decision cleanup lock")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", lock_decision_once)

    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )
    transaction_dirs = list(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert len(transaction_dirs) == 1
    transaction_dir = transaction_dirs[0]
    assert {child.name for child in transaction_dir.iterdir()} == {"commit.decision"}

    later_config = json.loads(config.config_file.read_text(encoding="utf-8"))
    later_config["theme"] = "dark"
    config.config_file.write_text(json.dumps(later_config), encoding="utf-8")
    later_config_bytes = config.config_file.read_bytes()

    assert transaction.recover_pending_threads_login_transactions(root)
    assert config.config_file.read_bytes() == later_config_bytes
    assert not transaction_dir.exists()


def test_post_replace_commit_marker_exception_reconciles_as_success(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_write_journal = transaction._write_journal
    committed_writes = 0

    def raise_after_committed_replace(transaction_dir, manifest):
        nonlocal committed_writes
        real_write_journal(transaction_dir, manifest)
        if manifest["state"] == "committed":
            committed_writes += 1
            raise OSError("simulated post-replace durability exception")

    monkeypatch.setattr(transaction, "_write_journal", raise_after_committed_replace)

    assert transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    assert committed_writes == 1
    assert config.instagram_username == "new_user"
    assert config.account.expected_username == "new_user"
    assert (
        json.loads(config.config_file.read_text(encoding="utf-8"))["instagram_username"]
        == "new_user"
    )
    assert agent.session_path.read_bytes() == b"new-encrypted-session"
    assert list(root.glob(f"{transaction._TRANSACTION_PREFIX}*")) == []


def test_session_failure_restores_exact_old_config_secrets_and_session(durable_fixture):
    _root, config, agent = durable_fixture
    old_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )
    agent.commit_result = "replace_then_fail"

    assert not transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    assert config.config_file.read_bytes() == old_bytes[0]
    assert config.secrets_file.read_bytes() == old_bytes[1]
    assert agent.session_path.read_bytes() == old_bytes[2]
    assert config.instagram_username == "old_user"
    assert config.account.expected_username == "old_user"


def test_startup_recovery_rolls_back_interrupted_prepared_transaction(durable_fixture):
    root, config, agent = durable_fixture
    old_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )
    transaction_dir, _manifest = transaction._prepare_transaction(
        root,
        agent.session_path,
        account_id="account-1",
        expected_username="new_user",
        candidate_session_digest=hashlib.sha256(agent.staged_path.read_bytes()).hexdigest(),
    )
    config.config_file.write_text('{"instagram_username":"partial"}', encoding="utf-8")
    config.secrets_file.write_text('{"secret":"partial"}', encoding="utf-8")

    assert transaction.recover_pending_threads_login_transactions(root)

    assert config.config_file.read_bytes() == old_bytes[0]
    assert config.secrets_file.read_bytes() == old_bytes[1]
    assert agent.session_path.read_bytes() == old_bytes[2]
    assert not transaction_dir.exists()


def test_startup_recovery_keeps_fully_committed_tuple(durable_fixture):
    root, config, agent = durable_fixture
    candidate_digest = hashlib.sha256(agent.staged_path.read_bytes()).hexdigest()
    transaction_dir, manifest = transaction._prepare_transaction(
        root,
        agent.session_path,
        account_id="account-1",
        expected_username="new_user",
        candidate_session_digest=candidate_digest,
    )
    config.instagram_username = "new_user"
    config.account.expected_username = "new_user"
    config.save()
    os.replace(agent.staged_path, agent.session_path)
    manifest["new_targets"] = transaction._capture_committed_targets(
        root,
        agent.session_path,
        account_id="account-1",
        expected_username="new_user",
        candidate_session_digest=candidate_digest,
    )
    manifest["state"] = "committed"
    transaction._write_journal(transaction_dir, manifest)

    assert transaction.recover_pending_threads_login_transactions(root)

    assert (
        json.loads(config.config_file.read_text(encoding="utf-8"))["instagram_username"]
        == "new_user"
    )
    assert "new_user" in config.secrets_file.read_text(encoding="utf-8")
    assert agent.session_path.read_bytes() == b"new-encrypted-session"
    assert not transaction_dir.exists()


def test_startup_recovery_rejects_mismatched_committed_tuple_and_restores_old(
    durable_fixture,
):
    root, config, agent = durable_fixture
    old_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )
    candidate_digest = hashlib.sha256(agent.staged_path.read_bytes()).hexdigest()
    transaction_dir, manifest = transaction._prepare_transaction(
        root,
        agent.session_path,
        account_id="account-1",
        expected_username="new_user",
        candidate_session_digest=candidate_digest,
    )
    config.instagram_username = "new_user"
    config.account.expected_username = "new_user"
    config.save()
    os.replace(agent.staged_path, agent.session_path)
    manifest["new_targets"] = transaction._capture_committed_targets(
        root,
        agent.session_path,
        account_id="account-1",
        expected_username="new_user",
        candidate_session_digest=candidate_digest,
    )
    manifest["state"] = "committed"
    transaction._write_journal(transaction_dir, manifest)
    agent.session_path.write_bytes(b"mismatched-session-after-marker")

    assert transaction.recover_pending_threads_login_transactions(root)

    assert config.config_file.read_bytes() == old_bytes[0]
    assert config.secrets_file.read_bytes() == old_bytes[1]
    assert agent.session_path.read_bytes() == old_bytes[2]
    assert not transaction_dir.exists()


def test_double_marker_write_ambiguity_returns_recovery_required(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_write_journal = transaction._write_journal
    real_verify_outcome = transaction._verify_committed_outcome

    def ambiguous_marker_write(transaction_dir, manifest):
        if manifest["state"] == "committed":
            real_write_journal(transaction_dir, manifest)
            raise OSError("simulated post-replace committed exception")
        if manifest["state"] == "prepared" and manifest.get("new_targets"):
            raise OSError("simulated pre-replace rollback-intent failure")
        return real_write_journal(transaction_dir, manifest)

    monkeypatch.setattr(transaction, "_write_journal", ambiguous_marker_write)
    monkeypatch.setattr(transaction, "_verify_committed_outcome", lambda *_args: False)

    result = transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    assert not result
    assert result.recovery_required is True
    transaction_dirs = list(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert len(transaction_dirs) == 1
    assert json.loads(
        (transaction_dirs[0] / "journal.json").read_text(encoding="utf-8")
    )["state"] == "committed"
    assert (transaction_dirs[0] / "config.backup").exists()
    assert (transaction_dirs[0] / "secrets.backup").exists()
    assert (transaction_dirs[0] / "session.backup").exists()

    monkeypatch.setattr(transaction, "_write_journal", real_write_journal)
    monkeypatch.setattr(
        transaction,
        "_verify_committed_outcome",
        real_verify_outcome,
    )
    assert transaction.recover_pending_threads_login_transactions(root)
    assert (
        json.loads(config.config_file.read_text(encoding="utf-8"))["instagram_username"]
        == "new_user"
    )
    assert agent.session_path.read_bytes() == b"new-encrypted-session"


def test_ambiguous_commit_decision_quarantines_later_config_saves(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    real_fsync_file = transaction._fsync_file

    def fail_decision_fsync(path):
        if path.name == transaction._DECISION_NAME:
            return False
        return real_fsync_file(path)

    monkeypatch.setattr(transaction, "_fsync_file", fail_decision_fsync)

    result = transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    assert result.recovery_required is True
    assert config.persistence_quarantine_reason == "threads_login_recovery_required"
    committed_bytes = (
        config.config_file.read_bytes(),
        config.secrets_file.read_bytes(),
        agent.session_path.read_bytes(),
    )
    assert json.loads(committed_bytes[0])["instagram_username"] == "new_user"

    assert config.save() is False
    assert config.config_file.read_bytes() == committed_bytes[0]
    assert config.secrets_file.read_bytes() == committed_bytes[1]
    assert agent.session_path.read_bytes() == committed_bytes[2]

    monkeypatch.setattr(transaction, "_fsync_file", real_fsync_file)
    assert transaction.recover_pending_threads_login_transactions(root)
    assert config.config_file.read_bytes() == committed_bytes[0]
    assert config.secrets_file.read_bytes() == committed_bytes[1]
    assert agent.session_path.read_bytes() == committed_bytes[2]
    assert list(root.glob(f"{transaction._TRANSACTION_PREFIX}*")) == []


def test_config_persistence_quarantine_blocks_every_write(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(config_module, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(
        config_module,
        "recover_pending_threads_login_transactions",
        lambda _path: True,
    )
    monkeypatch.setattr(config_module.Config, "load", lambda _self: None)
    config = config_module.Config()
    config.config_file.write_bytes(b"preserve-config")
    config.secrets_file.write_bytes(b"preserve-secrets")

    config.quarantine_persistence("threads_login_recovery_required")

    assert config.persistence_quarantined is True
    assert config.save() is False
    assert config._save_secrets() is False
    assert config.config_file.read_bytes() == b"preserve-config"
    assert config.secrets_file.read_bytes() == b"preserve-secrets"
    with pytest.raises(RuntimeError, match="quarantined"):
        config.set_gemini_api_keys(["must-not-mutate"])


def test_config_recovers_transactions_before_loading(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(config_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(config_module, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(
        config_module,
        "recover_pending_threads_login_transactions",
        lambda _path: events.append("recover") or True,
    )
    monkeypatch.setattr(
        config_module.Config,
        "load",
        lambda _self: events.append("load"),
    )

    config_module.Config()

    assert events == ["recover", "load"]


def test_config_fails_closed_when_startup_recovery_fails(monkeypatch, tmp_path):
    load_called = []
    monkeypatch.setattr(config_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(config_module, "secure_dir_permissions", lambda _path: True)
    monkeypatch.setattr(
        config_module,
        "recover_pending_threads_login_transactions",
        lambda _path: False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "load",
        lambda _self: load_called.append(True),
    )

    with pytest.raises(RuntimeError, match="transaction recovery failed"):
        config_module.Config()

    assert load_called == []


def test_failed_rollback_retains_journal_and_every_backup(durable_fixture, monkeypatch):
    root, config, agent = durable_fixture
    agent.commit_result = "replace_then_fail"
    monkeypatch.setattr(
        transaction, "_restore_snapshot", lambda *_args, **_kwargs: False
    )

    assert not transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )

    transaction_dirs = list(root.glob(f"{transaction._TRANSACTION_PREFIX}*"))
    assert len(transaction_dirs) == 1
    preserved = transaction_dirs[0]
    assert (preserved / "journal.json").exists()
    assert (preserved / "config.backup").exists()
    assert (preserved / "secrets.backup").exists()
    assert (preserved / "session.backup").exists()


def test_acl_failure_rejects_transaction_before_any_persistent_change(
    durable_fixture,
    monkeypatch,
):
    root, config, agent = durable_fixture
    old_config = config.config_file.read_bytes()
    old_session = agent.session_path.read_bytes()
    monkeypatch.setattr(
        transaction,
        "secure_file_permissions",
        lambda path: Path(path) != agent.staged_path,
    )

    assert not transaction.commit_threads_login_transaction(
        config,
        agent,
        agent.staged_path,
        account_id="account-1",
        verified_username="new_user",
    )
    assert config.config_file.read_bytes() == old_config
    assert agent.session_path.read_bytes() == old_session
    assert list(root.glob(f"{transaction._TRANSACTION_PREFIX}*")) == []
