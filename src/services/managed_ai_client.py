"""Authenticated client for the subscription-included managed AI service."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


DEFAULT_MANAGED_AI_URL = "https://coupuas-thread-auto-ten.vercel.app"
_ALLOWED_MANAGED_AI_HOSTS = frozenset({"coupuas-thread-auto-ten.vercel.app"})


def _trusted_managed_ai_base_url(value: str) -> str:
    """Return an owned HTTPS origin before attaching a login token."""
    candidate = str(value or DEFAULT_MANAGED_AI_URL).strip().rstrip("/")
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").strip().lower()
    if (
        parsed.scheme != "https"
        or host not in _ALLOWED_MANAGED_AI_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Managed AI service URL is not trusted")
    return f"https://{host}"


@dataclass(frozen=True)
class ManagedVariant:
    variant_id: str
    root_text: str
    product_comment_text: str


@dataclass(frozen=True)
class ManagedGeneration:
    ai_job_id: str
    reservation_id: str
    quota_mode: str
    prompt_version: str
    model: str
    degraded: bool
    degraded_reason: str
    variants: tuple[ManagedVariant, ...]


class ManagedAiClientError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 0,
        reservation_release_pending: bool = False,
        reservation_id: str = "",
        ai_job_id: str = "",
        retry_with_new_idempotency_key: bool = False,
    ):
        super().__init__(str(message or "AI 서비스 요청에 실패했습니다."))
        self.code = str(code or "MANAGED_AI_ERROR")
        self.status_code = int(status_code or 0)
        self.reservation_id = self._safe_reconciliation_id(reservation_id)
        self.ai_job_id = self._safe_reconciliation_id(ai_job_id)
        self.reservation_release_pending = bool(
            reservation_release_pending or self.reservation_id
        )
        self.retry_with_new_idempotency_key = bool(
            retry_with_new_idempotency_key
            and not self.reservation_release_pending
            and not self.reservation_id
        )

    @staticmethod
    def _safe_reconciliation_id(value: object) -> str:
        """Keep opaque IDs only; never retain arbitrary response payloads."""
        text = str(value or "").strip()
        if not text or len(text) > 256:
            return ""
        if any(ord(char) < 0x21 or ord(char) > 0x7E for char in text):
            return ""
        return text


class ManagedAiClient:
    """Call the Vercel service with the current application login token."""

    def __init__(
        self,
        base_url: str = "",
        *,
        session: Optional[requests.Session] = None,
        timeout: float = 50.0,
    ) -> None:
        resolved = str(
            base_url
            or os.getenv("THREAD_AUTO_MANAGED_AI_URL", "")
            or DEFAULT_MANAGED_AI_URL
        ).strip()
        self.base_url = _trusted_managed_ai_base_url(resolved)
        self._session = session or requests.Session()
        self.timeout = float(timeout)

    @staticmethod
    def _auth_state() -> Dict[str, Any]:
        from src import auth_client

        return auth_client.get_auth_state()

    @staticmethod
    def _normalize_features(product_info: Dict[str, Any]) -> List[str]:
        candidates: List[Any] = []
        for key in ("features", "product_features", "highlights"):
            value = product_info.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, str):
                candidates.extend(value.splitlines())
        normalized: List[str] = []
        for value in candidates:
            text = " ".join(str(value or "").split()).strip()
            if text and text not in normalized:
                normalized.append(text[:240])
            if len(normalized) >= 12:
                break
        return normalized

    def generate_variants(
        self,
        product_info: Dict[str, Any],
        *,
        idempotency_key: str = "",
    ) -> ManagedGeneration:
        state = self._auth_state()
        token = str(state.get("token") or "").strip()
        user_id = str(state.get("user_id") or "").strip()
        if not token or not user_id:
            raise ManagedAiClientError("AUTH_REQUIRED", "로그인 후 다시 시도해주세요.", status_code=401)

        title = str(
            product_info.get("title")
            or product_info.get("product_title")
            or ""
        ).strip()
        url = str(product_info.get("original_url") or product_info.get("url") or "").strip()
        keywords = str(product_info.get("search_keywords") or product_info.get("keywords") or "").strip()
        if not title or not url:
            raise ManagedAiClientError(
                "INVALID_PRODUCT_FACTS",
                "상품명과 상품 링크가 필요합니다.",
                status_code=422,
            )

        request_id = str(idempotency_key or uuid.uuid4()).strip()
        body = {
            "user_id": user_id,
            "product": {
                "title": title[:300],
                "url": url[:1000],
                "marketplace": str(product_info.get("marketplace") or "")[:40],
                "keywords": keywords[:500],
                "features": self._normalize_features(product_info),
            },
            "generation": {
                "locale": "ko-KR",
                "concept": str(product_info.get("post_concept") or "problem_solution"),
            },
            "client": {
                "app_version": str(os.getenv("THREAD_AUTO_APP_VERSION", "desktop")),
                "schema_version": 1,
            },
        }
        try:
            response = self._session.post(
                f"{self.base_url}/api/ai/thread-variants",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": request_id,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ManagedAiClientError(
                "AI_TEMPORARILY_UNAVAILABLE",
                "AI 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.",
                reservation_release_pending=True,
                ai_job_id=request_id,
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ManagedAiClientError(
                "INVALID_SERVER_RESPONSE",
                "AI 서버 응답을 확인할 수 없습니다.",
                status_code=response.status_code,
                reservation_release_pending=True,
                ai_job_id=request_id,
            ) from exc

        if not isinstance(payload, dict):
            raise ManagedAiClientError(
                "INVALID_SERVER_RESPONSE",
                "AI 서버 응답을 확인할 수 없습니다.",
                status_code=response.status_code,
                reservation_release_pending=True,
                ai_job_id=request_id,
            )

        reservation_id = ManagedAiClientError._safe_reconciliation_id(
            payload.get("reservation_id")
        )
        ai_job_id = ManagedAiClientError._safe_reconciliation_id(
            payload.get("ai_job_id")
        )
        retry_with_new_key = bool(
            payload.get("retry_with_new_idempotency_key") is True
            and payload.get("reservation_release_pending") is not True
            and not reservation_id
        )
        uncertain_status = response.status_code in {408, 409, 425, 429} or (
            response.status_code >= 500
        )
        release_pending = bool(
            payload.get("reservation_release_pending")
            or reservation_id
            or (uncertain_status and not retry_with_new_key)
        )

        def invalid_response(message: str) -> ManagedAiClientError:
            return ManagedAiClientError(
                "INVALID_SERVER_RESPONSE",
                message,
                status_code=response.status_code,
                reservation_release_pending=True,
                reservation_id=reservation_id,
                ai_job_id=ai_job_id or request_id,
            )

        if not response.ok or not payload.get("success"):
            raise ManagedAiClientError(
                str(payload.get("code") or "MANAGED_AI_ERROR"),
                str(payload.get("message") or f"AI 서버 오류 ({response.status_code})"),
                status_code=response.status_code,
                reservation_release_pending=release_pending,
                reservation_id=reservation_id,
                ai_job_id=ai_job_id or (request_id if release_pending else ""),
                retry_with_new_idempotency_key=retry_with_new_key,
            )

        raw_variants = payload.get("variants")
        if not reservation_id or not isinstance(raw_variants, list) or len(raw_variants) != 4:
            raise invalid_response(
                "AI 서버가 완성된 작업을 반환하지 못했습니다."
            )

        variants: List[ManagedVariant] = []
        seen = set()
        for raw in raw_variants:
            if not isinstance(raw, dict):
                raise invalid_response("AI 문안 형식이 올바르지 않습니다.")
            variant_id = str(raw.get("variant_id") or "").strip()
            root_text = str(raw.get("root_text") or "").strip()
            comment_text = str(raw.get("product_comment_text") or "").strip()
            if not variant_id or variant_id in seen or not root_text or not comment_text:
                raise invalid_response("AI 문안이 누락되었습니다.")
            seen.add(variant_id)
            variants.append(
                ManagedVariant(
                    variant_id=variant_id,
                    root_text=root_text,
                    product_comment_text=comment_text,
                )
            )

        return ManagedGeneration(
            ai_job_id=str(payload.get("ai_job_id") or request_id),
            reservation_id=reservation_id,
            quota_mode=str(payload.get("quota_mode") or "reservation").strip(),
            prompt_version=str(payload.get("prompt_version") or ""),
            model=str(payload.get("model") or "managed"),
            degraded=bool(payload.get("degraded")),
            degraded_reason=str(payload.get("degraded_reason") or "").strip(),
            variants=tuple(variants),
        )
