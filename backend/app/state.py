from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.cache import ResultCache
from app.core.local_engine import LocalEngine
from app.core.quota import QuotaManager
from app.core.registry import AccountRegistry
from app.core.scheduler import Scheduler
from app.providers.base import ProviderAdapter
from app.runtime_settings import RuntimeSettings


class KeyRateLimiter:
    """Per-key token bucket (RPM)."""

    def __init__(self) -> None:
        self._buckets: dict[int, tuple[float, float, float | None]] = {}

    def allow(self, key_id: int, limit: int | None, now: float | None = None) -> bool:
        if limit is None:
            return True
        moment = now if now is not None else time.monotonic()
        capacity = float(limit)
        rate = capacity / 60.0
        tokens, last, stored_limit = self._buckets.get(key_id, (capacity, moment, limit))
        if stored_limit != limit:
            tokens, last, stored_limit = capacity, moment, limit
        tokens = min(capacity, tokens + max(0.0, moment - last) * rate)
        if tokens < 1.0:
            self._buckets[key_id] = (tokens, moment, stored_limit)
            return False
        self._buckets[key_id] = (tokens - 1.0, moment, stored_limit)
        return True


MAX_TRACKED_LOGIN_IPS = 10_000


class LoginLimiter:
    """Per-IP hard limit plus a global delay-only layer."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 60.0) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._per_ip: dict[str, deque[float]] = defaultdict(deque)
        self._global: deque[float] = deque()

    def _prune(self, queue: deque[float], now: float) -> None:
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()

    def blocked(self, ip: str, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        queue = self._per_ip[ip]
        self._prune(queue, moment)
        return len(queue) >= self.max_failures

    def record_failure(self, ip: str, now: float | None = None) -> None:
        moment = now if now is not None else time.monotonic()
        self._per_ip.setdefault(ip, deque()).append(moment)
        self._global.append(moment)
        self._prune(self._global, moment)
        # [impl-review-fix] Bound memory when a spoofed/unique-IP spray fills the per-IP map.
        if len(self._per_ip) > MAX_TRACKED_LOGIN_IPS:
            self._prune_all(moment)

    def _prune_all(self, now: float) -> None:
        for address in list(self._per_ip):
            queue = self._per_ip[address]
            self._prune(queue, now)
            if not queue:
                del self._per_ip[address]

    def record_success(self, ip: str) -> None:
        self._per_ip.pop(ip, None)

    def delay(self, now: float | None = None) -> float:
        moment = now if now is not None else time.monotonic()
        self._prune(self._global, moment)
        if len(self._global) < self.max_failures:
            return 0.0
        return min(2.0, 0.2 * (len(self._global) - self.max_failures + 1))


@dataclass
class AppState:
    settings: Settings
    runtime: RuntimeSettings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    registry: AccountRegistry
    quota: QuotaManager
    cache: ResultCache
    http: httpx.AsyncClient
    adapters: dict[str, ProviderAdapter]
    scheduler: Scheduler
    local_engine: LocalEngine
    semaphore: asyncio.Semaphore
    settings_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # [P1 hardening] 登出/重置会话时 +1；admin token 内嵌 sv，不匹配即 401（单实例内存计数）。
    session_version: int = 1
    frontend_built: bool = False
    key_limiter: KeyRateLimiter = field(default_factory=KeyRateLimiter)
    login_limiter: LoginLimiter = field(default_factory=LoginLimiter)
