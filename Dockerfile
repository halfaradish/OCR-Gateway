# syntax=docker/dockerfile:1
# 多阶段：前端构建 → Python 依赖构建 → 运行镜像（venv + 应用源码 + 面板静态产物）。
ARG PYTHON_IMAGE=python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
ARG NODE_IMAGE=node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da

# ── 前端构建：pnpm 与依赖索引均可参数化（离线环境经 NPM_REGISTRY 指向镜像） ──────────
FROM ${NODE_IMAGE} AS frontend-builder
ARG NPM_REGISTRY=
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN if [ -n "$NPM_REGISTRY" ]; then         npm install -g pnpm@11.2.2 --registry "$NPM_REGISTRY";     else         npm install -g pnpm@11.2.2;     fi
RUN if [ -n "$NPM_REGISTRY" ]; then         pnpm install --frozen-lockfile --registry "$NPM_REGISTRY";     else         pnpm install --frozen-lockfile;     fi
COPY frontend/ ./
RUN pnpm build

FROM ${PYTHON_IMAGE} AS builder
ARG UV_DEFAULT_INDEX=
ARG UV_VERSION=0.13.6

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/app/.venv \
    UV_LINK_MODE=copy

WORKDIR /app

# uv 固定版本；镜像索引可参数化（离线环境不依赖默认 PyPI）。
RUN if [ -n "$UV_DEFAULT_INDEX" ]; then \
        pip install --no-cache-dir --index-url "$UV_DEFAULT_INDEX" "uv==${UV_VERSION}"; \
    else \
        pip install --no-cache-dir "uv==${UV_VERSION}"; \
    fi \
    && python -m venv /app/.venv

# 依赖层：只依赖清单与锁文件，代码改动不使其失效；local extra 随镜像内置。
COPY backend/pyproject.toml backend/uv.lock /app/
RUN if [ -n "$UV_DEFAULT_INDEX" ]; then \
        uv export --frozen --no-dev --no-emit-project --extra local --format requirements-txt --no-hashes \
            > /tmp/requirements.txt \
        && uv pip install --index-url "$UV_DEFAULT_INDEX" -r /tmp/requirements.txt; \
    else \
        uv export --frozen --no-dev --no-emit-project --extra local --format requirements-txt --no-hashes \
            > /tmp/requirements.txt \
        && uv pip install -r /tmp/requirements.txt; \
    fi \
    && /app/.venv/bin/python -c "import rapidocr, onnxruntime"

# 代码层：安装项目自身（--no-deps 避免再次解析依赖）。
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
RUN if [ -n "$UV_DEFAULT_INDEX" ]; then \
        uv pip install --index-url "$UV_DEFAULT_INDEX" --no-deps .; \
    else \
        uv pip install --no-deps .; \
    fi

FROM ${PYTHON_IMAGE} AS runtime
ARG APT_MIRROR=
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    DATA_DIR=/data \
    FRONTEND_DIST=/app/static

WORKDIR /app

# 非 root 运行身份：entrypoint 以 root 修复数据卷属主后降权到 app。
# libgomp1 是 onnxruntime 在 slim 基础镜像上的常见依赖；缺失时 import 会失败。
RUN if [ -n "$APT_MIRROR" ]; then \
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
            sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
        elif [ -f /etc/apt/sources.list ]; then \
            sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
        fi; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown app:app /data

COPY --from=builder /app/.venv /app/.venv
COPY --from=frontend-builder /app/frontend/dist /app/static
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
