import json
import stat
import threading
from pathlib import Path

import pytest

from src.services import account_queue as account_queue_module
from src.services.account_queue import (
    AccountQueueStore,
    QueuePersistenceError,
    QueueStateRecoveryRequired,
)


def test_account_queue_persists_stable_items_and_restores_state(tmp_path):
    queue = AccountQueueStore("account-a", tmp_path)
    item = queue.enqueue("https://example.test/product", title="Product")
    queue.set_phase("waiting", next_allowed_at="2026-07-30T12:00:00")

    restored = AccountQueueStore("account-a", tmp_path)
    state = restored.snapshot()

    assert state["version"] == 2
    assert state["account_id"] == "account-a"
    assert state["pending_items"][0]["item_id"] == item["item_id"]
    assert state["next_allowed_at"] == "2026-07-30T12:00:00"
    assert json.loads((tmp_path / "account-a.json").read_text(encoding="utf-8"))["phase"] == "waiting"


def test_current_item_is_restored_after_interrupted_work(tmp_path):
    queue = AccountQueueStore("account-a", tmp_path)
    item = queue.enqueue("https://example.test/product")
    assert queue.reserve_next()["item_id"] == item["item_id"]

    restored = AccountQueueStore("account-a", tmp_path)
    assert restored.snapshot()["current_item"]["item_id"] == item["item_id"]
    assert restored.requeue_current()["item_id"] == item["item_id"]
    assert restored.reserve_next()["item_id"] == item["item_id"]
    restored.complete_current("success")

    assert restored.snapshot()["processed_urls"] == ["https://example.test/product"]
    assert restored.snapshot()["stats"] == {"success": 1, "failed": 0, "skipped": 0}


def test_account_id_cannot_escape_queue_root(tmp_path):
    with pytest.raises(ValueError):
        AccountQueueStore("../outside", tmp_path)


def test_failed_queue_save_rolls_back_current_stage(monkeypatch, tmp_path):
    queue = AccountQueueStore("account-a", tmp_path)
    queue.enqueue("https://example.test/product")
    queue.reserve_next()
    before = queue.snapshot()
    monkeypatch.setattr(
        queue,
        "_save",
        lambda: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        queue.update_current(stage="posting")

    assert queue.snapshot() == before


@pytest.mark.parametrize(
    "raw_payload",
    [
        b'{"version": 2, "account_id": "account-a",',
        json.dumps(
            {
                "version": 2,
                "account_id": "different-account",
                "pending_items": [],
                "processed_urls": [],
                "phase": "idle",
                "next_allowed_at": None,
                "stats": {"success": 0, "failed": 0, "skipped": 0},
                "current_item": None,
                "last_error": None,
                "stop_requested": False,
            }
        ).encode(),
        json.dumps({"version": 2, "account_id": "account-a"}).encode(),
    ],
    ids=["torn-json", "wrong-account", "invalid-schema"],
)
def test_existing_untrusted_queue_is_preserved_and_quarantined(
    tmp_path,
    raw_payload,
):
    queue_path = tmp_path / "account-a.json"
    queue_path.write_bytes(raw_payload)

    queue = AccountQueueStore("account-a", tmp_path)
    state = queue.snapshot()

    assert state["recovery_required"] is True
    assert state["phase"] == "blocked"
    assert state["blocked_reason"] == "state_recovery_required"
    assert queue_path.read_bytes() == raw_payload
    with pytest.raises(QueueStateRecoveryRequired, match="state_recovery_required"):
        queue.enqueue("https://example.test/must-not-overwrite")
    assert queue_path.read_bytes() == raw_payload


def test_existing_queue_read_error_is_quarantined_without_overwrite(
    monkeypatch,
    tmp_path,
):
    original = AccountQueueStore("account-a", tmp_path)
    original.enqueue("https://example.test/original")
    queue_path = tmp_path / "account-a.json"
    original_bytes = queue_path.read_bytes()
    real_open = account_queue_module.Path.open

    def fail_target_read(path, mode="r", *args, **kwargs):
        if path == queue_path and mode == "r":
            raise OSError("simulated read failure")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(account_queue_module.Path, "open", fail_target_read)
    queue = AccountQueueStore("account-a", tmp_path)

    assert queue.snapshot()["recovery_required"] is True
    with pytest.raises(QueueStateRecoveryRequired):
        queue.set_phase("waiting")
    assert queue_path.read_bytes() == original_bytes


def test_new_queue_refuses_mutation_when_directory_acl_cannot_be_secured(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        account_queue_module,
        "secure_dir_permissions",
        lambda _path: False,
    )

    queue = AccountQueueStore("account-a", tmp_path)

    assert queue.snapshot()["recovery_required"] is True
    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/product")
    assert not (tmp_path / "account-a.json").exists()


def test_temporary_acl_failure_does_not_publish_or_change_memory(
    monkeypatch,
    tmp_path,
):
    queue = AccountQueueStore("account-a", tmp_path)
    before = queue.snapshot()
    monkeypatch.setattr(
        account_queue_module,
        "secure_file_permissions",
        lambda _path: False,
    )

    with pytest.raises(QueuePersistenceError):
        queue.enqueue("https://example.test/product")

    assert queue.snapshot() == before
    assert not (tmp_path / "account-a.json").exists()


def test_published_acl_failure_quarantines_ambiguous_state(
    monkeypatch,
    tmp_path,
):
    queue = AccountQueueStore("account-a", tmp_path)

    def secure_temp_only(path):
        return str(path).endswith(".tmp")

    monkeypatch.setattr(
        account_queue_module,
        "secure_file_permissions",
        secure_temp_only,
    )

    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/product")

    state = queue.snapshot()
    assert state["recovery_required"] is True
    assert state["recovery_reason"] == "queue_publish_durability_unknown"
    assert json.loads((tmp_path / "account-a.json").read_text(encoding="utf-8"))[
        "pending_items"
    ]
    with pytest.raises(QueueStateRecoveryRequired):
        queue.request_stop()


def test_replace_failure_preserves_original_and_blocks_later_mutation(
    monkeypatch,
    tmp_path,
):
    queue = AccountQueueStore("account-a", tmp_path)
    queue.enqueue("https://example.test/original")
    queue_path = tmp_path / "account-a.json"
    original_bytes = queue_path.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("replace failed")

    monkeypatch.setattr(account_queue_module.os, "replace", fail_replace)

    with pytest.raises(QueueStateRecoveryRequired):
        queue.set_phase("waiting")

    assert queue.snapshot()["recovery_required"] is True
    assert queue_path.read_bytes() == original_bytes
    with pytest.raises(QueueStateRecoveryRequired):
        queue.set_phase("idle")


def test_post_publish_fsync_failure_is_fail_closed(monkeypatch, tmp_path):
    queue = AccountQueueStore("account-a", tmp_path)
    real_fsync = account_queue_module.os.fsync
    calls = 0

    def fail_second_fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("final fsync failed")
        return real_fsync(descriptor)

    monkeypatch.setattr(account_queue_module.os, "fsync", fail_second_fsync)

    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/product")

    assert calls == 2
    assert queue.snapshot()["recovery_required"] is True
    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/another")


def test_save_fsyncs_file_and_parent_directory(monkeypatch, tmp_path):
    queue = AccountQueueStore("account-a", tmp_path)
    parent_fsyncs = []
    monkeypatch.setattr(
        queue,
        "_fsync_parent_directory",
        lambda path: parent_fsyncs.append(path),
    )

    queue.enqueue("https://example.test/product")

    assert parent_fsyncs == [tmp_path]


def test_concurrent_stores_merge_without_lost_updates(tmp_path):
    first = AccountQueueStore("account-a", tmp_path)
    second = AccountQueueStore("account-a", tmp_path)
    errors = []

    def add_items(store, prefix):
        try:
            for index in range(10):
                store.enqueue(f"https://example.test/{prefix}-{index}")
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
            errors.append(exc)

    threads = [
        threading.Thread(target=add_items, args=(first, "first")),
        threading.Thread(target=add_items, args=(second, "second")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    restored = AccountQueueStore("account-a", tmp_path).snapshot()
    assert len(restored["pending_items"]) == 20
    assert len({item["url"] for item in restored["pending_items"]}) == 20


def test_concurrent_stores_can_create_the_same_absent_root(monkeypatch, tmp_path):
    queue_root = tmp_path / "new-queues"
    mkdir_barrier = threading.Barrier(2)
    real_mkdir = Path.mkdir
    stores = []
    errors = []

    def synchronized_mkdir(path, *args, **kwargs):
        if path == queue_root:
            mkdir_barrier.wait(timeout=5)
        return real_mkdir(path, *args, **kwargs)

    def create_store(account_id):
        try:
            stores.append(AccountQueueStore(account_id, queue_root))
        except Exception as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    monkeypatch.setattr(Path, "mkdir", synchronized_mkdir)
    threads = [
        threading.Thread(target=create_store, args=("account-a",)),
        threading.Thread(target=create_store, args=("account-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(stores) == 2
    assert all(store.snapshot()["recovery_required"] is False for store in stores)


def test_file_removed_between_identity_check_and_reload_is_quarantined(
    monkeypatch,
    tmp_path,
):
    stale_store = AccountQueueStore("account-a", tmp_path)
    concurrent_store = AccountQueueStore("account-a", tmp_path)
    stale_store.enqueue("https://example.test/original")
    concurrent_store.enqueue("https://example.test/concurrent")
    queue_path = tmp_path / "account-a.json"
    real_load = stale_store._load

    def unlink_then_load(*, allow_missing=False):
        queue_path.unlink()
        return real_load(allow_missing=allow_missing)

    monkeypatch.setattr(stale_store, "_load", unlink_then_load)

    with pytest.raises(QueueStateRecoveryRequired, match="queue_file_disappeared"):
        stale_store.enqueue("https://example.test/must-not-publish")

    state = stale_store.snapshot()
    assert state["recovery_required"] is True
    assert state["recovery_reason"] == "queue_file_disappeared"
    assert not queue_path.exists()


def test_symlink_queue_root_is_quarantined_without_writing_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    root_link = tmp_path / "queue-link"
    try:
        root_link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    queue = AccountQueueStore("account-a", root_link)

    assert queue.snapshot()["recovery_required"] is True
    assert queue.snapshot()["recovery_reason"] == "queue_directory_type_invalid"
    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/must-not-write")
    assert not (target / "account-a.json").exists()


def test_non_directory_queue_root_is_quarantined(tmp_path):
    root_file = tmp_path / "not-a-directory"
    root_file.write_text("preserve me", encoding="utf-8")

    queue = AccountQueueStore("account-a", root_file)

    assert queue.snapshot()["recovery_required"] is True
    assert queue.snapshot()["recovery_reason"] == "queue_directory_type_invalid"
    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/must-not-write")
    assert root_file.read_text(encoding="utf-8") == "preserve me"


def test_detected_symlink_mode_never_creates_account_file(monkeypatch, tmp_path):
    suspicious_root = tmp_path / "reported-symlink"
    suspicious_root.mkdir()
    real_lstat = Path.lstat
    directory_stat = suspicious_root.stat()
    symlink_stat = list(directory_stat)
    symlink_stat[0] = stat.S_IFLNK | 0o777
    reported_symlink = account_queue_module.os.stat_result(symlink_stat)

    def report_root_as_symlink(path):
        if path == suspicious_root:
            return reported_symlink
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", report_root_as_symlink)

    queue = AccountQueueStore("account-a", suspicious_root)

    assert queue.snapshot()["recovery_reason"] == "queue_directory_type_invalid"
    with pytest.raises(QueueStateRecoveryRequired):
        queue.enqueue("https://example.test/must-not-write")
    assert not (suspicious_root / "account-a.json").exists()
