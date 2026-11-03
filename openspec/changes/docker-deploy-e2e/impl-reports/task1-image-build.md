---
ticket: 1
title: 镜像构建层（S1）
head: 0aa887e6acda5fb7f95038d3d8b1771bc646592c
status: DONE
suite_scope: {"base": "2a549d1df780dfbaf675fdcfbe1ebab9d8d7d248", "head": "HEAD", "mode": "closeout", "domains_configured": true, "hit_domains": ["backend"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

## 改动

- 新增 `.dockerignore`：排除 `.git`、`**/.venv`、`**/tests`、`**/data`、缓存目录、`openspec/`、`docs/`、
  `.env*`（构建上下文只保留运行期所需内容）。
- 新增多阶段 `Dockerfile`：
  - 构建阶段固定基础镜像 digest（design 的 `sha256:b18b261e...`，与本机镜像 digest 一致）、显式安装
    `uv==0.13.6`、创建 `/app/.venv`；依赖层只 COPY `backend/pyproject.toml` 与 `backend/uv.lock`，
    走 `uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes` →
    `uv pip install --index-url`，与 ADR-0001 一致。
  - 代码层 COPY `backend/app`、`backend/alembic`、`backend/alembic.ini` 后 `uv pip install --no-deps .`
    安装项目自身（hatchling 经同一索引构建）。
  - 运行阶段仅复制 `/app/.venv` 与应用源码；`DATA_DIR=/data`、`PATH` 指向 venv。
- `UV_DEFAULT_INDEX` 为空时回落到默认索引（不硬编码区域镜像进仓库），非空时构建期与项目构建均走该索引。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 构建 | `docker build --platform linux/amd64 --build-arg UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple -t ocr-gateway:0.1.0 -t ocr-gateway:latest .` | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 依赖一致性 | `uv export --frozen --no-dev --no-emit-project --format requirements-txt --no-hashes`（38 项）与镜像内 `python -m pip list --format=freeze` 归一化比对 | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 上下文排除 | `printf 'FROM scratch\nCOPY <path> /x\n' \| docker build -q -f - .`：`backend/.venv` / `backend/tests` / `docs` / `openspec` / `.git` 均失败，`backend/app` 成功 | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 镜像运行期 | `docker run --rm ocr-gateway:0.1.0 python -c "import app; print(app.__version__)"` → `0.1.0` | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 无 dev 依赖 | `docker run --rm ocr-gateway:0.1.0 python -c "import pytest"` → `ModuleNotFoundError`（退出码 1）；`test -d /app/tests` 不存在 | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 凭证扫描 | `docker create` + `docker export \| tar -xO \| grep -c "change-me-please"` → 0；`docker history --no-trunc \| grep -Ei "MASTER_KEY\|ADMIN_PASSWORD"` → 无匹配 | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 镜像规格 | `docker image inspect --format '{{.Size}} {{json .RepoTags}} {{.Os}}/{{.Architecture}}'` → `225185940`、两个 tag、`linux/amd64` | 0 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |
| 负例构建 | `docker build`（不传 `UV_DEFAULT_INDEX`，默认索引不可达）→ 构建失败、无镜像产出 | 1 | 未知 | 0aa887e6acda5fb7f95038d3d8b1771bc646592c |

## concerns

- **凭证扫描的边界**：仓库与机器上当前**不存在真实 `.env`**（Task 5 才由人注入真实凭证），故扫描以
  `.env.example` 的占位值（`change-me-please`）、镜像历史与环境变量注入面为对象；示例 Master Key 的
  那串 `A` 在 `PIL/ImageFont.py` 中有同形长串（二进制/源码误报，非凭证），因此以「示例值出现次数 0 +
  历史无 ENV 注入 + 上下文无 `.env`」作为证据组合。
- **离线机器上的测试命令**：`openspec/sdflow-lite.json` 的 unit 层用 `uv run --project backend pytest`；
  本机默认索引不可达时需带 `UV_DEFAULT_INDEX`（或 `--offline` 且缓存已热）。**实测坑**：非 frozen 的
  `uv run` 带自定义索引会把 `backend/uv.lock` 的下载 URL 改写为该镜像（违反 ADR-0001）——本次已即时
  还原（提交 `5a0e608`），后续统一以 `UV_FROZEN=1 UV_DEFAULT_INDEX=<mirror>` 运行，锁文件哈希不变
  （`f8b5874c…` 运行前后一致）。收尾 verify 沿用同一环境变量口径，不改配置内的命令文本。
- 构建耗时：首次含依赖下载约数分钟，缓存后代码层迭代为秒级（与 design Decisions 的预期一致）。
