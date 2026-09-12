"""Pure display policy shared by the desktop workspaces."""
from datetime import datetime, timedelta
from urllib.parse import urlsplit

ACCOUNT_CHECK_FRESH_FOR = timedelta(hours=24)


def local_datetime(value):
    try:
        result = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return result.astimezone()
    except (ValueError, TypeError, OverflowError):
        return None


def account_health(account, latest=None, now=None):
    now = now or datetime.now().astimezone()
    latest = latest or {}
    state = latest.get('state') or getattr(account, 'last_check_status', '')
    if state == 'pending':
        return '확인 중', 'pending'
    if state == 'error':
        return '재로그인 필요', 'error'
    expected = str(getattr(account, 'expected_username', '')).lstrip('@').lower()
    verified = str(getattr(account, 'last_verified_username', '')).lstrip('@').lower()
    checked = local_datetime(getattr(account, 'last_verified_at', ''))
    if not checked or not verified or verified != expected:
        return '연결 확인 필요', 'warning'
    if now - checked > ACCOUNT_CHECK_FRESH_FOR or checked > now:
        return '확인 오래됨', 'warning'
    return '최근 확인됨', 'success'


def today_metrics(rows, now=None):
    now = now or datetime.now().astimezone()
    today = [row for row in rows if (when := local_datetime(row.get('uploaded_at'))) and when.date() == now.date()]
    success = sum(row.get('result') == '성공' for row in today)
    failed = sum(row.get('result') == '실패' for row in today)
    return {'오늘 완료': success, '오늘 성공률': f'{success * 100 / (success + failed):.1f}%' if success + failed else '집계 전'}


def subscription_details(state, plan):
    """Never infer a charge date from an entitlement's expiry."""
    recurring = bool(getattr(plan, 'recurring', False))
    paid = plan is not None
    expires = local_datetime(state.get('expires_at'))
    billing = local_datetime(state.get('next_billing_at') or state.get('next_payment_at'))
    return {
        'renewal_label': '이용 기간 종료' if recurring else '만료일',
        'renewal_date': expires.strftime('%Y-%m-%d') if expires else '',
        'renewal_empty': '무료 이용 중' if not paid else '이용 기간 정보 미제공 · 결제 관리에서 확인',
        'billing_date': billing.strftime('%Y-%m-%d') if recurring and billing else '',
        'billing_empty': '자동 결제 없음' if not recurring else '다음 결제일 미제공 · 결제 관리에서 확인',
        'payment_method': str(state.get('payment_method_label') or ''),
        'payment_empty': '등록된 결제 없음' if not paid else '결제수단은 결제 관리에서 확인',
    }


def safe_post_url(value):
    try:
        parsed = urlsplit(str(value or ''))
        if parsed.scheme == 'https' and parsed.hostname in {'threads.net', 'www.threads.net', 'threads.com', 'www.threads.com'} and '/post/' in parsed.path:
            return str(value)
    except ValueError:
        pass
    return ''
