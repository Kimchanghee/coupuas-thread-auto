"""Process one durable queue item using an account-specific Threads session."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from src.services.multi_account_coordinator import AccountRunResult
from src.services.thread_payload import build_product_thread_payload


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
            return True
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
        value = str(
            os.getenv("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "") or ""
        ).strip().lower()
        return value in {"1", "true", "yes", "y", "on"}

    def reserve(self) -> QuotaReservation:
        if self._bypass_enabled():
            return QuotaReservation(bypass=True)

        from src import auth_client

        result = auth_client.reserve_work()
        if isinstance(result, dict) and result.get("unsupported"):
            availability = auth_client.check_work_available()
            if not self._allowed(availability):
                message = (
                    availability.get("message", "사용 가능한 작업량이 없습니다.")
                    if isinstance(availability, dict)
                    else "작업량 확인에 실패했습니다."
                )
                raise AccountBlockedError("quota_unavailable", str(message))
            return QuotaReservation(legacy=True)
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

    def _recover_interrupted_current(
        self,
        queue_store,
        history,
        item,
    ) -> Optional[AccountRunResult]:
        stage = str(item.get("stage") or "")
        reservation = self._reservation_from_item(item)
        if stage in {"reserved", "reservation_release_pending"}:
            if self._quota.release(reservation) is not True:
                queue_store.update_current(stage="reservation_release_pending")
                queue_store.set_phase(
                    "blocked",
                    last_error="reservation_release_pending",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="reservation_release_pending",
                )
            queue_store.requeue_current()
            return None
        if stage == "posted_commit_pending":
            committed = False
            try:
                committed = bool(reservation and self._quota.commit(reservation))
            except Exception:
                committed = False
            if committed:
                url = str(item.get("url") or "")
                product_name = str(item.get("product_name") or url)
                queue_store.complete_current("success")
                history.add_link(url, product_name, success=True)
                return AccountRunResult(
                    processed=True,
                    pending_count=self._pending_count(queue_store),
                    success=True,
                )
            queue_store.set_phase(
                "blocked",
                last_error="quota_commit_pending_recovery_failed",
            )
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason="quota_commit_pending",
            )
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
            return AccountRunResult(processed=False, pending_count=0)

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

        try:
            self._log(account_id, "상품 정보와 게시글을 생성하는 중...")
            reset_cancel = getattr(self._pipeline, "reset_cancel", None)
            if callable(reset_cancel):
                reset_cancel()
            post_data = self._pipeline.process_link(url, user_keywords=keyword)
        except Exception as exc:
            from src.coupang_uploader import CancelledException

            if isinstance(exc, CancelledException):
                queue_store.requeue_current()
                self._log(account_id, "중지 요청으로 현재 링크를 대기열에 되돌렸습니다.")
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                )
            queue_store.complete_current("failed", str(exc)[:300])
            self._log(account_id, f"상품 처리 실패: {exc}")
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
        if self._stop_requested(queue_store):
            if reservation is not None:
                self._quota.release(reservation)
            queue_store.requeue_current()
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
                queue_store.requeue_current()
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                )
            if reservation is None:
                reservation = self._quota.reserve()
            queue_store.update_current(
                stage="reserved",
                reservation_id=str(getattr(reservation, "reservation_id", "") or ""),
                reservation_legacy=bool(getattr(reservation, "legacy", False)),
                reservation_bypass=bool(getattr(reservation, "bypass", False)),
                product_name=product_name,
            )
            if self._stop_requested(queue_store):
                if self._quota.release(reservation) is not True:
                    queue_store.update_current(
                        stage="reservation_release_pending"
                    )
                    queue_store.set_phase(
                        "blocked",
                        last_error="reservation_release_pending",
                    )
                    return AccountRunResult(
                        processed=False,
                        pending_count=self._pending_count(queue_store),
                        block_reason="reservation_release_pending",
                    )
                reservation = None
                queue_store.requeue_current()
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
            try:
                quota_committed = self._quota.commit(reservation)
            except Exception:
                quota_committed = False
            if not quota_committed:
                queue_store.set_phase(
                    "blocked",
                    last_error="quota_commit_failed_after_post",
                )
                history.add_link(url, product_name, success=True)
                self._log(
                    account_id,
                    "게시 성공 후 작업량 동기화에 실패해 이 계정만 중단합니다.",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="quota_commit_failed",
                )
            reservation = None
            queue_store.complete_current("success")
            history.add_link(url, product_name, success=True)
            self._log(account_id, f"업로드 성공: {product_name}")
            return AccountRunResult(
                processed=True,
                pending_count=self._pending_count(queue_store),
                success=True,
            )
        except AccountBlockedError as exc:
            if reservation is not None and self._quota.release(reservation) is not True:
                queue_store.update_current(stage="reservation_release_pending")
                queue_store.set_phase(
                    "blocked",
                    last_error="reservation_release_pending",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="reservation_release_pending",
                )
            queue_store.requeue_current()
            queue_store.set_phase("blocked", last_error=str(exc))
            self._log(account_id, str(exc))
            return AccountRunResult(
                processed=False,
                pending_count=self._pending_count(queue_store),
                block_reason=exc.code,
            )
        except Exception as exc:
            current = queue_store.snapshot().get("current_item") or {}
            stage = str(current.get("stage") or "")
            if stage in {"posting", "posting_unknown", "posted_commit_pending"}:
                queue_store.set_phase("blocked", last_error=str(exc)[:300])
                self._log(account_id, f"업로드 오류: {exc}")
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="uncertain_external_post",
                )
            if reservation is not None and self._quota.release(reservation) is not True:
                queue_store.update_current(stage="reservation_release_pending")
                queue_store.set_phase(
                    "blocked",
                    last_error="reservation_release_pending",
                )
                return AccountRunResult(
                    processed=False,
                    pending_count=self._pending_count(queue_store),
                    block_reason="reservation_release_pending",
                )
            queue_store.complete_current("failed", str(exc)[:300])
            history.add_link(url, product_name, success=False)
            self._log(account_id, f"업로드 오류: {exc}")
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
