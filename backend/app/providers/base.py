from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ErrorKind(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class ProviderError(Exception):
    """Base class for adapter-level failures."""


class RetryableError(ProviderError):
    def __init__(
        self,
        kind: ErrorKind,
        message: str,
        cooldown_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.cooldown_seconds = cooldown_seconds


class InputError(ProviderError):
    """The vendor rejected the request itself; the scheduler must not switch accounts."""


class ImageError(InputError):
    pass


class UrlFetchError(InputError):
    pass


@dataclass(frozen=True)
class Line:
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    text: str
    lines: list[Line]


@dataclass
class AccountRuntime:
    id: int
    provider: str
    name: str
    credentials: dict[str, str]
    priority: int
    weight: int
    enabled: bool
    timeout_ms: int
    max_concurrency: int
    qps_limit: float | None
    quota_daily: int | None
    quota_monthly: int | None
    quota_total: int | None
    reset_day: int
    state: str = "active"
    cooldown_until: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    ewma_latency_ms: float = 1000.0
    last_used_at: datetime | None = None
    in_flight: int = 0
    tokens: float = field(default=0.0, init=False)
    last_refill: float = field(default_factory=time.monotonic, init=False)
    exhausted_period_key: str | None = None
    exhausted_reason: str | None = None

    def __post_init__(self) -> None:
        self.tokens = self.qps_limit if self.qps_limit is not None else 0.0


class ProviderAdapter(Protocol):
    provider: str

    async def recognize(
        self,
        account: AccountRuntime,
        image: bytes,
        language: str,
        timeout: float,
    ) -> ProviderResult: ...

    def invalidate(self, account_id: int) -> None: ...


LANGUAGE_MAP: dict[str, dict[str, str]] = {
    "baidu": {"zh": "CHN_ENG", "en": "ENG", "auto": "CHN_ENG"},
    "tencent": {"zh": "zh", "en": "en", "auto": "auto"},
}

PROVIDER_NAMES = {"baidu": "百度智能云", "tencent": "腾讯云"}
