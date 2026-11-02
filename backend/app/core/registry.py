from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quota import QuotaManager, daily_key
from app.db import utcnow
from app.models import Account
from app.providers.base import AccountRuntime, ErrorKind
from app.security import decrypt_credentials


class AccountRegistry:
    """In-process account runtime state (single event loop, no locks)."""

    def __init__(self, master_key: bytes) -> None:
        self._master_key = master_key
        self._accounts: dict[int, AccountRuntime] = {}
        self._dirty: set[int] = set()

    def load(self, accounts: list[Account]) -> None:
        self._accounts = {account.id: self._to_runtime(account) for account in accounts}

    def _to_runtime(self, account: Account) -> AccountRuntime:
        credentials = decrypt_credentials(self._master_key, account.credentials_enc)
        return AccountRuntime(
            id=account.id,
            provider=account.provider,
            name=account.name,
            credentials={str(k): str(v) for k, v in credentials.items()},
            priority=account.priority,
            weight=account.weight,
            enabled=account.enabled,
            timeout_ms=account.timeout_ms,
            max_concurrency=account.max_concurrency,
            qps_limit=account.qps_limit,
            quota_daily=account.quota_daily,
            quota_monthly=account.quota_monthly,
            quota_total=account.quota_total,
            reset_day=account.reset_day,
            state=account.state,
            cooldown_until=account.cooldown_until,
            last_error_code=account.last_error_code,
            last_error_message=account.last_error_message,
            ewma_latency_ms=account.ewma_latency_ms,
            last_used_at=account.last_used_at,
        )

    def register(self, account: Account) -> None:
        self._accounts[account.id] = self._to_runtime(account)

    def update(self, account: Account) -> None:
        runtime = self._to_runtime(account)
        previous = self._accounts.get(account.id)
        if previous is not None:
            runtime.state = previous.state
            runtime.cooldown_until = previous.cooldown_until
            runtime.last_error_code = previous.last_error_code
            runtime.last_error_message = previous.last_error_message
            runtime.ewma_latency_ms = previous.ewma_latency_ms
            runtime.last_used_at = previous.last_used_at
            runtime.in_flight = previous.in_flight
            runtime.exhausted_period_key = previous.exhausted_period_key
            runtime.exhausted_reason = previous.exhausted_reason
            runtime.tokens = previous.tokens
            runtime.last_refill = previous.last_refill
        if previous is not None and not previous.enabled and account.enabled:
            runtime.state = "active"
            runtime.cooldown_until = None
            runtime.last_error_code = None
            runtime.last_error_message = None
            runtime.exhausted_period_key = None
            runtime.exhausted_reason = None
        self._accounts[account.id] = runtime
        self._dirty.add(account.id)

    def reset_state(self, account_id: int) -> None:
        runtime = self._accounts.get(account_id)
        if runtime is None:
            return
        runtime.state = "active"
        runtime.cooldown_until = None
        runtime.last_error_code = None
        runtime.last_error_message = None
        runtime.exhausted_period_key = None
        runtime.exhausted_reason = None
        self._dirty.add(account_id)

    def remove(self, account_id: int) -> None:
        self._accounts.pop(account_id, None)
        self._dirty.discard(account_id)

    def get(self, account_id: int) -> AccountRuntime | None:
        return self._accounts.get(account_id)

    def all(self) -> list[AccountRuntime]:
        return list(self._accounts.values())

    def _recover(self, account: AccountRuntime, quota: QuotaManager, now: datetime) -> None:
        if account.state == "cooling" and account.cooldown_until is not None:
            if account.cooldown_until <= now:
                account.state = "active"
                account.cooldown_until = None
                account.last_error_code = None
                account.last_error_message = None
                self._dirty.add(account.id)
        if account.state != "quota_exhausted":
            return
        if account.exhausted_reason == "vendor":
            if account.exhausted_period_key == "total":
                return
            if account.exhausted_period_key and daily_key(now) != account.exhausted_period_key:
                self._set_active(account)
            return
        if quota.available(account, now):
            self._set_active(account)
        elif account.exhausted_period_key and daily_key(now) != account.exhausted_period_key:
            self._set_active(account)

    def _set_active(self, account: AccountRuntime) -> None:
        account.state = "active"
        account.cooldown_until = None
        account.exhausted_period_key = None
        account.exhausted_reason = None
        self._dirty.add(account.id)

    def _has_token(self, account: AccountRuntime, now: float) -> bool:
        if account.qps_limit is None:
            return True
        elapsed = max(0.0, now - account.last_refill)
        tokens = min(account.qps_limit, account.tokens + elapsed * account.qps_limit)
        return tokens >= 1.0

    def _take_token(self, account: AccountRuntime, now: float) -> bool:
        if account.qps_limit is None:
            return True
        elapsed = max(0.0, now - account.last_refill)
        account.tokens = min(account.qps_limit, account.tokens + elapsed * account.qps_limit)
        account.last_refill = now
        if account.tokens < 1.0:
            return False
        account.tokens -= 1.0
        return True

    def candidates(
        self, provider: str, quota: QuotaManager, now: datetime | None = None
    ) -> list[AccountRuntime]:
        moment = now or utcnow()
        result: list[AccountRuntime] = []
        for account in self._accounts.values():
            if provider != "auto" and account.provider != provider:
                continue
            if not account.enabled:
                continue
            self._recover(account, quota, moment)
            if account.state != "active":
                continue
            exhausted, pin = quota.exhausted(account, moment)
            if exhausted:
                account.state = "quota_exhausted"
                account.exhausted_period_key = pin
                account.exhausted_reason = "local"
                self._dirty.add(account.id)
                continue
            if account.in_flight >= account.max_concurrency:
                continue
            if not self._has_token(account, time.monotonic()):
                continue
            result.append(account)
        result.sort(
            key=lambda item: (
                item.priority,
                item.ewma_latency_ms,
                item.last_used_at or datetime.min,
                -item.weight,
            )
        )
        return result

    def available_count(self, provider: str, quota: QuotaManager) -> int:
        return len(self.candidates(provider, quota))

    def acquire(self, account: AccountRuntime) -> bool:
        if account.in_flight >= account.max_concurrency:
            return False
        if not self._take_token(account, time.monotonic()):
            return False
        account.in_flight += 1
        return True

    def release(self, account: AccountRuntime) -> None:
        account.in_flight = max(0, account.in_flight - 1)

    def mark_success(self, account: AccountRuntime, latency_ms: float, now: datetime) -> None:
        account.ewma_latency_ms = 0.2 * latency_ms + 0.8 * account.ewma_latency_ms
        account.last_used_at = now
        account.state = "active"
        account.cooldown_until = None
        account.last_error_code = None
        account.last_error_message = None
        account.exhausted_period_key = None
        account.exhausted_reason = None
        self._dirty.add(account.id)

    def mark_failure(
        self,
        account: AccountRuntime,
        kind: ErrorKind,
        message: str,
        cooldown_seconds: float | None,
        now: datetime,
    ) -> None:
        account.last_error_code = kind.value
        account.last_error_message = message[:500]
        if kind is ErrorKind.AUTH_FAILED:
            account.state = "invalid"
            account.cooldown_until = None
        elif kind is ErrorKind.QUOTA_EXCEEDED:
            account.state = "quota_exhausted"
            account.cooldown_until = None
            account.exhausted_reason = "vendor"
            if account.quota_total is not None:
                account.exhausted_period_key = "total"
            else:
                account.exhausted_period_key = daily_key(now)
        else:
            account.state = "cooling"
            default = 10.0 if kind is ErrorKind.PROVIDER_ERROR else 30.0
            seconds = cooldown_seconds if cooldown_seconds is not None else default
            if kind is ErrorKind.PROVIDER_ERROR:
                seconds = min(max(seconds, 1.0), 60.0)
            else:
                seconds = min(max(seconds, 1.0), 300.0)
            account.cooldown_until = now + timedelta(seconds=seconds)
        self._dirty.add(account.id)

    def apply_quota_limit(
        self, account: AccountRuntime, quota: QuotaManager, now: datetime | None = None
    ) -> None:
        exhausted, pin = quota.exhausted(account, now or utcnow())
        if not exhausted:
            return
        account.state = "quota_exhausted"
        account.exhausted_period_key = pin
        account.exhausted_reason = "local"
        self._dirty.add(account.id)

    async def persist(self, session: AsyncSession) -> int:
        if not self._dirty:
            return 0
        ids = sorted(self._dirty)
        rows = (
            await session.execute(select(Account).where(Account.id.in_(ids)))
        ).scalars().all()
        for row in rows:
            runtime = self._accounts.get(row.id)
            if runtime is None:
                continue
            row.state = runtime.state
            row.cooldown_until = runtime.cooldown_until
            row.last_error_code = runtime.last_error_code
            row.last_error_message = runtime.last_error_message
            row.ewma_latency_ms = runtime.ewma_latency_ms
            row.last_used_at = runtime.last_used_at
            row.updated_at = utcnow()
        await session.commit()
        self._dirty.clear()
        return len(rows)

