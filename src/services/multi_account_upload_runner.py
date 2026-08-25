"""Process one durable queue item using an account-specific Threads session."""

from __future__ import annotations

import hashlib
import inspect
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from src.services.multi_account_coordinator import AccountRunResult
from src.services.thread_payload import build_product_thread_payload
from src.runtime_security import development_quota_bypass_enabled
from src.services.retry_policy import (
    MAX_TRANSIENT_RETRIES,
    is_transient_error,
    retry_delay_seconds,
)


class AccountBlockedError(RuntimeError):
    """Raised when an account needs user action before uploads may continue."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "blocked")


@dataclass
class QuotaReservation:
    reservation_id: str = ""
    legacy: bool = False
    bypass: bool = False


class AuthQuotaAdapter:
    """Preserve the existing reserve/commit/release billing contract."""

    @staticmethod
    def _allowed(result) -> bool:
        if not isinstance(result, dict):
            return False
        if result.get("unsupported"):
            return False
        if "available" in result:
            return bool(result.get("available"))
        if "allowed" in result:
            return bool(result.get("allowed"))
        if "success" in result:
            return bool(result.get("success"))
        if "status" in result:
            return bool(result.get("status"))
        return False

    @staticmethod
    def _bypass_enabled() -> bool:
        return development_quota_bypass_enabled()

    def reserve(self, idempotency_key: str | None = None) -> QuotaReservation:
        if self._bypass_enabled():
            return QuotaReservation(bypass=True)

        from src import auth_client

        result = auth_client.reserve_work(idempotency_key)
        if isinstance(result, dict) and result.get("unsupported"):
            raise AccountBlockedError(
                "quota_reservation_unsupported",
                "안전한 작업 예약 기능을 사용할 수 없어 업로드를 중단합니다.",
            )
        if not self._allowed(result):
            message = (
                result.get("message", "사용 가능한 작업량이 없습니다.")
                if isinstance(result, dict)
                else "작업량 확인에 실패했습니다."
            )
            raise AccountBlockedError("quota_unavailable", str(message))
        reservation_id = str(
            result.get("reservation_id")
            or result.get("reserve_id")
            or result.get("work_token")
            or ""
        ).strip()
        if not reservation_id:
            raise AccountBlockedError(
                "quota_reservation_missing",
                "작업 예약 ID가 없어 안전상 업로드를 중단합니다.",
            )
        return QuotaReservation(reservation_id=reservation_id)

    def recover(self, idempotency_key: str) -> Optional[QuotaReservation]:
        """Return a replayed or freshly created reconciliation reservation.

        The idempotent reserve endpoint is not lookup-only.  If the original
        request never arrived, this call can create a fresh reservation; the
        caller must receive it as well so it can be released immediately.
        """
        from src import auth_client

        result = auth_client.reserve_work(idempotency_key)
        if not isinstance(result, dict) or result.get("unsupported"):
            return None
        reservation_id = str(
            result.get("reservation_id")
            or result.get("reserve_id")
            or result.get("work_token")
            or ""
        ).strip()
        is_replay = str(result.get("code") or "") == "IDEMPOTENCY_REPLAY"
        if is_replay and str(result.get("reservation_status") or "").lower() != "reserved":
            return None
        if not reservation_id:
            return None
        return QuotaReservation(reservation_id=reservation_id)

    def commit(self, reservation: QuotaReservation) -> bool:
        if reservation.bypass:
            return True
        from src import auth_client

        if reservation.legacy:
            result = auth_client.use_work()
        else:
            result = auth_client.commit_reserved_work(reservation.reservation_id)
        return self._allowed(result)

    def release(self, reservation: Optional[QuotaReservation]) -> bool:
        if (
            reservation is None
            or reservation.bypass
            or reservation.legacy
            or not reservation.reservation_id
        ):
            return True
        from src import auth_client

        result = auth_client.release_reserved_work(reservation.reservation_id)
        return self._allowed(result)


class MultiAccountUploadRunner:
    """Bridge durable account queues to the existing parser and Threads helper."""

    def __init__(
        self,
        *,
        account_resolver: Callable[[str], object],
        queue_resolver: Callable[[str], object],
        history_resolver: Callable[[str], object],
        pipeline,
        browser_factory: Optional[Callable[..., object]] = None,
        helper_factory: Optional[Callable[[object], object]] = None,
        navigator: Optional[Callable[[object], None]] = None,
        quota_adapter: Optional[object] = None,
        log: Optional[Callable[[str, str], None]] = None,
    ):
        self._account_resolver = account_resolver
        self._queue_resolver = queue_resolver
        self._history_resolver = history_resolver
        self._pipeline = pipeline
        self._browser_factory = browser_factory or self._default_browser_factory
        self._helper_factory = helper_factory or self._default_helper_factory
        self._navigator = navigator or self._default_navigator
        self._quota = quota_adapter or AuthQuotaAdapter()
        self._log_callback = log

    @staticmethod
    def _default_browser_factory(*, profile_id: str):
        from src.computer_use_agent import ComputerUseAgent

        return ComputerUseAgent(
            api_key="dummy-key-for-session-setup",
            headless=False,
            profile_dir=profile_id,
        )

    @staticmethod
    def _default_helper_factory(page):
        from src.threads_playwright_helper import ThreadsPlaywrightHelper

        return ThreadsPlaywrightHelper(page)

    @staticmethod
    def _default_navigator(page) -> None:
        from src.threads_navigation import goto_threads_with_fallback

        goto_threads_with_fallback(
            page,
            path="/",
            timeout=15000,
            retries_per_url=1,
        )

    def _log(self, account_id: str, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(account_id, str(message or ""))

    @staticmethod
    def _pending_count(queue_store) -> int:
        state = queue_store.snapshot()
        return len(state.get("pending_items") or []) + (
            1 if state.get("current_item") else 0
        )

    @staticmethod
    def _stop_requested(queue_store) -> bool:
        return bool(queue_store.snapshot().get("stop_requested"))

    def _process_pipeline_link(
        self,
        url: str,
        keyword: Optional[str],
        idempotency_key: str,
    ):
        """Pass the durable key when the pipeline supports the new contract."""
        kwargs = {"user_keywords": keyword}
        try:
            parameters = inspect.signature(self._pipeline.process_link).parameters
            if "idempotency_key" in parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            ):
                kwargs["idempotency_key"] = idempotency_key
        except (TypeError, ValueError):
            # Compatibility with opaque/native callables. The built-in
            # pipeline always exposes the explicit keyword.
            pass
        return self._pipeline.process_link(url, **kwargs)

    @staticmethod
    def _reservation_from_item(item) -> Optional[QuotaReservation]:
        reservation_id = str(item.get("reservation_id") or "")
        legacy = bool(item.get("reservation_legacy"))
        bypass = bool(item.get("reservation_bypass"))
        if not reservation_id and not legacy and not bypass:
            return None
        return QuotaReservation(
            reservation_id=reservation_id,
            legacy=legacy,
            bypass=bypass,
        )

    @staticmethod
    def _persist_reservation(queue_store, reservation, product_name: str) -> None:
        """Durably record a reservation before any further external work."""
        queue_store.update_current(
            stage="reserved",
            reservation_id=str(getattr(reservation, "reservation_id", "") or ""),
            reservation_legacy=bool(getattr(reservation, "legacy", False)),
            reservation_bypass=bool(getattr(reservation, "bypass", False)),
            product_name=product_name,
        )

    def _release_reservation(self, queue_store, reservation) -> bool:
        """Release a reservation or leave enough state for safe recovery."""
        if reservation is None:
            return True
        try:
            released = self._quota.release(reservation) is True
        except Exception:
            released = False
        if released:
            return True
        self._persist_reservation(
            queue_store,
            reservation,
            str((queue_store.snapshot().get("current_item") or {}).get("product_name") or ""),
        )
        queue_store.update_current(stage="reservation_release_pending")
        queue_store.set_phase(
            "blocked",
            last_error="reservation_release_pending",
        )
        return False

    def _release_pending_result(self, queue_store) -> AccountRunResult:
        return AccountRunResult(
            processed=False,
            pending_count=self._pending_count(queue_store),
            block_reason="reservation_release_pending",
        )

    def _recover_replayed_reservation(self, item) -> Optional[QuotaReservation]:
        recover = getattr(self._quota, "recover", None)
        idempotency_key = str(item.get("idempotency_key") or "").strip()
        if not callable(recover) or not idempotency_key:
            return None
        try:
            reservation = recover(idempotency_key)
        except Exception:
            return None
        if not isinstance(reservation, QuotaReservation):
            return None
        return reservation if reservation.reservation_id else None

    @staticmethod
    def _rotate_idempotency_and_requeue(queue_store) -> None:
        """Start a new logical attempt after a conclusive non-post release."""
        queue_store.update_current(
            stage="requeue_pending",
            idempotency_key=uuid.uuid4().hex,
        )
        queue_store.requeue_current()

    def _complete_history_pending(
        self,
        queue_store,
        history,
        item,
    ) -> AccountRunResult:
        """Persist duplicate protection before removing the durable queue item."""
        url = str(item.get("url") or "")
        product_name = str(item.get("product_name") or url)
        try:
            history.add_link(url, product_name, success=True)
        except Exception:
            queue_store.set_phase("blocked", last_error="history_write_pending")
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="history_write_pending",
            )
        try:
            queue_store.complete_current("success")
        except Exception:
            queue_store.set_phase("blocked", last_error="queue_completion_pending")
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="history_write_pending",
            )
        return AccountRunResult(
            processed=True,
            pending_count=self._pending_count(queue_store),
            success=True,
        )

    def _recover_interrupted_current(
        self,
        queue_store,
        history,
        item,
    ) -> Optional[AccountRunResult]:
        stage = str(item.get("stage") or "")
        reservation = self._reservation_from_item(item)
        if stage == "requeue_pending":
            queue_store.requeue_current()
            return None
        if stage in {"reserved", "reservation_release_pending"}:
            if (
                stage == "reservation_release_pending"
                and reservation is None
                and item.get("reconciliation_lookup_pending")
            ):
                reservation = self._recover_replayed_reservation(item)
                if reservation is None:
                    queue_store.set_phase(
                        "blocked",
                        last_error="reservation_release_pending",
                    )
                    return self._release_pending_result(queue_store)
                self._persist_reservation(
                    queue_store,
                    reservation,
                    str(item.get("product_name") or ""),
                )
                queue_store.update_current(
                    stage="reservation_release_pending",
                    reconciliation_lookup_pending=False,
                )
            if not self._release_reservation(queue_store, reservation):
                return self._release_pending_result(queue_store)
            retry_count = int(item.get("retry_count", 0) or 0)
            if retry_count > MAX_TRANSIENT_RETRIES:
                queue_store.complete_current(
                    "failed",
                    "managed_ai_retry_exhausted",
                )
                return AccountRunResult(
                    processed=True,
                    pending_count=self._pending_count(queue_store),
                )
            if str(item.get("resolution") or "") == "not_posted":
                next_key = str(item.get("next_idempotency_key") or "").strip()
                if not next_key:
                    next_key = uuid.uuid4().hex
                queue_store.update_current(
                    stage="requeue_pending",
                    idempotency_key=next_key,
                    reservation_id="",
                    reservation_legacy=False,
                    reservation_bypass=False,
                )
                queue_store.requeue_current()
            else:
                self._rotate_idempotency_and_requeue(queue_store)
            return None
        if stage == "posted_commit_pending":
            committed = reservation is None
            try:
                if reservation is not None:
                    committed = bool(self._quota.commit(reservation))
            except Exception:
                committed = False
            if committed:
                queue_store.update_current(
                    stage="history_write_pending",
                    reservation_id="",
                    reservation_legacy=False,
                    reservation_bypass=False,
                )
                current = queue_store.snapshot().get("current_item") or item
                return self._complete_history_pending(queue_store, history, current)
            queue_store.set_phase(
                "blocked",
                last_error="quota_commit_pending_recovery_failed",
            )
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="quota_commit_pending",
            )
        if stage == "history_write_pending":
            return self._complete_history_pending(queue_store, history, item)
        if stage in {"posting", "posting_unknown"}:
            queue_store.set_phase(
                "blocked",
                last_error="uncertain_external_post_requires_review",
            )
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="uncertain_external_post",
            )
        queue_store.requeue_current()
        return None

    def resolve_posting_unknown(
        self,
        account_id: str,
        resolution: str,
    ) -> AccountRunResult:
        """Durably resolve an externally ambiguous Threads post."""
        choice = str(resolution or "").strip().lower()
        if choice not in {"posted", "not_posted", "later"}:
            raise ValueError("resolution must be posted, not_posted, or later")

        queue_store = self._queue_resolver(account_id)
        history = self._history_resolver(account_id)
        item = queue_store.snapshot().get("current_item")
        if not isinstance(item, dict) or str(item.get("stage") or "") not in {
            "posting",
            "posting_unknown",
        }:
            raise ValueError("account has no ambiguous posting item")

        if choice == "later":
            queue_store.set_phase(
                "blocked",
                last_error="uncertain_external_post_requires_review",
            )
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="uncertain_external_post",
            )

        if choice == "posted":
            queue_store.update_current(
                stage="posted_commit_pending",
                resolution="posted",
            )
            current = queue_store.snapshot().get("current_item") or item
            result = self._recover_interrupted_current(
                queue_store,
                history,
                current,
            )
            if result is None:
                raise RuntimeError("posted resolution did not reach a durable state")
            return result

        next_key = str(item.get("next_idempotency_key") or "").strip()
        if not next_key:
            next_key = uuid.uuid4().hex
        queue_store.update_current(
            stage="reservation_release_pending",
            resolution="not_posted",
            next_idempotency_key=next_key,
        )
        current = queue_store.snapshot().get("current_item") or item
        reservation = self._reservation_from_item(current)
        if not self._release_reservation(queue_store, reservation):
            return self._release_pending_result(queue_store)
        queue_store.update_current(
            stage="requeue_pending",
            idempotency_key=next_key,
            reservation_id="",
            reservation_legacy=False,
            reservation_bypass=False,
        )
        queue_store.requeue_current()
        return AccountRunResult(
            processed=False,
            pending_count=self._pending_count(queue_store),
        )

    def process_one(self, account_id: str) -> AccountRunResult:
        account = self._account_resolver(account_id)
        if account is None:
            raise AccountBlockedError("account_missing", "Threads 계정을 찾을 수 없습니다.")

        queue_store = self._queue_resolver(account_id)
        history = self._history_resolver(account_id)
        existing_item = queue_store.snapshot().get("current_item")
        if isinstance(existing_item, dict):
            recovery = self._recover_interrupted_current(
                queue_store,
                history,
                existing_item,
            )
            if recovery is not None:
                return recovery
        item = queue_store.reserve_next()
        if item is None:
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
            )

        url = str(item.get("url") or "").strip()
        keyword = str(item.get("keyword") or item.get("title") or "").strip() or None
        if not url:
            queue_store.complete_current("failed", "empty_url")
            return AccountRunResult(
                processed=True,
                pending_count=self._pending_count(queue_store),
            )

        if history.is_uploaded(url):
            queue_store.complete_current("skipped")
            self._log(account_id, f"중복 링크 건너뜀: {url}")
            return AccountRunResult(
                processed=True,
                pending_count=self._pending_count(queue_store),
                success=True,
            )

        item_id = str(item.get("item_id") or "").strip()
        idempotency_key = str(item.get("idempotency_key") or "").strip()
        if not idempotency_key:
            idempotency_key = hashlib.sha256(
                f"{account_id}|{item_id}|{url}".encode("utf-8")
            ).hexdigest()
            queue_store.update_current(idempotency_key=idempotency_key)

        try:
            self._log(account_id, "상품 정보와 게시글을 생성하는 중...")
            reset_cancel = getattr(self._pipeline, "reset_cancel", None)
            if callable(reset_cancel):
                reset_cancel()
            post_data = self._process_pipeline_link(
                url,
                keyword,
                idempotency_key,
            )
        except Exception as exc:
            from src.coupang_uploader import CancelledException

            if isinstance(exc, CancelledException):
                queue_store.requeue_current()
                self._log(account_id, "중지 요청으로 현재 링크를 대기열에 되돌렸습니다.")
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                )
            retry_with_new_key = bool(
                getattr(exc, "retry_with_new_idempotency_key", False)
                and not getattr(exc, "reservation_release_pending", False)
                and not str(getattr(exc, "reservation_id", "") or "").strip()
            )
            if retry_with_new_key:
                retry_count = int(item.get("retry_count", 0) or 0) + 1
                if retry_count > MAX_TRANSIENT_RETRIES:
                    queue_store.complete_current(
                        "failed",
                        "managed_ai_retry_exhausted",
                    )
                    return AccountRunResult(
                        processed=True,
                        pending_count=self._pending_count(queue_store),
                    )
                queue_store.update_current(
                    stage="requeue_pending",
                    idempotency_key=uuid.uuid4().hex,
                    retry_count=retry_count,
                )
                queue_store.requeue_current()
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    next_allowed_at=time.time() + retry_delay_seconds(retry_count),
                )
            if bool(getattr(exc, "reservation_release_pending", False)):
                retry_count = int(item.get("retry_count", 0) or 0) + 1
                reservation_id = str(
                    getattr(exc, "reservation_id", "") or ""
                ).strip()
                ai_job_id = str(getattr(exc, "ai_job_id", "") or "").strip()
                queue_store.update_current(
                    stage="reservation_release_pending",
                    reservation_id=reservation_id,
                    reservation_legacy=False,
                    reservation_bypass=False,
                    reconciliation_lookup_pending=not bool(reservation_id),
                    ai_job_id=ai_job_id,
                    retry_count=retry_count,
                )
                queue_store.set_phase(
                    "blocked",
                    last_error="reservation_release_pending",
                )
                current = queue_store.snapshot().get("current_item") or item
                recovery = self._recover_interrupted_current(
                    queue_store,
                    history,
                    current,
                )
                if recovery is not None:
                    return recovery
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    next_allowed_at=time.time() + retry_delay_seconds(1),
                )
            retry_count = int(item.get("retry_count", 0) or 0) + 1
            if is_transient_error(exc) and retry_count <= MAX_TRANSIENT_RETRIES:
                delay = retry_delay_seconds(retry_count)
                queue_store.update_current(
                    retry_count=retry_count,
                    last_retry_error=str(exc)[:300],
                )
                queue_store.requeue_current()
                self._log(
                    account_id,
                    f"일시적인 연결 문제로 {delay}초 후 다시 시도합니다. "
                    f"({retry_count}/{MAX_TRANSIENT_RETRIES})",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    next_allowed_at=time.time() + delay,
                )
            queue_store.complete_current("failed", str(exc)[:300])
            self._log(
                account_id,
                "상품 정보를 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
            )
            return AccountRunResult(
                processed=True,
                pending_count=self._pending_count(queue_store),
            )

        product_name = str(
            (post_data or {}).get("product_title")
            or (post_data or {}).get("title")
            or keyword
            or url
        )
        managed_reservation_id = str(
            (post_data or {}).get("managed_ai_reservation_id") or ""
        ).strip()
        managed_quota_mode = str(
            (post_data or {}).get("managed_ai_quota_mode") or "reservation"
        ).strip().lower()
        reservation = (
            QuotaReservation(
                reservation_id=managed_reservation_id,
                legacy=managed_quota_mode == "legacy",
            )
            if managed_reservation_id
            else None
        )
        if reservation is not None:
            self._persist_reservation(queue_store, reservation, product_name)
        if self._stop_requested(queue_store):
            if not self._release_reservation(queue_store, reservation):
                return self._release_pending_result(queue_store)
            self._rotate_idempotency_and_requeue(queue_store)
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
            )
        agent = None
        try:
            agent = self._browser_factory(profile_id=account.profile_id)
            agent.start_browser()
            self._navigator(agent.page)
            helper = self._helper_factory(agent.page)

            if not helper.check_login_status():
                raise AccountBlockedError(
                    "login_required",
                    "Threads 로그인이 필요합니다.",
                )
            if not helper.verify_account(account.expected_username):
                raise AccountBlockedError(
                    "account_mismatch",
                    f"설정된 @{account.expected_username} 계정과 로그인 계정이 다릅니다.",
                )

            if self._stop_requested(queue_store):
                if not self._release_reservation(queue_store, reservation):
                    return self._release_pending_result(queue_store)
                self._rotate_idempotency_and_requeue(queue_store)
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                )
            if reservation is None:
                if isinstance(self._quota, AuthQuotaAdapter):
                    reservation = self._quota.reserve(idempotency_key)
                else:
                    reservation = self._quota.reserve()
            self._persist_reservation(queue_store, reservation, product_name)
            if self._stop_requested(queue_store):
                if not self._release_reservation(queue_store, reservation):
                    return self._release_pending_result(queue_store)
                reservation = None
                self._rotate_idempotency_and_requeue(queue_store)
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                )
            payload = build_product_thread_payload(post_data)
            self._log(account_id, f"Threads 업로드 중: {product_name}")
            queue_store.update_current(stage="posting")
            if not helper.create_thread_direct(payload):
                helper_error = str(getattr(helper, "last_error", "") or "upload_failed")
                queue_store.update_current(stage="posting_unknown")
                queue_store.set_phase("blocked", last_error=helper_error[:300])
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="uncertain_external_post",
                )

            queue_store.update_current(stage="posted_commit_pending")
            recovery = self._recover_interrupted_current(
                queue_store,
                history,
                queue_store.snapshot().get("current_item") or item,
            )
            if recovery is None:
                raise RuntimeError("posted item recovery did not complete")
            if not recovery.success:
                self._log(
                    account_id,
                    "게시 성공 후 안전한 상태 동기화에 실패해 이 계정만 중단합니다.",
                )
                return recovery
            reservation = None
            self._log(account_id, f"업로드 성공: {product_name}")
            return recovery
        except AccountBlockedError as exc:
            if not self._release_reservation(queue_store, reservation):
                return self._release_pending_result(queue_store)
            self._rotate_idempotency_and_requeue(queue_store)
            queue_store.set_phase("blocked", last_error=str(exc))
            self._log(
                account_id,
                "이 계정의 작업을 계속하려면 설정을 확인해주세요.",
            )
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason=exc.code,
            )
        except Exception as exc:
            current = queue_store.snapshot().get("current_item") or {}
            stage = str(current.get("stage") or "")
            if stage in {"posting", "posting_unknown"}:
                queue_store.set_phase("blocked", last_error=str(exc)[:300])
                self._log(
                    account_id,
                    "게시 결과를 확인하지 못했습니다. Threads에서 게시 여부를 확인해주세요.",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="uncertain_external_post",
                )
            if stage == "posted_commit_pending":
                queue_store.set_phase("blocked", last_error=str(exc)[:300])
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="quota_commit_pending",
                )
            if stage == "history_write_pending":
                queue_store.set_phase("blocked", last_error=str(exc)[:300])
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="history_write_pending",
                )
            if not self._release_reservation(queue_store, reservation):
                return self._release_pending_result(queue_store)
            queue_store.complete_current("failed", str(exc)[:300])
            history.add_link(url, product_name, success=False)
            self._log(
                account_id,
                "게시글 업로드에 실패했습니다. 로그인 상태와 네트워크를 확인해주세요.",
            )
            return AccountRunResult(
                processed=True,
                pending_count=self._pending_count(queue_store),
            )
        finally:
            if agent is not None:
                try:
                    agent.save_session()
                except Exception:
                    pass
                try:
                    agent.close()
                except Exception:
                    pass
