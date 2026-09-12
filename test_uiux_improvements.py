import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QLineEdit
import src.main_window as module
from src.ui_components import PasswordEdit
from src.ui_presentation import account_health, today_metrics, subscription_details, safe_post_url


def test_failed_and_stale_connections_never_appear_healthy():
    now = datetime.now(timezone.utc)
    account = SimpleNamespace(expected_username="sample", last_verified_username="sample", last_verified_at=now.isoformat(), last_check_status="")
    assert account_health(account, now=now)[1] == "success"
    assert account_health(account, {"state": "error"}, now)[1] == "error"
    account.last_verified_at = (now - timedelta(days=2)).isoformat()
    assert account_health(account, now=now)[1] == "warning"
    account.last_verified_username = "different"
    assert account_health(account, now=now)[1] == "warning"


def test_today_metrics_exclude_previous_days_and_unknown_dates():
    now = datetime.now().astimezone()
    rows = [
        {"uploaded_at": now.isoformat(), "result": "성공"},
        {"uploaded_at": now.isoformat(), "result": "실패"},
        {"uploaded_at": (now - timedelta(days=1)).isoformat(), "result": "성공"},
        {"uploaded_at": "unknown", "result": "성공"},
    ]
    assert today_metrics(rows, now) == {"오늘 완료": 1, "오늘 성공률": "50.0%"}
    assert today_metrics([], now)["오늘 성공률"] == "집계 전"


def test_subscription_expiry_is_not_an_invented_charge_date():
    state = {"expires_at": "2026-10-01T12:00:00+09:00"}
    recurring = subscription_details(state, SimpleNamespace(recurring=True))
    assert recurring["renewal_date"]
    assert recurring["billing_date"] == ""
    assert "미제공" in recurring["billing_empty"]
    assert subscription_details(state, SimpleNamespace(recurring=False))["billing_empty"] == "자동 결제 없음"


def test_history_post_links_are_restricted_to_real_threads_paths():
    assert safe_post_url("https://www.threads.com/@sample/post/ABC")
    assert not safe_post_url("https://www.threads.com.evil.example/@sample/post/ABC")
    assert not safe_post_url("https://www.threads.com/@sample")
    assert not safe_post_url("javascript:alert(1)")


def test_retry_selects_original_account_and_preserves_its_draft(monkeypatch):
    app = QApplication.instance() or QApplication([])
    edit = QPlainTextEdit()
    edit.setPlainText("https://example.com/existing")
    account = SimpleNamespace(account_id="original", expected_username="owner")
    window = SimpleNamespace(
        _history_records_by_id={"record": {"account_id": "original", "url": "https://example.com/retry"}},
        _threads_accounts=lambda: [account],
        _ensure_threads_account_allowed=lambda account_id: True,
        _select_account_from_redesign_page=Mock(return_value=True),
        links_text=edit, _account_drafts={}, _switch_page=Mock(), _set_status=Mock(),
    )
    module.MainWindow._retry_history_record(window, "record")
    window._select_account_from_redesign_page.assert_called_once_with("original")
    assert edit.toPlainText().splitlines() == ["https://example.com/existing", "https://example.com/retry"]
    module.MainWindow._retry_history_record(window, "record")
    assert len(edit.toPlainText().splitlines()) == 2
    window._threads_accounts = lambda: []
    warning = Mock()
    monkeypatch.setattr(module, "show_warning", warning)
    module.MainWindow._retry_history_record(window, "record")
    warning.assert_called_once()
    edit.deleteLater()
    app.processEvents()


def test_all_queue_cancel_never_starts_a_post(monkeypatch):
    account = SimpleNamespace(account_id="a", expected_username="alpha", upload_interval=60)
    runtime = Mock()
    runtime.snapshots.return_value = {"a": {"pending_items": ["one"]}}
    runtime.snapshot.return_value = {"pending_items": ["one"]}
    window = SimpleNamespace(_multi_account_runtime=runtime, _threads_accounts=lambda: [account], _threads_account_limit=lambda: 1)
    confirm = Mock(return_value=False)
    monkeypatch.setattr(module, "ask_yes_no", confirm)
    module.MainWindow.start_all_accounts(window)
    assert "@alpha: 1개" in confirm.call_args.args[2]
    runtime.start_account.assert_not_called()


def test_password_visibility_preserves_input():
    app = QApplication.instance() or QApplication([])
    edit = PasswordEdit()
    edit.setText("local-test-value")
    edit.visibility_button.click()
    assert edit.echoMode() == QLineEdit.EchoMode.Normal
    edit.visibility_button.click()
    assert edit.echoMode() == QLineEdit.EchoMode.Password
    assert edit.text() == "local-test-value"
    edit.deleteLater()
    app.processEvents()


def test_failed_connection_state_survives_reload():
    from src.models.threads_account import ThreadsAccount
    account = ThreadsAccount.create("sample", last_check_status="error", last_checked_at=datetime.now(timezone.utc).isoformat())
    restored = ThreadsAccount.from_dict(account.to_dict())
    assert account_health(restored)[1] == "error"
    assert restored.last_checked_at == account.last_checked_at


def test_production_adapter_exposes_history_failure_instead_of_zero(monkeypatch):
    from src.models.threads_account import ThreadsAccount
    account = ThreadsAccount.create("sample")
    monkeypatch.setattr(module.config, "threads_accounts", [account])
    monkeypatch.setattr(module.auth_client, "get_auth_state", lambda: {})
    runtime = Mock()
    runtime.link_history.side_effect = OSError("history unavailable")
    window = SimpleNamespace(
        dashboard_page=Mock(), history_page=Mock(), accounts_page=Mock(), subscription_page=Mock(),
        _multi_account_runtime=runtime, _resolved_subscription_plan=None,
        _work_label=SimpleNamespace(text=lambda: "0 / 5 회"),
        _plan_badge=SimpleNamespace(text=lambda: "무료"),
        _apply_history_filters=Mock(), selected_threads_account_id=lambda: account.account_id,
        _threads_account_limit=lambda: 1,
    )
    module.MainWindow._refresh_auxiliary_pages(window)
    metrics = window.dashboard_page.render_dashboard.call_args.kwargs["metrics"]
    assert metrics["오늘 완료"] == "미확인"
    assert metrics["오늘 성공률"] == "미확인"


def test_latest_update_clears_previous_package_size():
    from src.update_dialog import UpdateDialog
    app = QApplication.instance() or QApplication([])
    dialog = UpdateDialog("1.0.0", update_info={"version": "2.0.0", "size_mb": 99})
    assert dialog.size_label.text()
    dialog._on_no_update()
    assert dialog.size_label.text() == ""
    dialog.deleteLater()
    app.processEvents()
