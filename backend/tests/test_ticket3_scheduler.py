from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from app.core.quota import QuotaManager
from app.core.registry import AccountRegistry
from app.core.scheduler import (
    DeadlineExceeded,
    NoCandidate,
    Scheduler,
    UpstreamFailed,
)
from app.db import utcnow
from app.models import Account
from app.providers.base import (
    AccountRuntime,
    ErrorKind,
    InputError,
    Line,
    ProviderResult,
    RetryableError,
)
from app.security import encrypt_credentials

MASTER_KEY = b"k" * 32


def make_account_model(account_id: int = 1, **overrides) -> Account:
    values = {
        "id": account_id,
        "provider": "baidu",
        "name": f"account-{account_id}",
        "owner_id": None,
        "credentials_enc": encrypt_credentials(
            MASTER_KEY, {"app_id": "1", "api_key": "AK", "secret_key": "SK"}
        ),
        "priority": 100,
        "weight": 1,
        "enabled": True,
        "timeout_ms": 8000,
        "max_concurrency": 2,
        "qps_limit": None,
        "quota_daily": None,
        "quota_monthly": None,
        "quota_total": None,
        "quota_unit": "image",
        "reset_day": 1,
        "state": "active",
        "cooldown_until": None,
        "last_error_code": None,
        "last_error_message": None,
        "ewma_latency_ms": 1000.0,
        "last_used_at": None,
    }
    values.update(overrides)
    return Account(**values)


def make_registry(*accounts: Account) -> AccountRegistry:
    registry = AccountRegistry(MASTER_KEY)
    registry.load(list(accounts))
    return registry


def make_runtime(account_id: int = 1, **overrides) -> AccountRuntime:
    values = {
        "id": account_id,
        "provider": "baidu",
        "name": f"runtime-{account_id}",
        "credentials": {"app_id": "1", "api_key": "AK", "secret_key": "SK"},
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


class FakeAdapter:
    provider = "baidu"

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[int] = []

    async def recognize(self, account, image, language, timeout):
        self.calls.append(account.id)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def invalidate(self, account_id: int) -> None:
        return None


def test_provider_filter_and_priority_sorting() -> None:
    registry = make_registry(
        make_account_model(1, priority=100, ewma_latency_ms=300),
        make_account_model(2, priority=10, ewma_latency_ms=900),
        make_account_model(3, provider="tencent", priority=1),
    )
    quota = QuotaManager()
    candidates = registry.candidates("auto", quota)
    assert [account.id for account in candidates] == [3, 2, 1]
    baidu_only = registry.candidates("baidu", quota)
    assert [account.id for account in baidu_only] == [2, 1]


def test_sorting_uses_ewma_last_used_and_weight() -> None:
    registry = make_registry(
        make_account_model(1, ewma_latency_ms=300),
        make_account_model(2, ewma_latency_ms=900),
    )
    quota = QuotaManager()
    assert [account.id for account in registry.candidates("auto", quota)] == [1, 2]

    registry = make_registry(
        make_account_model(1, ewma_latency_ms=300, last_used_at=datetime(2020, 1, 1)),
        make_account_model(2, ewma_latency_ms=300, last_used_at=datetime(2021, 1, 1)),
    )
    assert [account.id for account in registry.candidates("auto", quota)] == [1, 2]

    registry = make_registry(
        make_account_model(1, ewma_latency_ms=300, weight=1),
        make_account_model(2, ewma_latency_ms=300, weight=5),
    )
    assert [account.id for account in registry.candidates("auto", quota)] == [2, 1]


def test_cooling_accounts_are_excluded_and_recover_lazily() -> None:
    registry = make_registry(
        make_account_model(1, state="cooling", cooldown_until=utcnow() + timedelta(seconds=60))
    )
    quota = QuotaManager()
    assert registry.candidates("auto", quota) == []

    runtime = registry.get(1)
    assert runtime is not None
    runtime.cooldown_until = utcnow() - timedelta(seconds=1)
    candidates = registry.candidates("auto", quota)
    assert [account.id for account in candidates] == [1]
    assert runtime.state == "active"


def test_concurrency_limit_excludes_account() -> None:
    registry = make_registry(make_account_model(1, max_concurrency=2))
    quota = QuotaManager()
    runtime = registry.get(1)
    assert runtime is not None
    runtime.in_flight = 2
    assert registry.candidates("auto", quota) == []
    assert registry.acquire(runtime) is False


def test_quota_exhaustion_excludes_account() -> None:
    registry = make_registry(make_account_model(1, quota_daily=1))
    quota = QuotaManager()
    runtime = registry.get(1)
    assert runtime is not None
    quota.increment(runtime)
    assert registry.candidates("auto", quota) == []
    assert runtime.state == "quota_exhausted"


def test_qps_bucket_excludes_account() -> None:
    registry = make_registry(make_account_model(1, qps_limit=1))
    quota = QuotaManager()
    runtime = registry.get(1)
    assert runtime is not None
    runtime.tokens = 0.0
    runtime.last_refill = time.monotonic()
    assert registry.candidates("auto", quota) == []
    runtime.tokens = 1.0
    assert [account.id for account in registry.candidates("auto", quota)] == [1]


def test_ewma_updates_on_success() -> None:
    registry = make_registry(make_account_model(1, ewma_latency_ms=1000.0))
    runtime = registry.get(1)
    assert runtime is not None
    registry.mark_success(runtime, 500.0, utcnow())
    assert runtime.ewma_latency_ms == pytest.approx(900.0)


def test_failure_marks_account_state() -> None:
    registry = make_registry(make_account_model(1))
    runtime = registry.get(1)
    assert runtime is not None
    registry.mark_failure(runtime, ErrorKind.AUTH_FAILED, "bad", None, utcnow())
    assert runtime.state == "invalid"
    registry.mark_failure(runtime, ErrorKind.PROVIDER_ERROR, "5xx", None, utcnow())
    assert runtime.state == "cooling"
    registry.mark_failure(runtime, ErrorKind.QUOTA_EXCEEDED, "quota", None, utcnow())
    assert runtime.state == "quota_exhausted"


def _deadline(seconds: float = 20.0) -> float:
    """Absolute monotonic budget as computed by the public endpoint (R-SCH-03)."""
    return time.monotonic() + seconds


def _result(text: str = "ok") -> ProviderResult:
    return ProviderResult(provider="baidu", text=text, lines=[Line(text=text)])


async def test_scheduler_switches_on_retryable_error() -> None:
    registry = make_registry(make_account_model(1), make_account_model(2))
    quota = QuotaManager()
    adapter = FakeAdapter(
        [
            RetryableError(ErrorKind.PROVIDER_ERROR, "server error"),
            _result("second"),
        ]
    )
    scheduler = Scheduler(registry, quota, {"baidu": adapter})
    result = await scheduler.recognize("baidu", b"img", "zh", _deadline())
    assert adapter.calls == [1, 2]
    assert result.account_id == 2
    assert result.text == "second"


async def test_scheduler_input_error_does_not_switch() -> None:
    registry = make_registry(make_account_model(1), make_account_model(2))
    quota = QuotaManager()
    adapter = FakeAdapter([InputError("bad image")])
    scheduler = Scheduler(registry, quota, {"baidu": adapter})
    with pytest.raises(InputError):
        await scheduler.recognize("baidu", b"img", "zh", _deadline())
    assert adapter.calls == [1]


async def test_scheduler_all_provider_errors_return_502() -> None:
    registry = make_registry(make_account_model(1))
    quota = QuotaManager()
    adapter = FakeAdapter(
        [RetryableError(ErrorKind.PROVIDER_ERROR, "server error")]
    )
    scheduler = Scheduler(registry, quota, {"baidu": adapter})
    with pytest.raises(UpstreamFailed) as raised:
        await scheduler.recognize("baidu", b"img", "zh", _deadline())
    assert raised.value.status_code == 502


async def test_scheduler_no_candidate_returns_503() -> None:
    registry = make_registry()
    scheduler = Scheduler(registry, QuotaManager(), {"baidu": FakeAdapter([])})
    with pytest.raises(NoCandidate) as raised:
        await scheduler.recognize("auto", b"img", "zh", _deadline())
    assert raised.value.status_code == 503


async def test_scheduler_auth_failures_return_503() -> None:
    registry = make_registry(make_account_model(1))
    quota = QuotaManager()
    adapter = FakeAdapter([RetryableError(ErrorKind.AUTH_FAILED, "bad key")])
    scheduler = Scheduler(registry, quota, {"baidu": adapter})
    with pytest.raises(NoCandidate) as raised:
        await scheduler.recognize("baidu", b"img", "zh", _deadline())
    assert raised.value.status_code == 503


async def test_scheduler_deadline_returns_504() -> None:
    registry = make_registry(make_account_model(1))
    scheduler = Scheduler(registry, QuotaManager(), {"baidu": FakeAdapter([])})
    with pytest.raises(DeadlineExceeded) as raised:
        await scheduler.recognize("baidu", b"img", "zh", _deadline(-1))
    assert raised.value.status_code == 504
