from src.subscription_plans import (
    FREE_MONTHLY_USES,
    MONTHLY_PLAN,
    WEEKLY_PLAN,
    resolve_account_limit,
)


def test_public_plan_contract():
    assert FREE_MONTHLY_USES == 5
    assert WEEKLY_PLAN.price_krw == 19_000
    assert WEEKLY_PLAN.duration_days == 7
    assert WEEKLY_PLAN.account_limit == 1
    assert WEEKLY_PLAN.recurring is False
    assert MONTHLY_PLAN.price_krw == 49_000
    assert MONTHLY_PLAN.account_limit == 10
    assert MONTHLY_PLAN.recurring is True


def test_account_limit_prefers_server_entitlement_and_fails_closed():
    assert resolve_account_limit({}) == 1
    assert resolve_account_limit({"plan_id": WEEKLY_PLAN.plan_id}) == 1
    assert resolve_account_limit({"plan_id": MONTHLY_PLAN.plan_id}) == 10
    assert resolve_account_limit({"plan_id": MONTHLY_PLAN.plan_id, "account_limit": 3}) == 3
    assert resolve_account_limit({"user_type": "admin"}) == 10
