from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import QuotaCounter
from app.providers.base import AccountRuntime

SHANGHAI = ZoneInfo("Asia/Shanghai")
PERIOD_TYPES = ("daily", "monthly", "total")


def _local(now: datetime | None = None) -> datetime:
    base = now or utcnow()
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base.astimezone(SHANGHAI)


def daily_key(now: datetime | None = None) -> str:
    return _local(now).date().isoformat()


def monthly_key(now: datetime | None = None, reset_day: int = 1) -> str:
    local = _local(now)
    day = min(max(reset_day, 1), 28)
    if local.day >= day:
        start = date(local.year, local.month, day)
    else:
        last_month = local.replace(day=1) - timedelta(days=1)
        start = date(last_month.year, last_month.month, day)
    return start.isoformat()


def period_key(account: AccountRuntime, period_type: str, now: datetime | None = None) -> str:
    if period_type == "daily":
        return daily_key(now)
    if period_type == "monthly":
        return monthly_key(now, account.reset_day)
    return "all"


@dataclass
class _Counter:
    period_key: str
    used: int


class QuotaManager:
    """In-memory quota counters, flushed to SQLite every two seconds."""

    def __init__(self) -> None:
        self._counters: dict[tuple[int, str, str], int] = {}

    def used(self, account: AccountRuntime, period_type: str, now: datetime | None = None) -> int:
        key = period_key(account, period_type, now)
        return self._counters.get((account.id, period_type, key), 0)

    def available(self, account: AccountRuntime, now: datetime | None = None) -> bool:
        limits = {
            "daily": account.quota_daily,
            "monthly": account.quota_monthly,
            "total": account.quota_total,
        }
        for period_type, limit in limits.items():
            if limit is None:
                continue
            if self.used(account, period_type, now) >= limit:
                return False
        return True

    def exhausted(self, account: AccountRuntime, now: datetime | None = None) -> tuple[bool, str]:
        """Return (exhausted, period_key_to_pin). `total` means never auto-recovers."""
        if account.quota_total is not None and self.used(account, "total", now) >= account.quota_total:
            return True, "total"
        for period_type in ("daily", "monthly"):
            limit = account.quota_daily if period_type == "daily" else account.quota_monthly
            if limit is not None and self.used(account, period_type, now) >= limit:
                return True, daily_key(now)
        return False, ""

    def increment(self, account: AccountRuntime, now: datetime | None = None) -> None:
        for period_type in PERIOD_TYPES:
            key = period_key(account, period_type, now)
            cell = (account.id, period_type, key)
            self._counters[cell] = self._counters.get(cell, 0) + 1

    def reset_account(self, account_id: int) -> None:
        for cell in [c for c in self._counters if c[0] == account_id]:
            del self._counters[cell]

    async def load(self, session: AsyncSession, accounts: list[AccountRuntime]) -> None:
        self._counters.clear()
        rows = (await session.execute(select(QuotaCounter))).scalars().all()
        by_id = {account.id: account for account in accounts}
        now = utcnow()
        for row in rows:
            account = by_id.get(row.account_id)
            if account is None:
                continue
            if row.period_key != period_key(account, row.period_type, now):
                continue
            if row.period_type not in PERIOD_TYPES:
                continue
            self._counters[(row.account_id, row.period_type, row.period_key)] = row.used

    async def flush(self, session: AsyncSession) -> int:
        now = utcnow()
        written = 0
        for (account_id, period_type, key), used in list(self._counters.items()):
            stmt = (
                sqlite_insert(QuotaCounter)
                .values(
                    account_id=account_id,
                    period_type=period_type,
                    period_key=key,
                    used=used,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["account_id", "period_type", "period_key"],
                    set_={"used": used, "updated_at": now},
                )
            )
            await session.execute(stmt)
            written += 1
        await session.commit()
        return written

    async def reset_account_db(self, session: AsyncSession, account_id: int) -> None:
        await session.execute(delete(QuotaCounter).where(QuotaCounter.account_id == account_id))
