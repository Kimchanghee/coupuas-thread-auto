import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")

from PyQt6.QtWidgets import QApplication

from src.hidpi import configure_high_dpi, recommended_window_size
from src import auth_client
from src.login_window import LoginWindow
from src.main_window import MainWindow


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

    for width, height in ((900, 620), (1280, 800), (1360, 900)):
        window.resize(width, height)
        app.processEvents()

        central = window.centralWidget()
        page = window._pages[0]
        settings_page = window._pages[1]
        assert page.geometry().right() < central.width()
        assert settings_page.geometry().right() < central.width()
        assert window.links_text.geometry().right() < page.width()
        assert window.link_table.geometry().right() < page.width()
        assert window.link_table.height() >= 42
        assert window._settings_tab_bar.geometry().right() < settings_page.width()
        assert window._settings_scroll.geometry().right() < settings_page.width()
        assert window._settings_save_btn.geometry().right() < settings_page.width()
        assert window._settings_scroll.geometry().bottom() < window._settings_save_btn.y()

        window._switch_page(1)
        window._settings_tab_bar.setCurrentIndex(0)
        app.processEvents()
        assert window._settings_automation_sec.geometry().right() < window._settings_content.width()
        assert window.settings_post_concept_combo.geometry().right() < window._settings_automation_sec.width()

    window.toggle_inline_help(True)
    app.processEvents()
    assert window._settings_help_panel.isVisible()
    assert window._settings_scroll.y() > window._settings_tab_bar.geometry().bottom()

    window.close()
    window.deleteLater()
    app.processEvents()


def test_login_window_collapses_brand_and_scrolls_on_small_work_area(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(auth_client, "get_saved_credentials", lambda: {})
    window = LoginWindow()
    window.show()
    window.resize(600, 600)
    app.processEvents()

    assert not window.left_panel.isVisible()
    assert window.right_panel.width() == 420
    assert window.right_panel.x() == 90
    assert window._form_scroll.verticalScrollBar().maximum() > 0

    window.resize(720, 760)
    app.processEvents()
    assert window.left_panel.isVisible()
    assert window.right_panel.x() == 300
    assert window._form_scroll.verticalScrollBar().maximum() == 0

    window.close()
    window.deleteLater()
    app.processEvents()
