import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.update_dialog import UpdateDialog


def test_update_dialog_is_responsive_and_uses_readable_korean_copy():
    app = QApplication.instance() or QApplication([])
    dialog = UpdateDialog(
        "3.0.66",
        update_info={
            "version": "3.0.66",
            "size_mb": 112.4,
            "changelog": "세션 안정성과 업데이트 화면을 개선했습니다.",
        },
    )
    dialog.show()
    app.processEvents()

    assert dialog.minimumWidth() >= 560
    assert dialog.maximumWidth() > dialog.minimumWidth()
    assert dialog.windowTitle() == "Thread Auto 업데이트"
    assert "3.0.66" in dialog.status_label.text()
    assert dialog.install_btn.minimumHeight() >= 46
    assert dialog.changelog_text.font().family() != "Consolas"
    assert dialog.font().family() == app.font().family()
    assert dialog.changelog_text.font().family() == app.font().family()
    assert dialog.status_label.font().family() == app.font().family()

    for width, height in ((560, 520), (720, 620)):
        dialog.resize(width, height)
        app.processEvents()
        assert dialog.install_btn.geometry().right() < dialog.width()
        assert dialog.install_btn.geometry().bottom() < dialog.height()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_update_dialog_emits_install_request_and_shows_progress():
    app = QApplication.instance() or QApplication([])
    update_info = {
        "version": "3.0.66",
        "size_mb": 112.4,
        "changelog": "업데이트 흐름 개선",
    }
    dialog = UpdateDialog("3.0.66", update_info=update_info)
    requested = []
    dialog.install_requested.connect(requested.append)
    dialog.show()

    dialog.install_btn.click()
    dialog.set_download_progress(43.2)
    app.processEvents()

    assert requested and requested[0]["version"] == "3.0.66"
    assert dialog.progress_bar.isVisible()
    assert dialog.progress_bar.value() == 43
    assert "43%" in dialog.progress_label.text()

    dialog.set_install_error("네트워크 연결을 확인해 주세요.")
    assert dialog.install_btn.isEnabled()
    assert "네트워크" in dialog.status_detail.text()

    dialog.set_install_error("RuntimeError: provider unavailable")
    assert "RuntimeError" not in dialog.status_detail.text()
    assert "provider unavailable" not in dialog.status_detail.text()
    assert "업데이트" in dialog.status_detail.text()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_update_dialog_offers_safe_manual_download_after_install_error(monkeypatch):
    app = QApplication.instance() or QApplication([])
    download_url = (
        "https://github.com/Kimchanghee/coupuas-thread-auto/releases/"
        "download/v3.0.74/CoupangThreadAutoSetup.exe"
    )
    opened_urls = []
    monkeypatch.setattr(
        "src.update_dialog.QDesktopServices.openUrl",
        lambda url: opened_urls.append(url.toString()) or True,
    )

    dialog = UpdateDialog(
        "3.0.73",
        update_info={
            "version": "3.0.74",
            "size_mb": 101.3,
            "changelog": "업데이트 안정성을 개선했습니다.",
            "download_url": download_url,
        },
    )
    dialog.show()
    app.processEvents()

    assert dialog.manual_download_btn.isHidden()

    dialog.set_install_error("자동 업데이트를 완료하지 못했습니다.")
    app.processEvents()
    assert dialog.manual_download_btn.isVisible()

    dialog.manual_download_btn.click()
    assert opened_urls == [download_url]

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
