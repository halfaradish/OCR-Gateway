from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass

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
    account_id: int
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
        request_deadline_ms: int,
    ) -> None:
        self._registry = registry
        self._quota = quota
        self._adapters = adapters
        self._deadline_seconds = request_deadline_ms / 1000.0

    async def recognize(
        self, provider: str, image: bytes, language: str
    ) -> ScheduleResult:
        candidates = self._registry.candidates(provider, self._quota, utcnow())
        if not candidates:
            raise NoCandidate("no available account")

        deadline = time.monotonic() + self._deadline_seconds
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
                vendor_latency = int((time.monotonic() - started) * 1000)
                del vendor_latency
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


__all__ = [
    "DeadlineExceeded",
    "NoCandidate",
    "ScheduleResult",
    "Scheduler",
    "SchedulerError",
    "UpstreamFailed",
    "AccountRuntime",
]
