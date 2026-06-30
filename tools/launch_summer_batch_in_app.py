"""Launch the PyQt app with the prepared 50-item summer queue already running."""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")
os.environ.setdefault("THREAD_AUTO_LOGIN_WAIT_SECONDS", str(24 * 60 * 60))
os.environ.setdefault("THREAD_AUTO_DISABLE_ACTIVITY_LOGS", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
os.environ.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")
os.environ.setdefault("THREAD_AUTO_FORCE_SINGLE_POST", "1")
os.environ.setdefault("THREAD_AUTO_STDERR_PRINTS_INFO", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as app_main  # noqa: E402
from src.app_logging import setup_logging  # noqa: E402
from src.config import config  # noqa: E402
from src.hidpi import center_window, configure_high_dpi  # noqa: E402
from src.main_window import MainWindow  # noqa: E402
from src.services.post_concepts import CONCEPT_TODAY_ISSUE  # noqa: E402
from src.theme import Colors, Typography, resolve_fonts  # noqa: E402

logger = logging.getLogger(__name__)
QUEUE_PATH = Path.home() / ".shorts_thread_maker" / "summer_coupang_thread_queue_20260622.json"
RESUME_PATH = Path.home() / ".shorts_thread_maker" / "upload_resume_queue.json"
INTERVAL_SECONDS = 4 * 60 * 60


def _load_pending_items() -> list[tuple[str, str]]:
    payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    seen: set[str] = set()
    items: list[tuple[str, str]] = []
    for raw_item in payload.get("items", []):
        if str(raw_item.get("status") or "").strip().lower() != "pending":
            continue
        url = str(raw_item.get("url") or "").strip()
        if not url or url in seen:
            continue
        title = str(raw_item.get("title") or raw_item.get("keyword") or "여름 추천 상품").strip()
        seen.add(url)
        items.append((url, title))
    return items


def _load_resume_items() -> tuple[list[tuple[str, str]], int, float | None]:
    if not RESUME_PATH.exists():
        return [], INTERVAL_SECONDS, None

    try:
        payload = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("저장된 업로드 대기열을 읽지 못했습니다.")
        return [], INTERVAL_SECONDS, None

    pending: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_item in payload.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        status = str(raw_item.get("status") or "").strip().lower()
        if status not in {"pending", "running"}:
            continue
        url = str(raw_item.get("url") or "").strip()
        if not url or url in seen:
            continue
        title = str(
            raw_item.get("keyword")
            or raw_item.get("title")
            or raw_item.get("product_title")
            or "여름 추천 상품"
        ).strip()
        pending.append((url, title))
        seen.add(url)

    try:
        interval = max(int(payload.get("interval") or INTERVAL_SECONDS), 30)
    except (TypeError, ValueError):
        interval = INTERVAL_SECONDS

    try:
        next_allowed_at = float(payload.get("next_allowed_at")) if payload.get("next_allowed_at") else None
    except (TypeError, ValueError):
        next_allowed_at = None

    return pending, interval, next_allowed_at


def _clear_queue(window: MainWindow) -> None:
    while True:
        try:
            window.link_queue.get_nowait()
        except queue.Empty:
            break


def _start_prepared_batch(window: MainWindow) -> None:
    config.load()
    config.upload_interval = INTERVAL_SECONDS
    config.post_concept = CONCEPT_TODAY_ISSUE
    config.save()
    window._load_settings()

    resume_items, resume_interval, resume_next_allowed_at = _load_resume_items()
    if resume_items:
        link_data = resume_items
        interval = resume_interval
        next_allowed_at = resume_next_allowed_at
        source = "summer_batch_resume_launcher"
        window.signals.log.emit(f"저장된 여름 상품 대기열 {len(link_data)}개를 이어서 시작합니다.")
    else:
        link_data = _load_pending_items()
        interval = INTERVAL_SECONDS
        next_allowed_at = None
        source = "summer_batch_launcher"
        if len(link_data) != 50:
            window.signals.log.emit(f"준비된 여름 상품 대기열이 50개가 아닙니다: {len(link_data)}개")
            return

    window._switch_page(0)
    try:
        window._sidebar_buttons[0].setChecked(True)
    except Exception:
        pass
    if window.start_link_data_batch(
        link_data,
        interval=interval,
        source=source,
        next_allowed_at=next_allowed_at,
    ):
        window.signals.log.emit(f"여름 상품 {len(link_data)}개 대기열 시작됨 - 업로드 간격 {interval}초")
        window._log_user_activity(
            "summer_batch_launcher_started",
            f"links={len(link_data)}; interval={interval}; source={source}",
        )
    return

    interval = max(config.upload_interval, 30)
    urls_only = "\n".join(url for url, _title in link_data)
    window.links_text.setPlainText(urls_only)
    window._switch_page(0)
    try:
        window._sidebar_buttons[0].setChecked(True)
    except Exception:
        pass

    window.is_running = True
    window.start_btn.setEnabled(False)
    window.add_btn.setEnabled(True)
    window.stop_btn.setEnabled(True)
    window.status_badge.update_style(Colors.WARNING, "실행중")
    window._sidebar_status_label.setText("실행중")
    window._sidebar_success_label.setText("성공: 0")
    window._sidebar_failed_label.setText("실패: 0")
    window._sidebar_total_label.setText("전체: 0")
    window._progress_queue_label.setText(f"전체: 0 / {len(link_data)}")
    window._reset_steps()
    window._populate_link_table(link_data)

    with window._urls_lock:
        window.processed_urls.clear()
        _clear_queue(window)
        for item in link_data:
            window.link_queue.put(item)
            window.processed_urls.add(item[0])

    api_key = window._resolve_runtime_gemini_api_key(validate=False)
    ig_username = config.instagram_username
    if ig_username:
        profile_name = window._sanitize_profile_name(ig_username)
        profile_dir = f".threads_profile_{profile_name}"
    else:
        profile_dir = ".threads_profile"

    worker_config = {
        "api_key": api_key,
        "profile_dir": profile_dir,
    }
    window._active_pipeline = window.pipeline
    worker = threading.Thread(
        target=window._run_upload_queue,
        args=(interval, worker_config, window._active_pipeline),
        daemon=True,
        name="summer-batch-app-worker",
    )
    worker.start()
    window.signals.log.emit(f"여름 상품 50개 대기열 시작됨 - 업로드 간격 {interval}초")
    window._log_user_activity(
        "summer_batch_launcher_started",
        f"links={len(link_data)}; interval={interval}; profile_dir={profile_dir}",
    )


def _show_settings_for_verification(window: MainWindow) -> None:
    try:
        config.load()
        window._load_settings()
        window._switch_page(2, source="summer_batch_show_settings")
        window.raise_()
        window.activateWindow()
        logger.info("Settings page opened for visible concept verification.")
    except Exception:
        logger.exception("Failed to open settings page for verification.")


def _configure_app() -> QApplication:
    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app_main._apply_app_icon(app)
    app_main._init_qt_app_font(app)
    resolve_fonts()
    base_font = QFont(Typography.FAMILY, 12)
    base_font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(base_font)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    return app


def main() -> int:
    log_file = setup_logging(capture_print=True)
    logger.info("Summer batch app launcher started; log_file=%s", log_file)

    app = _configure_app()
    auth_result = app_main._build_developer_auth_result()
    app_main._inject_developer_auth_state(auth_result)

    window = MainWindow()
    window._auth_data = auth_result
    window._login_ref = None
    if hasattr(window, "_update_account_display"):
        window._update_account_display()
    window.setWindowTitle("Coupang Partners Thread Automation - Summer 50 Running")
    center_window(window)
    window.show()
    app._main_window = window

    QTimer.singleShot(1500, lambda: _start_prepared_batch(window))
    QTimer.singleShot(6500, lambda: _show_settings_for_verification(window))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
