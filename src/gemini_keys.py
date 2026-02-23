"""Gemini API key helpers (multi-key normalization and failover selection)."""

from __future__ import annotations

import logging
import os
from typing import Iterable, Optional, Tuple

from src.config import config

logger = logging.getLogger(__name__)

MAX_GEMINI_API_KEYS = 10
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

_KEY_ERROR_MARKERS = (
    "invalid api key",
    "api key not valid",
    "api_key_invalid",
    "unauthenticated",
    "permission denied",
    "forbidden",
    "401",
    "403",
    "quota",
    "resource_exhausted",
    "429",
    "revoked",
    "expired",
)

_NETWORK_ERROR_MARKERS = (
    "timed out",
    "timeout",
    "connection",
    "dns",
    "temporary failure",
    "service unavailable",
    "max retries exceeded",
)


def normalize_gemini_api_keys(values: Iterable[str] | str | None) -> list[str]:
    if isinstance(values, str):
        source = [values]
    elif isinstance(values, Iterable):
        source = list(values)
    else:
        source = []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in source:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
        if len(normalized) >= MAX_GEMINI_API_KEYS:
            break
    return normalized


def get_configured_gemini_api_keys() -> list[str]:
    if hasattr(config, "get_gemini_api_keys"):
        keys = normalize_gemini_api_keys(config.get_gemini_api_keys())
    else:
        keys = normalize_gemini_api_keys([getattr(config, "gemini_api_key", "")])
    if not keys:
        single = str(getattr(config, "gemini_api_key", "") or "").strip()
        if single:
            keys = [single]
    return keys


def save_configured_gemini_api_keys(keys: Iterable[str]) -> list[str]:
    normalized = normalize_gemini_api_keys(keys)
    if hasattr(config, "set_gemini_api_keys"):
        config.set_gemini_api_keys(normalized)
    else:
        config.gemini_api_key = normalized[0] if normalized else ""
    config.save()
    return normalized


def _classify_probe_error(exc: BaseException) -> Optional[bool]:
    message = str(exc or "").lower()
    if any(marker in message for marker in _KEY_ERROR_MARKERS):
        return False
    if any(marker in message for marker in _NETWORK_ERROR_MARKERS):
        return None
    return False


def probe_gemini_api_key(api_key: str) -> Tuple[Optional[bool], str]:
    key = str(api_key or "").strip()
    if len(key) < 10:
        return False, "API 키 형식이 올바르지 않습니다."

    model = os.getenv("GOOGLE_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

    try:
        from google import genai

        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents="ping",
        )
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return True, ""
        return True, ""
    except ImportError:
        # If SDK is unavailable, keep the key order and continue without probe.
        return None, "google-genai SDK가 없어 API 키 검증을 건너뜁니다."
    except Exception as exc:
        verdict = _classify_probe_error(exc)
        return verdict, str(exc)


def select_working_gemini_api_key(validate: bool = True) -> str:
    keys = get_configured_gemini_api_keys()
    if not keys:
        return ""
    if not validate:
        return keys[0]

    selected = ""
    selected_reason = ""

    for index, key in enumerate(keys):
        verdict, reason = probe_gemini_api_key(key)
        if verdict is True:
            selected = key
            break
        if verdict is None:
            # Network/unknown state: use current order without forced rotation.
            selected = key
            selected_reason = reason
            break
        logger.warning("Gemini API 키 %d 검증 실패: %s", index + 1, reason)

    if not selected:
        return ""

    if selected_reason:
        logger.info("Gemini API 키 검증 보류: %s", selected_reason)

    if selected != keys[0]:
        reordered = [selected] + [k for k in keys if k != selected]
        save_configured_gemini_api_keys(reordered)
        logger.warning("Gemini API 키 자동 전환 완료: 기존 1번 키에서 다음 키로 변경")
    return selected
