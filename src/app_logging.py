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

_ALLOWED_LOGGER_PREFIXES = ("main", "src", "runtime", "__main__")

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

_LOCALIZE_PATTERNS = [
    (re.compile(r"\bPython=", re.IGNORECASE), "파이썬 버전="),
    (re.compile(r"\bPlatform=", re.IGNORECASE), "플랫폼="),
    (re.compile(r"\bLog file=", re.IGNORECASE), "로그 파일="),
    (re.compile(r"\bUI\b", re.IGNORECASE), "화면"),
    (re.compile(r"\bAPI key\b", re.IGNORECASE), "API 키"),
    (re.compile(r"\buser_id=", re.IGNORECASE), "사용자ID="),
    (re.compile(r"\blinks=", re.IGNORECASE), "링크수="),
    (re.compile(r"\binterval=", re.IGNORECASE), "간격="),
    (re.compile(r"\bqueue=", re.IGNORECASE), "대기열="),
    (re.compile(r"\bversion=", re.IGNORECASE), "버전="),
    (
        re.compile(r"\bblocked api host lock due to integrity validation failure\.?", re.IGNORECASE),
        "무결성 검증에 실패한 API 호스트 잠금 파일을 차단했습니다.",
    ),
    (
        re.compile(r"\bblocked api host change due to security policy\.?", re.IGNORECASE),
        "보안 정책으로 API 호스트 변경을 차단했습니다.",
    ),
    (
        re.compile(r"\bfailed to persist api host lock\.?", re.IGNORECASE),
        "API 호스트 잠금 정보 저장에 실패했습니다.",
    ),
    (
        re.compile(r"\bfailed to verify api tls certificate pin\.?", re.IGNORECASE),
        "API TLS 인증서 핀 검증에 실패했습니다.",
    ),
    (
        re.compile(r"\bblocked api tls certificate pin mismatch\.?", re.IGNORECASE),
        "보안 정책으로 API TLS 인증서 핀 불일치를 차단했습니다.",
    ),
    (re.compile(r"\bDownload error:\s*", re.IGNORECASE), "다운로드 오류: "),
    (re.compile(r"\bUpdate installation error:\s*", re.IGNORECASE), "업데이트 설치 오류: "),
    (re.compile(r"\bUpdate signature validation failed\.?", re.IGNORECASE), "업데이트 서명 검증에 실패했습니다."),
    (re.compile(r"\bExpected update checksum is missing\.?", re.IGNORECASE), "업데이트 체크섬 정보가 없습니다."),
    (re.compile(r"\bUpdate checksum validation failed\.?", re.IGNORECASE), "업데이트 체크섬 검증에 실패했습니다."),
    (
        re.compile(r"\bAuto-update is only supported in packaged executable mode\.?", re.IGNORECASE),
        "자동 업데이트는 배포 실행 파일 모드에서만 지원됩니다.",
    ),
    (re.compile(r"\bCurrent version:\s*", re.IGNORECASE), "현재 버전: "),
    (re.compile(r"\bChecking for updates\.{0,3}", re.IGNORECASE), "업데이트 확인 중..."),
    (re.compile(r"\bNew version found:\s*", re.IGNORECASE), "새 버전 발견: "),
    (re.compile(r"\bChangelog:\s*", re.IGNORECASE), "변경 내역: "),
    (re.compile(r"\bProgress:\s*", re.IGNORECASE), "진행률: "),
    (re.compile(r"\bDownloaded:\s*", re.IGNORECASE), "다운로드 완료: "),
    (re.compile(r"\bRestart app to install the update\.?", re.IGNORECASE), "업데이트 설치를 위해 앱을 다시 시작해주세요."),
    (re.compile(r"\bDownload failed\b", re.IGNORECASE), "다운로드 실패"),
    (re.compile(r"\bAlready on latest version\.?", re.IGNORECASE), "이미 최신 버전입니다."),
    (re.compile(r"\bGoogle API client is not configured\.?", re.IGNORECASE), "Google API 클라이언트가 설정되지 않았습니다."),
    (re.compile(r"\bNo API candidates returned\b", re.IGNORECASE), "API 응답 후보가 없습니다."),
    (re.compile(r"\bTask complete:\s*", re.IGNORECASE), "작업 완료: "),
    (re.compile(r"\bTurn limit reached\b", re.IGNORECASE), "턴 제한에 도달했습니다."),
    (re.compile(r"\bUsage:\s*", re.IGNORECASE), "사용법: "),
    (re.compile(r"\bexecute:\s*", re.IGNORECASE), "실행: "),
    (re.compile(r"\bexecution error\b", re.IGNORECASE), "실행 오류"),
    (re.compile(r"\bparsing\b", re.IGNORECASE), "파싱"),
    (re.compile(r"\bparse\b", re.IGNORECASE), "파싱"),
    (re.compile(r"\bproduct id\b", re.IGNORECASE), "상품 ID"),
    (re.compile(r"\btitle\b", re.IGNORECASE), "상품명"),
    (re.compile(r"\bkeywords\b", re.IGNORECASE), "키워드"),
    (re.compile(r"\bimage url\b", re.IGNORECASE), "이미지 URL"),
    (re.compile(r"\bsuccess\b", re.IGNORECASE), "성공"),
    (re.compile(r"\bfailed\b", re.IGNORECASE), "실패"),
    (re.compile(r"\berror\b", re.IGNORECASE), "오류"),
    (re.compile(r"\bwarning\b", re.IGNORECASE), "경고"),
    (re.compile(r"at least\s+(\d+)\s+characters?", re.IGNORECASE), r"최소 \1자"),
    (re.compile(r"at most\s+(\d+)\s+characters?", re.IGNORECASE), r"최대 \1자"),
]


def _sanitize_log_text(text: str) -> str:
    safe = str(text or "")
    for pattern, replacement in _SENSITIVE_PATTERNS:
        safe = pattern.sub(replacement, safe)
    return safe


def _localize_log_text(text: str) -> str:
    localized = str(text or "")
    for pattern, replacement in _LOCALIZE_PATTERNS:
        localized = pattern.sub(replacement, localized)
    return localized


def _resolve_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.DEBUG)


def get_log_dir() -> Path:
    return Path.home() / ".shorts_thread_maker" / "logs"


def get_log_file(app_name: str = "coupuas-thread-auto") -> Path:
    safe_name = app_name.replace(" ", "-").lower()
    return get_log_dir() / f"{safe_name}.log"


def _is_allowed_logger_name(name: str) -> bool:
    allow_all = os.getenv("THREAD_AUTO_LOG_ALL_LOGGERS", "1").strip() != "0"
    if allow_all:
        return True

    logger_name = str(name or "")
    for prefix in _ALLOWED_LOGGER_PREFIXES:
        if logger_name == prefix or logger_name.startswith(f"{prefix}."):
            return True
    return False


def _normalize_record_message(record: logging.LogRecord) -> None:
    if getattr(record, "_normalized_by_app_logging", False):
        return
    try:
        text = record.getMessage()
    except Exception:
        text = str(getattr(record, "msg", ""))
    text = _localize_log_text(_sanitize_log_text(text))
    record.msg = text
    record.args = ()
    record._normalized_by_app_logging = True


def _project_path_filter() -> logging.Filter:
    project_root = Path(__file__).resolve().parent.parent

    class ProjectPathFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not _is_allowed_logger_name(getattr(record, "name", "")):
                return False

            _normalize_record_message(record)

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


class SafeKoreanFormatter(logging.Formatter):
    def __init__(self, *args, hide_exception_details: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.hide_exception_details = bool(hide_exception_details)

    def formatException(self, exc_info):  # noqa: N802 - logging API override
        if self.hide_exception_details:
            return "예외 상세 정보는 보안 정책으로 숨김 처리되었습니다."
        return super().formatException(exc_info)


def _install_exception_hooks() -> None:
    global _PREV_EXCEPTHOOK, _PREV_THREAD_EXCEPTHOOK
    logger = logging.getLogger("runtime.exceptions")

    if _PREV_EXCEPTHOOK is None:
        _PREV_EXCEPTHOOK = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        logger.exception(
            "처리되지 않은 예외가 발생했습니다.",
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
                "처리되지 않은 스레드 예외: thread=%s",
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
        text = _localize_log_text(_sanitize_log_text(sep.join(str(arg) for arg in args)))

        try:
            if text:
                if target in (sys.stderr, sys.__stderr__):
                    stderr_logger.error(text)
                elif target in (None, sys.stdout, sys.__stdout__):
                    stdout_logger.info(text)
        except Exception:
            # Never break print behavior because of logging failures.
            pass

        local_kwargs = dict(kwargs)
        _ORIGINAL_PRINT(text, **local_kwargs)

    builtins.print = _logged_print
    _PRINT_HOOKED = True


def _run_runtime_security_check(is_frozen: bool, runtime_logger: logging.Logger) -> None:
    if not is_frozen:
        return

    try:
        from src.runtime_security import RuntimeSecurityError, enforce_runtime_security
    except Exception as exc:
        runtime_logger.warning("런타임 보안 모듈을 불러오지 못했습니다: %s", exc)
        return

    try:
        enforce_runtime_security()
        runtime_logger.info("런타임 보안 점검을 통과했습니다.")
    except RuntimeSecurityError:
        runtime_logger.exception("런타임 보안 점검에 실패했습니다.")
        raise
    except Exception:
        runtime_logger.exception("런타임 보안 점검 중 예외가 발생했습니다.")
        raise


def setup_logging(
    app_name: str = "coupuas-thread-auto",
    level: Optional[str] = None,
    capture_print: bool = True,
) -> Path:
    global _INITIALIZED

    if _INITIALIZED:
        return get_log_file(app_name)

    is_frozen = bool(getattr(sys, "frozen", False))
    if level:
        log_level_name = level
    else:
        # 기본값을 DEBUG로 두어 터미널에서 가능한 모든 로그를 확인할 수 있게 합니다.
        log_level_name = os.getenv("THREAD_AUTO_LOG_LEVEL", "DEBUG")

    log_level = _resolve_level(log_level_name)
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = get_log_file(app_name)

    root = logging.getLogger()
    root.setLevel(log_level)

    formatter = SafeKoreanFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(process)d:%(threadName)s | "
        "%(name)s | %(project_file)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        hide_exception_details=is_frozen,
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
    _run_runtime_security_check(is_frozen, runtime_logger)
    runtime_logger.info("로깅 초기화 완료")
    runtime_logger.info("파이썬 버전=%s", sys.version.replace("\n", " "))
    runtime_logger.info("플랫폼=%s", platform.platform())
    runtime_logger.info("로그 파일=%s", log_file)

    _INITIALIZED = True
    return log_file
