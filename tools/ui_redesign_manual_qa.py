# ruff: noqa: I001
"""Visible, deterministic manual-QA harness for the Thread Auto redesign.

Run from the repository root::

    python tools/ui_redesign_manual_qa.py

The harness displays the real ``LoginWindow`` and ``MainWindow`` but replaces
network, authentication, upload, update, payment, persistence and browser
boundaries with local no-op implementations.  Product mutation controls are
disabled and a separate always-on-top control window drives view, breakpoint,
page and visual-state inspection.

``--smoke`` exercises every control path with Qt's offscreen platform and exits
without opening a visible window.  It is intended for CI/import verification,
not as a replacement for human Computer Use inspection.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any


if "--smoke" in sys.argv or "--capture-dir" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["THREAD_AUTO_DISABLE_HEARTBEAT"] = "1"
os.environ["THREAD_AUTO_DISABLE_AUTO_UPDATE"] = "1"
os.environ["THREAD_AUTO_DISABLE_RESUME_PROMPT"] = "1"
os.environ["THREAD_AUTO_DISABLE_ONBOARDING"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import requests

from src import auth_client
from src.hidpi import configure_high_dpi
from src.login_window import LoginWindow
from src.main_window import MainWindow
from src.onboarding_dialog import OnboardingDialog
from src.theme import Colors, Radius, Typography, global_stylesheet, resolve_fonts
from src.update_dialog import UpdateDialog
import src.main_window as main_window_module


QA_TITLE = "THREAD AUTO — OFFLINE UI REDESIGN QA"
BLOCKED_TOOLTIP = "OFFLINE UI QA에서는 실제 업무 동작이 차단됩니다."


MOCK_ACCOUNTS = [
    {
        "id": "qa-daily",
        "account_id": "qa-daily",
        "display_name": "Daily Living Note",
        "name": "Daily Living Note",
        "username": "@daily.living_note",
        "status": "정상 · 게시 준비됨",
        "status_kind": "healthy",
        "description": "생활용품 큐레이션용 QA 계정입니다.",
        "last_checked": "오늘 10:42",
        "session_status": "로그인 유지 중",
        "next_check": "오늘 14:42",
    },
    {
        "id": "qa-studio",
        "account_id": "qa-studio",
        "display_name": "Nordic Studio",
        "name": "Nordic Studio",
        "username": "@nordic.studio",
        "status": "재확인 필요",
        "status_kind": "warning",
        "description": "세션 주의 상태를 확인하기 위한 QA 계정입니다.",
        "last_checked": "어제 18:10",
        "session_status": "24시간 내 재로그인 권장",
        "next_check": "오늘 12:00",
    },
]

MOCK_HISTORY = [
    {
        "id": "qa-job-1042",
        "job_id": "qa-job-1042",
        "time": "오늘 10:42",
        "started_at": "오늘 10:42",
        "channel": "쿠팡",
        "product": "무선 미니 선풍기",
        "account": "@daily.living_note",
        "result": "게시 완료",
        "duration": "3분 18초",
        "status": "성공",
        "status_kind": "success",
        "action": "상세 보기",
    },
    {
        "id": "qa-job-0931",
        "job_id": "qa-job-0931",
        "time": "오늘 09:31",
        "started_at": "오늘 09:31",
        "channel": "네이버",
        "product": "폴더블 수납 박스",
        "account": "@nordic.studio",
        "result": "세션 만료",
        "duration": "1분 04초",
        "status": "확인 필요",
        "status_kind": "error",
        "action": "재시도",
    },
    {
        "id": "qa-job-0820",
        "job_id": "qa-job-0820",
        "time": "어제 18:20",
        "started_at": "어제 18:20",
        "channel": "AliExpress",
        "product": "데스크 케이블 정리함",
        "account": "@daily.living_note",
        "result": "게시 완료",
        "duration": "4분 11초",
        "status": "성공",
        "status_kind": "success",
        "action": "상세 보기",
    },
]

MOCK_METRICS = [
    {"label": "오늘 게시", "value": "12", "detail": "어제보다 3건 증가", "kind": "success"},
    {"label": "성공률", "value": "96.2%", "detail": "최근 30일", "kind": "success"},
    {"label": "대기열", "value": "3", "detail": "예상 17분", "kind": "warning"},
    {"label": "연결 계정", "value": "2 / 10", "detail": "1개 재확인 필요", "kind": "warning"},
]

MOCK_PLANS = [
    {
        "id": "basic",
        "name": "베이직",
        "tagline": "한 계정으로 가볍게 시작",
        "price": "월 49,000원",
        "features": ["Threads 계정 1개", "기본 쇼핑 채널", "작업 기록"],
        "action_label": "요금제 선택",
    },
    {
        "id": "shopping-pro",
        "name": "쇼핑 프로",
        "tagline": "멀티 채널 운영을 위한 현재 요금제",
        "price": "월 69,000원",
        "features": ["Threads 계정 10개", "전체 제휴 채널", "우선 지원"],
        "current": True,
        "action_label": "현재 이용 중",
    },
]


class OfflineActionBlocked(RuntimeError):
    """Raised if an unmocked network boundary is reached in the QA harness."""


class OfflinePipeline:
    """Constructor-compatible pipeline that never reads a key or performs I/O."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __getattr__(self, name: str):
        def blocked(*_args, **_kwargs):
            raise OfflineActionBlocked(f"pipeline action blocked in offline QA: {name}")

        return blocked


class OfflineBoundaries:
    """Small reversible patch set limited to external/service boundaries."""

    def __init__(self) -> None:
        self._originals: list[tuple[object, str, Any]] = []
        self._installed = False

    def _replace(self, owner: object, name: str, value: Any) -> None:
        if not hasattr(owner, name):
            return
        self._originals.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    @staticmethod
    def _auth_state() -> dict[str, Any]:
        return {
            "status": True,
            "id": "offline-qa-user",
            "user_id": "offline-qa-user",
            "username": "qa.editor",
            "plan": "쇼핑 프로",
            "plan_name": "쇼핑 프로",
            "work_count": 17,
            "remaining_work": 17,
            "token": "offline-qa-placeholder",
        }

    @staticmethod
    def _blocked_request(*_args, **_kwargs):
        raise OfflineActionBlocked("HTTP request blocked by offline UI QA harness")

    def install(self) -> None:
        if self._installed:
            return
        self._installed = True

        auth_state = self._auth_state
        self._replace(auth_client, "get_saved_credentials", lambda: None)
        self._replace(auth_client, "remember_login_credentials", lambda *_a, **_k: True)
        self._replace(auth_client, "remember_username", lambda *_a, **_k: None)
        self._replace(auth_client, "get_auth_state", auth_state)
        self._replace(auth_client, "is_logged_in", lambda: True)
        self._replace(auth_client, "get_free_trial_work_count", lambda *_a, **_k: 17)
        self._replace(auth_client, "log_action", lambda *_a, **_k: None)
        self._replace(auth_client, "clear_local_session", lambda: None)
        self._replace(auth_client, "logout", lambda: True)
        self._replace(
            auth_client,
            "login",
            lambda username, _password, force=False: {
                **auth_state(),
                "username": str(username or "qa.editor"),
                "force": bool(force),
            },
        )
        self._replace(
            auth_client,
            "check_username",
            lambda username: {
                "available": True,
                "message": f"{username}은(는) QA에서 사용 가능합니다.",
            },
        )
        self._replace(
            auth_client,
            "register",
            lambda *_a, **_k: {
                "success": True,
                "data": {
                    "user_id": "offline-qa-user",
                    "username": "qa.editor",
                    "token": "offline-qa-placeholder",
                    "work_count": 17,
                },
            },
        )
        self._replace(
            auth_client,
            "heartbeat",
            lambda *_a, **_k: {"status": True, "message": "offline QA"},
        )
        self._replace(
            auth_client,
            "refresh_account_state",
            lambda *_a, **_k: {"status": True, **auth_state()},
        )
        self._replace(
            auth_client,
            "check_work_available",
            lambda: {"status": False, "message": BLOCKED_TOOLTIP},
        )
        for name in (
            "use_work",
            "reserve_work",
            "commit_reserved_work",
            "release_reserved_work",
            "create_payapp_checkout",
            "create_payapp_subscription",
            "get_payapp_subscriptions",
            "cancel_payapp_subscription",
            "get_subscription_status",
            "get_payment_status",
        ):
            self._replace(
                auth_client,
                name,
                lambda *_a, **_k: {"status": False, "success": False, "message": BLOCKED_TOOLTIP},
            )

        self._replace(requests.sessions.Session, "request", self._blocked_request)
        self._replace(webbrowser, "open", lambda *_a, **_k: False)
        self._replace(webbrowser, "open_new", lambda *_a, **_k: False)
        self._replace(webbrowser, "open_new_tab", lambda *_a, **_k: False)
        self._replace(main_window_module, "CoupangPartnersPipeline", OfflinePipeline)

    def restore(self) -> None:
        while self._originals:
            owner, name, value = self._originals.pop()
            setattr(owner, name, value)
        self._installed = False


class OfflineMainWindow(MainWindow):
    """Production MainWindow with lifecycle/service hooks made inert."""

    def _init_activity_logger(self) -> None:
        self._activity_logger = None
        self._activity_log_stop = None
        self._activity_log_thread = None

    def _log_user_activity(self, *_args, **_kwargs) -> None:
        return None

    def _load_settings(self) -> None:
        """Do not read API keys, browser profiles or other local secrets."""

    def _init_multi_account_runtime(self) -> None:
        self._multi_account_runtime = None

    def _save_resume_state(self, *_args, **_kwargs) -> None:
        return None

    def _resume_after_completed_update(self) -> None:
        return None

    def _prompt_resume_queue_if_needed(self) -> None:
        return None

    def _check_for_updates_silent(self) -> None:
        return None

    def _send_heartbeat(self) -> None:
        if hasattr(self, "_apply_heartbeat_result"):
            self._apply_heartbeat_result({"state": "disabled"})

    def _open_external_link(self, _url: str, _context: str) -> bool:
        if hasattr(self, "status_label"):
            self.status_label.setText("외부 링크 차단 · OFFLINE QA")
        return False

    def _do_logout(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText("로그아웃 차단 · OFFLINE QA")

    def check_for_updates(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText("업데이트 차단 · OFFLINE QA")

    def _refresh_auxiliary_pages(self) -> None:
        if not all(
            hasattr(self, name)
            for name in ("dashboard_page", "history_page", "accounts_page", "subscription_page")
        ):
            return
        self.dashboard_page.render_dashboard(
            metrics=MOCK_METRICS,
            accounts=MOCK_ACCOUNTS,
            recent_jobs=MOCK_HISTORY,
        )
        self.history_page.set_filter_options(
            periods=["최근 7일", "최근 30일", "전체"],
            accounts=["전체 계정", "@daily.living_note", "@nordic.studio"],
            statuses=["전체 상태", "성공", "확인 필요"],
        )
        self.history_page.render_history(rows=MOCK_HISTORY, metrics=MOCK_METRICS)
        self.accounts_page.render_accounts(
            accounts=MOCK_ACCOUNTS,
            selected_id="qa-daily",
            limit=10,
            plan_name="쇼핑 프로",
        )
        self.subscription_page.render_subscription(
            subscription={
                "plan_name": "쇼핑 프로",
                "description": "전체 제휴 채널과 Threads 계정 10개를 운영합니다.",
                "usage_label": "17회 남음",
                "renewal_date": "2026-09-25",
                "billing_date": "2026-09-25",
                "payment_method": "QA 전용 표시 데이터",
                "support_response_time": "평일 평균 2시간 이내",
            },
            plans=MOCK_PLANS,
        )

    def closeEvent(self, event) -> None:
        self._closed = True
        for name in ("_heartbeat_timer", "_update_timer"):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.stop()
        pipeline = getattr(self, "_active_pipeline", None) or getattr(self, "pipeline", None)
        if pipeline is not None:
            pipeline.cancel()
        event.accept()


class ManualQaController(QMainWindow):
    """Always-on-top local controls for deterministic visual verification."""

    PAGE_SPECS = (
        (2, "Alt+1", "운영 홈"),
        (0, "Alt+2", "자동화"),
        (3, "Alt+3", "작업 기록"),
        (4, "Alt+4", "Threads 계정"),
        (1, "Alt+5", "설정"),
        (5, "Alt+6", "구독 · 지원"),
    )
    SIZE_SPECS = (
        (1360, 900, "Wide 1360 × 900", "Ctrl+1"),
        (900, 620, "Standard 900 × 620", "Ctrl+2"),
        (760, 560, "Minimum 760 × 560", "Ctrl+3"),
    )
    AUTH_SIZE_SPECS = (
        (720, 760, "기본 720 × 760", "Ctrl+7"),
        (420, 560, "최소 420 × 560", "Ctrl+8"),
    )
    STATE_SPECS = (
        ("validated", "검증 완료", "Ctrl+Shift+V"),
        ("running", "실행 중", "Ctrl+Shift+R"),
        ("paused", "일시정지", "Ctrl+Shift+P"),
        ("offline", "오프라인", "Ctrl+Shift+O"),
        ("session_expired", "세션 만료", "Ctrl+Shift+E"),
        ("finished", "완료", "Ctrl+Shift+F"),
    )

    def __init__(self, app: QApplication, boundaries: OfflineBoundaries) -> None:
        super().__init__()
        self.app = app
        self.boundaries = boundaries
        self._shutting_down = False
        self._shortcuts: list[QShortcut] = []
        self._active_view = "login"
        self._active_size = "720 × 760"
        self._active_page = "—"
        self._active_state = "—"

        self.setWindowTitle(f"{QA_TITLE} — CONTROL")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(388, 850)
        self.setMinimumSize(360, 620)
        self._build_ui()

        self.login_window = LoginWindow()
        self.login_window.setWindowTitle(f"{QA_TITLE} — LOGIN / REGISTER")
        self.login_window.login_success.connect(self._on_local_login)
        self._seed_auth_fields()

        self.main_window = OfflineMainWindow()
        self.main_window.setWindowTitle(f"{QA_TITLE} — MAIN")
        self.main_window._auth_data = OfflineBoundaries._auth_state()
        self.main_window._login_ref = self.login_window
        self._seed_main_window()
        self._lock_mutating_controls()
        for button in getattr(self.main_window, "_sidebar_buttons", []):
            button.setShortcut(QKeySequence())

        self._bind_shortcuts()
        self.show_login()
        self._place_controller()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("qaControlRoot")
        root.setStyleSheet(
            f"QWidget#qaControlRoot {{ background-color: {Colors.INK}; }}"
            f"QLabel {{ color: {Colors.TEXT_ON_INK}; }}"
            f"QLabel[qaRole='muted'] {{ color: {Colors.TEXT_ON_INK_MUTED}; }}"
            f"QFrame[qaRole='section'] {{ background-color: #172832;"
            f" border: 1px solid #2A414C; border-radius: {Radius.CARD}; }}"
            f"QPushButton {{ background-color: {Colors.PAPER}; color: {Colors.INK};"
            f" border: 1px solid {Colors.LINE}; border-radius: {Radius.INPUT};"
            " min-height: 38px; padding: 0 10px; font-weight: 650; text-align: left; }"
            f"QPushButton:hover, QPushButton:focus {{ background-color: {Colors.SKY};"
            f" border: 2px solid {Colors.SIGNAL_TEAL}; }}"
            f"QPushButton[qaRole='danger'] {{ color: {Colors.CORAL}; }}"
        )
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        title = QLabel("OFFLINE UI QA CONTROL")
        title.setStyleSheet("font-size: 15pt; font-weight: 800;")
        subtitle = QLabel(
            "실제 화면 + 로컬 목 데이터\n네트워크 · 업로드 · 결제 · 저장은 차단됨"
        )
        subtitle.setProperty("qaRole", "muted")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            f"background-color: {Colors.SKY}; color: {Colors.INK};"
            f" border-radius: {Radius.INPUT}; padding: 10px; font-weight: 650;"
        )
        outer.addWidget(self.summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        self.controls_layout = QVBoxLayout(panel)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)
        scroll.setWidget(panel)
        outer.addWidget(scroll, 1)

        view_section, view_grid = self._section("1. 화면", "Ctrl+L / Ctrl+R / Ctrl+M")
        self._add_control_button(view_grid, 0, 0, "로그인  Ctrl+L", self.show_login)
        self._add_control_button(view_grid, 0, 1, "회원가입  Ctrl+R", self.show_register)
        self._add_control_button(view_grid, 1, 0, "메인  Ctrl+M", self.show_main, 1, 2)
        self.controls_layout.addWidget(view_section)

        auth_section, auth_grid = self._section("2. 인증 화면 크기", "Ctrl+7 / Ctrl+8")
        for column, (width, height, label, shortcut) in enumerate(self.AUTH_SIZE_SPECS):
            self._add_control_button(
                auth_grid,
                0,
                column,
                f"{label}  {shortcut}",
                lambda _checked=False, w=width, h=height: self.resize_auth(w, h),
            )
        self.controls_layout.addWidget(auth_section)

        size_section, size_grid = self._section("3. 메인 기준 크기", "Ctrl+1 / 2 / 3")
        for row, (width, height, label, _shortcut) in enumerate(self.SIZE_SPECS):
            self._add_control_button(
                size_grid,
                row,
                0,
                label,
                lambda _checked=False, w=width, h=height: self.resize_main(w, h),
                1,
                2,
            )
        self.controls_layout.addWidget(size_section)

        page_section, page_grid = self._section("4. 메인 6페이지", "Alt+1 … Alt+6")
        for index, (page, shortcut, label) in enumerate(self.PAGE_SPECS):
            self._add_control_button(
                page_grid,
                index // 2,
                index % 2,
                f"{label}  {shortcut}",
                lambda _checked=False, p=page: self.show_page(p),
            )
        self.controls_layout.addWidget(page_section)

        state_section, state_grid = self._section("5. 자동화 시각 상태", "Ctrl+Shift+문자")
        for index, (state, label, shortcut) in enumerate(self.STATE_SPECS):
            self._add_control_button(
                state_grid,
                index // 2,
                index % 2,
                f"{label}  {shortcut.replace('Ctrl+Shift+', '⇧')}",
                lambda _checked=False, key=state: self.inject_state(key),
            )
        self.controls_layout.addWidget(state_section)

        self.controls_layout.addStretch(1)
        exit_button = QPushButton("QA 종료  Ctrl+Q")
        exit_button.setProperty("qaRole", "danger")
        exit_button.clicked.connect(self.shutdown)
        outer.addWidget(exit_button)
        self._update_summary()

    def _section(self, title: str, hint: str) -> tuple[QFrame, QGridLayout]:
        frame = QFrame()
        frame.setProperty("qaRole", "section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QLabel(f"{title}   ·   {hint}")
        header.setStyleSheet("font-weight: 750;")
        layout.addWidget(header)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return frame, grid

    @staticmethod
    def _add_control_button(
        layout: QGridLayout,
        row: int,
        column: int,
        text: str,
        callback: Callable[..., None],
        row_span: int = 1,
        column_span: int = 1,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(callback)
        layout.addWidget(button, row, column, row_span, column_span)
        return button

    def _bind(self, sequence: str, callback: Callable[[], None]) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _bind_shortcuts(self) -> None:
        self._bind("Ctrl+L", self.show_login)
        self._bind("Ctrl+R", self.show_register)
        self._bind("Ctrl+Shift+2", self.show_register_step_two)
        self._bind("Ctrl+M", self.show_main)
        self._bind("Ctrl+Q", self.shutdown)
        for width, height, _label, shortcut in self.SIZE_SPECS:
            self._bind(shortcut, lambda w=width, h=height: self.resize_main(w, h))
        for width, height, _label, shortcut in self.AUTH_SIZE_SPECS:
            self._bind(shortcut, lambda w=width, h=height: self.resize_auth(w, h))
        for page, shortcut, _label in self.PAGE_SPECS:
            self._bind(shortcut, lambda p=page: self.show_page(p))
        for state, _label, shortcut in self.STATE_SPECS:
            self._bind(shortcut, lambda key=state: self.inject_state(key))

    def _seed_auth_fields(self) -> None:
        self.login_window.login_id.setText("qa.editor")
        self.login_window.login_pw.setText("OfflineQa123!")
        self.login_window.remember_cb.setChecked(False)
        self.login_window.auto_login_cb.setChecked(False)
        self.login_window.login_status.setText(
            "OFFLINE UI QA · 로그인은 로컬 목 응답만 사용합니다."
        )
        for name, value in (
            ("reg_name", "QA 검수자"),
            ("reg_email", "qa@example.invalid"),
            ("reg_username", "qa_editor"),
            ("reg_pw", "OfflineQa123!"),
            ("reg_pw_confirm", "OfflineQa123!"),
            ("reg_contact", "01000000000"),
        ):
            widget = getattr(self.login_window, name, None)
            if widget is not None:
                widget.setText(value)

    def _seed_main_window(self) -> None:
        window = self.main_window
        window._header_username_full_text = "qa.editor"
        window._header_username_label.setText("qa.editor")
        window._connection_label.setText("로컬 QA")
        window._online_dot.setStyleSheet(
            f"background-color: {Colors.EMERALD}; border-radius: 4px;"
        )
        window._work_label.setText("17회 남음")
        window._plan_badge.setText("쇼핑 프로")
        window.username_edit.setText("@daily.living_note")
        window.hour_spin.setValue(4)
        window.min_spin.setValue(0)
        window.sec_spin.setValue(0)
        window._pay_phone_edit.clear()
        for row in getattr(window, "_gemini_key_rows", []):
            edit = row.get("edit") if isinstance(row, dict) else None
            if edit is not None:
                edit.clear()
        window._refresh_auxiliary_pages()
        self.inject_state("validated", bring_to_front=False)

    def _lock_mutating_controls(self) -> None:
        names = (
            "logout_btn",
            "update_btn",
            "start_btn",
            "start_all_btn",
            "add_btn",
            "stop_btn",
            "stop_all_btn",
            "_upload_save_btn",
            "threads_account_add_btn",
            "threads_account_remove_btn",
            "threads_login_btn",
            "check_login_btn",
            "_grok_install_btn",
            "_grok_login_btn",
            "_grok_check_btn",
            "_add_gemini_key_btn",
            "_pay_weekly_btn",
            "_pay_monthly_btn",
            "_pay_shopping_weekly_btn",
            "_pay_shopping_monthly_btn",
            "_pay_cancel_btn",
            "_pay_refresh_btn",
            "_settings_save_btn",
            "_contact_btn",
        )
        for name in names:
            widget = getattr(self.main_window, name, None)
            if widget is not None:
                widget.setEnabled(False)
                widget.setToolTip(BLOCKED_TOOLTIP)

        auxiliary_buttons = (
            getattr(self.main_window.history_page, "export_button", None),
            getattr(self.main_window.accounts_page, "add_account_button", None),
            getattr(self.main_window.accounts_page, "reconnect_button", None),
            getattr(self.main_window.accounts_page, "test_button", None),
            getattr(self.main_window.accounts_page, "remove_button", None),
            getattr(self.main_window.subscription_page, "manage_button", None),
            getattr(self.main_window.subscription_page, "support_button", None),
        )
        for widget in auxiliary_buttons:
            if widget is not None:
                widget.setEnabled(False)
                widget.setToolTip(BLOCKED_TOOLTIP)
        for widget in self.main_window.subscription_page.findChildren(QPushButton):
            widget.setEnabled(False)
            widget.setToolTip(BLOCKED_TOOLTIP)

    def _on_local_login(self, auth_result: dict[str, Any]) -> None:
        self.main_window._auth_data = dict(auth_result or OfflineBoundaries._auth_state())
        self.show_main()
        self._active_state = "로컬 로그인 완료"
        self._update_summary()

    def show_login(self) -> None:
        self.main_window.hide()
        self.login_window.stack.setCurrentIndex(0)
        self.login_window.resize(720, 760)
        self.login_window.show()
        self.login_window.raise_()
        self.login_window.activateWindow()
        self._active_view = "로그인"
        self._active_size = "720 × 760"
        self._active_page = "—"
        self._update_summary()

    def show_register(self) -> None:
        self.main_window.hide()
        if hasattr(self.login_window, "_show_register_step"):
            self.login_window._show_register_step(0)
        self.login_window.stack.setCurrentIndex(1)
        self.login_window.resize(720, 760)
        self.login_window.show()
        self.login_window.raise_()
        self.login_window.activateWindow()
        self._active_view = "회원가입"
        self._active_size = "720 × 760"
        self._active_page = "—"
        self._update_summary()

    def show_register_step_two(self) -> None:
        """Expose the second registration step to keyboard-only QA."""
        self.show_register()
        if hasattr(self.login_window, "_show_register_step"):
            self.login_window._show_register_step(1)

    def show_main(self) -> None:
        self.login_window.hide()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self._active_view = "메인"
        self._active_size = f"{self.main_window.width()} × {self.main_window.height()}"
        self._active_page = self.main_window._PAGE_LABELS.get(
            self.main_window._current_page, "—"
        )
        self._update_summary()

    def resize_auth(self, width: int, height: int) -> None:
        if self.login_window.stack.currentIndex() == 1:
            self.show_register()
        else:
            self.show_login()
        self.login_window.resize(width, height)
        self._active_size = f"{width} × {height}"
        self._update_summary()

    def resize_main(self, width: int, height: int) -> None:
        self.show_main()
        self.main_window.resize(width, height)
        QApplication.processEvents()
        self._active_size = f"{width} × {height}"
        self._update_summary()

    def show_page(self, page: int) -> None:
        self.show_main()
        self.main_window._switch_page(page, source="offline_manual_qa")
        self.main_window._refresh_auxiliary_pages()
        self._lock_mutating_controls()
        self._active_page = self.main_window._PAGE_LABELS.get(page, str(page))
        self._update_summary()

    def inject_state(self, key: str, *, bring_to_front: bool = True) -> None:
        if bring_to_front:
            self.show_page(0)
        window = self.main_window
        if not window.links_text.toPlainText().strip():
            window.links_text.setPlainText(
                "https://link.coupang.com/a/offline-qa\n"
                "https://naver.me/offline-qa\n"
                "https://www.aliexpress.com/item/1005000000000.html"
            )

        payloads = {
            "validated": {
                "phase": "idle",
                "message": "3개 링크 검증 완료 · 실행할 준비가 되었습니다.",
                "pending": 3,
                "total": 3,
                "completed": 0,
            },
            "running": {
                "phase": "processing",
                "message": "상품 정보를 바탕으로 게시물을 생성하고 있습니다.",
                "current_item": "무선 미니 선풍기",
                "pending": 2,
                "total": 3,
                "completed": 0,
            },
            "paused": {
                "phase": "paused",
                "message": "현재 위치를 저장했습니다. 이어서 실행할 수 있습니다.",
                "pending": 2,
                "total": 3,
                "completed": 1,
            },
            "offline": {
                "phase": "offline",
                "message": "연결이 복구되면 중단 지점부터 자동으로 이어갑니다.",
                "pending": 2,
                "total": 3,
                "completed": 1,
            },
            "session_expired": {
                "phase": "session_expired",
                "message": "Threads 로그인 세션이 만료되었습니다. 다시 연결해 주세요.",
                "current_item": "@nordic.studio",
                "pending": 2,
                "total": 3,
                "completed": 1,
            },
            "finished": {
                "phase": "finished",
                "message": "3개 링크의 자동화가 완료되었습니다.",
                "pending": 0,
                "total": 3,
                "completed": 2,
                "failed": 1,
            },
        }
        if key not in payloads:
            raise ValueError(f"unknown QA visual state: {key}")

        stage_by_state = {
            "validated": 1,
            "running": 1,
            "paused": 2,
            "offline": 2,
            "session_expired": 2,
        }
        stage = stage_by_state.get(key)
        if stage is not None:
            window._pipeline_rail.set_progress(stage)
        window._set_run_state(payloads[key])
        if key == "finished":
            window._set_results(2, 1)
        elif key == "validated":
            window._set_results(0, 0)
            window.status_badge.update_style(Colors.EMERALD, "검증 완료")
        if key in {"offline", "session_expired"}:
            color = Colors.AMBER if key == "offline" else Colors.CORAL
            label = "오프라인" if key == "offline" else "세션 만료"
            window._online_dot.setStyleSheet(
                f"background-color: {color}; border-radius: 4px;"
            )
            window._connection_label.setText(label)
            window._connection_label.setStyleSheet(
                f"color: {color}; font-size: 9pt; font-weight: 700; background: transparent;"
            )
        else:
            window._online_dot.setStyleSheet(
                f"background-color: {Colors.EMERALD}; border-radius: 4px;"
            )
            window._connection_label.setText("로컬 QA")
        window._append_log(f"[OFFLINE QA] {key} 시각 상태를 주입했습니다.")
        self._lock_mutating_controls()
        self._active_state = next(
            label for state, label, _shortcut in self.STATE_SPECS if state == key
        )
        self._active_page = "자동화"
        self._update_summary()

    def _update_summary(self) -> None:
        if not hasattr(self, "summary"):
            return
        self.summary.setText(
            f"화면  {self._active_view}\n"
            f"크기  {self._active_size}\n"
            f"페이지  {self._active_page}   ·   상태  {self._active_state}"
        )

    def _place_controller(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = max(available.left(), available.right() - self.width() - 16)
        y = available.top() + 16
        self.move(x, y)

    def exercise_all(self) -> None:
        """Deterministically exercise every advertised path for ``--smoke``."""

        self.show_login()
        self.show_register()
        self.resize_auth(420, 560)
        for width, height, _label, _shortcut in self.SIZE_SPECS:
            self.resize_main(width, height)
        for page, _shortcut, _label in self.PAGE_SPECS:
            self.show_page(page)
        for state, _label, _shortcut in self.STATE_SPECS:
            self.inject_state(state)
        QApplication.processEvents()
        assert len(self.main_window._pages) == 6
        assert self.main_window._pipeline_rail.stage_count == 4
        assert self.main_window.width() >= 760
        assert not self.main_window.start_btn.isEnabled()
        assert not self.main_window._settings_save_btn.isEnabled()

    @staticmethod
    def _capture_widget(widget: QWidget, destination: Path) -> None:
        QApplication.processEvents()
        pixmap = widget.grab()
        if pixmap.isNull() or not pixmap.save(str(destination), "PNG"):
            raise RuntimeError(f"QA 화면 캡처에 실패했습니다: {destination}")

    def capture_all(self, destination: Path) -> int:
        """Capture every release viewport, page, and visual state as PNG."""
        destination.mkdir(parents=True, exist_ok=True)
        captured = 0

        for view_name, show_view in (
            ("login", self.show_login),
            ("register-step1", self.show_register),
        ):
            show_view()
            for width, height in ((720, 760), (420, 560)):
                self.resize_auth(width, height)
                self._capture_widget(
                    self.login_window,
                    destination / f"auth-{view_name}-{width}x{height}.png",
                )
                captured += 1

        self.show_register()
        self.login_window._show_register_step(1)
        self._capture_widget(
            self.login_window,
            destination / "auth-register-step2-720x760.png",
        )
        captured += 1

        for width, height, _label, _shortcut in self.SIZE_SPECS:
            self.resize_main(width, height)
            for page, _page_shortcut, page_label in self.PAGE_SPECS:
                self.show_page(page)
                slug = {
                    2: "dashboard",
                    0: "automation",
                    3: "history",
                    4: "accounts",
                    1: "settings",
                    5: "subscription",
                }[page]
                self._capture_widget(
                    self.main_window,
                    destination / f"main-{slug}-{width}x{height}.png",
                )
                captured += 1
            for state, _state_label, _state_shortcut in self.STATE_SPECS:
                self.inject_state(state)
                self._capture_widget(
                    self.main_window,
                    destination / f"automation-{state}-{width}x{height}.png",
                )
                captured += 1

        for width, height in ((1360, 900), (760, 560)):
            self.resize_main(width, height)
            self.show_page(1)
            for tab in range(self.main_window._settings_tab_bar.count()):
                self.main_window._settings_tab_bar.setCurrentIndex(tab)
                QApplication.processEvents()
                self._capture_widget(
                    self.main_window,
                    destination / f"settings-tab{tab + 1}-{width}x{height}.png",
                )
                captured += 1

        self.resize_main(1360, 900)
        self.show_page(0)
        self.main_window.open_tutorial()
        QApplication.processEvents()
        self._capture_widget(
            self.main_window,
            destination / "help-overlay-1360x900.png",
        )
        captured += 1
        self.main_window._tutorial_overlay.hide()

        onboarding = OnboardingDialog(self.main_window)
        onboarding.set_step_status(0, "complete", "현재 이용량: 17회 남음")
        onboarding.set_step_status(1, "needs_attention", "Threads 연결 테스트가 필요합니다.")
        onboarding.set_step_status(2, "complete", "업로드 간격 4분")
        onboarding.show()
        for step in range(len(onboarding.STEPS)):
            onboarding.set_current_step(step)
            self._capture_widget(
                onboarding,
                destination / f"onboarding-step{step + 1}-1040x720.png",
            )
            captured += 1
        onboarding.resize(640, 500)
        onboarding.set_current_step(0)
        self._capture_widget(
            onboarding,
            destination / "onboarding-compact-640x500.png",
        )
        captured += 1
        onboarding.close()

        update_info = {
            "version": "3.2.0",
            "size_mb": 48.2,
            "changelog": "반응형 화면과 자동화 상태 안내를 개선했습니다.",
        }
        update = UpdateDialog("3.1.0", update_info=update_info)
        update.show()
        update_states = (
            ("checking", update.set_checking),
            ("latest", update._on_no_update),
            ("available", lambda: update._on_update_found(update_info)),
            ("downloading", lambda: update.set_download_progress(58)),
            ("installing", update.set_installing),
            ("error", lambda: update.set_install_error("오프라인 QA 오류")),
        )
        for state, setter in update_states:
            setter()
            self._capture_widget(
                update,
                destination / f"update-{state}-640x580.png",
            )
            captured += 1
        update.close()
        return captured

    def _wait_for_auth_workers(self) -> None:
        for name in ("_login_thread", "_reg_worker", "_username_worker"):
            worker = getattr(self.login_window, name, None)
            if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():
                worker.wait(1500)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._wait_for_auth_workers()
        self.login_window.hide()
        self.main_window.hide()
        for name in ("_heartbeat_timer", "_update_timer"):
            timer = getattr(self.main_window, name, None)
            if timer is not None:
                timer.stop()
        self.main_window._closed = True
        pipeline = getattr(self.main_window, "pipeline", None)
        if pipeline is not None:
            pipeline.cancel()
        self.boundaries.restore()
        self.hide()
        self.app.quit()

    def closeEvent(self, event) -> None:
        self.shutdown()
        event.accept()


def _load_bundled_fonts(app: QApplication) -> None:
    fonts_dir = ROOT / "fonts"
    if fonts_dir.is_dir():
        for path in fonts_dir.iterdir():
            if path.suffix.lower() in {".ttf", ".otf"}:
                QFontDatabase.addApplicationFont(str(path))
    resolve_fonts()
    app.setFont(QFont(Typography.FAMILY, 10))


def _configure_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Colors.PORCELAIN))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.INK))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.PAPER))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_INPUT))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.INK))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.PAPER))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.INK))
    app.setPalette(palette)
    app.setStyleSheet(global_stylesheet())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline manual QA for the UI redesign")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Exercise all QA paths offscreen and exit",
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        help="오프라인 QA 화면 전체를 PNG로 저장할 디렉터리",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_high_dpi()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName(QA_TITLE)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    _load_bundled_fonts(app)
    _configure_palette(app)

    boundaries = OfflineBoundaries()
    boundaries.install()
    try:
        controller = ManualQaController(app, boundaries)
    except Exception:
        boundaries.restore()
        raise

    app._offline_ui_qa_controller = controller  # type: ignore[attr-defined]
    if args.smoke:
        controller.exercise_all()
        controller.shutdown()
        QApplication.processEvents()
        print("OFFLINE UI QA SMOKE PASS: views=3 sizes=5 pages=6 states=6")
        return 0
    if args.capture_dir is not None:
        count = controller.capture_all(args.capture_dir)
        controller.shutdown()
        QApplication.processEvents()
        print(f"OFFLINE UI QA CAPTURE PASS: {count} PNG files")
        return 0

    controller.show()
    controller.raise_()
    controller.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
