"""Run a live GUI registration/login smoke test against the configured API.

This intentionally creates a new trial account. It never prints or persists the
generated password. Run manually:

    python tools/live_auth_ui_smoke.py --confirm-live-account
"""

from __future__ import annotations

import argparse
import atexit
import secrets
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import auth_client  # noqa: E402
import src.login_window as login_window_module  # noqa: E402
from src.login_window import LoginWindow  # noqa: E402
from src.main_window import MainWindow  # noqa: E402


def _wait_for(app: QApplication, predicate, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    app.processEvents()
    return bool(predicate())


def _suffix(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-live-account",
        action="store_true",
        help="Required acknowledgement that this creates a live test account.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=15.0,
        help="How long the authenticated main window must remain responsive.",
    )
    args = parser.parse_args()
    if not args.confirm_live_account:
        parser.error("--confirm-live-account is required")

    suffix = _suffix()
    username = f"st_ui_{suffix}"
    password = f"St!{_suffix(14)}9"
    email = f"{username}@example.com"
    contact = f"0100000{secrets.randbelow(10000):04d}"

    app = QApplication.instance() or QApplication(sys.argv)
    cleanup_windows = []

    def _cleanup_live_smoke() -> None:
        nonlocal password
        for cleanup_window in reversed(cleanup_windows):
            try:
                cleanup_window.close()
            except Exception:
                pass
        try:
            app.processEvents()
        except Exception:
            pass
        try:
            auth_client.logout()
        except Exception:
            pass
        try:
            auth_client.remember_login_credentials("", "")
        except Exception:
            pass
        password = ""

    atexit.register(_cleanup_live_smoke)
    notices: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    login_result: dict = {}

    login_window_module.show_info = (
        lambda _parent, title, message: notices.append((str(title), str(message)))
    )
    login_window_module.show_warning = (
        lambda _parent, title, message: warnings.append((str(title), str(message)))
    )

    window = LoginWindow()
    cleanup_windows.append(window)
    window.login_success.connect(lambda result: login_result.update(result or {}))
    window.show()
    if not _wait_for(app, window.isVisible, timeout=5):
        print("[FAIL] 로그인 창이 표시되지 않았습니다.")
        return 1

    shot_dir = PROJECT_ROOT / "output" / "live-auth"
    shot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    window.grab().save(str(shot_dir / f"{timestamp}-01-login.png"), "PNG")

    window.btn_go_register.click()
    app.processEvents()
    if window.stack.currentIndex() != 1:
        print("[FAIL] 회원가입 화면으로 전환되지 않았습니다.")
        return 1

    window.reg_name.setText("자동 검증")
    window.reg_email.setText(email)
    window.reg_username.setText(username)
    window.reg_pw.setText(password)
    window.reg_pw_confirm.setText(password)
    window.reg_contact.setText(contact)
    window.reg_legal_consent.setChecked(True)
    window.btn_check_user.click()

    if not _wait_for(
        app,
        lambda: window.btn_check_user.isEnabled() and window._username_available,
        timeout=20,
    ):
        print(f"[FAIL] 아이디 중복 확인 실패: {window.reg_user_status.text()}")
        return 1
    window.grab().save(str(shot_dir / f"{timestamp}-02-register-ready.png"), "PNG")

    window.btn_register.click()
    if not _wait_for(
        app,
        lambda: window.stack.currentIndex() == 0
        and window.login_id.text().strip().lower() == username,
        timeout=30,
    ):
        warning_text = warnings[-1][1] if warnings else "응답 없음"
        print(f"[FAIL] 회원가입 실패: {warning_text}")
        return 1

    window.grab().save(str(shot_dir / f"{timestamp}-03-register-complete.png"), "PNG")
    window.remember_cb.setChecked(True)
    window.auto_login_cb.setChecked(True)
    window.btn_login.click()
    if not _wait_for(app, lambda: login_result.get("status") is True, timeout=30):
        print(f"[FAIL] 로그인 실패: {window.login_status.text()}")
        return 1
    if not auth_client.is_logged_in():
        print("[FAIL] 로그인 성공 후 인증 세션이 유지되지 않았습니다.")
        return 1

    window.grab().save(str(shot_dir / f"{timestamp}-04-login-success.png"), "PNG")
    window.close()
    app.processEvents()

    if not auth_client.logout():
        print("[FAIL] 첫 로그인 세션을 정상 종료하지 못했습니다.")
        return 1

    restart_result: dict = {}
    restart_window = LoginWindow()
    cleanup_windows.append(restart_window)
    restart_window.login_success.connect(
        lambda result: restart_result.update(result or {})
    )
    restart_window.show()
    if not _wait_for(app, lambda: restart_result.get("status") is True, timeout=30):
        print(f"[FAIL] 재실행 자동 로그인 실패: {restart_window.login_status.text()}")
        return 1
    restart_window.grab().save(
        str(shot_dir / f"{timestamp}-05-auto-login-success.png"),
        "PNG",
    )

    main_window = MainWindow()
    cleanup_windows.append(main_window)
    main_window._auth_data = dict(restart_result)
    main_window.show()
    restart_window.hide()
    if not _wait_for(app, main_window.isVisible, timeout=10):
        print("[FAIL] 인증 후 메인 창이 표시되지 않았습니다.")
        return 1

    hold_deadline = time.monotonic() + max(1.0, args.hold_seconds)
    while time.monotonic() < hold_deadline:
        app.processEvents()
        if not main_window.isVisible():
            print("[FAIL] 유지 검증 중 메인 창이 종료되었습니다.")
            return 1
        time.sleep(0.05)
    main_window.grab().save(
        str(shot_dir / f"{timestamp}-06-main-window-stable.png"),
        "PNG",
    )

    print(f"[OK] endpoint={auth_client.API_SERVER_URL}")
    print(f"[OK] username={username}")
    print(f"[OK] user_id={login_result.get('id') or login_result.get('user_id')}")
    print("[OK] live GUI registration, login, auto-login, and main-window stability verified")
    main_window.close()
    restart_window.close()
    app.processEvents()
    auth_client.logout()
    auth_client.remember_login_credentials("", "")
    password = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
