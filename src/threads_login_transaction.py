"""Durable transaction for verified Threads account/session updates.

The login flow changes three persistent objects that must always agree:
``config.json``, ``secrets.json`` and the encrypted Playwright session.  A
prepared journal and exact-byte backups make an interrupted update recoverable
before :class:`src.config.Config` loads any of those objects.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
import tempfile
import threading
import uuid
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from src.fs_security import secure_dir_permissions, secure_file_permissions

logger = logging.getLogger(__name__)

_TRANSACTION_PREFIX = ".threads_login_transaction."
_JOURNAL_NAME = "journal.json"
_DECISION_NAME = "commit.decision"
_JOURNAL_VERSION = 1
_SESSION_FILENAME = "storage_state.sec"
_transaction_lock = threading.RLock()


@dataclass(frozen=True, slots=True)
class ThreadsLoginTransactionResult:
    """Tri-state result; only a durably verified commit is truthy."""

    status: str

    def __bool__(self) -> bool:
        return self.status == "committed"

    @property
    def recovery_required(self) -> bool:
        return self.status == "recovery_required"


_COMMITTED = ThreadsLoginTransactionResult("committed")
_ROLLED_BACK = ThreadsLoginTransactionResult("rolled_back")
_RECOVERY_REQUIRED = ThreadsLoginTransactionResult("recovery_required")


def _fsync_directory(path: Path) -> bool:
    """Durably flush namespace changes where Python exposes directory fsync."""
    if os.name == "nt":
        # os.replace is atomic on the same Windows volume. Python does not
        # expose the directory handle flags needed by FlushFileBuffers.
        return True
    descriptor: int | None = None
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        os.fsync(descriptor)
        return True
    except OSError:
        logger.exception("Threads 로그인 트랜잭션 디렉터리 동기화 실패")
        return False
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _fsync_file(path: Path) -> bool:
    try:
        # Windows rejects FlushFileBuffers on a read-only handle.
        with path.open("r+b") as handle:
            os.fsync(handle.fileno())
        return True
    except OSError:
        logger.exception("Threads 로그인 트랜잭션 파일 동기화 실패")
        return False


def _is_direct_child(path: Path, parent: Path) -> bool:
    try:
        return path.resolve(strict=False).parent == parent.resolve(strict=True)
    except OSError:
        return False


def _validate_config_root(config_dir: Any) -> Path:
    root = Path(config_dir)
    if not root.exists() or not root.is_dir() or root.is_symlink():
        raise PermissionError("설정 디렉터리 형식이 안전하지 않습니다.")
    resolved = root.resolve(strict=True)
    if not secure_dir_permissions(resolved):
        raise PermissionError("설정 디렉터리 권한을 보호하지 못했습니다.")
    return resolved


def _validate_session_relative_path(value: Any) -> Path:
    relative = Path(str(value or ""))
    parts = relative.parts
    if (
        relative.is_absolute()
        or len(parts) != 3
        or parts[0] != "sessions"
        or not all(
            character.isalnum() or character in {"_", "-"} for character in parts[1]
        )
        or parts[1] in {".", ".."}
        or parts[2] != _SESSION_FILENAME
    ):
        raise ValueError("저널의 브라우저 세션 경로가 안전하지 않습니다.")
    return relative


def _validate_target(path: Path, *, allow_missing: bool = True) -> None:
    if not path.exists():
        if allow_missing:
            return
        raise FileNotFoundError(path)
    if path.is_symlink() or not path.is_file():
        raise PermissionError("트랜잭션 대상 파일 형식이 안전하지 않습니다.")
    if not secure_file_permissions(path):
        raise PermissionError("트랜잭션 대상 파일 권한을 보호하지 못했습니다.")


def _write_exact_backup(source: Path, backup: Path) -> dict[str, Any]:
    _validate_target(source)
    if not source.exists():
        return {"existed": False, "backup": "", "sha256": ""}
    if not _is_direct_child(backup, backup.parent):
        raise ValueError("백업 경로가 안전하지 않습니다.")

    digest = hashlib.sha256()
    with source.open("rb") as input_handle, backup.open("xb") as output_handle:
        while True:
            chunk = input_handle.read(64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            output_handle.write(chunk)
        output_handle.flush()
        os.fsync(output_handle.fileno())
    if not secure_file_permissions(backup) or not _fsync_file(backup):
        raise PermissionError("Threads 로그인 롤백 백업을 보호하지 못했습니다.")
    return {
        "existed": True,
        "backup": backup.name,
        "sha256": digest.hexdigest(),
    }


def _write_journal(transaction_dir: Path, manifest: dict[str, Any]) -> None:
    journal_path = transaction_dir / _JOURNAL_NAME
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(transaction_dir),
            prefix="journal.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(manifest, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        if not secure_file_permissions(temp_path):
            raise PermissionError(
                "Threads 로그인 임시 저널 권한을 보호하지 못했습니다."
            )
        os.replace(temp_path, journal_path)
        temp_path = None
        if (
            not secure_file_permissions(journal_path)
            or not _fsync_file(journal_path)
            or not _fsync_directory(transaction_dir)
        ):
            raise OSError("Threads 로그인 저널을 영구 저장하지 못했습니다.")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _write_commit_decision(transaction_dir: Path, transaction_id: str) -> None:
    """Publish the immutable commit decision after the exact tuple is verified."""
    decision_path = transaction_dir / _DECISION_NAME
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(transaction_dir),
            prefix="decision.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(
                {"version": _JOURNAL_VERSION, "transaction_id": transaction_id},
                handle,
                sort_keys=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        if not secure_file_permissions(temp_path):
            raise PermissionError("Threads 로그인 커밋 결정 권한을 보호하지 못했습니다.")
        os.replace(temp_path, decision_path)
        temp_path = None
        if (
            not secure_file_permissions(decision_path)
            or not _fsync_file(decision_path)
            or not _fsync_directory(transaction_dir)
        ):
            raise OSError("Threads 로그인 커밋 결정을 영구 저장하지 못했습니다.")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _has_durable_commit_decision(
    transaction_dir: Path, transaction_id: str
) -> bool | None:
    """Return True for verified, False for absent, and None for unverifiable.

    An existing decision is the immutable commit point.  Any inability to read,
    validate, secure, or flush it must fail closed; it must never be conflated
    with an unequivocally absent decision and reopen the rollback path.
    """
    decision_path = transaction_dir / _DECISION_NAME
    try:
        decision_stat = decision_path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    if stat.S_ISLNK(decision_stat.st_mode) or not stat.S_ISREG(
        decision_stat.st_mode
    ):
        return None
    try:
        _validate_target(decision_path, allow_missing=False)
        payload = json.loads(decision_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload != {
            "version": _JOURNAL_VERSION,
            "transaction_id": transaction_id,
        }:
            return None
        if not _fsync_file(decision_path) or not _fsync_directory(transaction_dir):
            return None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return True


def _publish_commit_decision(
    transaction_dir: Path,
    transaction_id: str,
) -> bool | None:
    """Return True if durable, False if definitely absent, None if ambiguous."""
    try:
        _write_commit_decision(transaction_dir, transaction_id)
        return True
    except Exception:
        logger.warning("Threads 로그인 커밋 결정 게시 결과가 불확정합니다.", exc_info=True)
        decision_path = transaction_dir / _DECISION_NAME
        try:
            decision_status = _has_durable_commit_decision(
                transaction_dir, transaction_id
            )
            if decision_status is True:
                return True
            if decision_status is None:
                return None
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if decision_path.exists() or decision_path.is_symlink():
            return None
        return False


def _read_journal(root: Path, transaction_dir: Path) -> dict[str, Any]:
    if (
        not _is_direct_child(transaction_dir, root)
        or transaction_dir.is_symlink()
        or not transaction_dir.is_dir()
        or not secure_dir_permissions(transaction_dir)
    ):
        raise PermissionError("Threads 로그인 트랜잭션 디렉터리가 안전하지 않습니다.")
    journal_path = transaction_dir / _JOURNAL_NAME
    _validate_target(journal_path, allow_missing=False)
    manifest = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("Threads 로그인 저널 형식이 올바르지 않습니다.")
    transaction_id = transaction_dir.name.removeprefix(_TRANSACTION_PREFIX)
    if (
        manifest.get("version") != _JOURNAL_VERSION
        or manifest.get("transaction_id") != transaction_id
        or manifest.get("state")
        not in {"initializing", "prepared", "rolled_back", "committed"}
        or not isinstance(manifest.get("snapshots"), dict)
    ):
        raise ValueError("Threads 로그인 저널 메타데이터가 올바르지 않습니다.")
    _validate_session_relative_path(manifest.get("session_path"))
    account_id = str(manifest.get("account_id") or "")
    expected_username = str(manifest.get("expected_username") or "")
    candidate_digest = str(manifest.get("candidate_session_sha256") or "")
    if (
        not account_id
        or len(account_id) > 128
        or not re.fullmatch(r"[a-z0-9._]{1,30}", expected_username)
        or not re.fullmatch(r"[0-9a-f]{64}", candidate_digest)
        or not isinstance(manifest.get("new_targets"), dict)
    ):
        raise ValueError("Threads 로그인 커밋 검증 메타데이터가 올바르지 않습니다.")
    if manifest["state"] == "initializing":
        if manifest["snapshots"]:
            raise ValueError("초기화 중인 Threads 로그인 저널에 백업이 포함되었습니다.")
        return manifest
    for key in ("config", "secrets", "session"):
        record = manifest["snapshots"].get(key)
        if not isinstance(record, dict):
            raise TypeError("Threads 로그인 백업 메타데이터가 올바르지 않습니다.")
        if not isinstance(record.get("existed"), bool):
            raise TypeError("Threads 로그인 백업 메타데이터가 올바르지 않습니다.")
        if record["existed"]:
            backup_name = str(record.get("backup") or "")
            if backup_name != f"{key}.backup":
                raise ValueError("Threads 로그인 백업 경로가 올바르지 않습니다.")
            digest = str(record.get("sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Threads 로그인 백업 해시가 올바르지 않습니다.")
    if manifest["state"] == "committed":
        for key in ("config", "secrets", "session"):
            record = manifest["new_targets"].get(key)
            if not isinstance(record, dict) or not isinstance(
                record.get("existed"), bool
            ):
                raise TypeError(
                    "Threads 로그인 커밋 파일 메타데이터가 올바르지 않습니다."
                )
            digest = str(record.get("sha256") or "")
            if record["existed"] and not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Threads 로그인 커밋 파일 해시가 올바르지 않습니다.")
    return manifest


def _target_paths(root: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    session_relative = _validate_session_relative_path(manifest["session_path"])
    raw_session_root = root / "sessions"
    if (
        not raw_session_root.exists()
        or raw_session_root.is_symlink()
        or not raw_session_root.is_dir()
        or not secure_dir_permissions(raw_session_root)
    ):
        raise PermissionError("브라우저 세션 루트 디렉터리가 안전하지 않습니다.")
    session_target = (root / session_relative).resolve(strict=False)
    session_root = raw_session_root.resolve(strict=True)
    raw_profile = root / session_relative.parent
    if (
        not raw_profile.exists()
        or raw_profile.is_symlink()
        or not raw_profile.is_dir()
        or not secure_dir_permissions(raw_profile)
        or session_target.parent.parent != session_root
    ):
        raise ValueError("브라우저 세션 대상이 허용된 경로를 벗어났습니다.")
    return {
        "config": root / "config.json",
        "secrets": root / "secrets.json",
        "session": session_target,
    }


def _restore_snapshot(
    transaction_dir: Path,
    target: Path,
    record: dict[str, Any],
) -> bool:
    temp_path: Path | None = None
    try:
        target.parent.mkdir(parents=False, exist_ok=True)
        if target.parent.is_symlink() or not secure_dir_permissions(target.parent):
            raise PermissionError("복구 대상 디렉터리 권한을 보호하지 못했습니다.")
        if not record["existed"]:
            if target.exists() or target.is_symlink():
                target.unlink()
            return _fsync_directory(target.parent)

        backup = transaction_dir / str(record["backup"])
        if not _is_direct_child(backup, transaction_dir):
            raise ValueError("복구 백업 경로가 안전하지 않습니다.")
        _validate_target(backup, allow_missing=False)
        payload = backup.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError("복구 백업 무결성 검증에 실패했습니다.")

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(target.parent),
            prefix=f"{target.name}.restore.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        if not secure_file_permissions(temp_path):
            raise PermissionError("복구 임시 파일 권한을 보호하지 못했습니다.")
        os.replace(temp_path, target)
        temp_path = None
        if (
            not secure_file_permissions(target)
            or not _fsync_file(target)
            or not _fsync_directory(target.parent)
        ):
            raise OSError("이전 로그인 파일을 영구 복구하지 못했습니다.")
        return True
    except Exception:
        logger.exception("Threads 로그인 트랜잭션 백업 복구 실패")
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _remove_transaction_files(root: Path, transaction_dir: Path) -> bool:
    """Remove cleanup files while keeping the commit decision until last."""
    if not _is_direct_child(transaction_dir, root) or transaction_dir.is_symlink():
        return False
    try:
        journal = transaction_dir / _JOURNAL_NAME
        decision = transaction_dir / _DECISION_NAME
        children = list(transaction_dir.iterdir())
        if any(child.is_dir() and not child.is_symlink() for child in children):
            return False
        for child in children:
            if child in {journal, decision}:
                continue
            if child.is_dir() and not child.is_symlink():
                return False
            child.unlink(missing_ok=True)
        if not _fsync_directory(transaction_dir):
            return False
        # A committed decision survives every backup/temp cleanup failure. Once
        # all mutable cleanup files are gone, the journal can disappear first;
        # a decision-only remnant still means cleanup-only on the next startup.
        journal.unlink(missing_ok=True)
        if not _fsync_directory(transaction_dir):
            return False
        decision.unlink(missing_ok=True)
        if not _fsync_directory(transaction_dir):
            return False
        transaction_dir.rmdir()
        return _fsync_directory(root)
    except OSError:
        logger.warning("완료된 Threads 로그인 트랜잭션 파일을 정리하지 못했습니다.")
        return False


def _recover_one(root: Path, transaction_dir: Path) -> bool:
    if (
        not _is_direct_child(transaction_dir, root)
        or transaction_dir.is_symlink()
        or not transaction_dir.is_dir()
        or not secure_dir_permissions(transaction_dir)
    ):
        raise PermissionError("Threads 로그인 트랜잭션 디렉터리가 안전하지 않습니다.")
    transaction_id = transaction_dir.name.removeprefix(_TRANSACTION_PREFIX)
    decision_status = _has_durable_commit_decision(transaction_dir, transaction_id)
    if decision_status is None:
        logger.critical("Threads 로그인 커밋 결정을 안전하게 검증하지 못했습니다.")
        return False
    if decision_status is True:
        # Commit is immutable. The current files may contain legitimate changes
        # made after login committed while AV/file locks delayed cleanup.
        cleaned = _remove_transaction_files(root, transaction_dir)
        return cleaned or not (transaction_dir / _DECISION_NAME).exists()
    manifest = _read_journal(root, transaction_dir)
    if manifest["state"] in {"initializing", "rolled_back"}:
        # Persistent targets are never touched before the prepared state.
        cleaned = _remove_transaction_files(root, transaction_dir)
        return cleaned or not (transaction_dir / _JOURNAL_NAME).exists()
    if manifest["state"] == "committed":
        if _verify_committed_manifest(root, transaction_dir, manifest):
            try:
                _write_commit_decision(transaction_dir, transaction_id)
            except Exception:
                logger.critical(
                    "검증된 Threads 커밋 결정을 영구 저장하지 못했습니다.",
                    exc_info=True,
                )
                return False
            cleaned = _remove_transaction_files(root, transaction_dir)
            return cleaned or not (transaction_dir / _DECISION_NAME).exists()
        # Never bless a marker whose exact account/config/session tuple is no
        # longer provable. Durably switch it back to prepared before restoring.
        manifest["state"] = "prepared"
        try:
            _write_journal(transaction_dir, manifest)
        except Exception:
            logger.critical(
                "검증 실패한 Threads 커밋을 롤백 상태로 전환하지 못했습니다.",
                exc_info=True,
            )
            return False

    targets = _target_paths(root, manifest)
    snapshots = manifest["snapshots"]
    restored = all(
        _restore_snapshot(transaction_dir, targets[key], snapshots[key])
        for key in ("session", "secrets", "config")
    )
    if not restored:
        # Retain the journal and every exact-byte backup for the next startup or
        # manual recovery. Never trade recoverability for cosmetic cleanup.
        return False
    manifest["state"] = "rolled_back"
    try:
        _write_journal(transaction_dir, manifest)
    except Exception:
        logger.critical(
            "복구 완료 Threads 로그인 저널을 영구 저장하지 못했습니다.",
            exc_info=True,
        )
        return False
    cleaned = _remove_transaction_files(root, transaction_dir)
    return cleaned or not (transaction_dir / _JOURNAL_NAME).exists()


def recover_pending_threads_login_transactions(config_dir: Any) -> bool:
    """Recover every prepared login transaction before configuration is loaded."""
    with _transaction_lock:
        try:
            root = _validate_config_root(config_dir)
            pending = sorted(root.glob(f"{_TRANSACTION_PREFIX}*"))
            for transaction_dir in pending:
                journal = transaction_dir / _JOURNAL_NAME
                if not journal.exists():
                    # The initial journal is written before any backup. An empty
                    # directory (or its unfinished journal temp) therefore means
                    # no target was touched and can be cleaned safely. Anything
                    # else is ambiguous and must fail closed.
                    if (
                        not _is_direct_child(transaction_dir, root)
                        or transaction_dir.is_symlink()
                        or not transaction_dir.is_dir()
                        or not secure_dir_permissions(transaction_dir)
                    ):
                        return False
                    transaction_id = transaction_dir.name.removeprefix(
                        _TRANSACTION_PREFIX
                    )
                    decision = transaction_dir / _DECISION_NAME
                    if decision.exists() or decision.is_symlink():
                        if not _has_durable_commit_decision(
                            transaction_dir, transaction_id
                        ):
                            return False
                        if not _remove_transaction_files(root, transaction_dir):
                            return False
                        continue
                    children = list(transaction_dir.iterdir())
                    if any(
                        child.is_dir()
                        or child.is_symlink()
                        or not child.name.startswith("journal.")
                        or not child.name.endswith(".tmp")
                        for child in children
                    ):
                        return False
                    if not _remove_transaction_files(root, transaction_dir):
                        return False
                    continue
                if not _recover_one(root, transaction_dir):
                    return False
            return True
        except Exception:
            logger.critical(
                "중단된 Threads 로그인 트랜잭션을 복구하지 못했습니다.", exc_info=True
            )
            return False


def _prepare_transaction(
    root: Path,
    session_target: Path,
    *,
    account_id: str,
    expected_username: str,
    candidate_session_digest: str,
) -> tuple[Path, dict[str, Any]]:
    transaction_id = uuid.uuid4().hex
    transaction_dir = root / f"{_TRANSACTION_PREFIX}{transaction_id}"
    transaction_dir.mkdir(mode=0o700)
    if (
        not _is_direct_child(transaction_dir, root)
        or transaction_dir.is_symlink()
        or not secure_dir_permissions(transaction_dir)
    ):
        raise PermissionError("Threads 로그인 트랜잭션 디렉터리를 보호하지 못했습니다.")

    session_relative = session_target.relative_to(root)
    manifest = {
        "version": _JOURNAL_VERSION,
        "transaction_id": transaction_id,
        "state": "initializing",
        "session_path": session_relative.as_posix(),
        "account_id": account_id,
        "expected_username": expected_username,
        "candidate_session_sha256": candidate_session_digest,
        "snapshots": {},
        "new_targets": {},
    }
    _write_journal(transaction_dir, manifest)
    snapshots = {
        "config": _write_exact_backup(
            root / "config.json", transaction_dir / "config.backup"
        ),
        "secrets": _write_exact_backup(
            root / "secrets.json", transaction_dir / "secrets.backup"
        ),
        "session": _write_exact_backup(
            session_target, transaction_dir / "session.backup"
        ),
    }
    manifest["state"] = "prepared"
    manifest["snapshots"] = snapshots
    _write_journal(transaction_dir, manifest)
    if not _fsync_directory(root):
        raise OSError("Threads 로그인 트랜잭션 생성을 영구 저장하지 못했습니다.")
    return transaction_dir, manifest


def _validate_runtime_paths(
    config_obj: Any, agent: Any, staged_path: Any
) -> tuple[Path, Path, str]:
    root = _validate_config_root(config_obj.config_dir)
    if Path(config_obj.config_file).resolve(strict=False) != root / "config.json":
        raise ValueError("설정 파일 경로가 표준 위치와 일치하지 않습니다.")
    if Path(config_obj.secrets_file).resolve(strict=False) != root / "secrets.json":
        raise ValueError("보안 설정 파일 경로가 표준 위치와 일치하지 않습니다.")
    if not agent._is_valid_staged_session_path(staged_path):
        raise ValueError("후보 브라우저 세션 경로가 안전하지 않습니다.")
    candidate = Path(staged_path)
    _validate_target(candidate, allow_missing=False)
    candidate_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()

    session_target = Path(agent._get_storage_state_path()).resolve(strict=False)
    raw_profile_path = Path(agent.profile_path)
    if raw_profile_path.is_symlink():
        raise ValueError("브라우저 세션 프로필이 심볼릭 링크일 수 없습니다.")
    profile_path = raw_profile_path.resolve(strict=True)
    sessions_root = (root / "sessions").resolve(strict=True)
    if (
        profile_path.parent != sessions_root
        or profile_path.is_symlink()
        or session_target != profile_path / _SESSION_FILENAME
        or not secure_dir_permissions(profile_path)
    ):
        raise ValueError("브라우저 세션 경로가 표준 위치와 일치하지 않습니다.")
    _validate_target(session_target)
    return root, session_target, candidate_digest


def _verify_config_tuple(
    config_path: Path,
    secrets_path: Path,
    *,
    account_id: str,
    expected_username: str,
) -> bool:
    try:
        _validate_target(config_path, allow_missing=False)
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        accounts = (
            payload.get("threads_accounts") if isinstance(payload, dict) else None
        )
        matching_account = (
            next(
                (
                    account
                    for account in accounts
                    if isinstance(account, dict)
                    and account.get("account_id") == account_id
                ),
                None,
            )
            if isinstance(accounts, list)
            else None
        )
        if (
            not isinstance(payload, dict)
            or payload.get("instagram_username") != expected_username
            or not isinstance(matching_account, dict)
            or matching_account.get("expected_username") != expected_username
            or not _fsync_file(config_path)
        ):
            return False
        if secrets_path.exists():
            _validate_target(secrets_path, allow_missing=False)
            secrets_payload = json.loads(secrets_path.read_text(encoding="utf-8"))
            if not isinstance(secrets_payload, dict) or not _fsync_file(secrets_path):
                return False
        return _fsync_directory(config_path.parent)
    except Exception:
        logger.exception("저장된 Threads 계정 설정의 내구성 검증에 실패했습니다.")
        return False


def _verify_saved_config(
    config_obj: Any,
    *,
    account_id: str,
    expected_username: str,
) -> bool:
    return _verify_config_tuple(
        Path(config_obj.config_file),
        Path(config_obj.secrets_file),
        account_id=account_id,
        expected_username=expected_username,
    )


def _current_file_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        if path.is_symlink():
            raise PermissionError("커밋 대상이 끊어진 심볼릭 링크입니다.")
        return {"existed": False, "sha256": ""}
    _validate_target(path, allow_missing=False)
    payload = path.read_bytes()
    if not _fsync_file(path):
        raise OSError("Threads 로그인 커밋 파일을 동기화하지 못했습니다.")
    return {"existed": True, "sha256": hashlib.sha256(payload).hexdigest()}


def _capture_committed_targets(
    root: Path,
    session_target: Path,
    *,
    account_id: str,
    expected_username: str,
    candidate_session_digest: str,
) -> dict[str, dict[str, Any]]:
    config_path = root / "config.json"
    secrets_path = root / "secrets.json"
    if not _verify_config_tuple(
        config_path,
        secrets_path,
        account_id=account_id,
        expected_username=expected_username,
    ):
        raise OSError("Threads 로그인 설정 튜플을 검증하지 못했습니다.")
    records = {
        "config": _current_file_record(config_path),
        "secrets": _current_file_record(secrets_path),
        "session": _current_file_record(session_target),
    }
    if (
        not records["config"]["existed"]
        or not records["session"]["existed"]
        or records["session"]["sha256"] != candidate_session_digest
    ):
        raise ValueError("커밋된 Threads 세션이 검증된 후보와 일치하지 않습니다.")
    return records


def _file_matches_record(path: Path, record: dict[str, Any]) -> bool:
    exists = path.exists()
    if exists != bool(record["existed"]):
        return False
    if not exists:
        return not path.is_symlink()
    _validate_target(path, allow_missing=False)
    return hashlib.sha256(path.read_bytes()).hexdigest() == record[
        "sha256"
    ] and _fsync_file(path)


def _verify_committed_manifest(
    root: Path,
    transaction_dir: Path,
    manifest: dict[str, Any],
) -> bool:
    try:
        if manifest.get("state") != "committed":
            return False
        targets = _target_paths(root, manifest)
        records = manifest["new_targets"]
        if not all(
            _file_matches_record(targets[key], records[key])
            for key in ("config", "secrets", "session")
        ):
            return False
        if records["session"]["sha256"] != manifest["candidate_session_sha256"]:
            return False
        if not _verify_config_tuple(
            targets["config"],
            targets["secrets"],
            account_id=manifest["account_id"],
            expected_username=manifest["expected_username"],
        ):
            return False
        return (
            _fsync_directory(targets["session"].parent)
            and _fsync_directory(transaction_dir)
            and _fsync_directory(root)
        )
    except Exception:
        logger.warning("Threads 로그인 committed 튜플 검증 실패", exc_info=True)
        return False


def _verify_committed_outcome(
    root: Path,
    transaction_dir: Path,
) -> bool:
    """Resolve an exception after the atomic committed-journal replacement."""
    try:
        manifest = _read_journal(root, transaction_dir)
        return _verify_committed_manifest(root, transaction_dir, manifest)
    except Exception:
        logger.warning("Threads 로그인 커밋 결과를 확정하지 못했습니다.", exc_info=True)
        return False


def commit_threads_login_transaction(
    config_obj: Any,
    agent: Any,
    staged_path: Any,
    *,
    account_id: str,
    verified_username: str,
) -> ThreadsLoginTransactionResult:
    """Commit verified account metadata and encrypted session as one unit."""
    username = str(verified_username or "").strip()
    target_account_id = str(account_id or "").strip()
    if not username or not target_account_id:
        return _ROLLED_BACK

    config_lock = getattr(config_obj, "_lock", None)
    config_lock_context: AbstractContextManager[Any]
    if hasattr(config_lock, "__enter__") and hasattr(config_lock, "__exit__"):
        config_lock_context = cast(AbstractContextManager[Any], config_lock)
    else:
        config_lock_context = nullcontext()
    with _transaction_lock, config_lock_context:
        old_username = str(getattr(config_obj, "instagram_username", "") or "")
        account = config_obj.get_threads_account(target_account_id)
        if account is None:
            return _ROLLED_BACK
        old_expected = str(getattr(account, "expected_username", "") or "")
        transaction_dir: Path | None = None
        manifest: dict[str, Any] | None = None
        model_changed = False
        rollback_journal_ready = False
        candidate_digest = ""
        try:
            root, session_target, candidate_digest = _validate_runtime_paths(
                config_obj, agent, staged_path
            )
            if not recover_pending_threads_login_transactions(root):
                raise RuntimeError("이전 Threads 로그인 트랜잭션 복구가 필요합니다.")
            transaction_dir, manifest = _prepare_transaction(
                root,
                session_target,
                account_id=target_account_id,
                expected_username=username,
                candidate_session_digest=candidate_digest,
            )
            rollback_journal_ready = True

            model_changed = True
            config_obj.instagram_username = username
            config_obj.update_threads_account(
                target_account_id,
                expected_username=username,
            )
            if not config_obj.save() or not _verify_saved_config(
                config_obj,
                account_id=target_account_id,
                expected_username=username,
            ):
                raise OSError("Threads 계정 설정을 영구 저장하지 못했습니다.")
            if not agent.commit_staged_session(staged_path):
                raise OSError("검증된 Threads 세션을 커밋하지 못했습니다.")

            manifest["new_targets"] = _capture_committed_targets(
                root,
                session_target,
                account_id=target_account_id,
                expected_username=username,
                candidate_session_digest=candidate_digest,
            )
            manifest["state"] = "committed"
            rollback_journal_ready = False
            try:
                _write_journal(transaction_dir, manifest)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                # os.replace may already have made `committed` visible before a
                # post-replace ACL/fsync check raised. Reconcile that exact
                # on-disk outcome instead of reporting a false rollback.
                if _verify_committed_outcome(
                    root,
                    transaction_dir,
                ):
                    decision_status = _publish_commit_decision(
                        transaction_dir, str(manifest["transaction_id"])
                    )
                    if decision_status is True:
                        _remove_transaction_files(root, transaction_dir)
                        return _COMMITTED
                    if decision_status is None:
                        raise OSError(
                            "Threads 로그인 커밋 결정 결과를 확정하지 못했습니다."
                        )

                manifest["state"] = "prepared"
                try:
                    _write_journal(transaction_dir, manifest)
                    rollback_journal_ready = True
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    # A second atomic replace can itself be outcome-ambiguous.
                    # If the first committed outcome is now fully durable, it is
                    # a successful commit; otherwise preserve every recovery
                    # artifact and let startup resolve the visible journal.
                    if _verify_committed_outcome(
                        root,
                        transaction_dir,
                    ):
                        decision_status = _publish_commit_decision(
                            transaction_dir, str(manifest["transaction_id"])
                        )
                        if decision_status is True:
                            _remove_transaction_files(root, transaction_dir)
                            return _COMMITTED
                        if decision_status is None:
                            raise OSError(
                                "Threads 로그인 커밋 결정 결과를 확정하지 못했습니다."
                            )
                    raise OSError(
                        "Threads 로그인 커밋 결과를 안전하게 확정하지 못했습니다."
                    )
                raise OSError("Threads 로그인 커밋 표시를 롤백으로 전환했습니다.")
            if not _verify_committed_outcome(root, transaction_dir):
                manifest["state"] = "prepared"
                _write_journal(transaction_dir, manifest)
                rollback_journal_ready = True
                raise OSError("Threads 로그인 커밋 튜플의 최종 검증에 실패했습니다.")
            decision_status = _publish_commit_decision(
                transaction_dir, str(manifest["transaction_id"])
            )
            if decision_status is not True:
                if decision_status is None:
                    raise OSError(
                        "Threads 로그인 커밋 결정 결과를 확정하지 못했습니다."
                    )
                manifest["state"] = "prepared"
                _write_journal(transaction_dir, manifest)
                rollback_journal_ready = True
                raise OSError("Threads 로그인 커밋 결정을 게시하지 못했습니다.")
            if not _remove_transaction_files(root, transaction_dir):
                logger.warning(
                    "Threads 로그인은 커밋되었지만 트랜잭션 정리는 시작 시 재시도됩니다."
                )
            return _COMMITTED
        except Exception:
            logger.exception("검증된 Threads 로그인 트랜잭션 커밋 실패")
            recovered = False
            if (
                transaction_dir is not None
                and manifest is not None
                and rollback_journal_ready
            ):
                try:
                    manifest["state"] = "prepared"
                    targets = _target_paths(root, manifest)
                    recovered = all(
                        _restore_snapshot(
                            transaction_dir,
                            targets[key],
                            manifest["snapshots"][key],
                        )
                        for key in ("session", "secrets", "config")
                    )
                    if recovered:
                        manifest["state"] = "rolled_back"
                        try:
                            _write_journal(transaction_dir, manifest)
                        except Exception:
                            logger.critical(
                                "복구 완료 Threads 로그인 저널을 영구 저장하지 못했습니다.",
                                exc_info=True,
                            )
                            recovered = False
                        if recovered:
                            _remove_transaction_files(root, transaction_dir)
                except Exception:
                    logger.critical(
                        "Threads 로그인 트랜잭션 즉시 롤백 실패", exc_info=True
                    )
                    recovered = False

            if model_changed:
                config_obj.instagram_username = old_username
                try:
                    config_obj.update_threads_account(
                        target_account_id,
                        expected_username=old_expected,
                    )
                except Exception:
                    logger.critical(
                        "Threads 로그인 메모리 상태 롤백 실패", exc_info=True
                    )
                if recovered:
                    try:
                        config_obj.load()
                    except Exception:
                        logger.critical(
                            "복구된 Threads 설정 다시 불러오기 실패", exc_info=True
                        )
            if transaction_dir is not None and not recovered:
                try:
                    quarantine = getattr(config_obj, "quarantine_persistence", None)
                    if callable(quarantine):
                        quarantine("threads_login_recovery_required")
                    else:
                        setattr(
                            config_obj,
                            "_persistence_quarantine_reason",
                            "threads_login_recovery_required",
                        )
                except Exception:
                    logger.critical(
                        "Threads 로그인 복구 대기 중 설정 저장 격리 실패",
                        exc_info=True,
                    )
                return _RECOVERY_REQUIRED
            return _ROLLED_BACK
