from src.main_window import MainWindow


def test_dev_quota_bypass_enabled_by_env(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")
    assert MainWindow._is_dev_quota_bypass_enabled() is True


def test_dev_quota_bypass_disabled_by_env(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "0")
    assert MainWindow._is_dev_quota_bypass_enabled() is False


def test_work_allowed_accepts_known_success_shapes():
    assert MainWindow._is_work_allowed({"success": True}) is True
    assert MainWindow._is_work_allowed({"status": True}) is True
    assert MainWindow._is_work_allowed({"available": True}) is True


def test_work_allowed_rejects_missing_or_false_shapes():
    assert MainWindow._is_work_allowed({"success": False}) is False
    assert MainWindow._is_work_allowed({"status": False}) is False
    assert MainWindow._is_work_allowed({"available": False}) is False
    assert MainWindow._is_work_allowed({"message": "no quota"}) is False
    assert MainWindow._is_work_allowed(None) is False
