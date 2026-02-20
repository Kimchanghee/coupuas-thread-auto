import builtins
import logging
import os
import platform
import re
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_INITIALIZED = False
_PRINT_HOOKED = False
_ORIGINAL_PRINT = builtins.print
_PREV_EXCEPTHOOK = None
_PREV_THREAD_EXCEPTHOOK = None

_SENSITIVE_PATTERNS = [
    (re.compile(r"(x-goog-api-key\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(key=)([^&\s]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(sessionid\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(ds_user_id\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (
        re.compile(
            r"((?:['\"])?(?:password|passwd|pwd|token|access_token|refresh_token|api[_-]?key|secret|authorization|cookie|text)(?:['\"])?\s*[:=]\s*)(?:'[^']*'|\"[^\"]*\"|[^,\s}\]]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"([?&](?:token|access_token|refresh_token|api[_-]?key|password|passwd|pwd|secret|key)=)([^&\s]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
]


def _sanitize_log_text(text: str) -> str:
    safe = str(text or "")
    for pattern, replacement in _SENSITIVE_PATTERNS:
        safe = pattern.sub(replacement, safe)
    return safe


def _resolve_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.DEBUG)


def get_log_dir() -> Path:
    return Path.home() / ".shorts_thread_maker" / "logs"


def get_log_file(app_name: str = "coupuas-thread-auto") -> Path:
    safe_name = app_name.replace(" ", "-").lower()
    return get_log_dir() / f"{safe_name}.log"


def _project_path_filter() -> logging.Filter:
    project_root = Path(__file__).resolve().parent.parent

    class ProjectPathFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            pathname = getattr(record, "pathname", "")
            if pathname:
                try:
                    record.project_file = str(Path(pathname).resolve().relative_to(project_root))
                except Exception:
                    record.project_file = pathname
            else:
                record.project_file = "-"
            return True

    return ProjectPathFilter()


def _install_exception_hooks() -> None:
    global _PREV_EXCEPTHOOK, _PREV_THREAD_EXCEPTHOOK
    logger = logging.getLogger("runtime.exceptions")

    if _PREV_EXCEPTHOOK is None:
        _PREV_EXCEPTHOOK = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        logger.exception(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        if _PREV_EXCEPTHOOK is not None:
            _PREV_EXCEPTHOOK(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    if hasattr(threading, "excepthook"):
        if _PREV_THREAD_EXCEPTHOOK is None:
            _PREV_THREAD_EXCEPTHOOK = threading.excepthook

        def _threading_excepthook(args):
            logger.exception(
                "Unhandled thread exception: thread=%s",
                getattr(args.thread, "name", "unknown"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if _PREV_THREAD_EXCEPTHOOK is not None:
                _PREV_THREAD_EXCEPTHOOK(args)

        threading.excepthook = _threading_excepthook


def _install_print_hook() -> None:
    global _PRINT_HOOKED
    if _PRINT_HOOKED:
        return

    stdout_logger = logging.getLogger("runtime.print.stdout")
    stderr_logger = logging.getLogger("runtime.print.stderr")

    def _logged_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        target = kwargs.get("file")
        text = _sanitize_log_text(sep.join(str(arg) for arg in args))

        try:
            if text:
                if target in (sys.stderr, sys.__stderr__):
                    stderr_logger.error(text)
                elif target in (None, sys.stdout, sys.__stdout__):
                    stdout_logger.info(text)
        except Exception:
            # Never break print behavior because of logging failures.
            pass

        _ORIGINAL_PRINT(*args, **kwargs)

    builtins.print = _logged_print
    _PRINT_HOOKED = True


def setup_logging(
    app_name: str = "coupuas-thread-auto",
    level: Optional[str] = None,
    capture_print: bool = True,
) -> Path:
    global _INITIALIZED

    if _INITIALIZED:
        return get_log_file(app_name)

    log_level_name = level or os.getenv("THREAD_AUTO_LOG_LEVEL", "DEBUG")
    log_level = _resolve_level(log_level_name)
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = get_log_file(app_name)

    root = logging.getLogger()
    root.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(process)d:%(threadName)s | "
        "%(name)s | %(project_file)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    project_filter = _project_path_filter()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    file_handler.addFilter(project_filter)
    root.addHandler(file_handler)

    console_stream = getattr(sys, "stdout", None) or sys.__stdout__
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    console_handler.addFilter(project_filter)
    root.addHandler(console_handler)

    logging.captureWarnings(True)
    _install_exception_hooks()
    if capture_print:
        _install_print_hook()

    runtime_logger = logging.getLogger("runtime.bootstrap")
    runtime_logger.info("Logging initialized")
    runtime_logger.info("Python=%s", sys.version.replace("\n", " "))
    runtime_logger.info("Platform=%s", platform.platform())
    runtime_logger.info("Log file=%s", log_file)

    _INITIALIZED = True
    return log_file
