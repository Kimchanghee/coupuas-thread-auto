"""Behavior checks for the approved September 13 UI refinement."""
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")

import pytest
from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.QtTest import QTest
from src.redesign_pages import DashboardPage, HistoryPage, SubscriptionPage
import src.main_window as main


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dashboard_routes_attention_to_correct_account(app):
    page = DashboardPage()
    selected, added = [], []
    page.account_selected.connect(selected.append)
    page.add_account_requested.connect(lambda: added.append(True))
    healthy = {"id": "healthy", "status": "연결 정상"}
    page.render_dashboard(accounts=[healthy, {"id": "expired", "status": "세션 만료"}])
    page.next_action_button.click()
    assert selected == ["expired"]
    page.render_dashboard(accounts=[healthy])
    assert page.next_action_button.isHidden()
    page.render_dashboard(accounts=[])
    page.next_action_button.click()
    assert added == [True]
    page.deleteLater()


def test_history_refresh_preserves_identity_and_routes_recovery(app):
    page = HistoryPage()
    rows = [{"id": str(i), "product": f"상품 {i}", "result": "실패", "action": "계정 확인"} for i in range(30)]
    page.render_history(rows=rows)
    page.resize(1000, 650)
    page.show()
    app.processEvents()
    page.history_table.selectRow(12)
    scroll = page.history_table.verticalScrollBar().value()
    page.search_input.setText("상품")
    page.render_history(rows=list(reversed(rows)))
    assert page.history_table.currentRow() == 17
    assert page.history_table.verticalScrollBar().value() == scroll
    assert page.current_filters()["query"] == "상품"
    checked, opened = [], []
    page.account_check_requested.connect(checked.append)
    page.record_open_requested.connect(opened.append)
    page._handle_cell_action(17, 5)
    page._handle_cell_action(17, 2)
    assert checked == ["12"] and opened == ["12"]
    page.render_history(rows=[row for row in rows if row["id"] != "12"])
    assert page.history_table.currentRow() == -1
    page.close()
    page.deleteLater()


def test_plan_refresh_preserves_period_until_current_plan_changes(app):
    page = SubscriptionPage()
    plans = [{"id": "basic-month", "name": "월간", "current": True}, {"id": "basic-week", "name": "7일"}]
    page.render_subscription(plans=plans)
    page.plan_period_filter.setCurrentIndex(1)
    page.render_subscription(plans=plans)
    assert page.plan_period_filter.currentData() == "week"
    selected = []
    page.plan_selected.connect(selected.append)
    page.plans_comparison.cellWidget(3, 1).click()
    assert selected == ["basic-week"]
    plans[0]["current"], plans[1]["current"] = False, True
    page.render_subscription(plans=plans)
    assert not page.plans_comparison.cellWidget(3, 1).isEnabled()
    plans[0]["current"], plans[1]["current"] = True, False
    page.render_subscription(plans=plans)
    assert page.plan_period_filter.currentData() == "month"
    page.deleteLater()


@pytest.mark.parametrize("accept", [False, True])
def test_workspace_return_respects_unsaved_settings(app, monkeypatch, accept):
    focus = QPlainTextEdit()
    focus.setPlainText("existing draft")
    context = {"page": 0, "account_id": "original", "tab": 0, "focus": focus}
    window = SimpleNamespace(
        _workspace_return_context=context, _workspace_return_btn=Mock(),
        _current_page=1, _settings_dirty=True, _load_settings=Mock(),
        _threads_accounts=lambda: [SimpleNamespace(account_id="original")],
        _select_account_from_redesign_page=Mock(return_value=True), _switch_page=Mock(),
    )
    monkeypatch.setattr(main, "ask_yes_no", lambda *args: accept)
    main.MainWindow._return_to_workspace(window)
    assert focus.toPlainText() == "existing draft"
    if accept:
        window._load_settings.assert_called_once()
        window._select_account_from_redesign_page.assert_called_once_with("original")
        window._switch_page.assert_called_once_with(0, source="workspace_return")
        assert window._workspace_return_context is None
    else:
        window._load_settings.assert_not_called()
        window._switch_page.assert_not_called()
        assert window._workspace_return_context is context
    focus.deleteLater()


def test_workspace_return_stops_when_original_account_cannot_be_selected(app):
    context = {"page": 0, "account_id": "original", "tab": 0, "focus": None}
    window = SimpleNamespace(
        _workspace_return_context=context, _workspace_return_btn=Mock(),
        _threads_accounts=lambda: [SimpleNamespace(account_id="original")],
        _select_account_from_redesign_page=Mock(return_value=False), _switch_page=Mock(),
    )
    main.MainWindow._return_to_workspace(window)
    window._switch_page.assert_not_called()
    assert window._workspace_return_context is context


def test_inline_login_error_clears_after_user_edit(app, monkeypatch):
    from src.login_window import LoginWindow
    from src import auth_client
    monkeypatch.setattr(auth_client, "get_saved_credentials", dict)
    window = LoginWindow()
    window._show_field_feedback(window.login_id, "아이디를 입력하세요")
    feedback = window._field_feedback[window.login_id]
    assert not feedback.isHidden()
    QTest.keyClicks(window.login_id, "new-id")
    assert feedback.isHidden()
    assert window.login_id.accessibleDescription() == ""
    window.close()
    window.deleteLater()


def test_live_history_identity_survives_new_records(monkeypatch):
    from src.models.threads_account import ThreadsAccount
    account = ThreadsAccount.create("sample")
    monkeypatch.setattr(main.config, "threads_accounts", [account])
    monkeypatch.setattr(main.auth_client, "get_auth_state", lambda: {})
    runtime = Mock()
    old = {"url": "https://link.coupang.com/a/old", "uploaded_at": "2026-09-12T10:00:00", "success": False}
    runtime.link_history.return_value.get_records.return_value = [old]
    window = SimpleNamespace(
        dashboard_page=Mock(), history_page=Mock(), accounts_page=Mock(), subscription_page=Mock(),
        _multi_account_runtime=runtime, _resolved_subscription_plan=None,
        _work_label=SimpleNamespace(text=lambda: "0 / 5 회"),
        _plan_badge=SimpleNamespace(text=lambda: "무료"),
        _apply_history_filters=Mock(), selected_threads_account_id=lambda: account.account_id,
        _threads_account_limit=lambda: 1,
    )
    main.MainWindow._refresh_auxiliary_pages(window)
    old_id = window._all_history_rows[0]["id"]
    runtime.link_history.return_value.get_records.return_value = [
        {**old, "uploaded_at": "2026-09-13T10:00:00"}, old,
    ]
    main.MainWindow._refresh_auxiliary_pages(window)
    assert window._history_records_by_id[old_id]["uploaded_at"] == old["uploaded_at"]
    assert len(window._history_records_by_id) == 2
