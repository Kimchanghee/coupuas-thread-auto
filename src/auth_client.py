# -*- coding: utf-8 -*-
"""Auth client for dashboard API."""

import base64
import hashlib
import json
import logging
import os
import re
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env files without overriding existing environment values.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _env_path in [
    _PROJECT_ROOT.parent / "project-user-dashboard" / ".env",
    _PROJECT_ROOT / ".env",
]:
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

API_SERVER_URL = (
    os.getenv("USER_DASHBOARD_API_URL")
    or os.getenv("API_SERVER_URL", "")
).rstrip("/")
PROGRAM_TYPE = "stmaker"

if not API_SERVER_URL:
    logger.warning("API_SERVER_URL is not configured.")

# Credential storage
_CRED_DIR = Path.home() / ".shorts_thread_maker"
_CRED_FILE = _CRED_DIR / "auth.json"
_LOCK = threading.RLock()
_SENSITIVE_CRED_FIELDS = {"token", "remember_pw"}
_MIN_PASSWORD_LENGTH = 8


def _check_api_url() -> Optional[str]:
    if not API_SERVER_URL:
        return "Server URL is not configured. Set API_SERVER_URL in .env."
    if not API_SERVER_URL.startswith(("http://", "https://")):
        return f"Invalid server URL: {API_SERVER_URL}"

    parsed = urlparse(API_SERVER_URL)
    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            return "Only HTTPS API URL is allowed for security."
    return None


def _ensure_cred_dir() -> None:
    _CRED_DIR.mkdir(parents=True, exist_ok=True)


def _protect_secret(value: str) -> Optional[str]:
    if not isinstance(value, str) or not value or value.startswith("dpapi:"):
        return value

    if os.name != "nt":
        return None

    try:
        import ctypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        plain_bytes = value.encode("utf-8")
        in_buffer = ctypes.create_string_buffer(plain_bytes, len(plain_bytes))
        in_blob = DATA_BLOB(
            len(plain_bytes),
            ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        out_blob = DATA_BLOB()

        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "shorts_thread_maker",
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise ctypes.WinError()

        try:
            protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

        return f"dpapi:{base64.b64encode(protected).decode('ascii')}"
    except Exception:
        logger.warning("Failed to protect credential secret")
        return None


def _unprotect_secret(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("dpapi:"):
        return value

    if os.name != "nt":
        return ""

    try:
        import ctypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        encoded = value.split(":", 1)[1]
        protected = base64.b64decode(encoded.encode("ascii"))
        in_buffer = ctypes.create_string_buffer(protected, len(protected))
        in_blob = DATA_BLOB(
            len(protected),
            ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        out_blob = DATA_BLOB()

        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise ctypes.WinError()

        try:
            plain = ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)

        return plain
    except Exception:
        logger.exception("Failed to unprotect credential secret")
        return ""


def _load_cred() -> dict:
    with _LOCK:
        try:
            if _CRED_FILE.exists():
                with open(_CRED_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    for field in _SENSITIVE_CRED_FIELDS:
                        if field in payload:
                            payload[field] = _unprotect_secret(payload.get(field))
                    return payload
        except Exception:
            pass
        return {}


def _save_cred(data: dict) -> None:
    _ensure_cred_dir()
    serialized = dict(data or {})
    for field in _SENSITIVE_CRED_FIELDS:
        if field in serialized:
            protected = _protect_secret(serialized.get(field, ""))
            if protected is None:
                logger.warning("Skipping sensitive credential field '%s' (secure storage unavailable)", field)
                serialized.pop(field, None)
            else:
                serialized[field] = protected

    with _LOCK:
        try:
            with open(_CRED_FILE, "w", encoding="utf-8") as f:
                json.dump(serialized, f, ensure_ascii=False, indent=2)
            try:
                os.chmod(_CRED_FILE, 0o600)
            except OSError:
                pass
        except Exception as e:
            logger.error("Failed to save credentials: %s", e)


def _clear_cred() -> None:
    try:
        if _CRED_FILE.exists():
            _CRED_FILE.unlink()
    except Exception:
        pass


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_password_for_backend(password: str) -> str:
    """
    일부 기존 계정 호환을 위해 짧은 비밀번호는 백엔드 형식으로 확장합니다.
    """
    if not isinstance(password, str):
        password = str(password or "")
    if len(password) >= _MIN_PASSWORD_LENGTH:
        return password
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"spw_{digest[:16]}"


def _localize_message(message: str) -> str:
    if not isinstance(message, str):
        return ""

    text = message.strip()
    if not text:
        return ""

    lower = text.lower()
    if lower == "not logged in":
        return "로그인이 필요합니다."
    if lower == "field required":
        return "필수 항목입니다."

    min_len_match = re.search(r"at least\s+(\d+)\s+characters?", lower)
    if min_len_match:
        return f"최소 {min_len_match.group(1)}자 이상 입력해주세요."

    max_len_match = re.search(r"at most\s+(\d+)\s+characters?", lower)
    if max_len_match:
        return f"최대 {max_len_match.group(1)}자까지 입력 가능합니다."

    if "valid email address" in lower:
        return "올바른 이메일 주소를 입력해주세요."

    if "too many login attempts" in lower or "too many requests" in lower:
        return "요청이 많습니다. 잠시 후 다시 시도해주세요."

    return text


def _extract_validation_message(resp: requests.Response, default_message: str) -> str:
    payload = _safe_json(resp)

    detail_items = []
    if isinstance(payload.get("detail"), list):
        detail_items = payload["detail"]
    else:
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("details"), list):
            detail_items = error["details"]

    if detail_items and isinstance(detail_items[0], dict):
        first = detail_items[0]
        msg = _localize_message(str(first.get("msg", "")).strip())
        loc = first.get("loc")
        loc_text = ""
        if isinstance(loc, list):
            loc_text = ".".join(str(part) for part in loc if part is not None).strip()
        if loc_text and msg:
            return f"입력 오류 ({loc_text}): {msg}"
        if msg:
            return f"입력 오류: {msg}"

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return _localize_message(message.strip())

    error = payload.get("error")
    if isinstance(error, dict):
        error_message = error.get("message")
        if isinstance(error_message, str) and error_message.strip():
            return _localize_message(error_message.strip())

    return _localize_message(default_message)


def _extract_api_message(payload: Dict[str, Any], default_message: str = "") -> str:
    if not isinstance(payload, dict):
        return _localize_message(default_message)

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return _localize_message(message.strip())

    error = payload.get("error")
    if isinstance(error, dict):
        error_message = error.get("message")
        if isinstance(error_message, str) and error_message.strip():
            return _localize_message(error_message.strip())

    return _localize_message(default_message)


def _normalize_api_message(
    *,
    payload: Dict[str, Any],
    status_code: int,
    context: str,
    default_message: str = "",
) -> str:
    message = _extract_api_message(payload, default_message)
    message_lower = message.lower()

    error = payload.get("error") if isinstance(payload, dict) else None
    error_code = ""
    retry_after = ""
    if isinstance(error, dict):
        error_code = str(error.get("code", "")).upper()
        retry_after = str(error.get("retry_after", "")).strip()

    is_rate_limited = (
        status_code == 429
        or error_code == "RATE_LIMIT_ERROR"
        or "too many login attempts" in message_lower
        or "too many requests" in message_lower
    )
    if is_rate_limited:
        base = (
            "요청이 많아 회원가입이 일시 제한되었습니다. 잠시 후 다시 시도해주세요."
            if context == "register"
            else "요청이 많아 로그인이 일시 제한되었습니다. 잠시 후 다시 시도해주세요."
        )
        if retry_after:
            return f"{base} (제한: {retry_after})"
        return base

    return _localize_message(message)


def _resolve_client_ip() -> str:
    env_ip = os.getenv("THREAD_AUTO_CLIENT_IP", "").strip()
    if env_ip:
        return env_ip

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return ip
    except OSError:
        pass

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip:
            return ip
    except OSError:
        pass

    return "127.0.0.1"


_session = requests.Session()
_session.headers.update({
    "Content-Type": "application/json",
    "User-Agent": "ShortsThreadMaker/2.0",
})

_auth_state: Dict[str, Any] = {
    "user_id": None,
    "username": None,
    "token": None,
    "work_count": 0,
    "work_used": 0,
}


def get_auth_state() -> Dict[str, Any]:
    return dict(_auth_state)


def is_logged_in() -> bool:
    return _auth_state.get("token") is not None and _auth_state.get("user_id") is not None


def check_username(username: str) -> Dict[str, Any]:
    err = _check_api_url()
    if err:
        return {"available": False, "message": err}

    username = str(username or "").strip().lower()
    try:
        resp = _session.get(
            f"{API_SERVER_URL}/user/check-username/{username}",
            params={"program_type": PROGRAM_TYPE},
            timeout=5,
        )
        payload = _safe_json(resp)
        if resp.status_code == 200:
            if payload:
                payload.setdefault("available", False)
                payload.setdefault("message", _extract_api_message(payload, "아이디 확인 실패"))
                return payload
            return {"available": False, "message": "아이디 확인 응답이 비었습니다."}
        return {"available": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"available": False, "message": "서버 연결 실패"}
    except Exception as e:
        return {"available": False, "message": f"오류: {str(e)}"}


def register(name: str, username: str, password: str, contact: str, email: str) -> Dict[str, Any]:
    err = _check_api_url()
    if err:
        return {"success": False, "message": err}

    name = str(name or "").strip()
    username = str(username or "").strip().lower()
    password = str(password or "")
    email = str(email or "").strip()

    if len(name) < 2:
        return {"success": False, "message": "이름은 2자 이상 입력해주세요."}
    if len(username) < 4:
        return {"success": False, "message": "아이디는 4자 이상 입력해주세요."}
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return {"success": False, "message": "아이디는 영문/숫자/밑줄만 허용됩니다."}
    if not password:
        return {"success": False, "message": "비밀번호를 입력해주세요."}

    contact_clean = re.sub(r"[^0-9]", "", str(contact or ""))
    if len(contact_clean) < 10:
        return {"success": False, "message": "올바른 연락처를 입력해주세요."}

    backend_password = _normalize_password_for_backend(password)

    body = {
        "name": name,
        "username": username,
        "password": backend_password,
        "contact": contact_clean,
        "email": email if email else None,
        "program_type": PROGRAM_TYPE,
    }

    try:
        resp = _session.post(
            f"{API_SERVER_URL}/user/register/request",
            json=body,
            timeout=30,
        )
        payload = _safe_json(resp)

        if resp.status_code == 200:
            data = payload
            if not data:
                return {"success": False, "message": "회원가입 응답이 비었습니다."}
            if data.get("success") is False and not data.get("message"):
                data["message"] = _normalize_api_message(
                    payload=data,
                    status_code=resp.status_code,
                    context="register",
                    default_message="회원가입에 실패했습니다.",
                )
            if data.get("success"):
                result_data = data.get("data", {})
                token = result_data.get("token")
                user_id = result_data.get("user_id")
                if token and user_id:
                    _auth_state["user_id"] = user_id
                    _auth_state["username"] = username
                    _auth_state["token"] = token
                    _auth_state["work_count"] = result_data.get("work_count", 0)
                    _auth_state["work_used"] = 0
                    _save_cred({
                        "user_id": user_id,
                        "username": _auth_state["username"],
                        "token": token,
                    })
            return data

        if resp.status_code == 422:
            return {
                "success": False,
                "message": _extract_validation_message(resp, "입력값이 올바르지 않습니다."),
            }
        if resp.status_code == 429:
            return {
                "success": False,
                "message": _normalize_api_message(
                    payload=payload,
                    status_code=resp.status_code,
                    context="register",
                    default_message="요청이 많아 회원가입이 제한되었습니다.",
                ),
            }
        return {"success": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "서버 연결에 실패했습니다."}
    except Exception as e:
        logger.exception("Registration error")
        return {"success": False, "message": f"오류 발생: {str(e)}"}


def login(username: str, password: str, force: bool = False) -> Dict[str, Any]:
    err = _check_api_url()
    if err:
        return {"status": False, "message": err}

    username = str(username or "").strip().lower()
    password = str(password or "")
    if not username or not password:
        return {"status": False, "message": "아이디와 비밀번호를 입력해주세요."}

    backend_password = _normalize_password_for_backend(password)

    body = {
        "id": username,
        "pw": backend_password,
        "force": force,
        "ip": _resolve_client_ip(),
        "program_type": PROGRAM_TYPE,
    }

    try:
        resp = _session.post(
            f"{API_SERVER_URL}/user/login/god",
            json=body,
            timeout=15,
        )
        if resp.status_code == 200:
            data = _safe_json(resp)
            if not data:
                return {"status": False, "message": "로그인 응답이 비었습니다."}
            if data.get("status") is True:
                _auth_state["user_id"] = data.get("id")
                _auth_state["username"] = username
                _auth_state["token"] = data.get("key")
                _auth_state["work_count"] = data.get("work_count", 0)
                _auth_state["work_used"] = data.get("work_used", 0)
                _save_cred({
                    "user_id": _auth_state["user_id"],
                    "username": _auth_state["username"],
                    "token": _auth_state["token"],
                })
            elif data.get("status") is False and not data.get("message"):
                data["message"] = _normalize_api_message(
                    payload=data,
                    status_code=resp.status_code,
                    context="login",
                    default_message="로그인에 실패했습니다.",
                )
            return data

        if resp.status_code == 422:
            return {
                "status": False,
                "message": _extract_validation_message(resp, "입력값이 올바르지 않습니다."),
            }
        if resp.status_code == 429:
            payload = _safe_json(resp)
            return {
                "status": False,
                "message": _normalize_api_message(
                    payload=payload,
                    status_code=resp.status_code,
                    context="login",
                    default_message="요청이 많아 로그인이 제한되었습니다.",
                ),
            }
        return {"status": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"status": False, "message": "서버 연결에 실패했습니다."}
    except Exception as e:
        logger.exception("Login error")
        return {"status": False, "message": f"오류: {str(e)}"}


def logout() -> bool:
    user_id = _auth_state.get("user_id")
    token = _auth_state.get("token")

    if user_id and token:
        try:
            _session.post(
                f"{API_SERVER_URL}/user/logout/god",
                json={"id": user_id, "key": token},
                timeout=10,
            )
        except Exception as e:
            logger.warning("Logout API error (ignored): %s", e)

    _auth_state["user_id"] = None
    _auth_state["token"] = None

    cred = _load_cred()
    if cred:
        cred.pop("token", None)
        cred.pop("user_id", None)
        _save_cred(cred)

    return True


def heartbeat(current_task: str = "", app_version: str = "") -> Dict[str, Any]:
    if _check_api_url():
        return {"status": False}

    user_id = _auth_state.get("user_id")
    token = _auth_state.get("token")
    if not user_id or not token:
        return {"status": False, "message": "로그인이 필요합니다."}

    try:
        resp = _session.post(
            f"{API_SERVER_URL}/user/login/god/check",
            json={
                "id": user_id,
                "key": token,
                "current_task": current_task,
                "app_version": app_version,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return _safe_json(resp)
        return {"status": False}
    except Exception:
        return {"status": False}


def check_work_available() -> Dict[str, Any]:
    if _check_api_url():
        return {"success": False}

    user_id = _auth_state.get("user_id")
    token = _auth_state.get("token")
    if not user_id or not token:
        return {"success": False, "message": "로그인이 필요합니다."}

    try:
        resp = _session.post(
            f"{API_SERVER_URL}/user/work/check",
            json={"user_id": user_id, "token": token},
            timeout=10,
        )
        if resp.status_code == 200:
            return _safe_json(resp)
        return {"success": False}
    except Exception:
        return {"success": False}


def use_work() -> Dict[str, Any]:
    if _check_api_url():
        return {"success": False}

    user_id = _auth_state.get("user_id")
    token = _auth_state.get("token")
    if not user_id or not token:
        return {"success": False, "message": "로그인이 필요합니다."}

    try:
        resp = _session.post(
            f"{API_SERVER_URL}/user/work/use",
            json={"user_id": user_id, "token": token},
            timeout=10,
        )
        if resp.status_code == 200:
            data = _safe_json(resp)
            if data.get("success"):
                _auth_state["work_used"] = data.get("work_used", _auth_state["work_used"] + 1)
            return data
        return {"success": False}
    except Exception:
        return {"success": False}


def log_action(action: str, content: str = None, level: str = "INFO") -> None:
    if _check_api_url():
        return
    token = _auth_state.get("token")
    if not token:
        return

    try:
        _session.post(
            f"{API_SERVER_URL}/user/logs",
            json={"level": level, "action": action, "content": content},
            headers={"Authorization": f"Bearer {token}"},
            timeout=2.0,
        )
    except Exception as e:
        logger.debug("Failed to send activity log: %s", e)


def get_saved_credentials() -> Optional[Dict[str, str]]:
    cred = _load_cred()
    return cred if cred.get("username") else None


def friendly_login_message(res: Dict[str, Any]) -> str:
    status = res.get("status")
    msg = res.get("message", "")

    if status is True:
        return "로그인 성공"

    code_messages = {
        "EU001": "아이디 또는 비밀번호가 일치하지 않습니다.",
        "EU002": "계정이 비활성화되었습니다. 관리자에게 문의해주세요.",
        "EU003": "다른 곳에서 이미 로그인되어 있습니다.",
        "EU004": "구독이 만료되었습니다. 관리자에게 문의해주세요.",
        "EU005": "사용 가능한 작업 횟수가 없습니다.",
    }

    if isinstance(status, str) and status in code_messages:
        return code_messages[status]

    return _localize_message(msg) or "로그인에 실패했습니다."
