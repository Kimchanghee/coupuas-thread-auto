import os
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

import src.main_window as main_window_module
from src.main_window import MainWindow
from src.subscription_plans import (
    SHOPPING_PRO_FOUNDER_MONTHLY_PLAN,
    SHOPPING_PRO_WEEKLY_PLAN,
)
from src.theme import Breakpoints
from src.ui_components import PipelineRail


def _app():
    return QApplication.instance() or QApplication([])


def _close(window, app):
    window._closed = True
    window.close()
    window.deleteLater()
    app.processEvents()


def test_six_route_shell_uses_one_stacked_page_controller():
    app = _app()
    window = MainWindow()
    window.show()
    try:
        assert window._page_stack.count() == 6
        assert window._pages == [window._page_stack.widget(i) for i in range(6)]
        assert window._page_stack.currentIndex() == 2
        assert window._nav_button_by_page[2].isChecked()

        for page_index in (2, 0, 3, 4, 1, 5):
            window._switch_page(page_index, source="integration_test")
            app.processEvents()
            assert window._page_stack.currentIndex() == page_index
            assert window._page_stack.currentWidget() is window._pages[page_index]
            assert window._nav_button_by_page[page_index].isChecked()
            assert sum(button.isChecked() for button in window._nav_buttons) == 1
    finally:
        _close(window, app)


def test_automation_primary_action_stays_visible_at_supported_breakpoints():
    app = _app()
    window = MainWindow()
    window.show()
    try:
        window._switch_page(0, source="integration_test")
        for width, height in (
            (Breakpoints.MINIMUM_WIDTH, Breakpoints.MINIMUM_HEIGHT),
            (Breakpoints.STANDARD_WIDTH, 620),
            (1360, 900),
        ):
            window.resize(width, height)
            app.processEvents()

            page = window._pages[0]
            footer = window._automation_footer
            assert footer.parentWidget() is page
            assert footer.isVisibleTo(page)
            assert footer.geometry().bottom() < page.height()
            assert window._link_scroll.geometry().bottom() < footer.y()
            assert window.start_btn.parentWidget() is footer
            assert window.start_btn.isVisibleTo(footer)
            assert footer.rect().contains(window.start_btn.geometry())
    finally:
        _close(window, app)


def test_automation_footer_shows_only_actions_relevant_to_run_state():
    app = _app()
    window = MainWindow()
    window.resize(900, 620)
    window.show()
    window._switch_page(0, source="integration_test")
    try:
        window._set_run_state({"phase": "idle"})
        app.processEvents()
        assert window.start_btn.isVisible()
        assert window.start_all_btn.isVisible()
        assert not window.add_btn.isVisible()
        assert not window.stop_btn.isVisible()
        assert not window.stop_all_btn.isVisible()

        window._set_run_state(
            {"phase": "running", "pending": 2, "total": 3, "completed": 1}
        )
        app.processEvents()
        assert not window.start_btn.isVisible()
        assert not window.start_all_btn.isVisible()
        for button in (window.add_btn, window.stop_btn, window.stop_all_btn):
            assert button.isVisible()
            assert window._automation_footer.rect().contains(button.geometry())

        window._set_run_state(
            {"phase": "paused", "pending": 2, "total": 3, "completed": 1}
        )
        app.processEvents()
        assert window.start_btn.isVisible()
        assert window.start_btn.text() == "저장된 작업 이어서 실행"
        assert window.start_all_btn.isVisible()
        assert not window.add_btn.isVisible()
        assert not window.stop_btn.isVisible()
        assert not window.stop_all_btn.isVisible()
    finally:
        _close(window, app)


def test_paused_start_resumes_existing_queue_even_when_editor_has_text(monkeypatch):
    app = _app()
    window = MainWindow()
    try:
        resumed = []
        monkeypatch.setattr(window, "_ensure_threads_account_allowed", lambda *_args: True)
        monkeypatch.setattr(
            window,
            "_start_existing_selected_queue",
            lambda: resumed.append(True) or True,
        )
        window.links_text.setPlainText("https://link.coupang.com/a/existing")
        window._latest_run_state = {"phase": "stopped"}

        window.start_upload()

        assert resumed == [True]
    finally:
        _close(window, app)


def test_pipeline_public_state_tracks_controller_progress():
    app = _app()
    window = MainWindow()
    try:
        rail = window._pipeline_rail
        assert isinstance(rail, PipelineRail)
        assert rail.stages == tuple(window._PROCESS_STEPS)

        window._reset_steps()
        assert rail.current_index == 0
        assert "오류" not in rail.accessibleDescription()

        window._update_step(0, "active")
        assert rail.current_index == 0
        assert "링크 분석 진행 중" in rail.accessibleDescription()

        window._update_step(0, "done")
        assert rail.current_index == 1
        assert "링크 분석 완료" in rail.accessibleDescription()

        window._update_step(2, "error")
        assert rail.current_index == 2
        assert "Threads 업로드 오류" in rail.accessibleDescription()

        rail.complete()
        assert rail.current_index == rail.stage_count
        stage_descriptions = rail.accessibleDescription().split(", ")
        assert len(stage_descriptions) == rail.stage_count
        assert all(description.endswith(" 완료") for description in stage_descriptions)
    finally:
        _close(window, app)


def test_all_new_pages_avoid_horizontal_scroll_at_three_breakpoints():
    app = _app()
    window = MainWindow()
    window.show()
    auxiliary_pages = {
        2: window.dashboard_page,
        3: window.history_page,
        4: window.accounts_page,
        5: window.subscription_page,
    }
    try:
        for width, height in ((760, 560), (900, 620), (1360, 900)):
            window.resize(width, height)
            app.processEvents()
            for page_index, view in auxiliary_pages.items():
                window._switch_page(page_index, source="integration_test")
                app.processEvents()

                host = window._pages[page_index]
                assert view.geometry() == host.rect()
                assert (
                    view.scroll_area.horizontalScrollBarPolicy()
                    == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                assert view.scroll_area.horizontalScrollBar().maximum() == 0
                for table in view.findChildren(QTableWidget):
                    assert (
                        table.horizontalScrollBarPolicy()
                        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                    )
                    assert table.horizontalScrollBar().maximum() == 0
    finally:
        _close(window, app)


def test_history_filters_survive_refresh_and_empty_filter_exports_nothing(
    monkeypatch, tmp_path
):
    app = _app()
    window = MainWindow()
    now = datetime.now().astimezone()
    rows = [
        {
            "id": "ok",
            "time": now.strftime("%Y-%m-%d %H:%M"),
            "uploaded_at": now.isoformat(),
            "channel": "쿠팡",
            "product": "선풍기",
            "account": "계정 A",
            "result": "성공",
            "action": "열기",
            "url": "https://link.coupang.com/a/ok",
        },
        {
            "id": "old-fail",
            "time": (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M"),
            "uploaded_at": (now - timedelta(days=40)).isoformat(),
            "channel": "네이버",
            "product": "수납함",
            "account": "계정 B",
            "result": "실패",
            "action": "실패 재시도",
            "url": "https://naver.me/example",
        },
    ]
    try:
        window._all_history_rows = rows
        window.history_page.search_input.setText("없는 상품")
        window._apply_history_filters(window.history_page.current_filters())
        assert window._visible_history_rows == []
        assert window.history_page.history_table.rowCount() == 0

        notices = []
        monkeypatch.setattr(
            main_window_module,
            "show_info",
            lambda _parent, title, message: notices.append((title, message)),
        )
        destination = tmp_path / "should-not-exist.csv"
        monkeypatch.setattr(
            main_window_module.QFileDialog,
            "getSaveFileName",
            lambda *_args, **_kwargs: (str(destination), "CSV 파일 (*.csv)"),
        )
        window._export_history_csv()
        assert not destination.exists()
        assert notices and "내보낼 작업 기록" in notices[-1][1]

        window.history_page.search_input.clear()
        window.history_page.period_filter.setCurrentText("최근 7일")
        window._apply_history_filters(window.history_page.current_filters())
        assert [row["id"] for row in window._visible_history_rows] == ["ok"]

        window._refresh_auxiliary_pages()
        assert window.history_page.period_filter.currentText() == "최근 7일"
    finally:
        _close(window, app)


def test_subscription_and_accounts_use_exact_resolved_plan(monkeypatch):
    app = _app()
    window = MainWindow()
    try:
        monkeypatch.setattr(main_window_module.config, "threads_accounts", [])
        monkeypatch.setattr(window, "_threads_account_limit", lambda: 3)
        window._resolved_subscription_plan = SHOPPING_PRO_WEEKLY_PLAN
        window._refresh_auxiliary_pages()

        assert window.accounts_page.limit_badge.text() == "0 / 3개"
        assert "7일 쇼핑 프로" in window.accounts_page.plan_label.text()
        assert window.subscription_page.current_plan_name.text() == "7일 쇼핑 프로"

        current_cards = []
        for card in window.subscription_page._plan_widgets:
            labels = " ".join(label.text() for label in card.findChildren(QLabel))
            actions = card.findChildren(QPushButton)
            if any(not action.isEnabled() for action in actions):
                current_cards.append(labels)
        assert len(current_cards) == 1
        assert "쇼핑 프로 · 7일" in current_cards[0]
        assert "월간" not in current_cards[0]

        window._resolved_subscription_plan = SHOPPING_PRO_FOUNDER_MONTHLY_PLAN
        window._refresh_auxiliary_pages()
        founder_cards = []
        for card in window.subscription_page._plan_widgets:
            labels = " ".join(label.text() for label in card.findChildren(QLabel))
            actions = card.findChildren(QPushButton)
            if any(not action.isEnabled() for action in actions):
                founder_cards.append(labels)
        assert len(founder_cards) == 1
        assert "59,000원 / 30일" in founder_cards[0]
        assert "프로모션 최대 6회" in founder_cards[0]
    finally:
        _close(window, app)


def test_dashboard_account_health_row_opens_account_workspace():
    app = _app()
    window = MainWindow()
    window.show()
    try:
        window.dashboard_page.render_dashboard(
            accounts=[
                {
                    "id": "account-a",
                    "name": "계정 A",
                    "username": "@account_a",
                    "status": "정상",
                }
            ]
        )
        row = window.dashboard_page.findChild(QPushButton, "dashboardAccountRow0")
        assert row is not None
        row.click()
        app.processEvents()
        assert window._page_stack.currentIndex() == 4
    finally:
        _close(window, app)
