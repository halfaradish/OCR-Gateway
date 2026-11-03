from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import replace as dataclass_replace
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import (
    ADMIN_PASSWORD,
    auth_headers,
    create_account,
    create_api_key,
    create_user,
    make_image_bytes,
)

from alembic import command
from app import __version__
from app.core.cache import ResultCache
from app.core.quota import QuotaManager
from app.core.registry import AccountRegistry
from app.core.scheduler import Scheduler
from app.models import Account, Setting
from app.providers.base import AccountRuntime, Line, ProviderResult
from app.runtime_settings import RuntimeSettings, load_runtime_settings
from app.security import encrypt_credentials

MASTER_KEY = b"k" * 32


def _alembic_config(db_path: Path) -> Config:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def _columns(db_path: Path) -> dict[str, tuple]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("PRAGMA table_info(settings)").fetchall()
    return {row[1]: row for row in rows}


def test_settings_migration_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    config = _alembic_config(db_path)

    command.upgrade(config, "head")
    columns = _columns(db_path)
    assert set(columns) == {"key", "value", "updated_at"}
    assert columns["key"][2].upper() == "TEXT"
    assert columns["key"][5] == 1  # primary key
    assert columns["value"][2].upper() == "TEXT"
    assert columns["value"][3] == 1  # NOT NULL
    assert columns["updated_at"][3] == 1

    command.downgrade(config, "-1")
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "settings" not in tables

    command.upgrade(config, "head")
    assert _columns(db_path)


async def test_runtime_settings_load_merges_and_ignores_invalid(app, settings) -> None:
    state = app.state.gw
    assert state.runtime == RuntimeSettings.from_config(settings)

    async with state.session_factory() as session:
        session.add_all(
            [
                Setting(key="cache_ttl_seconds", value="120"),
                Setting(key="cache_max_entries", value="999999"),  # out of range
                Setting(key="default_timeout_ms", value="not-json"),  # undecodable
                Setting(key="mystery", value="1"),  # unknown key
            ]
        )
        await session.commit()

    async with state.session_factory() as session:
        loaded = await load_runtime_settings(session, settings)

    assert loaded.cache_ttl_seconds == 120
    assert loaded.cache_max_entries == settings.cache_max_entries
    assert loaded.default_timeout_ms == settings.default_timeout_ms


def test_cache_reconfigure_clears_entries_only_on_change() -> None:
    cache = ResultCache(True, 10, 60)
    cache.set("k", {"text": "value"})
    assert cache.get("k") is not None

    assert cache.reconfigure(True, 10, 60) is False
    assert cache.get("k") is not None

    assert cache.reconfigure(True, 20, 60) is True
    assert cache.get("k") is None

    assert cache.reconfigure(False, 20, 60) is True
    cache.set("k2", {"text": "value"})
    assert cache.get("k2") is None


def _registry(timeout_ms: int = 8000) -> AccountRegistry:
    account = Account(
        id=1,
        provider="baidu",
        name="baidu-main",
        owner_id=None,
        credentials_enc=encrypt_credentials(
            MASTER_KEY, {"app_id": "1", "api_key": "AK", "secret_key": "SK"}
        ),
        priority=100,
        weight=1,
        enabled=True,
        timeout_ms=timeout_ms,
        max_concurrency=2,
        qps_limit=None,
        quota_daily=None,
        quota_monthly=None,
        quota_total=None,
        quota_unit="image",
        reset_day=1,
        state="active",
        cooldown_until=None,
        last_error_code=None,
        last_error_message=None,
        ewma_latency_ms=1000.0,
        last_used_at=None,
    )
    registry = AccountRegistry(MASTER_KEY)
    registry.load([account])
    return registry


class _RecordingAdapter:
    provider = "baidu"

    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def invalidate(self, account_id: int) -> None:  # pragma: no cover - not used
        return None

    async def recognize(
        self, account: AccountRuntime, image: bytes, language: str, timeout: float
    ) -> ProviderResult:
        self.timeouts.append(timeout)
        return ProviderResult(provider="baidu", text="ok", lines=[Line(text="ok")])


async def test_scheduler_uses_remaining_budget_as_call_timeout() -> None:
    adapter = _RecordingAdapter()
    scheduler = Scheduler(_registry(), QuotaManager(), {"baidu": adapter})

    await scheduler.recognize("baidu", b"img", "zh", time.monotonic() + 0.5)
    await scheduler.recognize("baidu", b"img", "zh", time.monotonic() + 20)

    assert adapter.timeouts[0] == pytest.approx(0.5, abs=0.05)
    # Never above the account's own timeout even with a huge request budget.
    assert adapter.timeouts[1] == pytest.approx(8.0)


async def test_runtime_budget_covers_semaphore_wait(app_factory, settings) -> None:
    application, client = await app_factory(settings)
    state = application.state.gw
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    user = await create_user(client, headers, "member")
    key = await create_api_key(client, headers, user["id"], "member-key")

    state.semaphore = asyncio.Semaphore(0)  # no permit available: only the budget can end this

    async def call() -> tuple[int, float]:
        started = time.monotonic()
        response = await client.post(
            "/v1/ocr/image",
            headers=auth_headers(key["key"]),
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
        return response.status_code, time.monotonic() - started

    state.runtime = dataclass_replace(state.runtime, request_deadline_ms=150)
    status, fast = await call()
    assert status == 503
    assert fast < 1.0

    state.runtime = dataclass_replace(state.runtime, request_deadline_ms=1200)
    status, slow = await call()
    assert status == 503
    assert slow >= 1.0

    state.runtime = dataclass_replace(state.runtime, request_deadline_ms=20000)


async def test_get_settings_defaults_and_readonly(client, admin_headers) -> None:
    response = await client.get("/api/admin/settings", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["editable"] == {
        "cache_enabled": True,
        "cache_ttl_seconds": 3600,
        "cache_max_entries": 1000,
        "request_deadline_ms": 20000,
        "default_timeout_ms": 8000,
    }
    readonly = body["readonly"]
    assert readonly["api_auth_enabled"] is True
    assert readonly["version"] == __version__
    assert readonly["max_upload_bytes"] == 10 * 1024 * 1024
    assert readonly["max_concurrent_requests"] == 8
    assert readonly["session_ttl_seconds"] == 43200
    assert readonly["frontend_built"] is False


async def test_settings_partial_update_applies_and_persists(app, client, admin_headers) -> None:
    response = await client.put(
        "/api/admin/settings",
        json={"cache_ttl_seconds": 120, "cache_max_entries": 50},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["settings"]["cache_ttl_seconds"] == 120
    assert body["settings"]["cache_max_entries"] == 50
    assert body["settings"]["cache_enabled"] is True
    assert body["cache_cleared"] is True

    state = app.state.gw
    assert state.runtime.cache_ttl_seconds == 120
    async with state.session_factory() as session:
        reloaded = await load_runtime_settings(session, state.settings)
    assert reloaded.cache_ttl_seconds == 120
    assert reloaded.cache_max_entries == 50


async def test_settings_persist_across_process_restart(app_factory, settings) -> None:
    _app, client = await app_factory(settings)
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    updated = await client.put(
        "/api/admin/settings", json={"default_timeout_ms": 4321}, headers=headers
    )
    assert updated.status_code == 200

    restarted, restarted_client = await app_factory(settings)
    assert restarted.state.gw.runtime.default_timeout_ms == 4321
    fresh_login = await restarted_client.post(
        "/api/admin/login", json={"password": ADMIN_PASSWORD}
    )
    readable = await restarted_client.get(
        "/api/admin/settings",
        headers={"Authorization": f"Bearer {fresh_login.json()['token']}"},
    )
    assert readable.json()["editable"]["default_timeout_ms"] == 4321


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"cache_ttl_seconds": 59}, "cache_ttl_seconds", "缓存 TTL 需在 60 到 86400 秒之间。"),
        ({"cache_ttl_seconds": 86401}, "cache_ttl_seconds", "缓存 TTL 需在 60 到 86400 秒之间。"),
        ({"cache_ttl_seconds": "1800"}, "cache_ttl_seconds", "缓存 TTL 必须是整数。"),
        ({"cache_max_entries": 9}, "cache_max_entries", "缓存容量需在 10 到 2000 条之间。"),
        ({"request_deadline_ms": 500}, "request_deadline_ms", "请求总预算需在 1000 到 20000 毫秒之间。"),
        ({"default_timeout_ms": 60001}, "default_timeout_ms", "账号默认超时需在 1000 到 60000 毫秒之间。"),
        ({"cache_enabled": 1}, "cache_enabled", "缓存开关必须是布尔值。"),
        ({"unknown_setting": True}, "unknown_setting", "未知设置项：unknown_setting。"),
        ({"cache_ttl_seconds": None}, "cache_ttl_seconds", "缓存 TTL 必须是整数。"),
    ],
)
async def test_settings_validation_reports_fields(
    client, admin_headers, payload, field, message
) -> None:
    response = await client.put("/api/admin/settings", json=payload, headers=admin_headers)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == "invalid settings"
    fields = {item["field"]: item["message"] for item in error["fields"]}
    assert fields[field] == message


async def test_settings_invalid_payload_does_not_change_state(
    app, client, admin_headers
) -> None:
    before = app.state.gw.runtime
    response = await client.put(
        "/api/admin/settings",
        json={"cache_ttl_seconds": 120, "cache_max_entries": 1},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert app.state.gw.runtime == before


async def test_settings_cache_change_clears_entries(app, client, admin_headers) -> None:
    state = app.state.gw
    state.cache.set("k", {"text": "value"})
    assert len(state.cache) == 1

    same = await client.put(
        "/api/admin/settings", json={"cache_ttl_seconds": 3600}, headers=admin_headers
    )
    assert same.json()["cache_cleared"] is False
    assert len(state.cache) == 1

    changed = await client.put(
        "/api/admin/settings", json={"cache_ttl_seconds": 120}, headers=admin_headers
    )
    assert changed.json()["cache_cleared"] is True
    assert len(state.cache) == 0


async def test_settings_db_failure_returns_500_and_keeps_runtime(
    app, client, admin_headers, monkeypatch
) -> None:
    import app.api.admin as admin_module

    async def boom(session, values):  # noqa: ANN001 - test stub
        raise RuntimeError("database is down")

    monkeypatch.setattr(admin_module, "upsert_settings", boom)
    before = app.state.gw.runtime
    response = await client.put(
        "/api/admin/settings", json={"cache_ttl_seconds": 120}, headers=admin_headers
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert app.state.gw.runtime == before


async def test_concurrent_settings_updates_keep_db_and_runtime_in_sync(
    app, client, admin_headers
) -> None:
    async def put(value: int) -> int:
        response = await client.put(
            "/api/admin/settings",
            json={"cache_ttl_seconds": value},
            headers=admin_headers,
        )
        return response.status_code

    results = await asyncio.gather(put(120), put(240))
    assert results == [200, 200]

    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Setting, "cache_ttl_seconds")
    assert row is not None
    assert int(row.value) == state.runtime.cache_ttl_seconds


async def test_account_creation_uses_runtime_default_timeout(client, admin_headers) -> None:
    await client.put(
        "/api/admin/settings", json={"default_timeout_ms": 1234}, headers=admin_headers
    )
    defaulted = await create_account(client, admin_headers, "baidu", "defaulted")
    assert defaulted["timeout_ms"] == 1234

    explicit = await create_account(
        client, admin_headers, "baidu", "explicit", timeout_ms=4321
    )
    assert explicit["timeout_ms"] == 4321


async def test_account_patch_with_explicit_null_timeout_is_rejected(
    client, admin_headers
) -> None:
    account = await create_account(client, admin_headers, "baidu", "null-timeout")
    response = await client.patch(
        f"/api/admin/accounts/{account['id']}",
        json={"timeout_ms": None},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_settings_save_latency_p95_under_500ms(client, admin_headers) -> None:
    samples: list[float] = []
    for _ in range(20):
        started = time.monotonic()
        response = await client.put(
            "/api/admin/settings",
            json={"cache_ttl_seconds": 3600, "request_deadline_ms": 20000},
            headers=admin_headers,
        )
        assert response.status_code == 200
        samples.append((time.monotonic() - started) * 1000)
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    print(f"settings PUT p95={p95:.1f}ms")
    assert p95 < 500
