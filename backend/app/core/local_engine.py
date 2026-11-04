"""Local OCR engine lifecycle and process-pool orchestration.

The parent-process side owns a small state machine (``stopped`` / ``starting`` /
``ready`` / ``error`` / ``unavailable``), a killable spawn pool, warmup, and the
counters exposed by ``GET /api/admin/local-ocr/status``.

Only the event-loop thread mutates the state; no locks are required for fields.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import multiprocessing
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.workers import local_ocr

logger = logging.getLogger(__name__)

SPAWN_CONTEXT = multiprocessing.get_context("spawn")

_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s'\"]+|/[^\s'\"]+\.onnx)")
_READY_WAIT_SECONDS = 10.0
_POLL_INTERVAL_SECONDS = 0.02
_TERMINATE_TIMEOUT_SECONDS = 5.0
_MODEL_INFO = {
    "engine": "onnxruntime",
    "family": "PP-OCRv6",
    "variant": "small",
    "bundled": True,
}


class LocalOcrError(Exception):
    """Base error for local OCR runtime failures (mapped to 502 by the API)."""

    status_code = 502
    code = "PROVIDER_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LocalUnavailable(LocalOcrError):
    """Local OCR is disabled or its dependencies are not installed (403)."""

    status_code = 403
    code = "FORBIDDEN"


class LocalTimeout(LocalOcrError):
    """The local attempt exhausted its budget (504)."""

    status_code = 504
    code = "TIMEOUT"


class LocalCancelled(LocalOcrError):
    """The request belonged to a pool generation that has been rebuilt (503)."""

    status_code = 503
    code = "PROVIDER_UNAVAILABLE"


@dataclass(frozen=True)
class LocalResult:
    text: str
    lines: list[dict[str, Any]]
    latency_ms: int


PoolFactory = Callable[[int], Any]


def _default_pool_factory(max_concurrency: int) -> Any:
    return SPAWN_CONTEXT.Pool(
        processes=max_concurrency, initializer=local_ocr.worker_init
    )


def _sanitize_error(message: str) -> str:
    first_line = (message or "").strip().splitlines()[0] if message else ""
    return _PATH_RE.sub("<path>", first_line)[:200]


class LocalEngine:
    def __init__(
        self,
        *,
        enabled: bool = False,
        installed: bool | None = None,
        max_concurrency: int = 1,
        timeout_ms: int = 30000,
        reserve_ms: int = 5000,
        min_budget_ms: int = 1000,
        warmup_timeout_ms: int = 10000,
        retry_interval_ms: int = 30000,
        pool_factory: PoolFactory | None = None,
    ) -> None:
        self._enabled = enabled
        self._installed = self._detect_installed() if installed is None else installed
        self._max_concurrency = max(1, int(max_concurrency))
        self._timeout_ms = max(1, int(timeout_ms))
        self._reserve_ms = max(0, int(reserve_ms))
        self._min_budget_ms = max(0, int(min_budget_ms))
        self._warmup_timeout_ms = max(1, int(warmup_timeout_ms))
        self._retry_interval_ms = max(0, int(retry_interval_ms))
        self._pool_factory = pool_factory or _default_pool_factory

        self._state = "stopped" if self._installed else "unavailable"
        self._pool: Any | None = None
        self._generation = 0
        self._ready = asyncio.Event()
        self._lock = asyncio.Lock()
        self._warmup_task: asyncio.Task[None] | None = None
        self._last_error: str | None = None
        self._last_latency_ms: int | None = None
        self._next_retry_at = 0.0
        self._requests_total = 0
        self._fallback_total = 0

    @staticmethod
    def _detect_installed() -> bool:
        return (
            importlib.util.find_spec("rapidocr") is not None
            and importlib.util.find_spec("onnxruntime") is not None
        )

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Restore the persisted switch at application startup."""
        if not self._installed:
            self._state = "unavailable"
            if self._enabled:
                logger.warning("local_ocr.unavailable")
            return
        if self._enabled:
            await self.set_enabled(True)

    async def set_enabled(self, enabled: bool) -> None:
        async with self._lock:
            if enabled:
                if not self._installed:
                    self._enabled = False
                    self._state = "unavailable"
                    return
                self._enabled = True
                if self._state in ("ready", "starting") and self._pool is not None:
                    return
                self._state = "starting"
                self._last_error = None
                self._ready.clear()
                logger.info("local_ocr.enabled")
                self._spawn_warmup()
                return

            self._enabled = False
            if self._state == "stopped" and self._pool is None:
                return
            self._generation += 1
            self._ready.clear()
            await self._terminate_pool()
            self._state = "stopped"
            logger.info("local_ocr.disabled")

    def _spawn_warmup(self) -> None:
        if self._warmup_task is not None and not self._warmup_task.done():
            self._warmup_task.cancel()
        generation = self._generation
        self._warmup_task = asyncio.create_task(self._start_pool(generation))

    async def _start_pool(self, generation: int) -> None:
        try:
            pool = self._pool_factory(self._max_concurrency)
        except Exception as exc:  # noqa: BLE001 - surface through status
            self._mark_error(exc)
            return
        self._pool = pool
        started = time.monotonic()
        try:
            ok = await self._run_in_pool(
                local_ocr.warmup, (), self._warmup_timeout_ms / 1000.0, generation
            )
        except LocalCancelled:
            return
        except Exception as exc:  # noqa: BLE001 - surface through status
            await self._terminate_pool()
            # [impl-review-fix] A disable during warmup must win; do not overwrite
            # `stopped` with `error` after the user turned the switch off.
            if not self._enabled:
                return
            self._mark_error(exc)
            return
        if generation != self._generation:
            return
        if not ok:
            await self._terminate_pool()
            if not self._enabled:
                return
            self._mark_error("warmup produced no text")
            return
        self._state = "ready"
        self._ready.set()
        logger.info(
            "local_ocr.warmup",
            extra={
                "extra_fields": {
                    "model": "PP-OCRv6-small",
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            },
        )

    def _mark_error(self, exc: object) -> None:
        if isinstance(exc, LocalOcrError):
            message = exc.message
        else:
            message = str(exc) or exc.__class__.__name__
        self._last_error = _sanitize_error(message)
        self._state = "error"
        # Wake requests already waiting on `starting` so they fail fast instead of
        # burning the full ready-wait budget on an engine that will not become ready.
        self._ready.set()
        self._next_retry_at = time.monotonic() + self._retry_interval_ms / 1000.0
        logger.warning(
            "local_ocr.failed",
            extra={"extra_fields": {"error": self._last_error}},
        )

    async def _terminate_pool(self) -> None:
        pool = self._pool
        self._pool = None
        if pool is None:
            return

        def _kill() -> None:
            pool.terminate()
            pool.join()

        try:
            await asyncio.wait_for(
                asyncio.to_thread(_kill), timeout=_TERMINATE_TIMEOUT_SECONDS
            )
        except TimeoutError:
            # [impl-review-fix] Do not let a wedged native worker block the request
            # path or application shutdown; compose's grace period is 25s.
            logger.warning("local_ocr.terminate_timeout")

    async def shutdown(self) -> None:
        task = self._warmup_task
        self._warmup_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown path
                pass
        self._enabled = False
        self._generation += 1
        self._ready.clear()
        await self._terminate_pool()
        self._state = "stopped"

    # --------------------------------------------------------------- execution

    def is_available(self) -> bool:
        """Whether ``auto`` may reserve budget / fall back to local."""
        return self._installed and self._enabled and self._state in ("ready", "starting")

    async def recognize(
        self,
        image: bytes,
        language: str,
        deadline: float,
        *,
        fallback: bool = False,
    ) -> LocalResult:
        if not self._installed:
            raise LocalUnavailable("local OCR dependencies are not installed")
        if not self._enabled:
            raise LocalUnavailable("local OCR is not enabled")
        if self._state == "unavailable":
            raise LocalUnavailable("local OCR dependencies are not installed")

        if self._state == "error":
            if time.monotonic() < self._next_retry_at:
                raise LocalOcrError("local OCR is cooling down after a warmup failure")
            await self.set_enabled(True)

        if self._state in ("starting", "stopped"):
            if self._state == "stopped" and self._enabled:
                await self.set_enabled(True)
            remaining = deadline - time.monotonic()
            wait_s = min(_READY_WAIT_SECONDS, max(0.0, remaining))
            if wait_s <= 0:
                raise LocalTimeout("local OCR budget exhausted while warming up")
            try:
                await asyncio.wait_for(self._ready.wait(), timeout=wait_s)
            except TimeoutError as exc:
                raise LocalOcrError("local OCR is still warming up") from exc

        if self._state != "ready":
            raise LocalOcrError("local OCR is not ready")

        remaining = deadline - time.monotonic()
        timeout_s = min(self._timeout_ms / 1000.0, remaining)
        if timeout_s <= 0:
            raise LocalTimeout("local OCR budget exhausted")

        self._requests_total += 1
        if fallback:
            self._fallback_total += 1

        started = time.monotonic()
        generation = self._generation
        try:
            payload = await self._run_in_pool(
                local_ocr.run_ocr, (image, language), timeout_s, generation
            )
        except LocalTimeout:
            # [impl-review-fix] `_run_in_pool` terminated the stuck pool and moved to
            # `starting`; without a new warmup task every later request would wait for an
            # event nobody sets.
            if self._enabled:
                self._spawn_warmup()
            self._last_latency_ms = int((time.monotonic() - started) * 1000)
            raise
        except LocalOcrError:
            self._last_latency_ms = int((time.monotonic() - started) * 1000)
            raise
        latency_ms = int((time.monotonic() - started) * 1000)
        self._last_latency_ms = latency_ms
        return LocalResult(
            text=str(payload.get("text", "")),
            lines=list(payload.get("lines", [])),
            latency_ms=latency_ms,
        )

    async def _run_in_pool(
        self, func: Callable[..., Any], args: tuple[Any, ...], timeout_s: float, generation: int
    ) -> Any:
        pool = self._pool
        if pool is None:
            raise LocalOcrError("local OCR pool is not running")
        try:
            result = pool.apply_async(func, args)
        except Exception as exc:  # noqa: BLE001 - pool is broken
            raise LocalOcrError(f"local OCR pool rejected the task: {exc}") from exc

        deadline = time.monotonic() + max(0.0, timeout_s)
        while not result.ready():
            if generation != self._generation:
                raise LocalCancelled("local OCR pool was rebuilt")
            if time.monotonic() >= deadline:
                self._generation += 1
                self._ready.clear()
                if self._enabled:
                    self._state = "starting"
                await self._terminate_pool()
                logger.warning("local_ocr.timeout")
                raise LocalTimeout("local OCR timed out")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        try:
            value = result.get(0)
        except Exception as exc:  # noqa: BLE001 - worker raised
            raise LocalOcrError(str(exc) or exc.__class__.__name__) from exc
        if generation != self._generation:
            raise LocalCancelled("local OCR pool was rebuilt")
        return value

    # ------------------------------------------------------------------ status

    def status(self, total_budget_ms: int | None = None) -> dict[str, Any]:
        effective_timeout = self._timeout_ms
        effective_reserve = 0
        if total_budget_ms is not None:
            effective_timeout = min(self._timeout_ms, max(0, int(total_budget_ms)))
            effective_reserve = min(
                self._reserve_ms,
                max(0, int(total_budget_ms) - self._min_budget_ms),
            )
        next_retry: int | None = None
        if self._state == "error":
            next_retry = max(0, int((self._next_retry_at - time.monotonic()) * 1000))
        return {
            "enabled": self._enabled,
            "installed": self._installed,
            "state": self._state,
            "concurrency": self._max_concurrency,
            "timeout_ms": self._timeout_ms,
            "effective_timeout_ms": effective_timeout,
            "reserve_ms": self._reserve_ms,
            "effective_reserve_ms": effective_reserve,
            "model": dict(_MODEL_INFO),
            "last_latency_ms": self._last_latency_ms,
            "last_error": self._last_error,
            "next_retry_in_ms": next_retry,
            "requests_total": self._requests_total,
            "fallback_total": self._fallback_total,
        }


__all__ = [
    "LocalCancelled",
    "LocalEngine",
    "LocalOcrError",
    "LocalResult",
    "LocalTimeout",
    "LocalUnavailable",
    "SPAWN_CONTEXT",
]
