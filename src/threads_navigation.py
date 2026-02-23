# -*- coding: utf-8 -*-
"""Threads 웹 이동 공통 유틸리티."""

from __future__ import annotations

import os
import time
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urlparse

DEFAULT_THREADS_BASE_URLS: tuple[str, ...] = (
    "https://www.threads.net",
    "https://www.threads.com",
    "https://threads.net",
    "https://threads.com",
)


def _normalize_base_url(raw: str) -> str:
    text = str(raw or "").strip().rstrip("/")
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return ""
    return f"https://{host}"


def _dedupe_keep_order(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_base_url(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def get_threads_base_urls() -> tuple[str, ...]:
    """환경변수/기본값 기준 Threads 접속 후보 도메인 목록."""
    primary = os.getenv("THREAD_AUTO_THREADS_BASE_URL", "")
    extras_raw = os.getenv("THREAD_AUTO_THREADS_BASE_URLS", "")
    extras = [item.strip() for item in extras_raw.split(",") if item.strip()]
    ordered = [primary, *extras, *DEFAULT_THREADS_BASE_URLS]
    return _dedupe_keep_order(ordered) or DEFAULT_THREADS_BASE_URLS


def build_threads_url(base_url: str, path: str = "/") -> str:
    base = _normalize_base_url(base_url)
    raw_path = str(path or "/").strip()
    if not raw_path:
        raw_path = "/"
    if not raw_path.startswith(("/", "?")):
        raw_path = "/" + raw_path
    if raw_path.startswith("?"):
        raw_path = "/" + raw_path
    if raw_path == "/":
        return base
    return f"{base}{raw_path}"


def _short_error_text(error: Any, limit: int = 220) -> str:
    text = " ".join(str(error or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def friendly_threads_navigation_error(detail: str) -> str:
    text = str(detail or "")
    lower = text.lower()

    if (
        "err_http_response_code_failure" in lower
        or "http 500" in lower
        or "status 500" in lower
    ):
        return "Threads 서버가 일시적으로 불안정합니다(HTTP 500). 잠시 후 다시 시도해주세요."
    if "err_name_not_resolved" in lower or "name or service not known" in lower:
        return "Threads 서버 주소를 찾지 못했습니다. 네트워크/DNS 상태를 확인해주세요."
    if "timed out" in lower or "timeout" in lower:
        return "Threads 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."
    if "ssl" in lower or "certificate" in lower:
        return "Threads 보안 연결(SSL/TLS)에 실패했습니다. 네트워크 보안 설정을 확인해주세요."
    if "err_internet_disconnected" in lower:
        return "인터넷 연결이 끊어져 Threads 페이지를 열 수 없습니다."
    return "Threads 페이지를 열지 못했습니다. 잠시 후 다시 시도해주세요."


def is_browser_launch_error(detail: str) -> bool:
    text = str(detail or "").lower()
    markers = (
        "브라우저 시작에 실패했습니다",
        "browser executable",
        "executable doesn't exist",
        "failed to launch",
        "playwright install",
        "ms-playwright",
    )
    return any(marker in text for marker in markers)


def goto_threads_with_fallback(
    page: Any,
    *,
    path: str = "/",
    timeout: int = 15000,
    wait_until: str = "domcontentloaded",
    retries_per_url: int = 1,
    logger: Optional[Any] = None,
) -> str:
    """
    Threads 페이지 접속 시 threads.net/.com 도메인 폴백을 수행한다.
    성공한 최종 URL을 반환하고, 모두 실패하면 RuntimeError를 발생시킨다.
    """
    candidates = [build_threads_url(base, path) for base in get_threads_base_urls()]
    errors: list[str] = []
    max_retry = max(int(retries_per_url), 0)

    for url in candidates:
        for attempt in range(max_retry + 1):
            try:
                response = page.goto(url, wait_until=wait_until, timeout=timeout)
                status = getattr(response, "status", None) if response is not None else None
                if callable(status):
                    status = status()
                if isinstance(status, int) and status >= 500:
                    raise RuntimeError(f"HTTP {status}")
                if logger is not None:
                    logger.info("Threads 접속 성공: %s", url)
                return url
            except Exception as exc:
                short = _short_error_text(exc)
                errors.append(f"{url} -> {short}")
                if logger is not None:
                    logger.debug(
                        "Threads 접속 재시도 (%s/%s): %s (%s)",
                        attempt + 1,
                        max_retry + 1,
                        url,
                        short,
                    )
                if attempt < max_retry:
                    time.sleep(0.4 * (attempt + 1))

    last_error = errors[-1] if errors else "원인을 확인할 수 없습니다."
    if logger is not None:
        logger.warning(
            "Threads 접속 실패: 모든 후보 도메인 시도 후 실패 (%s개 URL, URL당 %s회 시도). 마지막 오류: %s",
            len(candidates),
            max_retry + 1,
            last_error,
        )
    raise RuntimeError(f"Threads 접속 실패: {last_error}")
