#!/bin/sh
# 容器启动契约：
#   1) 以 root 启动时修复数据卷属主，再以降权身份重新执行自身；
#   2) 非 root 身份下先迁移、再服务；迁移失败即退出，不进入对外服务状态。
set -eu

data_dir="${DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$data_dir"
    chown -R app:app "$data_dir"
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

echo "[entrypoint] applying database migrations"
alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] starting ocr-gateway (single worker)"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
