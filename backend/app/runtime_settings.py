from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import utcnow
from app.models import Setting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSettings:
    """Process-local snapshot of the editable settings (D-A2)."""

    cache_enabled: bool
    cache_ttl_seconds: int
    cache_max_entries: int
    request_deadline_ms: int
    default_timeout_ms: int
    local_ocr_enabled: bool

    @classmethod
    def from_config(cls, config: Settings) -> RuntimeSettings:
        return cls(
            cache_enabled=config.cache_enabled,
            cache_ttl_seconds=config.cache_ttl_seconds,
            cache_max_entries=config.cache_max_entries,
            request_deadline_ms=config.request_deadline_ms,
            default_timeout_ms=config.default_timeout_ms,
            local_ocr_enabled=config.local_ocr_enabled,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "cache_enabled": self.cache_enabled,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "cache_max_entries": self.cache_max_entries,
            "request_deadline_ms": self.request_deadline_ms,
            "default_timeout_ms": self.default_timeout_ms,
            "local_ocr_enabled": self.local_ocr_enabled,
        }


@dataclass(frozen=True)
class FieldRule:
    kind: type
    minimum: int | None
    maximum: int | None
    type_message: str
    range_message: str


# The user-visible texts below are the ones from the design's copy table (single source).
FIELD_RULES: dict[str, FieldRule] = {
    "cache_enabled": FieldRule(
        kind=bool,
        minimum=None,
        maximum=None,
        type_message="缓存开关必须是布尔值。",
        range_message="",
    ),
    "local_ocr_enabled": FieldRule(
        kind=bool,
        minimum=None,
        maximum=None,
        type_message="本地 OCR 开关必须是布尔值。",
        range_message="",
    ),
    "cache_ttl_seconds": FieldRule(
        kind=int,
        minimum=60,
        maximum=86400,
        type_message="缓存 TTL 必须是整数。",
        range_message="缓存 TTL 需在 60 到 86400 秒之间。",
    ),
    "cache_max_entries": FieldRule(
        kind=int,
        minimum=10,
        maximum=2000,
        type_message="缓存容量必须是整数。",
        range_message="缓存容量需在 10 到 2000 条之间。",
    ),
    "request_deadline_ms": FieldRule(
        kind=int,
        minimum=1000,
        maximum=20000,
        type_message="请求总预算必须是整数。",
        range_message="请求总预算需在 1000 到 20000 毫秒之间。",
    ),
    "default_timeout_ms": FieldRule(
        kind=int,
        minimum=1000,
        maximum=60000,
        type_message="账号默认超时必须是整数。",
        range_message="账号默认超时需在 1000 到 60000 毫秒之间。",
    ),
}


def validate_value(key: str, value: Any) -> tuple[bool, Any, str]:
    """→ (ok, normalized_value, message). Booleans are never accepted as ints."""
    rule = FIELD_RULES[key]
    if rule.kind is bool:
        if not isinstance(value, bool):
            return False, None, rule.type_message
        return True, value, ""
    if isinstance(value, bool) or not isinstance(value, int):
        return False, None, rule.type_message
    if (rule.minimum is not None and value < rule.minimum) or (
        rule.maximum is not None and value > rule.maximum
    ):
        return False, None, rule.range_message
    return True, value, ""


def _decode_stored(key: str, raw: str) -> tuple[bool, Any, str]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return False, None, "stored value is not valid JSON"
    return validate_value(key, value)


async def load_runtime_settings(session: AsyncSession, config: Settings) -> RuntimeSettings:
    """Merge env defaults with persisted overrides; invalid rows fall back with a warning."""
    base = RuntimeSettings.from_config(config)
    updates: dict[str, Any] = {}
    rows = (await session.execute(select(Setting))).scalars().all()
    for row in rows:
        if row.key not in FIELD_RULES:
            logger.warning(
                "settings.unknown_stored_key", extra={"extra_fields": {"field": row.key}}
            )
            continue
        ok, value, message = _decode_stored(row.key, row.value)
        if not ok:
            logger.warning(
                "settings.invalid_stored_value",
                extra={"extra_fields": {"field": row.key, "reason": message}},
            )
            continue
        updates[row.key] = value
    return replace(base, **updates)


async def upsert_settings(session: AsyncSession, values: dict[str, Any]) -> None:
    """Write every provided key in the caller's transaction (no commit here)."""
    now = utcnow()
    for key, value in values.items():
        encoded = json.dumps(value)
        statement = (
            sqlite_insert(Setting)
            .values(key=key, value=encoded, updated_at=now)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": encoded, "updated_at": now},
            )
        )
        await session.execute(statement)
