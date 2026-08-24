import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from src.redesign_pages import (
    AccountsPage,
    DashboardPage,
    HistoryPage,
    SubscriptionPage,
)
from src.theme import ControlHeight


def _app():
    return QApplication.instance() or QApplication([])


def _close_pages(app, pages):
    for page in pages:
        page.close()
        page.deleteLater()
    app.processEvents()


def _assert_no_horizontal_scroll(page):
    assert (
        page.scroll_area.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert page.scroll_area.horizontalScrollBar().maximum() == 0
    for table in page.findChildren(QTableWidget):
        assert (
            table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert table.horizontalScrollBar().maximum() == 0


def test_redesign_pages_instantiate_with_accessible_empty_states():
    app = _app()
    pages = [DashboardPage(), HistoryPage(), AccountsPage(), SubscriptionPage()]
    try:
        expected = {
            DashboardPage: ("dashboardPage", "운영 홈"),
            HistoryPage: ("historyPage", "작업 기록"),
            AccountsPage: ("accountsPage", "Threads 계정"),
            SubscriptionPage: ("subscriptionPage", "구독 및 지원"),
        }
        for page in pages:
            page.resize(760, 560)
            page.show()
        app.processEvents()

        for page in pages:
            object_name, accessible_name = expected[type(page)]
            assert page.objectName() == object_name
            assert page.accessibleName() == accessible_name
            assert page.scroll_area.widgetResizable()
            assert page.content.minimumWidth() == 0
            _assert_no_horizontal_scroll(page)

        assert not pages[0].recent_table.isVisible()
        assert not pages[1].history_table.isVisible()
        assert not pages[2].account_list.isVisible()
        assert pages[2].remove_button.isEnabled() is False
        assert pages[3].current_plan_name.text() == "구독 정보가 없습니다"
    finally:
        _close_pages(app, pages)


def test_redesign_pages_reflow_without_horizontal_scroll_at_supported_sizes():
    app = _app()
    pages = [DashboardPage(), HistoryPage(), AccountsPage(), SubscriptionPage()]
    try:
        for page in pages:
            page.show()

        for width, height in ((1360, 900), (900, 620), (760, 560)):
            for page in pages:
                page.resize(width, height)
            app.processEvents()

            for page in pages:
                assert page.content.width() <= page.scroll_area.viewport().width()
                _assert_no_horizontal_scroll(page)
                for button in page.findChildren(QPushButton):
                    assert button.minimumHeight() >= ControlHeight.INPUT
                for control in page.findChildren((QLineEdit, QComboBox)):
                    assert control.height() >= ControlHeight.INPUT

            compact = width < 1020
            assert pages[0]._compact is compact
            assert pages[1]._compact is compact
            assert pages[2]._compact is compact
            assert pages[3]._compact is compact
            assert pages[0].dashboard_pair_layout.direction() == (
                pages[0].dashboard_pair_layout.Direction.TopToBottom
                if compact
                else pages[0].dashboard_pair_layout.Direction.LeftToRight
            )
            assert pages[3].subscription_pair_layout.direction() == (
                pages[3].subscription_pair_layout.Direction.TopToBottom
                if compact
                else pages[3].subscription_pair_layout.Direction.LeftToRight
            )
    finally:
        _close_pages(app, pages)


def test_dashboard_renders_injected_rows_and_emits_intents():
    app = _app()
    page = DashboardPage()
    requested = []
    history = []
    selected = []
    page.new_automation_requested.connect(lambda: requested.append(True))
    page.history_open_requested.connect(lambda: history.append(True))
    page.account_selected.connect(selected.append)
    page.render_dashboard(
        metrics=[
            {"label": "오늘 완료", "value": "4건", "detail": "집계 시각 10:30"},
            {"label": "성공률", "value": "100%", "status_kind": "success"},
        ],
        accounts=[
            {"id": "account-1", "name": "daily.note", "status": "정상"},
        ],
        recent_jobs=[
            {
                "id": "job-1",
                "started_at": "10:12",
                "account": "daily.note",
                "result": "4 / 4 성공",
                "duration": "3분",
                "status": "완료",
            }
        ],
    )
    page.resize(900, 620)
    page.show()
    app.processEvents()
    try:
        assert page.recent_table.rowCount() == 1
        assert page.recent_table.item(0, 1).text() == "daily.note"
        assert page.recent_table.isVisible()
        page.new_automation_button.click()
        page.history_button.click()
        account_button = page.findChild(QPushButton, "dashboardAccountRow0")
        assert account_button is not None
        account_button.click()
        assert requested == [True]
        assert history == [True]
        assert selected == ["account-1"]
        _assert_no_horizontal_scroll(page)
    finally:
        _close_pages(app, [page])


def test_history_renders_rows_and_emits_filter_retry_export_intents():
    app = _app()
    page = HistoryPage()
    exported = []
    filters = []
    retried = []
    opened = []
    page.export_requested.connect(lambda: exported.append(True))
    page.filters_changed.connect(filters.append)
    page.retry_requested.connect(retried.append)
    page.record_open_requested.connect(opened.append)
    page.set_filter_options(
        periods=["최근 30일"],
        accounts=["모든 계정", "daily.note"],
        statuses=["전체", "실패"],
    )
    page.render_history(
        rows=[
            {
                "id": "record-retry",
                "time": "10:42",
                "channel": "네이버",
                "product": "수납 정리함",
                "account": "daily.note",
                "result": "업로드 실패",
                "action": "재시도",
            },
            {
                "id": "record-open",
                "time": "10:48",
                "channel": "쿠팡",
                "product": "무선 선풍기",
                "account": "daily.note",
                "result": "성공",
                "action": "열기",
            },
        ],
        metrics={"총 게시": "2건", "성공": "1건", "실패": "1건"},
    )
    page.resize(760, 560)
    page.show()
    app.processEvents()
    try:
        assert page.history_table.rowCount() == 2
        page.export_button.click()
        page.search_input.setText("수납")
        page.history_table.cellClicked.emit(0, 5)
        page.history_table.cellClicked.emit(1, 5)
        assert exported == [True]
        assert filters[-1]["query"] == "수납"
        assert retried == ["record-retry"]
        assert opened == ["record-open"]
        _assert_no_horizontal_scroll(page)
    finally:
        _close_pages(app, [page])


def test_accounts_master_detail_signals_and_compact_drill_in():
    app = _app()
    page = AccountsPage()
    selected = []
    added = []
    removed = []
    managed = []
    page.account_selected.connect(selected.append)
    page.add_account_requested.connect(lambda: added.append(True))
    page.remove_account_requested.connect(removed.append)
    page.manage_subscription_requested.connect(lambda: managed.append(True))
    page.render_accounts(
        accounts=[
            {
                "id": "account-7",
                "display_name": "daily.note",
                "username": "@daily.note",
                "status": "연결 정상",
                "last_checked": "3분 전",
                "session_status": "안전하게 저장됨",
                "next_check": "앱 시작 시",
            }
        ],
        limit=10,
        plan_name="쇼핑 프로 월간",
    )
    page.resize(760, 560)
    page.show()
    app.processEvents()
    try:
        assert page.account_list.count() == 1
        assert page.master_card.isVisible()
        assert not page.detail_card.isVisible()
        page.account_list.setCurrentRow(0)
        app.processEvents()
        assert selected == ["account-7"]
        assert not page.master_card.isVisible()
        assert page.detail_card.isVisible()
        assert page.detail_values["username"].text() == "@daily.note"
        page.remove_button.click()
        page.add_account_button.click()
        page.plan_button.click()
        assert removed == ["account-7"]
        assert added == [True]
        assert managed == [True]
        page.back_button.click()
        app.processEvents()
        assert page.master_card.isVisible()
        assert not page.detail_card.isVisible()
        _assert_no_horizontal_scroll(page)
    finally:
        _close_pages(app, [page])


def test_subscription_renders_injected_plan_data_and_emits_intents():
    app = _app()
    page = SubscriptionPage()
    managed = []
    supported = []
    selected = []
    page.manage_subscription_requested.connect(lambda: managed.append(True))
    page.support_requested.connect(lambda: supported.append(True))
    page.plan_selected.connect(selected.append)
    page.render_subscription(
        subscription={
            "plan_name": "쇼핑 프로 월간",
            "detail": "8개 쇼핑 채널 · Threads 계정 최대 10개",
            "usage_label": "18 / 50회 남음",
            "renewal_date": "9월 1일",
            "payment_method": "PayApp",
            "support_response_time": "평일 평균 응답 2시간 이내",
        },
        plans=[
            {
                "id": "basic",
                "name": "쿠팡 기본",
                "price": "월 49,000원",
                "features": ["쿠팡 링크 자동 분석", "AI 문구 생성 포함"],
            },
            {
                "id": "shopping-pro",
                "name": "쇼핑 프로",
                "price": "월 69,000원",
                "current": True,
                "features": ["8개 쇼핑 채널", "Threads 계정 최대 10개"],
            },
        ],
    )
    page.resize(900, 620)
    page.show()
    app.processEvents()
    try:
        assert page.current_plan_name.text() == "쇼핑 프로 월간"
        assert page.usage_value.text() == "18 / 50회 남음"
        page.manage_button.click()
        page.support_button.click()
        plan_button = page.findChild(QPushButton, "subscriptionPlanAction0")
        assert plan_button is not None and plan_button.isEnabled()
        plan_button.click()
        assert managed == [True]
        assert supported == [True]
        assert selected == ["basic"]
        _assert_no_horizontal_scroll(page)
    finally:
        _close_pages(app, [page])
