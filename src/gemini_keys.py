"""Gemini API key helpers (multi-key normalization and failover selection)."""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_GEMINI_API_KEYS = 10
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
FALLBACK_GEMINI_MODELS = (
    DEFAULT_GEMINI_MODEL,
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)

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

_MODEL_ERROR_MARKERS = (
    "not found",
    "model",
    "unsupported",
    "invalid argument",
    "404",
)


def _get_config():
    from src.config import config

    return config


def get_gemini_model_candidates(preferred: str | Iterable[str] | None = None) -> list[str]:
    """Return ordered Gemini model candidates with env and compatibility fallbacks."""
    raw_values: list[str] = []
    if preferred:
        if isinstance(preferred, str):
            raw_values.extend(preferred.split(","))
        else:
            raw_values.extend(str(item or "") for item in preferred)

    env_value = os.getenv("GOOGLE_GEMINI_MODEL", "")
    if env_value:
        raw_values.extend(env_value.split(","))

    raw_values.extend(FALLBACK_GEMINI_MODELS)

    candidates: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        model = str(raw or "").strip()
        if not model or model in seen:
            continue
        candidates.append(model)
        seen.add(model)
    return candidates


def is_retryable_gemini_model_error(exc: BaseException) -> bool:
    message = str(exc or "").lower()
    return any(marker in message for marker in _MODEL_ERROR_MARKERS)


def generate_content_with_model_fallback(
    client: Any,
    *,
    contents: Any,
    config: Any = None,
    preferred_model: str | Iterable[str] | None = None,
) -> tuple[Any, str]:
    """Generate content using the latest Gemini model alias with stable fallbacks."""
    last_error: BaseException | None = None
    for model in get_gemini_model_candidates(preferred_model):
        try:
            kwargs = {"model": model, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            return client.models.generate_content(**kwargs), model
        except Exception as exc:
            last_error = exc
            if is_retryable_gemini_model_error(exc):
                logger.warning("Gemini 모델 %s 호출 실패, 다음 후보로 재시도합니다: %s", model, exc)
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("사용 가능한 Gemini 모델 후보가 없습니다.")


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
    config = _get_config()
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
    config = _get_config()
    normalized = normalize_gemini_api_keys(keys)
    if hasattr(config, "set_gemini_api_keys"):
        config.set_gemini_api_keys(normalized)
    else:
        config.gemini_api_key = normalized[0] if normalized else ""
    if not config.save():
        config.load()
        raise OSError("Gemini API 키 설정을 저장하지 못했습니다.")
    return normalized


def _classify_probe_error(exc: BaseException) -> Optional[bool]:
    message = str(exc or "").lower()
    if any(marker in message for marker in _KEY_ERROR_MARKERS):
        return False
    if any(marker in message for marker in _NETWORK_ERROR_MARKERS):
        return None
    return False


def _safe_probe_error_message(exc: BaseException) -> str:
    message = str(exc or "").lower()
    if any(marker in message for marker in _NETWORK_ERROR_MARKERS):
        return "네트워크 상태를 확인할 수 없어 API 키 검증을 보류했습니다."
    if any(marker in message for marker in _KEY_ERROR_MARKERS):
        return "API 키가 유효하지 않거나 사용 한도에 도달했습니다."
    return "API 키를 확인하지 못했습니다."


def probe_gemini_api_key(api_key: str) -> Tuple[Optional[bool], str]:
    key = str(api_key or "").strip()
    if len(key) < 10:
        return False, "API 키 형식이 올바르지 않습니다."

    try:
        from google import genai

        client = genai.Client(api_key=key)
        response, _model = generate_content_with_model_fallback(
            client,
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
        return verdict, _safe_probe_error_message(exc)


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
        try:
            save_configured_gemini_api_keys(reordered)
        except OSError:
            logger.exception("Gemini API 키 자동 전환 결과를 저장하지 못했습니다.")
        else:
            logger.warning("Gemini API 키 자동 전환 완료: 기존 1번 키에서 다음 키로 변경")
    return selected
