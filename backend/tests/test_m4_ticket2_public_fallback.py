from __future__ import annotations

import asyncio
import sqlite3
import time
from io import BytesIO
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import (
    ADMIN_PASSWORD,
    auth_headers,
    create_api_key,
    create_user,
    make_image_bytes,
)
from PIL import Image
from sqlalchemy import select

from alembic import command
from app.core.local_engine import (
    LocalEngine,
    LocalOcrError,
    LocalResult,
    LocalTimeout,
)
from app.core.scheduler import Scheduler, SchedulerError, UpstreamFailed
from app.models import UsageEvent
from app.providers.base import (
    ErrorKind,
    InputError,
    Line,
    ProviderResult,
    RetryableError,
)
from app.utils.images import _encoded_size, _limit_bytes, normalize_image

LOCAL_TEXT = {"text": "local text", "lines": [{"text": "local text", "confidence": 0.88}]}


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
    def __init__(self) -> None:
        self.terminated = 0

    def apply_async(self, func, args=()):  # noqa: ANN001 - test double
        if getattr(func, "__name__", "") == "warmup":
            return _Result(True)
        return _Result(LOCAL_TEXT)

    def terminate(self) -> None:
        self.terminated += 1

    def join(self) -> None:
        return None


async def _ready_engine() -> LocalEngine:
    pool = _Pool()
    engine = LocalEngine(
        enabled=True, installed=True, pool_factory=lambda _n: pool
    )
    await engine.start()
    for _ in range(300):
        if engine.status()["state"] == "ready":
            return engine
        await asyncio.sleep(0.01)
    raise AssertionError(f"engine never became ready: {engine.status()}")


class _ErrorLocal:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def is_available(self) -> bool:
        return True

    def status(self) -> dict:
        return {"installed": True, "enabled": True, "state": "ready"}

    async def recognize(self, *_args, **_kwargs):  # noqa: ANN002, ANN003 - test double
        raise self.exc

    async def start(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


def _alembic_config(db_path: Path) -> Config:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def test_migration_roundtrip_maps_local_to_auto(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    config = _alembic_config(db_path)
    command.upgrade(config, "head")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO usage_events "
            "(request_id, provider, capability, success, latency_ms, quota_used, cached, created_at) "
            "VALUES ('r1', 'local', 'general_text', 1, 10, 0, 0, '2026-11-04 00:00:00')"
        )
        connection.commit()

    command.downgrade(config, "7c1f0d2a9b31")
    with sqlite3.connect(db_path) as connection:
        assert (
            connection.execute(
                "SELECT provider FROM usage_events WHERE request_id='r1'"
            ).fetchone()[0]
            == "auto"
        )

    command.upgrade(config, "head")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO usage_events "
            "(request_id, provider, capability, success, latency_ms, quota_used, cached, created_at) "
            "VALUES ('r2', 'local', 'general_text', 1, 10, 0, 0, '2026-11-04 00:00:00')"
        )
        connection.commit()


async def test_create_all_accepts_local_event(app) -> None:
    async with app.state.gw.session_factory() as session:
        session.add(
            UsageEvent(
                request_id="create-all-local",
                provider="local",
                capability="general_text",
                success=True,
                latency_ms=5,
                quota_used=0,
                cached=False,
            )
        )
        await session.commit()


class _Account:
    id = 1
    provider = "baidu"
    timeout_ms = 60000


class _Registry:
    def __init__(self) -> None:
        self.account = _Account()

    def candidates(self, provider, quota, now):  # noqa: ANN001 - test double
        return [self.account]

    def acquire(self, account) -> bool:  # noqa: ANN001 - test double
        return True

    def release(self, account) -> None:  # noqa: ANN001 - test double
        return None

    def mark_failure(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def mark_success(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None


class _Adapter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.timeouts: list[float] = []

    async def recognize(self, account, image, language, timeout):  # noqa: ANN001
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return ProviderResult(provider="baidu", text="cloud", lines=[Line(text="cloud")])


class _Local:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def is_available(self) -> bool:
        return True

    async def recognize(self, image, language, deadline, *, fallback=False):  # noqa: ANN001
        self.calls.append(fallback)
        return LocalResult(
            text="local",
            lines=[{"text": "local", "confidence": 0.9}],
            latency_ms=3,
        )


def _scheduler(adapter: _Adapter, local: _Local) -> Scheduler:
    return Scheduler(
        _Registry(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        {"baidu": adapter},  # type: ignore[dict-item]
        local_engine=local,
        reserve_ms=5000,
        min_budget_ms=1000,
    )


async def test_auto_reserves_budget_and_falls_back() -> None:
    adapter = _Adapter(RetryableError(ErrorKind.PROVIDER_ERROR, "boom"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    result = await scheduler.recognize("auto", b"img", "zh", time.monotonic() + 20)

    assert result.provider == "local"
    assert result.account_id is None
    assert adapter.timeouts[0] == pytest.approx(15.0, abs=0.2)
    assert local.calls == [True]


async def test_auto_small_budget_does_not_reserve_into_the_past() -> None:
    adapter = _Adapter(RetryableError(ErrorKind.PROVIDER_ERROR, "boom"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    result = await scheduler.recognize("auto", b"img", "zh", time.monotonic() + 3)

    assert result.provider == "local"
    assert adapter.timeouts[0] == pytest.approx(1.0, abs=0.2)
    assert local.calls == [True]


@pytest.mark.parametrize(
    ("total_seconds", "expected_cloud_seconds"),
    [(1.0, 1.0), (3.0, 1.0), (5.0, 1.0), (20.0, 15.0)],
)
async def test_auto_reserve_budget_boundaries(
    total_seconds: float, expected_cloud_seconds: float
) -> None:
    adapter = _Adapter(RetryableError(ErrorKind.PROVIDER_ERROR, "boom"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    if total_seconds <= 1.0:
        with pytest.raises(SchedulerError):
            await scheduler.recognize(
                "auto", b"img", "zh", time.monotonic() + total_seconds
            )
    else:
        await scheduler.recognize(
            "auto", b"img", "zh", time.monotonic() + total_seconds
        )

    assert adapter.timeouts[0] == pytest.approx(expected_cloud_seconds, abs=0.2)


async def test_auto_without_min_budget_returns_cloud_error() -> None:
    adapter = _Adapter(RetryableError(ErrorKind.PROVIDER_ERROR, "boom"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    with pytest.raises(SchedulerError) as excinfo:
        await scheduler.recognize("auto", b"img", "zh", time.monotonic() + 0.5)

    assert excinfo.value.code in ("PROVIDER_ERROR", "PROVIDER_UNAVAILABLE")
    assert local.calls == []


async def test_input_error_is_not_fallen_back() -> None:
    adapter = _Adapter(InputError("bad image"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    with pytest.raises(InputError):
        await scheduler.recognize("auto", b"img", "zh", time.monotonic() + 20)
    assert local.calls == []


async def test_explicit_cloud_does_not_fall_back() -> None:
    adapter = _Adapter(RetryableError(ErrorKind.PROVIDER_ERROR, "boom"))
    local = _Local()
    scheduler = _scheduler(adapter, local)

    with pytest.raises(UpstreamFailed):
        await scheduler.recognize("baidu", b"img", "zh", time.monotonic() + 20)
    assert local.calls == []


async def test_explicit_local_skips_cloud() -> None:
    adapter = _Adapter()
    local = _Local()
    scheduler = _scheduler(adapter, local)

    result = await scheduler.recognize("local", b"img", "zh", time.monotonic() + 20)

    assert result.provider == "local"
    assert result.account_id is None
    assert adapter.timeouts == []
    assert local.calls == [False]


def test_local_images_use_raw_jpeg_limits() -> None:
    assert _encoded_size(b"x" * 100, "local") == 100
    assert _limit_bytes("local", 1234) == 1234

    data = make_image_bytes(size=(10000, 100))
    local_encoded = normalize_image(data, "local", 10 * 1024 * 1024, 40_000_000)
    with Image.open(BytesIO(local_encoded)) as local_image:
        assert local_image.width == 10000

    baidu_encoded = normalize_image(data, "baidu", 10 * 1024 * 1024, 40_000_000)
    with Image.open(BytesIO(baidu_encoded)) as baidu_image:
        assert baidu_image.width <= 4096


async def _admin_headers(api_client):  # noqa: ANN001 - test helper
    response = await api_client.post(
        "/api/admin/login", json={"password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_api_local_success_records_zero_quota(app_factory, settings) -> None:
    application, api_client = await app_factory(settings)
    state = application.state.gw
    engine = await _ready_engine()
    state.local_engine = engine  # type: ignore[assignment]
    state.scheduler._local = engine  # type: ignore[attr-defined]

    admin = await _admin_headers(api_client)
    user = await create_user(api_client, admin, "local-user")
    key = await create_api_key(api_client, admin, user["id"], "local-key")

    response = await api_client.post(
        "/v1/ocr/image",
        headers=auth_headers(key["key"]),
        data={"provider": "local"},
        files={"file": ("a.png", make_image_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "local"
    assert body["quota"]["used"] == 0

    async with state.session_factory() as session:
        event = (
            await session.execute(
                select(UsageEvent).where(UsageEvent.request_id == body["request_id"])
            )
        ).scalar_one()
    assert event.provider == "local"
    assert event.account_id is None
    assert event.quota_used == 0
    await engine.shutdown()


async def test_api_local_disabled_403_wins_over_cache(
    app, client, admin_headers
) -> None:
    user = await create_user(client, admin_headers, "cache-user")
    key = await create_api_key(client, admin_headers, user["id"], "cache-key")
    image = make_image_bytes()
    state = app.state.gw
    state.cache.set(
        state.cache.build_key(image, "zh", "local"),
        {"provider": "local", "text": "cached", "lines": []},
    )

    response = await client.post(
        "/v1/ocr/image",
        headers=auth_headers(key["key"]),
        data={"provider": "local"},
        files={"file": ("a.png", image, "image/png")},
    )
    assert response.status_code == 403


async def test_api_auto_falls_back_to_local(app_factory, settings) -> None:
    application, api_client = await app_factory(settings)
    state = application.state.gw
    engine = await _ready_engine()
    state.local_engine = engine  # type: ignore[assignment]
    state.scheduler._local = engine  # type: ignore[attr-defined]

    admin = await _admin_headers(api_client)
    user = await create_user(api_client, admin, "fallback-user")
    key = await create_api_key(api_client, admin, user["id"], "fallback-key")

    response = await api_client.post(
        "/v1/ocr/image",
        headers=auth_headers(key["key"]),
        files={"file": ("a.png", make_image_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "local"
    assert response.json()["quota"]["used"] == 0
    await engine.shutdown()


async def test_api_local_error_mapping(app_factory, settings) -> None:
    application, api_client = await app_factory(settings)
    state = application.state.gw
    state.local_engine = _ErrorLocal(LocalTimeout("timed out"))  # type: ignore[assignment]
    state.scheduler._local = state.local_engine  # type: ignore[attr-defined]

    admin = await _admin_headers(api_client)
    user = await create_user(api_client, admin, "timeout-user")
    key = await create_api_key(api_client, admin, user["id"], "timeout-key")
    response = await api_client.post(
        "/v1/ocr/image",
        headers=auth_headers(key["key"]),
        data={"provider": "local"},
        files={"file": ("a.png", make_image_bytes(), "image/png")},
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "TIMEOUT"

    state.local_engine = _ErrorLocal(LocalOcrError("boom"))  # type: ignore[assignment]
    state.scheduler._local = state.local_engine  # type: ignore[attr-defined]
    response = await api_client.post(
        "/v1/ocr/image",
        headers=auth_headers(key["key"]),
        data={"provider": "local"},
        files={"file": ("a.png", make_image_bytes(), "image/png")},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"


async def test_providers_includes_local_entry(app_factory, settings) -> None:
    application, api_client = await app_factory(settings)
    state = application.state.gw

    admin = await _admin_headers(api_client)
    user = await create_user(api_client, admin, "providers-user")
    key = await create_api_key(api_client, admin, user["id"], "providers-key")
    response = await api_client.get(
        "/v1/providers", headers=auth_headers(key["key"])
    )
    assert response.status_code == 200
    entries = {item["code"]: item for item in response.json()["providers"]}
    assert entries["local"]["name"] == "本地 RapidOCR"
    assert entries["local"]["enabled"] is False
    assert "available_accounts" not in entries["local"]

    engine = await _ready_engine()
    state.local_engine = engine  # type: ignore[assignment]
    state.scheduler._local = engine  # type: ignore[attr-defined]
    response = await api_client.get(
        "/v1/providers", headers=auth_headers(key["key"])
    )
    entries = {item["code"]: item for item in response.json()["providers"]}
    assert entries["local"]["enabled"] is True
    await engine.shutdown()
