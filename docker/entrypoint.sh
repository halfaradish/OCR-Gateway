#!/bin/sh
# 容器启动契约：先迁移、再服务；迁移失败即退出，不进入对外服务状态。
set -eu

echo "[entrypoint] applying database migrations"
alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] starting ocr-gateway (single worker)"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
