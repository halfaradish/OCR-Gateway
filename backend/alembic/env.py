from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from alembic import context
from app import models  # noqa: F401 - register tables on Base.metadata
from app.db import Base

# [impl-review-fix] Keep migrations aligned with the app: the documented quickstart stores config in the repo-root
# .env, and pydantic-settings only loads it inside the app process.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001 - logging config is optional
        pass

target_metadata = Base.metadata


def get_url() -> str:
    xargs = context.get_x_argument(as_dictionary=True)
    url = (
        xargs.get("db_url")
        or os.environ.get("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
    )
    if not url:
        data_dir = os.environ.get("DATA_DIR")
        if data_dir:
            url = f"sqlite:///{(Path(data_dir) / 'ocr-gateway.db').as_posix()}"
        else:
            url = "sqlite:///./data/ocr-gateway.db"
    return url.replace("+aiosqlite", "")


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_sqlite_parent(url: str) -> None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    path = url[len(prefix):]
    if not path or path.startswith(":memory:") or path.startswith("file:"):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def run_migrations_online() -> None:
    url = get_url()
    _ensure_sqlite_parent(url)
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
