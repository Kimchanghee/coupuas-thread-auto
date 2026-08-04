"""Authenticated client for the subscription-included managed AI service."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


DEFAULT_MANAGED_AI_URL = "https://coupuas-thread-auto-three.vercel.app"


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
    def __init__(self, code: str, message: str, *, status_code: int = 0):
        super().__init__(str(message or "AI 서비스 요청에 실패했습니다."))
        self.code = str(code or "MANAGED_AI_ERROR")
        self.status_code = int(status_code or 0)


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
        self.base_url = resolved.rstrip("/")
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

    def generate_variants(self, product_info: Dict[str, Any]) -> ManagedGeneration:
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

        request_id = str(uuid.uuid4())
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
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ManagedAiClientError(
                "INVALID_SERVER_RESPONSE",
                "AI 서버 응답을 확인할 수 없습니다.",
                status_code=response.status_code,
            ) from exc

        if not response.ok or not payload.get("success"):
            raise ManagedAiClientError(
                str(payload.get("code") or "MANAGED_AI_ERROR"),
                str(payload.get("message") or f"AI 서버 오류 ({response.status_code})"),
                status_code=response.status_code,
            )

        reservation_id = str(payload.get("reservation_id") or "").strip()
        raw_variants = payload.get("variants")
        if not reservation_id or not isinstance(raw_variants, list) or len(raw_variants) != 4:
            raise ManagedAiClientError(
                "INVALID_SERVER_RESPONSE",
                "AI 서버가 완성된 작업을 반환하지 못했습니다.",
                status_code=response.status_code,
            )

        variants: List[ManagedVariant] = []
        seen = set()
        for raw in raw_variants:
            if not isinstance(raw, dict):
                raise ManagedAiClientError("INVALID_SERVER_RESPONSE", "AI 문안 형식이 올바르지 않습니다.")
            variant_id = str(raw.get("variant_id") or "").strip()
            root_text = str(raw.get("root_text") or "").strip()
            comment_text = str(raw.get("product_comment_text") or "").strip()
            if not variant_id or variant_id in seen or not root_text or not comment_text:
                raise ManagedAiClientError("INVALID_SERVER_RESPONSE", "AI 문안이 누락되었습니다.")
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
