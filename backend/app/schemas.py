from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None


class ApiKeyCreate(BaseModel):
    user_id: int
    name: str = Field(min_length=1, max_length=100)
    daily_limit: int | None = Field(default=100, ge=0)
    rpm_limit: int | None = Field(default=30, ge=0)


class ApiKeyUpdate(BaseModel):
    enabled: bool | None = None
    daily_limit: int | None = Field(default=None, ge=0)
    rpm_limit: int | None = Field(default=None, ge=0)


class AccountCreate(BaseModel):
    provider: Literal["baidu", "tencent"]
    name: str = Field(min_length=1, max_length=100)
    owner_id: int | None = None
    priority: int = 100
    weight: int = Field(default=1, ge=1)
    enabled: bool = True
    timeout_ms: int = Field(default=8000, gt=0)
    max_concurrency: int = Field(default=2, ge=1)
    qps_limit: float | None = Field(default=5.0, gt=0)
    quota_daily: int | None = Field(default=None, ge=0)
    quota_monthly: int | None = Field(default=None, ge=0)
    quota_total: int | None = Field(default=None, ge=0)
    reset_day: int = Field(default=1, ge=1, le=28)
    credentials: dict[str, str]


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    owner_id: int | None = None
    priority: int | None = None
    weight: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    timeout_ms: int | None = Field(default=None, gt=0)
    max_concurrency: int | None = Field(default=None, ge=1)
    qps_limit: float | None = Field(default=None, gt=0)
    quota_daily: int | None = Field(default=None, ge=0)
    quota_monthly: int | None = Field(default=None, ge=0)
    quota_total: int | None = Field(default=None, ge=0)
    reset_day: int | None = Field(default=None, ge=1, le=28)
    credentials: dict[str, str] | None = None


class OcrLineOut(BaseModel):
    text: str
    confidence: float | None


class QuotaOut(BaseModel):
    unit: str = "image"
    used: int


class OcrResponse(BaseModel):
    request_id: str
    provider: str
    text: str
    lines: list[OcrLineOut]
    latency_ms: int
    cached: bool
    quota: QuotaOut
    warnings: list[str]
