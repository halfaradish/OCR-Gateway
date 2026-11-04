from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import make_image_bytes

from app.core.local_engine import (
    SPAWN_CONTEXT,
    LocalCancelled,
    LocalEngine,
    LocalOcrError,
    LocalTimeout,
    LocalUnavailable,
)

BACKEND = Path(__file__).resolve().parents[1]


class FakeResult:
    def __init__(self, value=None, error=None, ready: bool = True) -> None:
        self.value = value
        self.error = error
        self.ready_flag = ready

    def ready(self) -> bool:
        return self.ready_flag

    def get(self, timeout=None):  # noqa: ANN001 - test double
        if self.error is not None:
            raise self.error
        return self.value


class FakePool:
    def __init__(
        self,
        *,
        warmup: FakeResult | None = None,
        run: FakeResult | None = None,
    ) -> None:
        self.warmup = warmup if warmup is not None else FakeResult(True)
        self.run = run if run is not None else FakeResult(
            {"text": "hello", "lines": [{"text": "hello", "confidence": 0.9}]}
        )
        self.created = 0
        self.terminated = 0
        self.calls: list[str] = []

    def apply_async(self, func, args=()):  # noqa: ANN001 - test double
        name = getattr(func, "__name__", "")
        self.calls.append(name)
        if name == "warmup":
            return self.warmup
        return self.run

    def terminate(self) -> None:
        self.terminated += 1

    def join(self) -> None:
        return None


def _factory(pool: FakePool):
    def create(_max_workers: int) -> FakePool:
        pool.created += 1
        return pool

    return create


async def _wait_state(engine: LocalEngine, state: str, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if engine.status()["state"] == state:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"state did not become {state!r}: {engine.status()}")


async def test_missing_dependency_is_unavailable() -> None:
    engine = LocalEngine(enabled=False, installed=False)
    await engine.start()
    assert engine.status()["state"] == "unavailable"
    assert engine.status()["installed"] is False
    with pytest.raises(LocalUnavailable):
        await engine.recognize(b"img", "zh", time.monotonic() + 5)


async def test_startup_restores_enabled_and_set_enabled_is_idempotent() -> None:
    pool = FakePool()
    engine = LocalEngine(enabled=True, installed=True, pool_factory=_factory(pool))
    await engine.start()
    await _wait_state(engine, "ready")
    assert pool.created == 1

    await engine.set_enabled(True)
    await engine.set_enabled(True)
    assert pool.created == 1
    await engine.shutdown()


async def test_recognize_returns_normalized_result() -> None:
    pool = FakePool()
    engine = LocalEngine(enabled=True, installed=True, pool_factory=_factory(pool))
    await engine.start()
    await _wait_state(engine, "ready")

    result = await engine.recognize(b"img", "zh", time.monotonic() + 5)
    assert result.text == "hello"
    assert result.lines == [{"text": "hello", "confidence": 0.9}]
    assert engine.status()["requests_total"] == 1
    assert engine.status()["last_latency_ms"] is not None
    await engine.shutdown()


async def test_timeout_terminates_pool_and_leaves_starting_state() -> None:
    never = FakeResult(ready=False)
    pool = FakePool(run=never)
    engine = LocalEngine(
        enabled=True,
        installed=True,
        timeout_ms=5000,
        pool_factory=_factory(pool),
    )
    await engine.start()
    await _wait_state(engine, "ready")

    with pytest.raises(LocalTimeout):
        await engine.recognize(b"img", "zh", time.monotonic() + 0.15)

    assert pool.terminated >= 1
    assert engine.status()["state"] == "starting"
    assert engine.status()["requests_total"] == 1
    await engine.shutdown()


async def test_rebuilt_pool_cancels_in_flight_request() -> None:
    pending = FakeResult(ready=False)
    pool = FakePool(run=pending)
    engine = LocalEngine(
        enabled=True,
        installed=True,
        timeout_ms=5000,
        pool_factory=_factory(pool),
    )
    await engine.start()
    await _wait_state(engine, "ready")

    task = asyncio.create_task(
        engine.recognize(b"img", "zh", time.monotonic() + 5)
    )
    await asyncio.sleep(0.05)
    await engine.set_enabled(False)
    pending.ready_flag = True

    with pytest.raises(LocalCancelled):
        await task
    await engine.shutdown()


async def test_warmup_failure_enters_error_with_backoff() -> None:
    pool = FakePool(warmup=FakeResult(False))
    engine = LocalEngine(
        enabled=True,
        installed=True,
        retry_interval_ms=60000,
        pool_factory=_factory(pool),
    )
    await engine.start()
    await _wait_state(engine, "error")
    status = engine.status()
    assert status["last_error"]
    assert status["next_retry_in_ms"] is not None
    assert status["next_retry_in_ms"] > 0

    with pytest.raises(LocalOcrError):
        await engine.recognize(b"img", "zh", time.monotonic() + 2)
    await engine.shutdown()


async def test_warmup_timeout_enters_error() -> None:
    pool = FakePool(warmup=FakeResult(ready=False))
    engine = LocalEngine(
        enabled=True,
        installed=True,
        warmup_timeout_ms=50,
        pool_factory=_factory(pool),
    )
    await engine.start()
    await _wait_state(engine, "error")
    assert pool.terminated >= 1
    await engine.shutdown()


async def test_worker_module_does_not_import_application_modules() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, app.workers.local_ocr; "
                "print('app.main' in sys.modules, 'app.config' in sys.modules, "
                "'app.state' in sys.modules)"
            ),
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False False False"


def test_spawn_context_is_used() -> None:
    assert SPAWN_CONTEXT.get_start_method() == "spawn"


def test_worker_empty_text_reports_warning(monkeypatch) -> None:
    from app.workers import local_ocr

    class EmptyResult:
        txts = None
        scores = None

    monkeypatch.setattr(local_ocr, "_engine", lambda _image: EmptyResult())
    payload = local_ocr.run_ocr(b"img", "zh")
    assert payload["text"] == ""
    assert payload["lines"] == []
    assert payload["warnings"] == ["EMPTY_TEXT"]


@pytest.mark.slow
def test_real_engine_does_not_open_sockets(monkeypatch) -> None:
    pytest.importorskip("rapidocr")
    import socket

    from app.workers import local_ocr

    def fail(*_args, **_kwargs):  # noqa: ANN002, ANN003 - test stub
        raise AssertionError("network access attempted")

    monkeypatch.setattr(local_ocr, "_engine", None)
    monkeypatch.setattr(socket, "socket", fail)
    assert local_ocr.warmup() is True


@pytest.mark.slow
async def test_real_pool_timeout_terminates_workers() -> None:
    import multiprocessing

    before = {process.pid for process in multiprocessing.active_children()}
    engine = LocalEngine(enabled=True, installed=True, timeout_ms=5000)
    await engine.start()
    await _wait_state(engine, "ready", timeout=60)

    with pytest.raises(LocalTimeout):
        await engine._run_in_pool(time.sleep, (5,), 0.1, engine._generation)
    await engine.shutdown()
    await asyncio.sleep(0.2)
    leaked = {
        process.pid for process in multiprocessing.active_children()
    } - before
    assert not leaked, f"worker processes leaked: {leaked}"


@pytest.mark.slow
async def test_real_pool_runs_two_tasks_in_parallel() -> None:
    engine = LocalEngine(
        enabled=True, installed=True, max_concurrency=2, timeout_ms=5000
    )
    await engine.start()
    await _wait_state(engine, "ready", timeout=60)

    started = time.monotonic()
    await asyncio.gather(
        engine._run_in_pool(time.sleep, (0.4,), 5, engine._generation),
        engine._run_in_pool(time.sleep, (0.4,), 5, engine._generation),
    )
    elapsed = time.monotonic() - started
    await engine.shutdown()
    assert elapsed < 0.75, f"tasks did not run in parallel: {elapsed:.2f}s"


@pytest.mark.slow
async def test_real_engine_recognizes_text() -> None:
    pytest.importorskip("rapidocr")
    from app.workers import local_ocr

    assert local_ocr.warmup() is True
    payload = local_ocr.run_ocr(make_image_bytes(text="OCR gateway 12345"), "zh")
    assert "12345" in payload["text"]
    assert payload["lines"]
    confidence = payload["lines"][0]["confidence"]
    assert confidence is None or 0.0 <= confidence <= 1.0

