from src.subscription_plans import (
    COMMERCE_SCOPE_COUPANG,
    COMMERCE_SCOPE_MULTI,
    FREE_MONTHLY_USES,
    MONTHLY_PLAN,
    SHOPPING_PRO_FOUNDER_MONTHLY_PLAN,
    SHOPPING_PRO_MONTHLY_PLAN,
    SHOPPING_PRO_WEEKLY_PLAN,
    WEEKLY_PLAN,
    marketplace_access_decision,
    resolve_account_limit,
    resolve_commerce_scope,
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
    assert MONTHLY_PLAN.commerce_scope == COMMERCE_SCOPE_COUPANG
    assert SHOPPING_PRO_WEEKLY_PLAN.price_krw == 29_000
    assert SHOPPING_PRO_WEEKLY_PLAN.account_limit == 3
    assert SHOPPING_PRO_WEEKLY_PLAN.recurring is False
    assert SHOPPING_PRO_MONTHLY_PLAN.price_krw == 69_000
    assert SHOPPING_PRO_MONTHLY_PLAN.account_limit == 10
    assert SHOPPING_PRO_MONTHLY_PLAN.recurring is True
    assert SHOPPING_PRO_FOUNDER_MONTHLY_PLAN.price_krw == 59_000
    assert SHOPPING_PRO_FOUNDER_MONTHLY_PLAN.public is False
    assert SHOPPING_PRO_FOUNDER_MONTHLY_PLAN.promotion_cycles == 6


def test_account_limit_prefers_server_entitlement_and_fails_closed():
    assert resolve_account_limit({}) == 1
    assert resolve_account_limit({"plan_id": WEEKLY_PLAN.plan_id}) == 1
    assert resolve_account_limit({"plan_id": MONTHLY_PLAN.plan_id}) == 10
    assert resolve_account_limit({"plan_id": MONTHLY_PLAN.plan_id, "account_limit": 3}) == 3
    assert resolve_account_limit({"plan_id": SHOPPING_PRO_WEEKLY_PLAN.plan_id}) == 3
    assert resolve_account_limit({"user_type": "admin"}) == 10


def test_commerce_scope_prefers_server_entitlement_and_fails_closed():
    assert resolve_commerce_scope({}) == COMMERCE_SCOPE_COUPANG
    assert resolve_commerce_scope({"plan_id": SHOPPING_PRO_MONTHLY_PLAN.plan_id}) == COMMERCE_SCOPE_MULTI
    assert resolve_commerce_scope({"commerce_scope": "multi"}) == COMMERCE_SCOPE_MULTI
    assert resolve_commerce_scope({"user_type": "admin"}) == COMMERCE_SCOPE_MULTI


def test_marketplace_access_supports_first_free_trial_and_paid_pro():
    naver_url = "https://smartstore.naver.com/main/products/123"
    coupang_url = "https://link.coupang.com/a/example"

    assert marketplace_access_decision({"user_type": "trial", "work_used": 0}, naver_url)[0]
    assert not marketplace_access_decision({"user_type": "trial", "work_used": 1}, naver_url)[0]
    assert marketplace_access_decision({"plan_id": SHOPPING_PRO_MONTHLY_PLAN.plan_id}, naver_url)[0]
    assert marketplace_access_decision({"plan_id": MONTHLY_PLAN.plan_id}, coupang_url)[0]
