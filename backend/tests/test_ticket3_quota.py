from __future__ import annotations

from datetime import datetime

from app.core.quota import QuotaManager, daily_key, monthly_key, period_key
from app.models import Account
from app.providers.base import AccountRuntime
from app.security import encrypt_credentials
from app.state import KeyRateLimiter


def make_runtime(account_id: int = 1, **overrides) -> AccountRuntime:
    values = {
        "id": account_id,
        "provider": "baidu",
        "name": "quota",
        "credentials": {},
        "priority": 100,
        "weight": 1,
        "enabled": True,
        "timeout_ms": 8000,
        "max_concurrency": 2,
        "qps_limit": None,
        "quota_daily": None,
        "quota_monthly": None,
        "quota_total": None,
        "reset_day": 1,
    }
    values.update(overrides)
    return AccountRuntime(**values)


def test_daily_key_rolls_at_shanghai_midnight() -> None:
    assert daily_key(datetime(2026, 1, 1, 15, 59)) == "2026-01-01"
    assert daily_key(datetime(2026, 1, 1, 16, 0)) == "2026-01-02"


def test_monthly_key_uses_reset_day() -> None:
    assert monthly_key(datetime(2026, 1, 4, 12, 0), 5) == "2025-12-05"
    assert monthly_key(datetime(2026, 1, 5, 12, 0), 5) == "2026-01-05"
    assert monthly_key(datetime(2026, 1, 31, 12, 0), 5) == "2026-01-05"


def test_period_key_total_is_all() -> None:
    runtime = make_runtime()
    assert period_key(runtime, "total") == "all"


def test_quota_available_and_exhausted() -> None:
    runtime = make_runtime(quota_daily=2)
    quota = QuotaManager()
    assert quota.available(runtime)
    quota.increment(runtime)
    assert quota.available(runtime)
    quota.increment(runtime)
    assert not quota.available(runtime)
    exhausted, pin = quota.exhausted(runtime)
    assert exhausted
    assert pin == daily_key()


def test_total_quota_pins_to_total() -> None:
    runtime = make_runtime(quota_total=1)
    quota = QuotaManager()
    quota.increment(runtime)
    exhausted, pin = quota.exhausted(runtime)
    assert exhausted
    assert pin == "total"


def test_null_quotas_are_unlimited() -> None:
    runtime = make_runtime()
    quota = QuotaManager()
    for _ in range(1000):
        quota.increment(runtime)
    assert quota.available(runtime)


async def test_quota_flush_and_load(app) -> None:
    state = app.state.gw
    runtime = make_runtime(account_id=999)
    async with state.session_factory() as session:
        session.add(
            Account(
                id=999,
                provider="baidu",
                name="quota-owner",
                credentials_enc=encrypt_credentials(b"k" * 32, {}),
            )
        )
        await session.commit()
    state.quota.increment(runtime)
    async with state.session_factory() as session:
        await state.quota.flush(session)
        fresh = QuotaManager()
        await fresh.load(session, [runtime])
    assert fresh.used(runtime, "daily") == 1
    assert fresh.used(runtime, "monthly") == 1
    assert fresh.used(runtime, "total") == 1


def test_rpm_limiter_resets_when_limit_changes() -> None:
    limiter = KeyRateLimiter()
    assert limiter.allow(7, 1, now=0.0)
    assert not limiter.allow(7, 1, now=0.1)
    assert limiter.allow(7, 2, now=0.2)
