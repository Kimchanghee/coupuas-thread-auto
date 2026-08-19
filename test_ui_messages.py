import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from src import ui_messages


def test_closed_alert_is_detached_from_parent():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()

    def close_modal():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, ui_messages.ThemedAlertDialog)
        dialog.accept()

    QTimer.singleShot(0, close_modal)
    ui_messages.show_error(parent, "업데이트 실패", "검증에 실패했습니다.")
    app.processEvents()

    assert parent.findChildren(ui_messages.ThemedAlertDialog) == []


def test_empty_alert_title_uses_readable_korean_fallback():
    app = QApplication.instance() or QApplication([])
    dialog = ui_messages.ThemedAlertDialog(
        None,
        title="",
        message="안내 내용",
        kind="info",
    )

    assert dialog.windowTitle() == "알림"
    dialog.deleteLater()
    app.processEvents()


def test_developer_exception_is_not_returned_as_user_copy():
    fallback = "작업을 완료하지 못했습니다. 잠시 후 다시 시도해주세요."

    assert (
        ui_messages.user_friendly_message(
            "RuntimeError: provider unavailable at C:\\app\\worker.py line 42",
            fallback,
        )
        == fallback
    )
    assert (
        ui_messages.user_friendly_message("네트워크 연결을 확인해주세요.", fallback)
        == "네트워크 연결을 확인해주세요."
    )


def test_mixed_korean_and_developer_details_use_safe_fallback():
    fallback = "게시 화면을 확인하지 못했습니다. 잠시 후 다시 시도해주세요."

    assert (
        ui_messages.user_friendly_message(
            "게시 실패: Locator.click strict mode violation at worker.py line 42",
            fallback,
        )
        == fallback
    )
    assert (
        ui_messages.user_friendly_message(
            "요소 확인 실패: net::ERR_CONNECTION_RESET",
            fallback,
        )
        == fallback
    )
    assert (
        ui_messages.user_friendly_message(
            "로그인 failed for user john",
            fallback,
        )
        == fallback
    )
    assert (
        ui_messages.user_friendly_message(
            "Threads 로그인 상태를 확인해주세요.",
            fallback,
        )
        == "Threads 로그인 상태를 확인해주세요."
    )
