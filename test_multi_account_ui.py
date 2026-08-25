"""Offscreen coverage for account selection in the main-window UI."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")

from PyQt6.QtWidgets import QApplication

import src.main_window as main_window
from src.config import config
from src.models.threads_account import ThreadsAccount
from src.services.account_queue import AccountQueueStore


class _ButtonState:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


class _Emitter:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values)


def test_finished_schedule_does_not_leave_main_window_running():
    schedule = SimpleNamespace(
        running=False,
        enabled=True,  # Defensive UI check for an old/stale runtime snapshot.
        pending_count=0,
        blocked_reason="",
        next_allowed_at=0.0,
    )
    payload = {
        "schedule": schedule,
        "pending_items": [],
        "current_item": None,
        "phase": "idle",
        "stats": {"success": 1, "failed": 0, "skipped": 0},
    }
    runtime = SimpleNamespace(snapshots=lambda: {"account-a": payload})
    window = SimpleNamespace(
        _multi_account_runtime=runtime,
        _pending_update_info=None,
        _upload_account_tabs=None,
        _ambiguous_post_prompt_accounts=set(),
        selected_threads_account_id=lambda: "account-a",
        _render_account_queue=lambda _account_id: None,
        _refresh_auxiliary_pages=lambda: None,
        signals=SimpleNamespace(run_state=_Emitter()),
        start_btn=_ButtonState(),
        add_btn=_ButtonState(),
        stop_btn=_ButtonState(),
        stop_all_btn=_ButtonState(),
        is_running=True,
    )

    main_window.MainWindow._on_account_runtime_state(
        window,
        "account-a",
        payload,
    )

    assert window.is_running is False
    assert window.start_btn.enabled is True
    assert window.stop_btn.enabled is False
    assert window.stop_all_btn.enabled is False


def test_multi_account_ambiguous_prompt_calls_runtime_resolver():
    resolved = []
    original_item = {
        "item_id": "item-a",
        "url": "https://example.test/a",
        "stage": "posting_unknown",
        "product_name": "테스트 상품",
    }
    runtime = SimpleNamespace(
        snapshot=lambda _account_id: {
            "current_item": original_item,
        },
        resolve_posting_unknown=lambda account_id, choice: (
            resolved.append((account_id, choice))
            or {
                "current_item": None,
                "pending_items": [
                    {
                        "item_id": "item-a",
                        "url": "https://example.test/a",
                    }
                ],
                "processed_urls": [],
                "schedule": SimpleNamespace(blocked_reason=""),
            }
        ),
    )
    window = SimpleNamespace(
        _multi_account_runtime=runtime,
        _ambiguous_post_prompt_accounts={"account-a"},
        _ask_ambiguous_post_result=lambda _title: "not_posted",
        signals=SimpleNamespace(log=_Emitter()),
    )

    main_window.MainWindow._resolve_multi_account_ambiguous_post(
        window,
        "account-a",
    )

    assert resolved == [("account-a", "not_posted")]
    assert window._ambiguous_post_prompt_accounts == set()
    assert window.signals.log.values == [
        ("게시 안 됨으로 확인해 안전하게 대기열에 다시 넣었습니다.",)
    ]


def test_multi_account_ambiguous_prompt_reports_pending_resolver_failures():
    scenarios = (
        ("posted", "quota_commit_pending", "posted_commit_pending", "작업량 확인"),
        ("posted", "history_write_pending", "history_write_pending", "게시 기록 저장"),
        (
            "not_posted",
            "reservation_release_pending",
            "reservation_release_pending",
            "예약 해제",
        ),
    )

    for choice, block_reason, stage, expected_text in scenarios:
        original_item = {
            "item_id": "item-a",
            "url": "https://example.test/a",
            "stage": "posting_unknown",
            "product_name": "테스트 상품",
        }
        runtime = SimpleNamespace(
            snapshot=lambda _account_id, item=original_item: {
                "current_item": item,
            },
            resolve_posting_unknown=lambda _account_id, _choice, value={
                "current_item": {
                    **original_item,
                    "stage": stage,
                },
                "pending_items": [],
                "processed_urls": [],
                "schedule": SimpleNamespace(blocked_reason=block_reason),
            }: value,
        )
        window = SimpleNamespace(
            _multi_account_runtime=runtime,
            _ambiguous_post_prompt_accounts={"account-a"},
            _ask_ambiguous_post_result=lambda _title, value=choice: value,
            signals=SimpleNamespace(log=_Emitter()),
        )

        main_window.MainWindow._resolve_multi_account_ambiguous_post(
            window,
            "account-a",
        )

        messages = [values[0] for values in window.signals.log.values]
        assert len(messages) == 1
        assert expected_text in messages[0]
        assert "동기화했습니다" not in messages[0]
        assert "다시 넣었습니다" not in messages[0]


def test_multi_account_ambiguous_prompt_requires_terminal_snapshot_for_success():
    original_item = {
        "item_id": "item-a",
        "url": "https://example.test/a",
        "stage": "posting_unknown",
        "product_name": "테스트 상품",
    }
    runtime = SimpleNamespace(
        snapshot=lambda _account_id: {"current_item": original_item},
        resolve_posting_unknown=lambda _account_id, _choice: {
            "current_item": {
                **original_item,
                "stage": "posted_commit_pending",
            },
            "pending_items": [],
            "processed_urls": [],
            "schedule": SimpleNamespace(blocked_reason=""),
        },
    )
    window = SimpleNamespace(
        _multi_account_runtime=runtime,
        _ambiguous_post_prompt_accounts={"account-a"},
        _ask_ambiguous_post_result=lambda _title: "posted",
        signals=SimpleNamespace(log=_Emitter()),
    )

    main_window.MainWindow._resolve_multi_account_ambiguous_post(
        window,
        "account-a",
    )

    messages = [values[0] for values in window.signals.log.values]
    assert len(messages) == 1
    assert "아직 완료되지 않았습니다" in messages[0]
    assert "동기화했습니다" not in messages[0]


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
