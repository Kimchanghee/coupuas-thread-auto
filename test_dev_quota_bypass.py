from src.main_window import MainWindow


def test_dev_quota_bypass_enabled_by_env(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")
    assert MainWindow._is_dev_quota_bypass_enabled() is True


def test_dev_quota_bypass_disabled_by_env(monkeypatch):
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "0")
    assert MainWindow._is_dev_quota_bypass_enabled() is False

