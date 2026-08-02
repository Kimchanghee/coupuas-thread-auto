from types import SimpleNamespace

from src.update_resume import UpdateResumeStore, active_account_ids, update_completed


def test_active_account_ids_only_returns_running_queues_with_work():
    snapshots = {
        "active": {
            "pending_items": [{"url": "https://example.com/1"}],
            "schedule": SimpleNamespace(enabled=True, running=False),
        },
        "idle": {
            "pending_items": [{"url": "https://example.com/2"}],
            "schedule": SimpleNamespace(enabled=False, running=False),
        },
        "done": {
            "pending_items": [],
            "current_item": None,
            "schedule": SimpleNamespace(enabled=True, running=False),
        },
    }
    assert active_account_ids(snapshots) == ["active"]


def test_update_resume_store_round_trip_is_version_gated(tmp_path):
    store = UpdateResumeStore(tmp_path / "update-resume.json")
    store.save("v3.1.0", ["one", "one", "two"], legacy_running=True)

    payload = store.load()
    assert payload["account_ids"] == ["one", "two"]
    assert payload["legacy_running"] is True
    assert update_completed("v3.0.99", payload["target_version"]) is False
    assert update_completed("v3.1.0", payload["target_version"]) is True

    store.clear()
    assert store.load() is None


def test_update_resume_store_rejects_invalid_version(tmp_path):
    store = UpdateResumeStore(tmp_path / "update-resume.json")
    try:
        store.save("latest", ["one"])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid update target must be rejected")
