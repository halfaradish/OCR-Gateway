# ADR-0001: 容器内依赖安装用 `uv export` + `uv pip install`，而非 `uv sync --frozen`

- Status: accepted
- Date: 2026-11-03

## Context

OCR Gateway 需要打成 Docker 镜像，依赖必须可复现安装。仓库已跟踪 `backend/uv.lock`（427 KB，
`version = 1` / `revision = 5`），因此直觉上容器构建应当直接 `uv sync --frozen`——用锁文件保证版本
一致，正是 `--frozen` 的用途。

但本项目的部署环境对公网 PyPI 的直连能力并不可靠：构建机实测 `https://pypi.org/simple/hatchling/`
不可达（curl exit 28 超时），只有国内镜像（清华 TUNA、阿里云）返回 200。

在此前提下实测发现 `uv sync --frozen` **无法**在这种环境完成安装：

```
error: Failed to download `certifi==2026.10.23`
  cause: Failed to fetch: https://files.pythonhosted.org/packages/32/d1/.../certifi-2026.10.23-py3-none-any.whl
  cause: error sending request ... operation timed out
```

根因是 `uv.lock` 把**下载地址**与**版本**一起锁住了，而不只是版本：

- `grep -c "files.pythonhosted.org" backend/uv.lock` → **1292** 处硬编码 wheel / sdist URL；
- `grep -o 'registry = "[^"]*"' backend/uv.lock | sort -u` → 仅 `https://pypi.org/simple`。

`UV_DEFAULT_INDEX` / `UV_INDEX_URL` 只改变**索引解析**，不改变锁文件里已记录的**下载 URL**，因此
换镜像源对这个失败无效。

## Decision

镜像构建不用 `uv sync --frozen`，改为三步，且**不修改被跟踪的 `uv.lock`**：

1. `uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes` —— 从锁文件导出精确版本
   （本项目为 38 个 `==` 锁定项）；`--no-emit-project` 去掉默认首行 `-e .`——否则只 COPY 了
   `pyproject.toml` / `uv.lock` 的依赖层会在无源码时构建失败；`[spec-review-amendment]`
2. `uv pip install --index-url <mirror> -r <requirements>` —— 按导出的**版本**从镜像下载 wheel；
   执行前 MUST 已有可用 venv（如 `/app/.venv`）或显式 `--system` / `UV_SYSTEM_PYTHON=1`；
   `[spec-review-amendment]` 亲验：无 venv 时报 `No virtual environment found`；
3. `uv pip install --index-url <mirror> --no-deps .` —— 安装项目自身（构建后端 hatchling 亦从镜像取）。

镜像地址由 `ARG UV_DEFAULT_INDEX` 传入，compose / `.env` 提供取值，**仓内默认留空**——不把任何
区域镜像写进仓库。

容器内实测结果：`imports ok 0.1.0`（`fastapi` / `sqlalchemy` / `aiosqlite` / `alembic` / `PIL` /
`cryptography` / `app` 全部可导入）。

## Alternatives

- **`uv sync --frozen`（直觉方案，已否决）** —— 保留锁文件的全部语义，但依赖 `files.pythonhosted.org`
  可达；在构建机上必然超时。若部署环境能直连 PyPI，此方案更优，因此该否决是**环境相关**的，不是
  技术优劣判断。
- **对镜像重新生成 `uv.lock`（已否决）** —— 能让 `uv sync --frozen` 跑通，但会把 mirror URL 固化进
  **被 git 跟踪**的锁文件，任何 clone 到其他地区或 CI 的副本都会莫名走国内镜像。
- **镜像内删除锁文件、自由解析（已否决）** —— 能装通，但完全丢失版本锁定，构建不可复现。

## Consequences

- **正面**：保留锁文件的版本精确性；同时不把区域镜像固化进仓库；构建可移植。
- **负面**：Dockerfile 里出现 `uv export | uv pip install` 这种不常见形状，读者若不看本 ADR 会认为
  写错了——这正是本 ADR 存在的理由。
- **负面**：三条命令比一条 `uv sync` 多一次中间产物（requirements.txt），需要 `--frozen` 保证导出
  与锁一致，否则会静默漂移。
- **维护提示**：升级依赖时 `uv.lock` 仍由 `uv lock` 正常维护，**不要**为了构建去改它的 URL。
- **失效条件**：若构建/部署环境能直连 `pypi.org` 与 `files.pythonhosted.org`，可简化回
  `uv sync --frozen`，届时本 ADR 应标为 `superseded`。

## 评审修订（spec-review-amendment · 2026-11-03）

- **`uv export` 默认含项目自身**：亲验 `uv export --frozen --no-dev --format requirements-txt --no-hashes | head -3`
  → 首个依赖项行是 `-e .`；加 `--no-emit-project` 后无该行、38 个 `==` 项。原 Decision 第 1 步漏此参数，
  依赖层（只 COPY `pyproject.toml` + `uv.lock`）会在无 `app/` 时构建失败。
- **`uv pip install` 需要 venv**：亲验无 venv 时 `uv pip install --dry-run --no-deps .` 报
  `error: No virtual environment found; run 'uv venv' ... or pass '--system'`。原 Decision 第 2/3 步
  未记录；实现 MUST 先建 `/app/.venv`（或显式 `--system`）。
- **构建工具链**：`python:3.12-slim` 不自带 uv，构建阶段 MUST 显式安装固定版本
  （如 `pip install --index-url "$UV_DEFAULT_INDEX" uv==0.13.6`）；`COPY --from=ghcr.io/astral-sh/uv`
  依赖 ghcr.io 可达，本机 Docker Hub 直连已不可达，不能假定。
- **多阶段产物**：若采用多阶段构建，运行时层 MUST `COPY --from=<build> /app/.venv /app/.venv`；
  entrypoint MUST 使用 `/app/.venv/bin/alembic`、`/app/.venv/bin/uvicorn`（或把 `/app/.venv/bin`
  加入 `PATH`），否则 console scripts 不在运行时层的 `PATH` 内。
