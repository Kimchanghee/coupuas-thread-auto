"""
Experimental Gemini Computer Use agent (browser control via Playwright).

This module wires up the official Computer Use preview model
(`gemini-2.5-computer-use-preview-10-2025`) with a simple action executor that
runs inside Playwright. It is intentionally sandboxed and opt-in; it does NOT
run anywhere in the main app flow by default.
"""
from __future__ import annotations

import json
import ipaddress
import logging
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from google import genai
from google.genai import types
from google.genai.types import Content, Part

try:
    from playwright.sync_api import Page, sync_playwright
    _PLAYWRIGHT_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    Page = Any  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_IMPORT_ERROR = exc

from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.secure_storage import protect_secret, unprotect_secret
from src.system_process import run_process


SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900
logger = logging.getLogger(__name__)


def _denormalize_x(x: int, screen_width: int) -> int:
    return int(x / 1000 * screen_width)


def _denormalize_y(y: int, screen_height: int) -> int:
    return int(y / 1000 * screen_height)


@dataclass
class ExecutedAction:
    name: str
    result: Dict[str, Any]


class ComputerUseAgent:
    ALLOWED_NAVIGATION_DOMAINS = {
        "threads.net",
        "threads.com",
        "instagram.com",
        "facebook.com",
        "meta.com",
    }
    ALLOWED_NAVIGATION_EXACT_HOSTS = {
        "www.google.com",
    }
    MAX_TYPE_TEXT_LENGTH = 4000
    ALLOWED_SAFE_KEYS = {
        "ENTER",
        "TAB",
        "SHIFT+TAB",
        "BACKSPACE",
        "DELETE",
        "ESCAPE",
        "ARROWUP",
        "ARROWDOWN",
        "ARROWLEFT",
        "ARROWRIGHT",
        "HOME",
        "END",
        "PAGEUP",
        "PAGEDOWN",
        "CONTROL+A",
        "CONTROL+C",
        "CONTROL+V",
        "CONTROL+X",
        "CONTROL+ENTER",
    }
    PLAYWRIGHT_INSTALL_TIMEOUT_SEC = 300

    SESSION_FILENAME = "storage_state.sec"
    SESSION_STAGE_PREFIX = f"{SESSION_FILENAME}.stage."
    SESSION_BACKUP_PREFIX = f"{SESSION_FILENAME}.backup."
    SESSION_TEMP_SUFFIX = ".tmp"

    def __init__(
        self,
        api_key: Optional[str] = None,
        headless: bool = False,
        profile_dir: str = ".threads_profile",
        load_saved_session: bool = True,
    ):
        """
        Args:
            api_key: Google API key
            headless: whether to run browser in headless mode
            profile_dir: logical profile id (used to derive encrypted session path)
            load_saved_session: default for whether ``start_browser`` restores the
                encrypted saved session. Login/relogin flows should pass ``False``
                so the previous verified session remains untouched while a fresh
                candidate is verified.
        """
        resolved_api_key = str(
            api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        ).strip()
        if resolved_api_key and resolved_api_key != "dummy-key-for-session-setup":
            self.client = genai.Client(api_key=resolved_api_key)
        else:
            self.client = None
        # Avoid keeping plaintext API key as a long-lived instance field.
        self.api_key = ""
        resolved_api_key = ""

        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.headless = headless
        self._load_saved_session_default = bool(load_saved_session)

        self.profile_name = self._normalize_profile_name(profile_dir)
        self.profile_path = self._resolve_profile_path(self.profile_name)
        self.legacy_profile_path = self._resolve_legacy_profile_path(profile_dir)
        self.profile_dir = str(self.profile_path)

    @classmethod
    def _is_allowed_navigation_url(cls, raw_url: str) -> bool:
        text = str(raw_url or "").strip()
        if not text:
            return False
        if text == "about:blank":
            return True

        try:
            parsed = urlparse(text)
        except Exception:
            return False

        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return False

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # Not an IP literal. Continue domain checks.
            pass

        if host in cls.ALLOWED_NAVIGATION_EXACT_HOSTS:
            return True

        for domain in cls.ALLOWED_NAVIGATION_DOMAINS:
            if host == domain or host.endswith(f".{domain}"):
                return True
        return False

    @classmethod
    def _enforce_allowed_page_url(cls, page: Page, action: str = "navigation") -> None:
        current_url = str(getattr(page, "url", "") or "")
        if cls._is_allowed_navigation_url(current_url):
            return
        if current_url == "about:blank":
            return
        try:
            page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass
        raise ValueError(f"허용되지 않은 최종 URL입니다 ({action}): {current_url}")

    @classmethod
    def _is_allowed_document_request(cls, raw_url: str) -> bool:
        return cls._is_allowed_navigation_url(raw_url)

    @classmethod
    def _sanitize_type_text(cls, value: Any) -> str:
        text = str(value or "")
        if len(text) > cls.MAX_TYPE_TEXT_LENGTH:
            raise ValueError("Input text exceeds maximum allowed length")
        if any(ord(ch) < 32 and ch not in {"\n", "\r", "\t"} for ch in text):
            raise ValueError("Input text contains disallowed control characters")
        return text

    @classmethod
    def _normalize_keys(cls, keys: str) -> str:
        text = re.sub(r"\s+", "", str(keys or "").upper())
        text = text.replace("CTRL", "CONTROL")
        return text

    @staticmethod
    def _normalize_profile_name(value: str) -> str:
        raw = str(value or "default").strip().replace("\\", "_").replace("/", "_")
        raw = raw.replace(" ", "_").replace(".", "_")
        safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-"})
        return safe or "default"

    @staticmethod
    def _resolve_profile_path(profile_name: str) -> Path:
        root = Path.home() / ".shorts_thread_maker" / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        if not secure_dir_permissions(root):
            raise PermissionError("브라우저 세션 루트 디렉터리 권한을 보호하지 못했습니다.")

        profile_path = root / profile_name
        profile_path.mkdir(parents=True, exist_ok=True)
        if not secure_dir_permissions(profile_path):
            raise PermissionError("브라우저 세션 디렉터리 권한을 보호하지 못했습니다.")
        return profile_path

    @staticmethod
    def _resolve_legacy_profile_path(value: str) -> Optional[Path]:
        """Confine one-time plaintext migration to a direct child of the app cwd."""
        raw = str(value or "").strip()
        candidate = Path(raw)
        if (
            not raw
            or candidate.is_absolute()
            or len(candidate.parts) != 1
            or candidate.name in {"", ".", ".."}
        ):
            return None
        root = Path.cwd().resolve()
        resolved = (root / candidate.name).resolve(strict=False)
        return resolved if resolved.parent == root else None

    def _get_storage_state_path(self) -> str:
        return str(self.profile_path / self.SESSION_FILENAME)

    def _ensure_session_directory_acl(self) -> bool:
        try:
            profile_path = Path(self.profile_path)
            return (
                profile_path.exists()
                and profile_path.is_dir()
                and secure_dir_permissions(profile_path)
            )
        except Exception:
            logger.exception("브라우저 세션 디렉터리 권한 확인에 실패했습니다.")
            return False

    @staticmethod
    def _fsync_directory(path: Path) -> bool:
        """Flush directory metadata where the platform exposes that operation."""
        if os.name == "nt":
            # Windows has no portable Python API for opening a directory handle
            # with the flags required by FlushFileBuffers. ``os.replace`` still
            # provides the atomic namespace transition used by this transaction.
            return True
        descriptor: Optional[int] = None
        try:
            descriptor = os.open(str(path), os.O_RDONLY)
            os.fsync(descriptor)
            return True
        except OSError:
            logger.exception("브라우저 세션 디렉터리 동기화에 실패했습니다.")
            return False
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _is_valid_staged_session_path(self, value: Any) -> bool:
        try:
            candidate = Path(value).resolve(strict=False)
            profile_path = Path(self.profile_path).resolve(strict=False)
        except (OSError, TypeError, ValueError):
            return False
        return (
            candidate.parent == profile_path
            and candidate.name.startswith(self.SESSION_STAGE_PREFIX)
            and candidate.name.endswith(self.SESSION_TEMP_SUFFIX)
            and candidate.name != self.SESSION_FILENAME
        )

    def _load_storage_state(self) -> Optional[Dict[str, Any]]:
        secure_path = Path(self._get_storage_state_path())
        if not self._ensure_session_directory_acl():
            logger.error("브라우저 세션 디렉터리가 안전하지 않아 저장 세션을 불러오지 않습니다.")
            return None
        if secure_path.exists():
            try:
                if secure_path.is_symlink() or not secure_path.is_file():
                    raise RuntimeError("브라우저 세션 파일 형식이 안전하지 않습니다.")
                if not secure_file_permissions(secure_path):
                    raise PermissionError("브라우저 세션 파일 권한을 보호하지 못했습니다.")
                payload = secure_path.read_text(encoding="utf-8")
                if not payload.startswith(("dpapi:", "fernet:")):
                    raise RuntimeError("브라우저 세션 파일이 암호화되어 있지 않습니다.")
                plain = unprotect_secret(payload)
                if plain:
                    data = json.loads(plain)
                    if self.is_valid_storage_state(data):
                        return data
            except Exception:
                logger.warning(
                    "암호화된 브라우저 세션을 안전하게 불러오지 못했습니다.",
                    exc_info=True,
                )
            # An existing secure-session path is authoritative. Do not fall
            # back to an older plaintext file when it is corrupt or unsafe.
            return None

        # Legacy plaintext migration path.
        legacy_path = (
            self.legacy_profile_path / "storage_state.json"
            if self.legacy_profile_path is not None
            else None
        )
        if legacy_path is not None and legacy_path.exists():
            try:
                if legacy_path.is_symlink() or not legacy_path.is_file():
                    raise RuntimeError("레거시 브라우저 세션 파일 형식이 안전하지 않습니다.")
                if not secure_file_permissions(legacy_path):
                    raise PermissionError("레거시 브라우저 세션 파일 권한을 보호하지 못했습니다.")
                data = json.loads(legacy_path.read_text(encoding="utf-8"))
                if self.is_valid_storage_state(data):
                    # Migrate immediately so plaintext session does not linger.
                    if self._write_storage_state(data):
                        return data
            except Exception:
                pass

        return None

    @staticmethod
    def is_valid_storage_state(state: Any) -> bool:
        """Validate the minimum Playwright storage-state contract."""
        if not isinstance(state, dict):
            return False
        cookies = state.get("cookies")
        origins = state.get("origins")
        if not isinstance(cookies, list) or not isinstance(origins, list):
            return False
        if any(not isinstance(cookie, dict) for cookie in cookies):
            return False
        for origin in origins:
            if not isinstance(origin, dict):
                return False
            if not isinstance(origin.get("origin"), str):
                return False
            local_storage = origin.get("localStorage")
            if not isinstance(local_storage, list):
                return False
            if any(not isinstance(item, dict) for item in local_storage):
                return False
        return True

    def capture_session_state(self) -> Dict[str, Any]:
        """Capture the current browser state without persisting it."""
        if not self.context:
            raise RuntimeError("저장할 브라우저 세션이 없습니다.")
        state = self.context.storage_state()
        if not self.is_valid_storage_state(state):
            raise RuntimeError("브라우저 세션 형식이 올바르지 않습니다.")
        return state

    def validate_session_state_identity(
        self,
        state: Dict[str, Any],
        expected_username: str,
        *,
        timeout: int = 15000,
    ) -> bool:
        """Verify a captured state in a disposable browser context."""
        expected = str(expected_username or "").strip()
        if not expected or not self.is_valid_storage_state(state) or self.browser is None:
            return False

        validation_context = None
        try:
            validation_context = self.browser.new_context(
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
                storage_state=state,
            )

            def _guard_document_navigation(route, request):
                try:
                    if (
                        request.resource_type == "document"
                        and not self._is_allowed_document_request(request.url)
                    ):
                        route.abort()
                        return
                except Exception:
                    route.abort()
                    return
                route.continue_()

            validation_context.route("**/*", _guard_document_navigation)
            validation_page = validation_context.new_page()

            from src.threads_navigation import goto_threads_with_fallback
            from src.threads_playwright_helper import ThreadsPlaywrightHelper

            goto_threads_with_fallback(
                validation_page,
                path="/",
                timeout=max(1000, int(timeout)),
                retries_per_url=1,
                logger=logger,
            )
            helper = ThreadsPlaywrightHelper(validation_page)
            return bool(
                helper.check_login_status()
                and helper.verify_account(expected)
            )
        except Exception:
            logger.warning(
                "후보 브라우저 세션의 Threads 계정을 검증하지 못했습니다.",
                exc_info=True,
            )
            return False
        finally:
            if validation_context is not None:
                try:
                    validation_context.close()
                except Exception:
                    logger.warning("후보 세션 검증 컨텍스트를 닫지 못했습니다.")

    def stage_session(self, state: Optional[Dict[str, Any]] = None) -> Path:
        """Encrypt and fsync a candidate session in a protected sibling file."""
        candidate_state = self.capture_session_state() if state is None else state
        if not self.is_valid_storage_state(candidate_state):
            raise RuntimeError("브라우저 세션 형식이 올바르지 않습니다.")
        if not self._ensure_session_directory_acl():
            raise PermissionError("브라우저 세션 디렉터리 권한을 보호하지 못했습니다.")

        secure_path = Path(self._get_storage_state_path())
        payload = json.dumps(candidate_state, ensure_ascii=False)
        protected = protect_secret(payload, f"shorts_thread_maker.session.{self.profile_name}")
        if not protected or not str(protected).startswith(("dpapi:", "fernet:")):
            raise RuntimeError("브라우저 세션을 암호화하지 못했습니다.")

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(secure_path.parent),
                prefix=self.SESSION_STAGE_PREFIX,
                suffix=self.SESSION_TEMP_SUFFIX,
                delete=False,
            ) as handle:
                handle.write(protected)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)

            if not secure_file_permissions(temp_path):
                raise PermissionError("후보 브라우저 세션 파일 권한을 보호하지 못했습니다.")
            if not self._ensure_session_directory_acl():
                raise PermissionError("브라우저 세션 디렉터리 권한을 다시 확인하지 못했습니다.")
            return temp_path
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("실패한 후보 브라우저 세션을 삭제하지 못했습니다.")
            raise

    def _copy_previous_session_for_rollback(self, secure_path: Path) -> Path:
        backup_path: Optional[Path] = None
        try:
            with secure_path.open("rb") as source, tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(secure_path.parent),
                prefix=self.SESSION_BACKUP_PREFIX,
                suffix=self.SESSION_TEMP_SUFFIX,
                delete=False,
            ) as backup:
                backup_path = Path(backup.name)
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    backup.write(chunk)
                backup.flush()
                os.fsync(backup.fileno())
            if not secure_file_permissions(backup_path):
                raise PermissionError("기존 브라우저 세션 백업 권한을 보호하지 못했습니다.")
            return backup_path
        except Exception:
            if backup_path is not None:
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def _rollback_session_replace(
        self,
        secure_path: Path,
        backup_path: Optional[Path],
        had_previous: bool,
    ) -> bool:
        restore_path: Optional[Path] = None
        try:
            if had_previous:
                if backup_path is None or not backup_path.exists():
                    return False
                # Restore from a copy so the only exact rollback backup remains
                # available until ACL and durability checks all succeed.
                with backup_path.open("rb") as source, tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=str(secure_path.parent),
                    prefix=f"{self.SESSION_FILENAME}.restore.",
                    suffix=self.SESSION_TEMP_SUFFIX,
                    delete=False,
                ) as restore:
                    restore_path = Path(restore.name)
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        restore.write(chunk)
                    restore.flush()
                    os.fsync(restore.fileno())
                if not secure_file_permissions(restore_path):
                    return False
                os.replace(restore_path, secure_path)
                restore_path = None
                acl_ok = secure_file_permissions(secure_path)
            else:
                secure_path.unlink(missing_ok=True)
                acl_ok = True
            return acl_ok and self._fsync_directory(secure_path.parent)
        except Exception:
            logger.exception("기존 브라우저 세션 복원에 실패했습니다.")
            return False
        finally:
            if restore_path is not None:
                try:
                    restore_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def commit_staged_session(self, staged_path: Any) -> bool:
        """Atomically replace the saved session, rolling back every failed commit."""
        if not self._is_valid_staged_session_path(staged_path):
            logger.error("프로필 디렉터리 밖의 후보 브라우저 세션 커밋을 거부했습니다.")
            return False

        candidate = Path(staged_path)
        secure_path = Path(self._get_storage_state_path())
        if not self._ensure_session_directory_acl():
            return False
        try:
            if candidate.is_symlink() or not candidate.is_file():
                return False
            if not secure_file_permissions(candidate):
                return False
            protected_payload = candidate.read_text(encoding="utf-8")
            if not protected_payload.startswith(("dpapi:", "fernet:")):
                return False
            plain_payload = unprotect_secret(protected_payload)
            if not plain_payload:
                return False
            decoded_state = json.loads(plain_payload)
            if not self.is_valid_storage_state(decoded_state):
                return False
            if secure_path.exists():
                if secure_path.is_symlink() or not secure_path.is_file():
                    return False
                if not secure_file_permissions(secure_path):
                    return False
        except Exception:
            logger.warning(
                "후보 브라우저 세션의 암호화 또는 구조 검증에 실패했습니다.",
                exc_info=True,
            )
            return False

        had_previous = secure_path.exists()
        backup_path: Optional[Path] = None
        replaced = False
        committed = False
        rollback_confirmed = False
        try:
            if had_previous:
                backup_path = self._copy_previous_session_for_rollback(secure_path)

            os.replace(candidate, secure_path)
            replaced = True
            if not secure_file_permissions(secure_path):
                raise PermissionError("저장된 브라우저 세션 파일 권한을 보호하지 못했습니다.")
            if not self._fsync_directory(secure_path.parent):
                raise OSError("브라우저 세션 디렉터리를 동기화하지 못했습니다.")
            committed = True
        except Exception:
            logger.exception("암호화된 브라우저 세션 커밋에 실패했습니다.")
            rollback_confirmed = not replaced or self._rollback_session_replace(
                secure_path,
                backup_path,
                had_previous,
            )
            if not rollback_confirmed:
                logger.critical("브라우저 세션 커밋 롤백을 완전히 확인하지 못했습니다.")
            return False
        finally:
            if backup_path is not None and (committed or rollback_confirmed):
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("브라우저 세션 롤백 백업을 삭제하지 못했습니다.")

        if not committed:
            return False

        legacy_path = (
            self.legacy_profile_path / "storage_state.json"
            if self.legacy_profile_path is not None
            else None
        )
        if legacy_path is not None and legacy_path.exists():
            try:
                legacy_path.unlink()
            except OSError:
                logger.warning("레거시 평문 브라우저 세션을 삭제하지 못했습니다.")
        return True

    def discard_staged_session(self, staged_path: Any) -> bool:
        """Delete an uncommitted candidate without touching the saved session."""
        if not self._is_valid_staged_session_path(staged_path):
            return False
        candidate = Path(staged_path)
        try:
            candidate.unlink(missing_ok=True)
            return not candidate.exists()
        except OSError:
            logger.exception("후보 브라우저 세션을 폐기하지 못했습니다.")
            return False

    def _write_storage_state(self, state: Dict[str, Any]) -> bool:
        staged_path: Optional[Path] = None
        try:
            staged_path = self.stage_session(state)
            return self.commit_staged_session(staged_path)
        except Exception:
            logger.exception("암호화된 브라우저 세션을 저장하지 못했습니다.")
            return False
        finally:
            if staged_path is not None:
                self.discard_staged_session(staged_path)

    # ------------------------------------------------------------------ setup
    def _launch_browser(self, channel: Optional[str] = None, executable_path: Optional[str] = None):
        launch_kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        if channel:
            launch_kwargs["channel"] = channel
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        return self.playwright.chromium.launch(**launch_kwargs)

    @staticmethod
    def _candidate_browser_paths() -> List[str]:
        env_candidates = [
            os.getenv("THREAD_AUTO_BROWSER_PATH", "").strip(),
            os.getenv("CHROME_PATH", "").strip(),
        ]
        default_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]

        unique_paths: List[str] = []
        seen: set[str] = set()
        for raw in [*env_candidates, *default_candidates]:
            if not raw:
                continue
            path = Path(raw).expanduser()
            if not path.exists() or not path.is_file():
                continue
            resolved = str(path.resolve())
            lowered = resolved.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique_paths.append(resolved)
        return unique_paths

    @classmethod
    def _iter_browser_candidates(cls) -> List[Dict[str, Optional[str]]]:
        candidates: List[Dict[str, Optional[str]]] = [
            {"channel": "chrome", "executable_path": None, "label": "chrome"},
            {"channel": "msedge", "executable_path": None, "label": "msedge"},
        ]
        for path in cls._candidate_browser_paths():
            candidates.append({"channel": None, "executable_path": path, "label": path})
        candidates.append({"channel": None, "executable_path": None, "label": "chromium"})
        return candidates

    @staticmethod
    def _is_missing_browser_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        markers = (
            "executable doesn't exist",
            "browser executable",
            "ms-playwright",
            "playwright install",
            "failed to launch",
        )
        return any(marker in text for marker in markers)

    @classmethod
    def _install_playwright_chromium(cls) -> bool:
        if getattr(sys, "frozen", False):
            return False

        try:
            completed = run_process(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                operation="playwright.install_chromium",
                process_logger=logger,
                capture_output=True,
                text=True,
                timeout=cls.PLAYWRIGHT_INSTALL_TIMEOUT_SEC,
                check=True,
            )
            stdout_text = str(completed.stdout or "").strip()
            if stdout_text:
                logger.info("Playwright 브라우저 설치 출력: %s", stdout_text[:300])
            return True
        except Exception as exc:
            logger.warning("Playwright 자동 설치에 실패했습니다: error_type=%s", type(exc).__name__)
            return False

    def start_browser(self, *, load_saved_session: Optional[bool] = None):
        """Start a browser context, optionally restoring the verified saved state."""
        if self.context:
            return
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright가 설치되어 있지 않습니다. "
                "먼저 `python3 -m pip install playwright` 실행 후 "
                "`python3 -m playwright install chromium`로 브라우저를 설치하세요."
            ) from _PLAYWRIGHT_IMPORT_ERROR

        self.playwright = sync_playwright().start()
        launch_errors: List[Exception] = []
        browser = None

        for candidate in self._iter_browser_candidates():
            channel = candidate.get("channel")
            executable_path = candidate.get("executable_path")
            label = str(candidate.get("label") or channel or "chromium")
            try:
                browser = self._launch_browser(channel=channel, executable_path=executable_path)
                logger.info("브라우저 실행 성공: %s", label)
                break
            except Exception as exc:
                launch_errors.append(exc)
                logger.warning("브라우저 실행 실패 (%s): error_type=%s", label, type(exc).__name__)

        missing_browser_error = any(self._is_missing_browser_error(err) for err in launch_errors)
        if browser is None and launch_errors and missing_browser_error:
            if self._install_playwright_chromium():
                try:
                    browser = self._launch_browser(channel=None, executable_path=None)
                    logger.info("Playwright Chromium 설치 후 브라우저 실행을 복구했습니다.")
                except Exception as exc:
                    launch_errors.append(exc)

        if browser is None:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

            last_error = launch_errors[-1] if launch_errors else RuntimeError("브라우저 실행 실패")
            hint = (
                "Google Chrome 설치 상태를 확인하고, 개발 환경이면 "
                "`python -m playwright install chromium` 명령을 실행해 주세요."
                if missing_browser_error
                else "브라우저 보안 정책 또는 실행 권한을 확인해 주세요."
            )
            raise RuntimeError(f"브라우저 시작에 실패했습니다. {hint} 원인: {last_error}") from last_error

        self.browser = browser

        context_kwargs: Dict[str, Any] = {
            "viewport": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
        }
        should_load_saved_session = (
            self._load_saved_session_default
            if load_saved_session is None
            else bool(load_saved_session)
        )
        if should_load_saved_session:
            storage_state = self._load_storage_state()
            if storage_state:
                context_kwargs["storage_state"] = storage_state

        self.context = self.browser.new_context(**context_kwargs)

        def _guard_document_navigation(route, request):
            try:
                if request.resource_type == "document" and not self._is_allowed_document_request(request.url):
                    logger.warning("허용되지 않은 문서 이동을 차단했습니다")
                    route.abort()
                    return
            except Exception:
                route.abort()
                return
            route.continue_()

        self.context.route("**/*", _guard_document_navigation)
        self.page = self.context.new_page()

    def save_session(self) -> bool:
        """Persist storage state encrypted at rest."""
        if not self.context:
            return False
        try:
            state = self.capture_session_state()
        except Exception as exc:
            raise RuntimeError(
                "암호화된 브라우저 세션을 저장하지 못했습니다."
            ) from exc
        if not self._write_storage_state(state):
            raise RuntimeError("암호화된 브라우저 세션을 저장하지 못했습니다.")
        return True

    def clear_saved_session(self) -> None:
        """Delete persisted browser session state for this profile."""
        secure_path = Path(self._get_storage_state_path())
        legacy_path = (
            self.legacy_profile_path / "storage_state.json"
            if self.legacy_profile_path is not None
            else None
        )
        for path in (secure_path, legacy_path):
            if path is None:
                continue
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def close(self, *, save_session: bool = True):
        """Close browser resources, optionally persisting verified state."""
        if save_session:
            try:
                self.save_session()
            except Exception:
                pass

        for resource, operation in (
            (self.context, "close"),
            (self.browser, "close"),
            (self.playwright, "stop"),
        ):
            if resource is None:
                continue
            try:
                getattr(resource, operation)()
            except Exception:
                logger.warning("브라우저 리소스 정리에 실패했습니다: %s", operation)
        self.page = None
        self.browser = None
        self.context = None
        self.playwright = None

    # ---------------------------------------------------------- action runner
    @staticmethod
    def _safe_action_args(args: Dict[str, Any]) -> str:
        if not isinstance(args, dict) or not args:
            return ""

        sensitive_keys = {
            "text",
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "authorization",
            "cookie",
        }

        items = []
        for key, value in args.items():
            key_text = str(key)
            if key_text.lower() in sensitive_keys:
                items.append(f"{key_text}=[REDACTED]")
                continue

            if isinstance(value, str):
                preview = value if len(value) <= 60 else value[:57] + "..."
                items.append(f"{key_text}={preview!r}")
            else:
                items.append(f"{key_text}={value!r}")

        return ", ".join(items[:8]) + (" ..." if len(items) > 8 else "")

    def _execute_function_calls(
        self, candidate, page: Page, screen_width: int, screen_height: int
    ) -> List[ExecutedAction]:
        results: List[ExecutedAction] = []
        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if getattr(part, "function_call", None)
        ]

        for fc in function_calls:
            fname = fc.name
            args = fc.args or {}
            extra_fields: Dict[str, Any] = {}
            print(f"  실행: {fname} ({self._safe_action_args(args)})")

            safety = args.get("safety_decision")
            if safety:
                extra_fields["safety_acknowledgement"] = True

            try:
                if fname == "open_web_browser":
                    pass
                elif fname == "wait_5_seconds":
                    time.sleep(5)
                elif fname == "go_back":
                    page.go_back()
                    self._enforce_allowed_page_url(page, fname)
                elif fname == "go_forward":
                    page.go_forward()
                    self._enforce_allowed_page_url(page, fname)
                elif fname == "search":
                    page.goto("https://www.google.com", wait_until="domcontentloaded")
                    self._enforce_allowed_page_url(page, fname)
                elif fname == "navigate":
                    url = args.get("url")
                    if url:
                        if not self._is_allowed_navigation_url(str(url)):
                            raise ValueError(f"허용되지 않은 URL 이동 요청입니다: {url}")
                        page.goto(url, wait_until="domcontentloaded")
                        self._enforce_allowed_page_url(page, fname)
                elif fname == "click_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    page.mouse.click(x, y)
                elif fname == "hover_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    page.mouse.move(x, y)
                elif fname == "type_text_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    text = self._sanitize_type_text(args.get("text", ""))
                    press_enter = bool(args.get("press_enter", False))
                    clear_before = bool(args.get("clear_before_typing", True))
                    page.mouse.click(x, y)
                    if clear_before:
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                    page.keyboard.type(text)
                    if press_enter:
                        page.keyboard.press("Enter")
                elif fname == "key_combination":
                    keys = args.get("keys")
                    if keys:
                        normalized = self._normalize_keys(str(keys))
                        if normalized not in self.ALLOWED_SAFE_KEYS:
                            raise ValueError(f"허용되지 않은 키 조합 요청입니다: {keys}")
                        page.keyboard.press(keys)
                elif fname == "scroll_document":
                    direction = args.get("direction", "down")
                    amount = 1200
                    if direction == "down":
                        page.mouse.wheel(0, amount)
                    elif direction == "up":
                        page.mouse.wheel(0, -amount)
                    elif direction == "left":
                        page.mouse.wheel(-amount, 0)
                    elif direction == "right":
                        page.mouse.wheel(amount, 0)
                elif fname == "scroll_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    direction = args.get("direction", "down")
                    magnitude = int(args.get("magnitude", 800))
                    page.mouse.move(x, y)
                    delta = magnitude if direction in ("down", "right") else -magnitude
                    if direction in ("down", "up"):
                        page.mouse.wheel(0, delta)
                    else:
                        page.mouse.wheel(delta, 0)
                elif fname == "drag_and_drop":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    dx = _denormalize_x(args["destination_x"], screen_width)
                    dy = _denormalize_y(args["destination_y"], screen_height)
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.mouse.move(dx, dy)
                    page.mouse.up()
                else:
                    extra_fields["warning"] = f"Unimplemented function: {fname}"

                page.wait_for_timeout(500)
                page.wait_for_load_state("domcontentloaded")
                self._enforce_allowed_page_url(page, fname)
                time.sleep(0.5)
                results.append(ExecutedAction(fname, extra_fields))
            except Exception as e:
                print(f"  실행 오류 ({fname}): {e}")
                results.append(ExecutedAction(fname, {"error": str(e)}))

        return results

    def _get_function_responses(self, page: Page, results: List[ExecutedAction]):
        screenshot_bytes = page.screenshot(type="png")
        current_url = page.url
        responses = []
        for item in results:
            payload = {"url": current_url}
            payload.update(item.result)
            responses.append(
                types.FunctionResponse(
                    name=item.name,
                    response=payload,
                    parts=[
                        types.FunctionResponsePart(
                            inline_data=types.FunctionResponseBlob(
                                mime_type="image/png", data=screenshot_bytes
                            )
                        )
                    ],
                )
            )
        return responses

    # --------------------------------------------------------------- main loop
    def run_goal(self, goal: str, turn_limit: int = 8, skip_navigation: bool = False):
        if self.client is None:
            print("Google API 클라이언트가 설정되지 않았습니다.")
            return None
        if os.getenv("THREAD_AUTO_ALLOW_AI_SCREENSHOTS", "").strip() != "1":
            print(
                "AI 스크린샷 전송이 비활성화되어 있습니다. "
                "사용하려면 THREAD_AUTO_ALLOW_AI_SCREENSHOTS=1 로 설정하세요."
            )
            return None

        self.start_browser()
        assert self.page

        if not skip_navigation:
            self.page.goto("about:blank")
        initial_screenshot = self.page.screenshot(type="png")

        config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER
                    )
                )
            ],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

        contents: List[Content] = [
            Content(
                role="user",
                parts=[
                    Part(text=goal),
                    Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=initial_screenshot,
                        )
                    ),
                ],
            )
        ]

        for turn in range(turn_limit):
            print(f"\n--- {turn + 1}회차 ---")
            response = self.client.models.generate_content(
                model="gemini-2.5-computer-use-preview-10-2025",
                contents=contents,
                config=config,
            )

            if not response.candidates or len(response.candidates) == 0:
                print("API 응답 후보가 없습니다.")
                return None

            candidate = response.candidates[0]
            contents.append(candidate.content)

            has_fc = any(getattr(p, "function_call", None) for p in candidate.content.parts)
            if not has_fc:
                final_text = " ".join(
                    [p.text for p in candidate.content.parts if getattr(p, "text", None)]
                )
                print(f"작업 완료: {final_text}")
                return final_text

            results = self._execute_function_calls(candidate, self.page, SCREEN_WIDTH, SCREEN_HEIGHT)
            responses = self._get_function_responses(self.page, results)

            contents.append(
                Content(
                    role="user",
                    parts=[Part(function_response=r) for r in responses],
                )
            )

        print("턴 제한에 도달했습니다.")
        return None


def main(argv: List[str]):
    if len(argv) < 2:
        print('사용법: python -m src.computer_use_agent "<목표 텍스트>"')
        sys.exit(1)

    goal = argv[1]
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    agent = ComputerUseAgent(api_key=api_key, headless=False)
    try:
        agent.run_goal(goal)
    finally:
        agent.close()


if __name__ == "__main__":
    main(sys.argv)
