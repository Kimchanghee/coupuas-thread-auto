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
