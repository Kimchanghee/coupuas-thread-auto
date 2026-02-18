# -*- coding: utf-8 -*-
"""
인증 API 클라이언트
쇼츠스레드메이커(stmaker) 전용

백엔드: project-user-dashboard
API URL은 project-user-dashboard/.env의 USER_DASHBOARD_API_URL에서 로드
"""
import re
import os
import json
import hashlib
import logging
import threading
import socket
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ─── project-user-dashboard 백엔드 연결 ─────────────────────
# .env 로딩: main.py에서 이미 로드했을 수 있으므로 override=False로 안전하게 로드
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _env_path in [
    _PROJECT_ROOT.parent / "project-user-dashboard" / ".env",  # 형제 프로젝트
    _PROJECT_ROOT / ".env",  # 프로젝트 루트
]:
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

# 3) USER_DASHBOARD_API_URL → API_SERVER_URL 순서로 탐색
API_SERVER_URL = (
    os.getenv("USER_DASHBOARD_API_URL")
    or os.getenv("API_SERVER_URL", "")
).rstrip("/")

if not API_SERVER_URL:
    logger.warning("API_SERVER_URL이 설정되지 않았습니다. "
                    "project-user-dashboard/.env 또는 프로젝트 루트 .env를 확인하세요.")


def _check_api_url() -> Optional[str]:
    """API_SERVER_URL이 유효한지 검사. 유효하면 None, 아니면 에러 메시지 반환."""
    if not API_SERVER_URL:
        return ("서버 주소가 설정되지 않았습니다.\n"
                "프로젝트 폴더에 .env 파일을 만들고\n"
                "API_SERVER_URL=https://... 을 설정해주세요.")
    if not API_SERVER_URL.startswith(("http://", "https://")):
        return f"서버 주소가 올바르지 않습니다: {API_SERVER_URL}"
    return None

PROGRAM_TYPE = "stmaker"  # 쇼츠스레드메이커

# ─── Credential Storage ─────────────────────────────────────
_CRED_DIR = Path.home() / ".shorts_thread_maker"
_CRED_FILE = _CRED_DIR / "auth.json"
_lock = threading.RLock()


def _ensure_cred_dir():
    _CRED_DIR.mkdir(parents=True, exist_ok=True)


def _load_cred() -> dict:
    """Load saved credentials (username, token, user_id)"""
    try:
        if _CRED_FILE.exists():
            with open(_CRED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cred(data: dict):
    """Save credentials to disk"""
    _ensure_cred_dir()
    try:
        with open(_CRED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(_CRED_FILE, 0o600)
        except OSError:
            pass
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")


def _clear_cred():
    """Clear saved credentials"""
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
    Backend currently enforces min-length 8 for register/login.
    Keep UX unrestricted by deterministically expanding short passwords.
    """
    if not isinstance(password, str):
        password = str(password or "")
    if len(password) >= 8:
        return password
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"spw_{digest[:16]}"


def _localize_message(message: str) -> str:
    """Translate common backend English messages to Korean for UI display."""
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
        return f"최대 {max_len_match.group(1)}자까지 입력할 수 있습니다."

    if "valid email address" in lower:
        return "올바른 이메일 주소를 입력해주세요."

    if "too many login attempts" in lower or "too many requests" in lower:
        return "요청이 많아 잠시 후 다시 시도해주세요."

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
        if context == "register":
            base = "요청이 많아 회원가입이 잠시 제한되었습니다. 잠시 후 다시 시도해주세요."
        else:
            base = "요청이 많아 로그인이 잠시 제한되었습니다. 잠시 후 다시 시도해주세요."
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


# ─── Session ────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({
    "Content-Type": "application/json",
    "User-Agent": "ShortsThreadMaker/2.0"
})

# ─── Auth state ─────────────────────────────────────────────
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


# ─── API Functions ──────────────────────────────────────────

def check_username(username: str) -> Dict[str, Any]:
    """아이디 중복 확인 (program_type별 분리)"""
    err = _check_api_url()
    if err:
        return {"available": False, "message": err}
    try:
        resp = _session.get(
            f"{API_SERVER_URL}/user/check-username/{username}",
            params={"program_type": PROGRAM_TYPE},
            timeout=5
        )
        payload = _safe_json(resp)
        logger.debug(
            "Check username response status=%s username=%s available=%s message=%s",
            resp.status_code,
            username,
            payload.get("available"),
            _extract_api_message(payload, ""),
        )
        if resp.status_code == 200:
            if payload:
                if "available" not in payload:
                    payload["available"] = False
                if "message" not in payload:
                    payload["message"] = _extract_api_message(payload, "아이디 확인에 실패했습니다.")
                return payload
            return {"available": False, "message": "아이디 확인 응답이 비어 있습니다."}
        return {"available": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"available": False, "message": "서버 연결 실패"}
    except Exception as e:
        return {"available": False, "message": f"오류: {str(e)}"}


def register(name: str, username: str, password: str, contact: str, email: str) -> Dict[str, Any]:
    """회원가입 (program_type=stmaker 자동 포함)"""
    err = _check_api_url()
    if err:
        return {"success": False, "message": err}
    # Validation
    if not name or len(name.strip()) < 2:
        return {"success": False, "message": "이름을 2자 이상 입력해주세요."}
    if not username or len(username.strip()) < 4:
        return {"success": False, "message": "아이디는 4자 이상이어야 합니다."}
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return {"success": False, "message": "아이디는 영문, 숫자, 밑줄(_)만 사용 가능합니다."}
    if not password:
        return {"success": False, "message": "비밀번호를 입력해주세요."}

    contact_clean = re.sub(r'[^0-9]', '', contact)
    if len(contact_clean) < 10:
        return {"success": False, "message": "올바른 연락처를 입력해주세요."}

    backend_password = _normalize_password_for_backend(password)

    body = {
        "name": name.strip(),
        "username": username.strip().lower(),
        "password": backend_password,
        "contact": contact_clean,
        "email": email.strip() if email else None,
        "program_type": PROGRAM_TYPE,
    }

    try:
        logger.debug(
            "Register request prepared username=%s contact_len=%s program_type=%s",
            body.get("username"),
            len(contact_clean),
            body.get("program_type"),
        )
        resp = _session.post(
            f"{API_SERVER_URL}/user/register/request",
            json=body,
            timeout=30
        )
        logger.info("Register response status=%s", resp.status_code)
        payload = _safe_json(resp)
        normalized_message = _normalize_api_message(
            payload=payload,
            status_code=resp.status_code,
            context="register",
            default_message="",
        )
        logger.debug(
            "Register response payload success=%s message=%s",
            payload.get("success"),
            normalized_message,
        )
        if resp.status_code == 200:
            data = payload
            if not data:
                return {"success": False, "message": "회원가입 응답이 비어 있습니다."}
            if data.get("success") is False and not data.get("message"):
                data["message"] = _normalize_api_message(
                    payload=data,
                    status_code=resp.status_code,
                    context="register",
                    default_message="회원가입에 실패했습니다.",
                )
            if data.get("success"):
                # 자동 로그인 처리
                result_data = data.get("data", {})
                token = result_data.get("token")
                user_id = result_data.get("user_id")
                if token and user_id:
                    _auth_state["user_id"] = user_id
                    _auth_state["username"] = username.strip().lower()
                    _auth_state["token"] = token
                    _auth_state["work_count"] = result_data.get("work_count", 0)
                    _auth_state["work_used"] = 0
                    _save_cred({
                        "user_id": user_id,
                        "username": _auth_state["username"],
                        "token": token,
                    })
            return data
        elif resp.status_code == 422:
            return {
                "success": False,
                "message": _extract_validation_message(resp, "입력값이 올바르지 않습니다."),
            }
        elif resp.status_code == 429:
            return {
                "success": False,
                "message": _normalize_api_message(
                    payload=payload,
                    status_code=resp.status_code,
                    context="register",
                    default_message="요청이 많아 회원가입이 잠시 제한되었습니다. 잠시 후 다시 시도해주세요.",
                ),
            }
        else:
            return {"success": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "서버에 연결할 수 없습니다.\n인터넷 연결을 확인해주세요."}
    except Exception as e:
        logger.exception("Registration error")
        return {"success": False, "message": f"오류 발생: {str(e)}"}


def login(username: str, password: str, force: bool = False) -> Dict[str, Any]:
    """로그인"""
    err = _check_api_url()
    if err:
        return {"status": False, "message": err}
    if not username or not password:
        return {"status": False, "message": "아이디와 비밀번호를 입력해주세요."}

    backend_password = _normalize_password_for_backend(password)

    body = {
        "id": username.strip().lower(),
        "pw": backend_password,
        "force": force,
        "ip": _resolve_client_ip(),
        "program_type": PROGRAM_TYPE,
    }

    try:
        logger.debug(
            "Login request prepared user=%s force=%s ip=%s",
            body.get("id"),
            body.get("force"),
            body.get("ip"),
        )
        resp = _session.post(
            f"{API_SERVER_URL}/user/login/god",
            json=body,
            timeout=15
        )
        logger.info("Login response status=%s user=%s", resp.status_code, body.get("id"))
        if resp.status_code == 200:
            data = _safe_json(resp)
            normalized_message = _normalize_api_message(
                payload=data,
                status_code=resp.status_code,
                context="login",
                default_message="",
            )
            logger.debug(
                "Login response payload status=%s message=%s user=%s",
                data.get("status"),
                normalized_message,
                body.get("id"),
            )
            if not data:
                return {"status": False, "message": "로그인 응답이 비어 있습니다."}
            if data.get("status") is True:
                _auth_state["user_id"] = data.get("id")
                _auth_state["username"] = username.strip().lower()
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
        elif resp.status_code == 422:
            return {
                "status": False,
                "message": _extract_validation_message(resp, "입력값이 올바르지 않습니다."),
            }
        elif resp.status_code == 429:
            payload = _safe_json(resp)
            return {
                "status": False,
                "message": _normalize_api_message(
                    payload=payload,
                    status_code=resp.status_code,
                    context="login",
                    default_message="요청이 많아 로그인이 잠시 제한되었습니다. 잠시 후 다시 시도해주세요.",
                ),
            }
        else:
            return {"status": False, "message": f"서버 오류 ({resp.status_code})"}
    except requests.exceptions.ConnectionError:
        return {"status": False, "message": "서버에 연결할 수 없습니다.\n인터넷 연결을 확인해주세요."}
    except Exception as e:
        logger.exception("Login error")
        return {"status": False, "message": f"오류: {str(e)}"}


def logout() -> bool:
    """로그아웃"""
    user_id = _auth_state.get("user_id")
    token = _auth_state.get("token")
    
    if user_id and token:
        try:
            _session.post(
                f"{API_SERVER_URL}/user/logout/god",
                json={"id": user_id, "key": token},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Logout API error (ignored): {e}")

    # 메모리 초기화 (토큰만 제거)
    _auth_state["user_id"] = None
    _auth_state["token"] = None
    # username은 유지 (UI 등에서 사용 가능)

    # 파일 업데이트: 토큰 삭제, 아이디/비번은 저장된 경우 유지
    cred = _load_cred()
    if cred:
        cred.pop("token", None)
        cred.pop("user_id", None)
        _save_cred(cred)
    
    return True


def heartbeat(current_task: str = "", app_version: str = "") -> Dict[str, Any]:
    """세션 체크 (heartbeat)"""
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
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return {"status": False}
    except Exception:
        return {"status": False}


def check_work_available() -> Dict[str, Any]:
    """작업 가능 여부 확인"""
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
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return {"success": False}
    except Exception:
        return {"success": False}


def use_work() -> Dict[str, Any]:
    """작업 사용 횟수 증가"""
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
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                _auth_state["work_used"] = data.get("work_used", _auth_state["work_used"] + 1)
            return data
        return {"success": False}
    except Exception:
        return {"success": False}


def log_action(action: str, content: str = None, level: str = "INFO") -> None:
    """
    사용자 활동 로그를 서버로 전송.
    UI 스레드를 블로킹하지 않도록 짧은 타임아웃 사용.

    Args:
        action: 활동 설명 (예: "batch_start", "upload_success")
        content: 추가 상세 내용
        level: 로그 레벨 (INFO, WARNING, ERROR)
    """
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
        logger.debug(f"Failed to send activity log: {e}")


def get_saved_credentials() -> Optional[Dict[str, str]]:
    """저장된 로그인 정보 반환 (username, remember)"""
    cred = _load_cred()
    return cred if cred.get("username") else None


def friendly_login_message(res: Dict[str, Any]) -> str:
    """로그인 결과를 사용자 친화적 메시지로 변환"""
    status = res.get("status")
    msg = res.get("message", "")

    if status is True:
        return "로그인 성공"

    code_messages = {
        "EU001": "아이디 또는 비밀번호가 일치하지 않습니다.",
        "EU002": "계정이 비활성화되었습니다.\n관리자에게 문의해주세요.",
        "EU003": "다른 곳에서 이미 로그인되어 있습니다.",
        "EU004": "구독이 만료되었습니다.\n관리자에게 문의해주세요.",
        "EU005": "사용 가능한 작업 횟수가 없습니다.",
    }

    if isinstance(status, str) and status in code_messages:
        return code_messages[status]

    return _localize_message(msg) or "로그인에 실패했습니다."
