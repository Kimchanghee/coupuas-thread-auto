import os
from itertools import pairwise

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src import auth_client
from src.hidpi import configure_high_dpi, recommended_window_size
from src.login_window import LoginWindow
from src.main_window import (
    LINK_TABLE_CHANNEL_COLUMN,
    LINK_TABLE_STATUS_COLUMN,
    MainWindow,
)


def test_high_dpi_uses_native_qt_scaling_without_forced_shrink(monkeypatch):
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)
    configure_high_dpi()
    assert "QT_SCALE_FACTOR" not in os.environ
    assert recommended_window_size(1920, 1080) == (1360, 900)
    assert recommended_window_size(1024, 768) == (960, 676)


def test_main_window_reflows_at_compact_and_wide_sizes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()

    for width, height in ((760, 560), (900, 620), (1360, 900)):
        window.resize(width, height)
        app.processEvents()

        central = window.centralWidget()
        page = window._pages[0]
        settings_page = window._pages[1]
        assert window._header.geometry().bottom() < window._page_stack.y()
        assert window._sidebar.geometry().right() < window._page_stack.x()
        assert window._page_stack.geometry().bottom() < window._status_bar_frame.y()
        assert window._page_stack.geometry().right() < central.width()
        assert window._status_bar_frame.geometry().right() < central.width()
        assert page.geometry().right() < central.width()
        assert settings_page.geometry().right() < central.width()
        assert window.links_text.geometry().right() < page.width()
        assert window.link_table.geometry().right() < page.width()
        assert window.link_table.height() >= 42
        assert (
            window._link_scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert window._link_scroll.horizontalScrollBar().maximum() == 0
        compact_table = window._page_stack.width() < 900
        assert window.link_table.isColumnHidden(2) is compact_table
        assert window.link_table.isColumnHidden(4) is compact_table
        assert window._settings_tab_bar.geometry().right() < settings_page.width()
        assert window._settings_scroll.geometry().right() < settings_page.width()
        assert window._settings_footer.geometry().right() < settings_page.width()
        assert window._settings_scroll.geometry().bottom() < window._settings_footer.y()
        assert window._settings_save_btn.parentWidget() is window._settings_footer
        assert window._settings_footer.rect().contains(
            window._settings_save_btn.geometry()
        )

        window._switch_page(1)
        window._settings_tab_bar.setCurrentIndex(0)
        app.processEvents()
        assert (
            window._settings_automation_sec.geometry().right()
            < window._settings_content.width()
        )
        assert (
            window.settings_post_concept_combo.geometry().right()
            < window._settings_automation_sec.width()
        )

    window.toggle_inline_help(True)
    app.processEvents()
    assert window._settings_help_panel.isVisible()
    assert window._settings_scroll.y() > window._settings_tab_bar.geometry().bottom()

    window.close()
    window.deleteLater()
    app.processEvents()


def test_link_input_immediately_lists_channel_colors_and_exclusions():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.links_text.setPlainText(
            "https://link.coupang.com/a/example\n"
            "https://naver.me/example\n"
            "https://toss.im/_m/example\n"
            "https://ozip.me/example?af\n"
            "https://www.musinsa.com/curator/goods/example\n"
            "https://lounge.kurly.com/link/example\n"
            "https://oy.run/example\n"
            "https://www.aliexpress.com/item/123.html\n"
            "https://link.coupang.com/a/example\n"
            "https://example.com/item/1\n"
            "http://smartstore.naver.com/main/products/123"
        )
        app.processEvents()

        assert window.link_count_badge.text() == "사용 8개"
        assert window.link_table.columnCount() == 5
        assert window.link_table.rowCount() == 11
        assert window._link_table_label.text() == "입력 링크 미리보기"
        expected_channels = [
            "쿠팡",
            "네이버",
            "토스",
            "오늘집",
            "무신사",
            "컬리",
            "올영",
            "Ali",
        ]
        channel_colors = set()
        for row, expected_channel in enumerate(expected_channels):
            channel_item = window.link_table.item(row, LINK_TABLE_CHANNEL_COLUMN)
            assert expected_channel in channel_item.text()
            channel_colors.add(channel_item.foreground().color().name())
        assert len(channel_colors) == len(expected_channels)
        assert window.link_table.item(8, LINK_TABLE_STATUS_COLUMN).text() == "중복 제외"
        assert "미지원" in window.link_table.item(9, LINK_TABLE_CHANNEL_COLUMN).text()
        assert "오류" in window.link_table.item(10, LINK_TABLE_CHANNEL_COLUMN).text()
        assert "사용 가능 8" in window._links_hint.accessibleDescription()
        assert "중복 1" in window._links_hint.accessibleDescription()
        assert "미지원 1" in window._links_hint.accessibleDescription()
        assert "오류 1" in window._links_hint.accessibleDescription()
    finally:
        window._closed = True
        window.close()
        window.deleteLater()
        app.processEvents()


def test_header_update_button_expands_for_version_text():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(900, 620)
    window.show()
    window.update_btn.setText("업데이트 3.0.62")
    window.update_btn.setVisible(True)
    window._relayout_header_account_card()
    app.processEvents()

    assert window.update_btn.width() >= window.update_btn.sizeHint().width()
    assert window.update_btn.geometry().right() < window.centralWidget().width()

    window.close()
    window.deleteLater()
    app.processEvents()


def test_header_username_is_elided_with_full_value_in_tooltip():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    full_username = "very_long_account_identifier_that_must_remain_readable"
    window._auth_data = {"username": full_username}
    window._update_account_display()
    app.processEvents()

    visible_text = window._header_username_label.text()
    assert window._header_username_label.toolTip() == full_username
    assert visible_text == full_username or "…" in visible_text
    assert (
        window._header_username_label.fontMetrics().horizontalAdvance(visible_text)
        <= window._header_username_label.width()
    )

    window.close()
    window.deleteLater()
    app.processEvents()


def test_header_controls_never_overlap_when_update_is_available():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    window.update_btn.setText("업데이트 3.0.62")
    window.update_btn.setVisible(True)
    window._header_username_full_text = (
        "very_long_account_identifier_that_must_remain_readable"
    )

    for width in (900, 1110, 1280, 1360):
        window.resize(width, 800)
        window._relayout_header_account_card()
        app.processEvents()
        controls = [
            window._work_label,
            window._header_username_label,
            window._online_dot,
            window._connection_label,
            window._plan_badge,
            window.update_btn,
            window.tutorial_btn,
            window.logout_btn,
        ]
        visible_controls = sorted(
            (item for item in controls if item.isVisible()), key=lambda item: item.x()
        )
        for left, right in pairwise(visible_controls):
            assert left.geometry().right() < right.x(), (
                width,
                left.objectName() or left.text(),
                right.objectName() or right.text(),
            )

    window.close()
    window.deleteLater()
    app.processEvents()


def test_login_window_collapses_brand_without_scrolling_on_small_work_area(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", dict)
    window = LoginWindow()
    assert window.windowTitle() == "스레드 쇼핑 자동화 - 로그인"
    window.show()
    window.resize(600, 600)
    app.processEvents()

    assert not window.left_panel.isVisible()
    assert window.right_panel.width() == 420
    assert window.right_panel.x() == 90
    assert window._form_scroll.verticalScrollBar().maximum() == 0

    window.resize(720, 760)
    app.processEvents()
    assert window.left_panel.isVisible()
    assert window.right_panel.x() == 300
    assert window._form_scroll.verticalScrollBar().maximum() == 0

    window.close()
    window.deleteLater()
    app.processEvents()
