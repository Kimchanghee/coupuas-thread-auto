import json
import pytest

from src.services.account_queue import AccountQueueStore


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
