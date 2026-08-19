import sys
from pathlib import Path

from src.main_window import MainWindow
from src.services.multi_account_upload_runner import AuthQuotaAdapter


def test_dev_quota_bypass_enabled_by_env(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("THREAD_AUTO_DEV_ENTRYPOINT", "1")
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")
    assert MainWindow._is_dev_quota_bypass_enabled() is True
    assert AuthQuotaAdapter._bypass_enabled() is True


def test_dev_quota_bypass_disabled_by_env(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("THREAD_AUTO_DEV_ENTRYPOINT", "1")
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "0")
    assert MainWindow._is_dev_quota_bypass_enabled() is False


def test_dev_quota_bypass_requires_explicit_source_entrypoint(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("THREAD_AUTO_DEV_ENTRYPOINT", raising=False)
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")

    assert MainWindow._is_dev_quota_bypass_enabled() is False
    assert AuthQuotaAdapter._bypass_enabled() is False


def test_dev_quota_bypass_is_always_disabled_in_frozen_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("THREAD_AUTO_DEV_ENTRYPOINT", "1")
    monkeypatch.setenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")

    assert MainWindow._is_dev_quota_bypass_enabled() is False
    assert AuthQuotaAdapter._bypass_enabled() is False


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


def test_importing_main_does_not_enable_development_quota_bypass():
    source = (Path(__file__).parent / "main.py").read_text(encoding="utf-8")
    import_scope = source[: source.index("def main():")]

    assert "THREAD_AUTO_DEV_ENTRYPOINT" not in import_scope
    assert "THREAD_AUTO_DEV_BYPASS_WORK_QUOTA" not in import_scope
