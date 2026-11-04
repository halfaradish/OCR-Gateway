from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String, nullable=False)
    key_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("daily_limit IS NULL OR daily_limit >= 0", name="ck_api_keys_daily"),
        CheckConstraint("rpm_limit IS NULL OR rpm_limit >= 0", name="ck_api_keys_rpm"),
        Index("ix_api_keys_user_id", "user_id"),
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    credentials_enc: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=8000, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    qps_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    quota_daily: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_unit: Mapped[str] = mapped_column(String, default="image", nullable=False)
    reset_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state: Mapped[str] = mapped_column(String, default="active", nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    ewma_latency_ms: Mapped[float] = mapped_column(Float, default=1000.0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("provider IN ('baidu', 'tencent')", name="ck_accounts_provider"),
        CheckConstraint("weight >= 1", name="ck_accounts_weight"),
        CheckConstraint("timeout_ms > 0", name="ck_accounts_timeout"),
        CheckConstraint("max_concurrency >= 1", name="ck_accounts_concurrency"),
        CheckConstraint("qps_limit IS NULL OR qps_limit > 0", name="ck_accounts_qps"),
        CheckConstraint(
            "quota_daily IS NULL OR quota_daily >= 0", name="ck_accounts_quota_daily"
        ),
        CheckConstraint(
            "quota_monthly IS NULL OR quota_monthly >= 0", name="ck_accounts_quota_monthly"
        ),
        CheckConstraint(
            "quota_total IS NULL OR quota_total >= 0", name="ck_accounts_quota_total"
        ),
        CheckConstraint("quota_unit IN ('image')", name="ck_accounts_quota_unit"),
        CheckConstraint("reset_day BETWEEN 1 AND 28", name="ck_accounts_reset_day"),
        CheckConstraint(
            "state IN ('active', 'cooling', 'invalid', 'quota_exhausted')",
            name="ck_accounts_state",
        ),
        Index("ix_accounts_provider", "provider"),
        Index("ix_accounts_enabled_state", "enabled", "state"),
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    capability: Mapped[str] = mapped_column(String, default="general_text", nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "provider IN ('baidu', 'tencent', 'auto', 'local')",
            name="ck_usage_provider",
        ),
        CheckConstraint("latency_ms >= 0", name="ck_usage_latency"),
        CheckConstraint("quota_used >= 0", name="ck_usage_quota"),
        Index("ix_usage_events_created_at", "created_at"),
        Index("ix_usage_events_key_created", "api_key_id", "created_at"),
    )


class QuotaCounter(Base):
    __tablename__ = "quota_counters"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    period_type: Mapped[str] = mapped_column(String, primary_key=True)
    period_key: Mapped[str] = mapped_column(String, primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('daily', 'monthly', 'total')", name="ck_quota_period_type"
        ),
        CheckConstraint("used >= 0", name="ck_quota_used"),
    )


class Setting(Base):
    """Runtime-editable settings (D-A2); `value` holds a JSON-encoded scalar."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
