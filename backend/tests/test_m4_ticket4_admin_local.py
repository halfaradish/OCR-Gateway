from __future__ import annotations

import asyncio
import time

from conftest import ADMIN_PASSWORD

from app.core.local_engine import LocalEngine


class _Result:
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


class _Pool:
    def __init__(self, warmup_error: Exception | None = None, warmup_value=True) -> None:
        self.warmup_error = warmup_error
        self.warmup_value = warmup_value
        self.created = 0
        self.terminated = 0

    def apply_async(self, func, args=()):  # noqa: ANN001 - test double
        if getattr(func, "__name__", "") == "warmup":
            return _Result(self.warmup_value, self.warmup_error)
        return _Result({"text": "local", "lines": []})

    def terminate(self) -> None:
        self.terminated += 1

    def join(self) -> None:
        return None


def _fake_engine(
    *, enabled: bool = False, installed: bool = True, warmup_error: Exception | None = None
) -> tuple[LocalEngine, _Pool]:
    pool = _Pool(warmup_error=warmup_error)

    def create(_max_workers: int) -> _Pool:
        pool.created += 1
        return pool

    engine = LocalEngine(
        enabled=enabled,
        installed=installed,
        pool_factory=create,
    )
    return engine, pool


async def _wait_state(engine: LocalEngine, state: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if engine.status()["state"] == state:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"state did not become {state!r}: {engine.status()}")


async def test_local_status_requires_admin(client) -> None:
    response = await client.get("/api/admin/local-ocr/status")
    assert response.status_code == 401


async def test_local_status_defaults(client, admin_headers) -> None:
    response = await client.get("/api/admin/local-ocr/status", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert isinstance(body["installed"], bool)
    assert body["state"] in ("stopped", "unavailable")
    assert body["concurrency"] == 1
    assert body["timeout_ms"] == 30000
    assert body["effective_timeout_ms"] == 20000
    assert body["reserve_ms"] == 5000
    assert body["effective_reserve_ms"] == 5000
    assert body["model"] == {
        "engine": "onnxruntime",
        "family": "PP-OCRv6",
        "variant": "small",
        "bundled": True,
    }
    assert body["last_latency_ms"] is None
    assert body["last_error"] is None
    assert body["next_retry_in_ms"] is None
    assert body["requests_total"] == 0
    assert body["fallback_total"] == 0


async def test_toggle_enables_engine_clears_cache_and_is_idempotent(
    app, client, admin_headers
) -> None:
    engine, pool = _fake_engine()
    app.state.gw.local_engine = engine  # type: ignore[assignment]
    app.state.gw.cache.set("k", {"text": "value"})

    first = await client.put(
        "/api/admin/settings", json={"local_ocr_enabled": True}, headers=admin_headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["settings"]["local_ocr_enabled"] is True
    assert first.json()["cache_cleared"] is True
    assert len(app.state.gw.cache) == 0
    await _wait_state(engine, "ready")
    assert pool.created == 1

    again = await client.put(
        "/api/admin/settings", json={"local_ocr_enabled": True}, headers=admin_headers
    )
    assert again.status_code == 200
    assert pool.created == 1

    status = await client.get("/api/admin/local-ocr/status", headers=admin_headers)
    assert status.json()["enabled"] is True
    assert status.json()["state"] == "ready"

    off = await client.put(
        "/api/admin/settings", json={"local_ocr_enabled": False}, headers=admin_headers
    )
    assert off.status_code == 200
    assert off.json()["cache_cleared"] is True
    assert engine.status()["state"] == "stopped"


async def test_toggle_type_error_reports_field(app, client, admin_headers) -> None:
    response = await client.put(
        "/api/admin/settings",
        json={"local_ocr_enabled": "yes"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    fields = {item["field"]: item["message"] for item in response.json()["error"]["fields"]}
    assert fields["local_ocr_enabled"] == "本地 OCR 开关必须是布尔值。"
    assert app.state.gw.runtime.local_ocr_enabled is False


async def test_restart_restores_enabled_engine(
    app_factory, settings, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "LocalEngine",
        lambda **kwargs: LocalEngine(
            installed=True, pool_factory=lambda _n: _Pool(), **kwargs
        ),
    )

    first_app, first_client = await app_factory(settings)
    login = await first_client.post(
        "/api/admin/login", json={"password": ADMIN_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    updated = await first_client.put(
        "/api/admin/settings", json={"local_ocr_enabled": True}, headers=headers
    )
    assert updated.status_code == 200
    await _wait_state(first_app.state.gw.local_engine, "ready")

    second_app, second_client = await app_factory(settings)
    assert second_app.state.gw.runtime.local_ocr_enabled is True
    await _wait_state(second_app.state.gw.local_engine, "ready")
    second_login = await second_client.post(
        "/api/admin/login", json={"password": ADMIN_PASSWORD}
    )
    status = await second_client.get(
        "/api/admin/local-ocr/status",
        headers={"Authorization": f"Bearer {second_login.json()['token']}"},
    )
    assert status.json()["enabled"] is True
    assert status.json()["state"] == "ready"


async def test_status_unavailable_when_dependencies_missing(
    app, client, admin_headers
) -> None:
    app.state.gw.local_engine = LocalEngine(enabled=False, installed=False)  # type: ignore[assignment]
    response = await client.get("/api/admin/local-ocr/status", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["installed"] is False
    assert response.json()["state"] == "unavailable"

    enabled = await client.put(
        "/api/admin/settings", json={"local_ocr_enabled": True}, headers=admin_headers
    )
    assert enabled.status_code == 200
    # The preference is persisted, but the engine refuses to run without the extra.
    assert enabled.json()["settings"]["local_ocr_enabled"] is True
    assert app.state.gw.local_engine.status()["enabled"] is False
    assert app.state.gw.local_engine.status()["state"] == "unavailable"


async def test_status_error_is_sanitized(app, client, admin_headers) -> None:
    engine, _pool = _fake_engine(
        enabled=True, warmup_error=RuntimeError(r"C:\models\secret\model.onnx failed")
    )
    app.state.gw.local_engine = engine  # type: ignore[assignment]
    await engine.start()
    await _wait_state(engine, "error")

    response = await client.get("/api/admin/local-ocr/status", headers=admin_headers)
    body = response.json()
    assert body["state"] == "error"
    assert body["last_error"] == "<path> failed"
    assert body["next_retry_in_ms"] is not None
