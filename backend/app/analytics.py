from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement

from app.api.deps import ApiError
from app.core.quota import SHANGHAI

MAX_WINDOW_DAYS = 90
DEFAULT_WINDOW_DAYS = 7
DAY_BUCKET_FORMAT = "%Y-%m-%d"
LOCAL_DAY_MODIFIER = "+8 hours"
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def to_local(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC).astimezone(SHANGHAI)


def to_utc_naive(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


def local_today_start(now_local: datetime | None = None) -> datetime:
    local = now_local or to_local(datetime.now(UTC).replace(tzinfo=None))
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class TimeWindow:
    """Half-open-capable UTC window; date-form `to` is exclusive (end of that local day)."""

    start: datetime
    end: datetime
    end_exclusive: bool

    def conditions(self, column: Any) -> list[ColumnElement]:
        conditions: list[ColumnElement] = [column >= self.start]
        if self.end_exclusive:
            conditions.append(column < self.end)
        else:
            conditions.append(column <= self.end)
        return conditions

    def local_dates(self) -> list[date]:
        last = self.end - timedelta(microseconds=1) if self.end_exclusive else self.end
        first_day = to_local(self.start).date()
        last_day = to_local(last).date()
        if last_day < first_day:
            last_day = first_day
        return [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]


def _parse_bound(
    raw: str | None, *, default: datetime, is_end: bool
) -> tuple[datetime, bool]:
    if raw is None or not raw.strip():
        return to_utc_naive(default), False
    text = raw.strip()
    if _DATE_ONLY_RE.match(text):
        try:
            day = date.fromisoformat(text)
        except ValueError as exc:
            raise ApiError(400, "BAD_REQUEST", "invalid time filter") from exc
        start_local = datetime.combine(day, time.min, tzinfo=SHANGHAI)
        if is_end:
            # A date-only `to` includes that whole local day: exclusive next-day boundary.
            return to_utc_naive(start_local + timedelta(days=1)), True
        return to_utc_naive(start_local), False
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "BAD_REQUEST", "invalid time filter") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SHANGHAI)
    return to_utc_naive(moment), False


def parse_window(
    from_raw: str | None, to_raw: str | None, now: datetime | None = None
) -> TimeWindow:
    """Shared time semantics for summary/series/logs (R-ADM-06)."""
    now_utc = now or datetime.now(UTC).replace(tzinfo=None)
    now_local = to_local(now_utc)
    default_end = now_local
    default_start = local_today_start(now_local) - timedelta(days=DEFAULT_WINDOW_DAYS - 1)

    start, _ = _parse_bound(from_raw, default=default_start, is_end=False)
    end, exclusive = _parse_bound(to_raw, default=default_end, is_end=True)
    window = TimeWindow(start=start, end=end, end_exclusive=exclusive)

    if start > end or (exclusive and start == end):
        raise ApiError(400, "BAD_REQUEST", "invalid time range")
    if len(window.local_dates()) > MAX_WINDOW_DAYS:
        raise ApiError(400, "BAD_REQUEST", "time range exceeds 90 days")
    return window


