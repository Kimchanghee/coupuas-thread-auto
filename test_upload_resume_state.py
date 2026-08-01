import json
import threading
from types import SimpleNamespace

from src.main_window import MainWindow
from src.main_window import QMessageBox


def _make_resume_fake(tmp_path):
    fake = SimpleNamespace(
        _resume_state_path=tmp_path / "upload_resume_queue.json",
        _resume_state_lock=threading.RLock(),
        _resume_items=[],
        _resume_interval=60,
        _resume_next_allowed_at=None,
    )
    for name in (
        "_normalize_link_data",
        "_save_resume_state",
        "_initialize_resume_state",
        "_mark_resume_item",
        "_set_resume_next_allowed_at",
        "_resume_pending_link_data",
        "_load_resume_state_file",
        "_archive_legacy_resume_state",
        "_reconcile_ambiguous_post_items",
    ):
        setattr(fake, name, getattr(MainWindow, name).__get__(fake, type(fake)))
    fake._is_resume_unfinished = MainWindow._is_resume_unfinished
    fake._is_work_allowed = MainWindow._is_work_allowed
    return fake


def test_resume_state_persists_only_unfinished_items(tmp_path):
    fake = _make_resume_fake(tmp_path)

    fake._initialize_resume_state(
        [
            ("https://link.coupang.com/a/item1", "summer fan"),
            ("https://link.coupang.com/a/item2", "cool mat"),
        ],
        14400,
        source="test",
    )
    fake._mark_resume_item("https://link.coupang.com/a/item1", "completed", "done")
    fake._mark_resume_item("https://link.coupang.com/a/item2", "running", "active")
    fake._set_resume_next_allowed_at(12345.0)

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["interval"] == 14400
    assert payload["next_allowed_at"] == 12345.0
    assert fake._resume_pending_link_data(payload) == [
        ("https://link.coupang.com/a/item2", "cool mat")
    ]

    fake._mark_resume_item("https://link.coupang.com/a/item2", "failed", "active")
    assert not fake._resume_state_path.exists()


def test_legacy_resume_file_is_archived_after_account_import(tmp_path):
    fake = _make_resume_fake(tmp_path)
    fake._resume_state_path.write_text('{"items":[]}', encoding="utf-8")

    fake._archive_legacy_resume_state()

    assert not fake._resume_state_path.exists()
    assert (
        tmp_path / "upload_resume_queue.migrated.json"
    ).read_text(encoding="utf-8") == '{"items":[]}'


def test_posted_commit_pending_is_persisted_but_never_reuploaded(tmp_path):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item1"
    fake._initialize_resume_state([(url, "item")], 60, source="test")

    fake._mark_resume_item(
        url,
        "posted_commit_pending",
        "posted item",
        reservation_id="reservation-1",
        idempotency_key="request-1",
    )

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["reservation_id"] == "reservation-1"
    assert fake._resume_pending_link_data(payload) == []


def test_ambiguous_posting_state_is_persisted_but_never_reuploaded(tmp_path):
    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item2"
    fake._initialize_resume_state([(url, "item")], 60, source="test")

    fake._mark_resume_item(
        url,
        "posting_unknown",
        "possibly posted item",
        reservation_id="reservation-2",
        idempotency_key="request-2",
    )

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["status"] == "posting_unknown"
    assert fake._resume_pending_link_data(payload) == []


def test_confirmed_not_posted_releases_and_rotates_idempotency_key(tmp_path, monkeypatch):
    from src import auth_client

    fake = _make_resume_fake(tmp_path)
    url = "https://link.coupang.com/a/item3"
    state = {
        "interval": 60,
        "items": [
            {
                "url": url,
                "status": "posting_unknown",
                "reservation_id": "reservation-3",
                "idempotency_key": "old-request-key",
            }
        ],
    }
    fake._resume_items = [dict(state["items"][0])]
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
    )
    released = []
    monkeypatch.setattr(
        auth_client,
        "release_reserved_work",
        lambda reservation_id: released.append(reservation_id) or {"success": True},
    )

    fake._reconcile_ambiguous_post_items(state)

    assert released == ["reservation-3"]
    assert state["items"][0]["status"] == "pending"
    assert "reservation_id" not in state["items"][0]
    assert "idempotency_key" not in state["items"][0]
