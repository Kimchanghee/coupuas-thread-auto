"""Lightweight repository sanity checks for regression prevention."""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

COMPILE_TARGETS = [
    "src/main_window.py",
    "src/auth_client.py",
    "src/coupang_uploader.py",
    "src/settings_dialog.py",
    "src/threads_playwright_helper.py",
]

REQUIRED_MARKERS = {
    "src/main_window.py": [
        "def _build_page2_settings",
        "def _relayout_settings_sections",
        "def _request_payapp_checkout",
        "def _open_contact",
        "def _open_threads_login",
        "def _check_login_status",
        "self._add_gemini_key_btn",
        "카카오톡 문의하기",
        "구독 결제",
    ],
    "src/auth_client.py": [
        "def create_payapp_checkout",
        "def get_free_trial_work_count",
        "_FIXED_PAYAPP_PLAN_ID",
    ],
    "src/coupang_uploader.py": [
        "AI fallback 기능이 제거되어",
    ],
}


def fail(message: str) -> int:
    print(f"[FAIL] {message}")
    return 1


def run() -> int:
    print("== sanity_check ==")
    print(f"root: {ROOT}")

    for rel in COMPILE_TARGETS:
        path = ROOT / rel
        if not path.exists():
            return fail(f"missing compile target: {rel}")
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            return fail(f"compile error in {rel}: {exc}")
        print(f"[OK] compile: {rel}")

    for rel, markers in REQUIRED_MARKERS.items():
        path = ROOT / rel
        if not path.exists():
            return fail(f"missing marker target: {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            return fail(f"read error in {rel}: {exc}")

        for marker in markers:
            if marker not in text:
                return fail(f"marker missing in {rel}: {marker}")
        print(f"[OK] markers: {rel}")

    print("[OK] all sanity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
