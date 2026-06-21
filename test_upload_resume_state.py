import json
import threading
from types import SimpleNamespace

from src.main_window import MainWindow


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
    ):
        setattr(fake, name, getattr(MainWindow, name).__get__(fake, type(fake)))
    fake._is_resume_unfinished = MainWindow._is_resume_unfinished
    return fake


def test_resume_state_persists_only_unfinished_items(tmp_path):
    fake = _make_resume_fake(tmp_path)

    fake._initialize_resume_state(
        [
            ("https://www.coupang.com/vp/products/1", "summer fan"),
            ("https://www.coupang.com/vp/products/2", "cool mat"),
        ],
        14400,
        source="test",
    )
    fake._mark_resume_item("https://www.coupang.com/vp/products/1", "completed", "done")
    fake._mark_resume_item("https://www.coupang.com/vp/products/2", "running", "active")
    fake._set_resume_next_allowed_at(12345.0)

    payload = json.loads(fake._resume_state_path.read_text(encoding="utf-8"))
    assert payload["interval"] == 14400
    assert payload["next_allowed_at"] == 12345.0
    assert fake._resume_pending_link_data(payload) == [
        ("https://www.coupang.com/vp/products/2", "cool mat")
    ]

    fake._mark_resume_item("https://www.coupang.com/vp/products/2", "failed", "active")
    assert not fake._resume_state_path.exists()
