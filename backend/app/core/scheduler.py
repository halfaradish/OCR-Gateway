from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from app.core.local_engine import LocalResult, LocalUnavailable
from app.core.quota import QuotaManager
from app.core.registry import AccountRegistry
from app.db import utcnow
from app.providers.base import (
    AccountRuntime,
    ErrorKind,
    InputError,
    Line,
    ProviderAdapter,
    RetryableError,
)


class LocalEngineLike(Protocol):
    def is_available(self) -> bool: ...

    async def recognize(
        self, image: bytes, language: str, deadline: float, *, fallback: bool = False
    ) -> LocalResult: ...


class SchedulerError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        account_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.account_id = account_id


class NoCandidate(SchedulerError):
    status_code = 503
    code = "PROVIDER_UNAVAILABLE"


class DeadlineExceeded(SchedulerError):
    status_code = 504
    code = "TIMEOUT"


class UpstreamFailed(SchedulerError):
    status_code = 502
    code = "PROVIDER_ERROR"


@dataclass
class ScheduleResult:
    account_id: int | None
    provider: str
    text: str
    lines: list[Line]
    vendor_latency_ms: int


class Scheduler:
    def __init__(
        self,
        registry: AccountRegistry,
        quota: QuotaManager,
        adapters: Mapping[str, ProviderAdapter],
        *,
        local_engine: LocalEngineLike | None = None,
        reserve_ms: int = 5000,
        min_budget_ms: int = 1000,
    ) -> None:
        self._registry = registry
        self._quota = quota
        self._adapters = adapters
        self._local = local_engine
        self._reserve_ms = max(0, int(reserve_ms))
        self._min_budget_ms = max(0, int(min_budget_ms))

    async def recognize(
        self, provider: str, image: bytes, language: str, deadline: float
    ) -> ScheduleResult:
        """`deadline` is an absolute `time.monotonic()` budget computed by the caller (R-SCH-03).

        ``auto`` may hand the cloud phase a reduced deadline so local OCR keeps a reserve;
        the local phase itself always uses the original total deadline.
        """
        if provider == "local":
            return await self._recognize_local(
                image, language, deadline, fallback=False
            )

        local_available = self._local is not None and self._local.is_available()
        if provider == "auto" and local_available:
            total_ms = max(0.0, (deadline - time.monotonic()) * 1000.0)
            reserve_eff = min(
                self._reserve_ms, max(0.0, total_ms - self._min_budget_ms)
            )
            cloud_deadline = deadline - reserve_eff / 1000.0
            try:
                return await self._recognize_cloud(
                    provider, image, language, cloud_deadline
                )
            except InputError:
                raise
            except (NoCandidate, UpstreamFailed, DeadlineExceeded) as cloud_error:
                remaining_ms = (deadline - time.monotonic()) * 1000.0
                if remaining_ms < self._min_budget_ms:
                    raise cloud_error
                return await self._recognize_local(
                    image, language, deadline, fallback=True
                )

        return await self._recognize_cloud(provider, image, language, deadline)

    async def _recognize_cloud(
        self, provider: str, image: bytes, language: str, deadline: float
    ) -> ScheduleResult:
        candidates = self._registry.candidates(provider, self._quota, utcnow())
        if not candidates:
            raise NoCandidate("no available account")

        last_error: RetryableError | None = None
        last_provider: str | None = None
        last_account_id: int | None = None
        tried = 0

        for account in candidates:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeadlineExceeded(
                    "request deadline exhausted", last_provider, last_account_id
                )
            if not self._registry.acquire(account):
                continue
            tried += 1
            last_provider = account.provider
            last_account_id = account.id
            started = time.monotonic()
            try:
                timeout = min(account.timeout_ms / 1000.0, remaining)
                adapter = self._adapters[account.provider]
                result = await adapter.recognize(account, image, language, timeout)
            except RetryableError as exc:
                self._registry.mark_failure(
                    account,
                    exc.kind,
                    exc.message,
                    exc.cooldown_seconds,
                    utcnow(),
                    self._quota,
                )
                last_error = exc
                continue
            except InputError:
                raise
            finally:
                self._registry.release(account)

            vendor_latency = int((time.monotonic() - started) * 1000)
            self._registry.mark_success(account, vendor_latency, utcnow())
            return ScheduleResult(
                account_id=account.id,
                provider=result.provider,
                text=result.text,
                lines=result.lines,
                vendor_latency_ms=vendor_latency,
            )

        if tried == 0:
            raise NoCandidate("no available account", last_provider, last_account_id)
        if last_error is not None and last_error.kind is ErrorKind.PROVIDER_ERROR:
            raise UpstreamFailed(last_error.message, last_provider, last_account_id)
        raise NoCandidate(
            "all candidate accounts failed", last_provider, last_account_id
        )

    async def _recognize_local(
        self, image: bytes, language: str, deadline: float, *, fallback: bool
    ) -> ScheduleResult:
        if self._local is None:
            raise LocalUnavailable("local OCR is not configured")
        result: LocalResult = await self._local.recognize(
            image, language, deadline, fallback=fallback
        )
        lines: list[Line] = []
        for item in result.lines:
            confidence = item.get("confidence")
            lines.append(
                Line(
                    text=str(item.get("text", "")),
                    confidence=None if confidence is None else float(confidence),
                )
            )
        return ScheduleResult(
            account_id=None,
            provider="local",
            text=result.text,
            lines=lines,
            vendor_latency_ms=result.latency_ms,
        )


__all__ = [
    "DeadlineExceeded",
    "NoCandidate",
    "ScheduleResult",
    "Scheduler",
    "SchedulerError",
    "UpstreamFailed",
    "AccountRuntime",
]
