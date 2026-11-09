from __future__ import annotations

import base64
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.config import Settings, decode_master_key, enforce_single_worker
from app.db import Base
from app.main import create_app


def test_settings_rejects_invalid_master_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, master_key="short", admin_password="password123")


def test_settings_rejects_short_admin_password() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, master_key="k" * 32, admin_password="short")


def test_settings_defaults() -> None:
    # 无 .env 参与，直接验证类默认值（本机 .env 可能覆盖环境变量默认）。
    settings = Settings(_env_file=None, master_key="k" * 32, admin_password="password123")
    assert settings.default_timeout_ms == 8000
    assert settings.request_deadline_ms == 20000
    assert settings.cache_ttl_seconds == 3600
    assert settings.cache_max_entries == 1000
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.max_image_pixels == 25_000_000
    assert settings.max_concurrent_requests == 4
    assert settings.session_ttl_seconds == 43200


async def test_healthz_ok(client) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["version"]


async def test_healthz_reports_database_error(app, client) -> None:
    def broken_session_factory():
        raise RuntimeError("database is down")

    app.state.gw.session_factory = broken_session_factory
    response = await client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["db"] == "error"


def test_single_worker_guard(monkeypatch) -> None:
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with pytest.raises(RuntimeError):
        enforce_single_worker()
    monkeypatch.delenv("WEB_CONCURRENCY")
    monkeypatch.setenv("UVICORN_WORKERS", "3")
    with pytest.raises(RuntimeError):
        enforce_single_worker()


async def test_lifespan_refuses_multiple_workers(settings, monkeypatch) -> None:
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    application = create_app(settings)
    with pytest.raises(RuntimeError):
        async with application.router.lifespan_context(application):
            pass


def _alembic_config(db_path: Path | None = None) -> Config:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    if db_path is not None:
        config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def test_alembic_upgrade_and_downgrade_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"
    config = _alembic_config(db_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "api_keys",
        "accounts",
        "usage_events",
        "quota_counters",
    } <= tables
    engine.dispose()
    command.downgrade(config, "base")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert tables <= {"alembic_version"}
    engine.dispose()


def test_model_columns_match_design() -> None:
    tables = Base.metadata.tables
    assert {
        "users",
        "api_keys",
        "accounts",
        "usage_events",
        "quota_counters",
    } <= set(tables)
    accounts = tables["accounts"].columns
    assert {
        "provider",
        "credentials_enc",
        "priority",
        "weight",
        "max_concurrency",
        "qps_limit",
        "quota_daily",
        "quota_monthly",
        "quota_total",
        "reset_day",
        "state",
        "cooldown_until",
        "ewma_latency_ms",
    } <= set(accounts.keys())
    usage = tables["usage_events"].columns
    assert {
        "request_id",
        "user_id",
        "api_key_id",
        "account_id",
        "provider",
        "success",
        "error_code",
        "latency_ms",
        "quota_used",
        "cached",
        "image_hash",
        "created_at",
    } <= set(usage.keys())
    assert "text" not in usage
    assert "image_bytes" not in usage


async def test_sqlite_pragmas(app) -> None:
    state = app.state.gw
    async with state.engine.connect() as connection:
        journal = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
        synchronous = (await connection.execute(text("PRAGMA synchronous"))).scalar_one()
    assert str(journal).lower() == "wal"
    assert int(synchronous) == 1


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_cold_start_serves_healthz(tmp_path: Path) -> None:
    db_path = tmp_path / "e2e.db"
    command.upgrade(_alembic_config(db_path), "head")
    env = os.environ.copy()
    env.update(
        {
            "MASTER_KEY": base64.b64encode(b"e" * 32).decode("ascii"),
            "ADMIN_PASSWORD": "password123",
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}",
            "DATA_DIR": str(tmp_path),
        }
    )
    port = _free_port()
    backend = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(backend),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{port}/healthz", timeout=1.0, trust_env=False
                )
            except httpx.HTTPError:
                time.sleep(0.2)
                continue
            assert response.status_code == 200
            assert response.json()["db"] == "ok"
            return
        output = process.stdout.read().decode("utf-8", errors="replace") if process.stdout else ""
        raise AssertionError("server did not become healthy:\n" + output)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def test_master_key_accepts_prefixed_encodings() -> None:
    key = b"k" * 32
    assert decode_master_key("base64:" + base64.b64encode(key).decode("ascii")) == key
    assert decode_master_key("hex:" + key.hex()) == key


def test_env_example_master_key_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("MASTER_KEY="):
            assert len(decode_master_key(line.split("=", 1)[1])) == 32
            break
    else:  # pragma: no cover - example must contain the key
        raise AssertionError("MASTER_KEY missing from .env.example")


def test_alembic_uses_data_dir_env(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "envdata"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = _alembic_config()
    command.upgrade(config, "head")
    db_path = data_dir / "ocr-gateway.db"
    assert db_path.exists()
    assert not (tmp_path / "unused.db").exists()
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert "accounts" in inspect(engine).get_table_names()
    engine.dispose()
