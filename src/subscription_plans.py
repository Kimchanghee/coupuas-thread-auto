"""Client display metadata for server-enforced subscription plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.services.marketplaces import marketplace_for_url


WEEKLY_PLAN_ID = "stmaker_pro_week"
MONTHLY_PLAN_ID = "stmaker_pro_month"
SHOPPING_PRO_WEEKLY_PLAN_ID = "stmaker_shopping_pro_week"
SHOPPING_PRO_MONTHLY_PLAN_ID = "stmaker_shopping_pro_month"
SHOPPING_PRO_FOUNDER_MONTHLY_PLAN_ID = "stmaker_shopping_pro_founder_month"
FREE_MONTHLY_USES = 5
MAX_THREADS_ACCOUNTS = 10
COMMERCE_SCOPE_COUPANG = "coupang"
COMMERCE_SCOPE_MULTI = "multi"


@dataclass(frozen=True)
class SubscriptionPlan:
    plan_id: str
    label: str
    price_krw: int
    duration_days: int
    account_limit: int
    recurring: bool
    commerce_scope: str
    public: bool = True
    promotion_cycles: int | None = None

    @property
    def is_shopping_pro(self) -> bool:
        return self.commerce_scope == COMMERCE_SCOPE_MULTI


WEEKLY_PLAN = SubscriptionPlan(
    plan_id=WEEKLY_PLAN_ID,
    label="7일 쿠팡",
    price_krw=19_000,
    duration_days=7,
    account_limit=1,
    recurring=False,
    commerce_scope=COMMERCE_SCOPE_COUPANG,
)
SHOPPING_PRO_WEEKLY_PLAN = SubscriptionPlan(
    plan_id=SHOPPING_PRO_WEEKLY_PLAN_ID,
    label="7일 쇼핑 프로",
    price_krw=29_000,
    duration_days=7,
    account_limit=3,
    recurring=False,
    commerce_scope=COMMERCE_SCOPE_MULTI,
)
MONTHLY_PLAN = SubscriptionPlan(
    plan_id=MONTHLY_PLAN_ID,
    label="월간 기본",
    price_krw=49_000,
    duration_days=30,
    account_limit=MAX_THREADS_ACCOUNTS,
    recurring=True,
    commerce_scope=COMMERCE_SCOPE_COUPANG,
)
SHOPPING_PRO_MONTHLY_PLAN = SubscriptionPlan(
    plan_id=SHOPPING_PRO_MONTHLY_PLAN_ID,
    label="월간 쇼핑 프로",
    price_krw=69_000,
    duration_days=30,
    account_limit=MAX_THREADS_ACCOUNTS,
    recurring=True,
    commerce_scope=COMMERCE_SCOPE_MULTI,
)
SHOPPING_PRO_FOUNDER_MONTHLY_PLAN = SubscriptionPlan(
    plan_id=SHOPPING_PRO_FOUNDER_MONTHLY_PLAN_ID,
    label="기존 고객 쇼핑 프로",
    price_krw=59_000,
    duration_days=30,
    account_limit=MAX_THREADS_ACCOUNTS,
    recurring=True,
    commerce_scope=COMMERCE_SCOPE_MULTI,
    public=False,
    promotion_cycles=6,
)

PLANS = {
    plan.plan_id: plan
    for plan in (
        WEEKLY_PLAN,
        SHOPPING_PRO_WEEKLY_PLAN,
        MONTHLY_PLAN,
        SHOPPING_PRO_MONTHLY_PLAN,
        SHOPPING_PRO_FOUNDER_MONTHLY_PLAN,
    )
}
ONE_TIME_PLAN_IDS = frozenset(
    plan.plan_id for plan in PLANS.values() if not plan.recurring
)
RECURRING_PLAN_IDS = frozenset(
    plan.plan_id for plan in PLANS.values() if plan.recurring
)
SHOPPING_PRO_PLAN_IDS = frozenset(
    plan.plan_id for plan in PLANS.values() if plan.is_shopping_pro
)


def get_plan(plan_id: str) -> SubscriptionPlan:
    try:
        return PLANS[str(plan_id)]
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 요금제입니다: {plan_id}") from exc


def resolve_plan(state: Mapping[str, Any] | None) -> SubscriptionPlan | None:
    state = state or {}
    return PLANS.get(str(state.get("plan_id") or state.get("plan_type") or ""))


def resolve_account_limit(state: Mapping[str, Any] | None) -> int:
    state = state or {}
    if str(state.get("user_type") or "").lower() == "admin":
        return MAX_THREADS_ACCOUNTS
    server_limit = state.get("account_limit")
    if isinstance(server_limit, (int, float)) and int(server_limit) >= 1:
        return min(int(server_limit), MAX_THREADS_ACCOUNTS)
    plan = resolve_plan(state)
    return plan.account_limit if plan else 1


def resolve_commerce_scope(state: Mapping[str, Any] | None) -> str:
    state = state or {}
    if str(state.get("user_type") or "").lower() == "admin":
        return COMMERCE_SCOPE_MULTI
    server_scope = str(state.get("commerce_scope") or "").strip().lower()
    if server_scope in {COMMERCE_SCOPE_COUPANG, COMMERCE_SCOPE_MULTI}:
        return server_scope
    plan = resolve_plan(state)
    return plan.commerce_scope if plan else COMMERCE_SCOPE_COUPANG


def marketplace_access_decision(
    state: Mapping[str, Any] | None,
    product_url: str,
) -> tuple[bool, str]:
    """Return an entitlement decision for a supported product URL.

    Free users may use their first successful monthly job to try Shopping Pro.
    The server remains authoritative for paid commerce_scope and work_used.
    """
    marketplace = marketplace_for_url(product_url)
    if marketplace is None:
        return False, "지원하지 않는 상품 링크입니다."
    if marketplace.marketplace_id == "coupang":
        return True, ""

    state = state or {}
    if resolve_commerce_scope(state) == COMMERCE_SCOPE_MULTI:
        return True, ""

    user_type = str(state.get("user_type") or "trial").strip().lower()
    try:
        work_used = int(state.get("work_used") or 0)
    except (TypeError, ValueError):
        work_used = 0
    if user_type in {"trial", "free", ""} and work_used == 0:
        return True, "첫 쇼핑 프로 무료 체험"

    return (
        False,
        f"{marketplace.label} 링크는 쇼핑 프로 이용권에서 사용할 수 있습니다.",
    )
