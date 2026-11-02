from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app import models  # noqa: F401 - register tables on Base.metadata
from app.db import Base

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001 - logging config is optional
        pass

target_metadata = Base.metadata


def get_url() -> str:
    xargs = context.get_x_argument(as_dictionary=True)
    url = xargs.get("db_url") or os.environ.get("DATABASE_URL")
    if not url:
        url = config.get_main_option("sqlalchemy.url") or "sqlite:///./data/ocr-gateway.db"
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


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
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
