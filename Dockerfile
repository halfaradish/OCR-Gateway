# syntax=docker/dockerfile:1
# 多阶段：构建阶段产出只含运行期依赖的虚拟环境，运行阶段仅带 venv + 应用源码。
ARG PYTHON_IMAGE=python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30

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

# 依赖层：只依赖清单与锁文件，代码改动不使其失效。
COPY backend/pyproject.toml backend/uv.lock /app/
RUN if [ -n "$UV_DEFAULT_INDEX" ]; then \
        uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes \
            > /tmp/requirements.txt \
        && uv pip install --index-url "$UV_DEFAULT_INDEX" -r /tmp/requirements.txt; \
    else \
        uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes \
            > /tmp/requirements.txt \
        && uv pip install -r /tmp/requirements.txt; \
    fi

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
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    DATA_DIR=/data

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
