import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src import app_logging
from src.app_logging import _sanitize_log_text
from src import fs_security


ROOT = Path(__file__).resolve().parent


def test_local_log_sanitizer_removes_external_identifiers_and_paths():
    sanitized = _sanitize_log_text(
        "open https://alice:secret@example.com/private?token=value#fragment "
        "alice@example.com @private_user user_id=customer-123 "
        r"C:\Users\Alice\AppData\Local\secret.json "
        "url=/private/callback?opaque=value#fragment "
        "path=/home/alice/private/session.json "
        "profile_dir=.threads_profile_alice "
        "jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.signaturevalue12345"
    )

    assert "https://example.com" in sanitized
    assert "alice" not in sanitized.lower()
    assert "value" not in sanitized
    assert "fragment" not in sanitized
    assert "private_user" not in sanitized
    assert "customer-123" not in sanitized
    assert "C:\\Users" not in sanitized
    assert "/home/alice" not in sanitized
    assert ".threads_profile_alice" not in sanitized
    assert "opaque=value" not in sanitized
    assert "eyJhbGci" not in sanitized
    assert "[EMAIL]" in sanitized
    assert "@[HANDLE]" in sanitized
    assert "[PATH]" in sanitized


def test_remote_activity_call_sites_do_not_send_direct_business_identifiers():
    sources = {
        name: (ROOT / name).read_text(encoding="utf-8")
        for name in (
            "src/main_window.py",
            "src/coupang_uploader.py",
            "src/login_window.py",
        )
    }
    joined = "\n".join(sources.values())

    forbidden = (
        'f"username={self.username}"',
        'f"account_id={account.account_id}',
        'profile_dir={profile_dir}',
        'phone={phone_masked}',
        'f"url={url}; status={status}; product={product_name}"',
        'f"[{i}/{total}] {product_name}"',
        'auth_client.log_action("pipeline_error", str(e)',
        'auth_client.log_action("batch_error", str(exc)',
        'self._log_user_activity("batch_runtime_log", message_text)',
    )
    for value in forbidden:
        assert value not in joined


def test_production_entrypoints_do_not_capture_free_form_print_output():
    for name in ("main.py", "login_main.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "setup_logging(capture_print=False)" in source
        assert "setup_logging(capture_print=True)" not in source


def test_external_loggers_are_blocked_by_default(monkeypatch):
    monkeypatch.delenv("THREAD_AUTO_LOG_ALL_LOGGERS", raising=False)
    assert app_logging._is_allowed_logger_name("src.worker") is True
    assert app_logging._is_allowed_logger_name("urllib3.connectionpool") is False

    monkeypatch.setenv("THREAD_AUTO_LOG_ALL_LOGGERS", "1")
    assert app_logging._is_allowed_logger_name("urllib3.connectionpool") is True


def test_file_logging_requires_acl_and_hides_exception_details(monkeypatch, tmp_path):
    root_logger = logging.getLogger()
    existing_handlers = list(root_logger.handlers)
    acl_calls = []

    monkeypatch.setattr(app_logging, "_INITIALIZED", False)
    monkeypatch.setattr(app_logging, "get_log_dir", lambda: tmp_path)
    monkeypatch.setattr(
        fs_security,
        "secure_dir_permissions",
        lambda path: acl_calls.append(("dir", Path(path))) or True,
    )
    monkeypatch.setattr(
        fs_security,
        "secure_file_permissions",
        lambda path: acl_calls.append(("file", Path(path))) or True,
    )

    added_handlers = []
    try:
        log_path = app_logging.setup_logging(
            app_name="privacy-test",
            capture_print=False,
        )
        added_handlers = [
            handler for handler in root_logger.handlers if handler not in existing_handlers
        ]
        file_handler = next(
            handler for handler in added_handlers if isinstance(handler, RotatingFileHandler)
        )

        assert log_path == tmp_path / "privacy-test.log"
        assert acl_calls == [("dir", tmp_path), ("file", log_path)]
        assert file_handler.maxBytes == 5 * 1024 * 1024
        assert file_handler.backupCount == 3
        assert file_handler.formatter.hide_exception_details is True
    finally:
        for handler in added_handlers:
            root_logger.removeHandler(handler)
            handler.close()
