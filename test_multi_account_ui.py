"""Offscreen coverage for account selection in the main-window UI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")

from PyQt6.QtWidgets import QApplication

import src.main_window as main_window
from src.config import config
from src.models.threads_account import ThreadsAccount
from src.services.account_queue import AccountQueueStore


def test_upload_tabs_keep_drafts_and_render_their_own_queue(monkeypatch, tmp_path):
    _app = QApplication.instance() or QApplication([])
    first = ThreadsAccount.create("first_account")
    second = ThreadsAccount.create("second_account")
    original_accounts = config.threads_accounts
    original_active = config.active_threads_account_id
    original_username = config.instagram_username
    config.threads_accounts = [first, second]
    config.active_threads_account_id = first.account_id
    config.instagram_username = first.expected_username
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")

    AccountQueueStore(first.account_id, root=tmp_path / "queues").enqueue("https://link.coupang.com/a/first")
    AccountQueueStore(second.account_id, root=tmp_path / "queues").enqueue("https://link.coupang.com/a/second")

    window = main_window.MainWindow()
    try:
        assert window._upload_account_tabs.count() == 2
        assert window.selected_threads_account_id() == first.account_id
        assert window.link_table.item(0, main_window.LINK_TABLE_URL_COLUMN).text().endswith("/first")
        assert "쿠팡" in window.link_table.item(0, main_window.LINK_TABLE_CHANNEL_COLUMN).text()

        window.links_text.setPlainText("first draft")
        window._upload_account_tabs.setCurrentIndex(1)
        assert window.selected_threads_account_id() == second.account_id
        assert window.links_text.toPlainText() == ""
        assert window.link_table.item(0, main_window.LINK_TABLE_URL_COLUMN).text().endswith("/second")

        window.links_text.setPlainText("second draft")
        window._upload_account_tabs.setCurrentIndex(0)
        assert window.links_text.toPlainText() == "first draft"
    finally:
        window._closed = True
        window.close()
        config.threads_accounts = original_accounts
        config.active_threads_account_id = original_active
        config.instagram_username = original_username


def test_account_switch_renders_the_selected_accounts_login_status(monkeypatch, tmp_path):
    _app = QApplication.instance() or QApplication([])
    first = ThreadsAccount.create(
        "first_account",
        last_verified_username="first_account",
        last_verified_at="2026-08-17T10:00:00+09:00",
    )
    second = ThreadsAccount.create("second_account")
    original_accounts = config.threads_accounts
    original_active = config.active_threads_account_id
    original_username = config.instagram_username
    config.threads_accounts = [first, second]
    config.active_threads_account_id = first.account_id
    config.instagram_username = first.expected_username
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")

    window = main_window.MainWindow()
    try:
        assert window.login_status_label.text() == "@first_account · 마지막 확인"

        window._upload_account_tabs.setCurrentIndex(1)

        assert window.selected_threads_account_id() == second.account_id
        assert window.login_status_label.text() == "@second_account · 확인 필요"
    finally:
        window._closed = True
        window.close()
        config.threads_accounts = original_accounts
        config.active_threads_account_id = original_active
        config.instagram_username = original_username


def test_stale_login_result_does_not_replace_the_selected_account(monkeypatch, tmp_path):
    _app = QApplication.instance() or QApplication([])
    first = ThreadsAccount.create("first_account")
    second = ThreadsAccount.create("second_account")
    original_accounts = config.threads_accounts
    original_active = config.active_threads_account_id
    original_username = config.instagram_username
    config.threads_accounts = [first, second]
    config.active_threads_account_id = first.account_id
    config.instagram_username = first.expected_username
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")

    window = main_window.MainWindow()
    try:
        window._upload_account_tabs.setCurrentIndex(1)
        assert window.selected_threads_account_id() == second.account_id

        event = main_window.LoginStatusEvent(
            (True, "first_account", first.account_id, first.expected_username)
        )
        assert window.event(event) is True

        assert window.selected_threads_account_id() == second.account_id
        assert window.login_status_label.text() == "@second_account · 확인 필요"
        saved_first = config.get_threads_account(first.account_id)
        assert saved_first.last_verified_username == "first_account"
    finally:
        window._closed = True
        window.close()
        config.threads_accounts = original_accounts
        config.active_threads_account_id = original_active
        config.instagram_username = original_username


def test_login_browser_close_checks_the_account_that_opened_it(monkeypatch, tmp_path):
    _app = QApplication.instance() or QApplication([])
    first = ThreadsAccount.create("first_account")
    second = ThreadsAccount.create("second_account")
    original_accounts = config.threads_accounts
    original_active = config.active_threads_account_id
    original_username = config.instagram_username
    config.threads_accounts = [first, second]
    config.active_threads_account_id = first.account_id
    config.instagram_username = first.expected_username
    monkeypatch.setattr(config, "config_dir", tmp_path)
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "secrets_file", tmp_path / "secrets.json")

    window = main_window.MainWindow()
    checked_accounts = []
    try:
        window._threads_login_account_id = first.account_id
        window._threads_login_browser_open = True
        window._upload_account_tabs.setCurrentIndex(1)
        monkeypatch.setattr(
            window,
            "_check_login_status",
            lambda account_id=None: checked_accounts.append(account_id),
        )

        window._on_threads_browser_closed()

        assert checked_accounts == [first.account_id]
        assert window.selected_threads_account_id() == second.account_id
        assert window.login_status_label.text() == "@second_account · 확인 필요"
    finally:
        window._closed = True
        window.close()
        config.threads_accounts = original_accounts
        config.active_threads_account_id = original_active
        config.instagram_username = original_username
