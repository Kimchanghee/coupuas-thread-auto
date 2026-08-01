"""Client-side display metadata for server-enforced subscription plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


WEEKLY_PLAN_ID = "stmaker_pro_week"
MONTHLY_PLAN_ID = "stmaker_pro_month"
FREE_MONTHLY_USES = 5
MAX_THREADS_ACCOUNTS = 10


@dataclass(frozen=True)
class SubscriptionPlan:
    plan_id: str
    label: str
    price_krw: int
    duration_days: int
    account_limit: int
    recurring: bool


WEEKLY_PLAN = SubscriptionPlan(
    plan_id=WEEKLY_PLAN_ID,
    label="7일 이용권",
    price_krw=19_000,
    duration_days=7,
    account_limit=1,
    recurring=False,
)
MONTHLY_PLAN = SubscriptionPlan(
    plan_id=MONTHLY_PLAN_ID,
    label="월 정기권",
    price_krw=49_000,
    duration_days=30,
    account_limit=MAX_THREADS_ACCOUNTS,
    recurring=True,
)
PLANS = {WEEKLY_PLAN_ID: WEEKLY_PLAN, MONTHLY_PLAN_ID: MONTHLY_PLAN}


def get_plan(plan_id: str) -> SubscriptionPlan:
    try:
        return PLANS[str(plan_id)]
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 요금제입니다: {plan_id}") from exc


def resolve_account_limit(state: Mapping[str, Any] | None) -> int:
    state = state or {}
    if str(state.get("user_type") or "").lower() == "admin":
        return MAX_THREADS_ACCOUNTS
    server_limit = state.get("account_limit")
    if isinstance(server_limit, (int, float)) and int(server_limit) >= 1:
        return min(int(server_limit), MAX_THREADS_ACCOUNTS)
    plan = PLANS.get(str(state.get("plan_id") or state.get("plan_type") or ""))
    return plan.account_limit if plan else 1
