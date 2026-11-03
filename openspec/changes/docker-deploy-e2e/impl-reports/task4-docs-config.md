---
ticket: 4
title: 文档与配置面（S4）
head: cb1484f5ef128ac866d64766cbafba15a314c72a
status: DONE
suite_scope: {"base": "2a549d1df780dfbaf675fdcfbe1ebab9d8d7d248", "head": "HEAD", "mode": "closeout", "domains_configured": true, "hit_domains": ["backend"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

## 改动

- `README.md`：
  - 新增「快速开始（Docker Compose，约 2 分钟*）」为主路径：3 条命令（`cp .env.example .env` →
    `docker compose up -d` → `compose ps` + `curl /healthz`），并写明 TTHW 为**估算**（步骤数/命令数、
    每步耗时假设、首次构建不计入）。
  - 原 uv + uvicorn 路径改为「本机开发（uv 备选路径）」，补前置说明：默认索引需可达；离线用
    `UV_DEFAULT_INDEX`；避免非 frozen 的 `uv sync` 改写被跟踪的 `uv.lock`（用 `--frozen` /
    `UV_FROZEN=1`）。
  - 环境变量表：`DATA_DIR` 描述改为「SQLite 数据目录（容器内由 compose 固定为 `/data`）」；
    新增构建期 `UV_DEFAULT_INDEX` 行；`DATABASE_URL` 注明容器内置空。
  - 部署段：compose 主路径自动迁移、非 root、restart/优雅停止/日志轮转、数据卷；补 Caddy 与
    Nginx 的 HTTPS 反代片段；保留单 worker 约束与 `TRUST_PROXY_HEADERS` 说明；补回滚口径
    （备份覆盖 + 固定 tag）。
- `.env.example`：新增 `UV_DEFAULT_INDEX=`（构建期，默认留空）与容器 `DATA_DIR=/data` 覆盖、
  `DATABASE_URL` 置空的注释；保留 `change-me-please` 占位，未写入任何真实凭证。
- `backend/tests/test_ticket5_api.py::test_run_docs_cover_quickstart_and_operations`：原有 11 个断言针
  全部保留，新增 `docker compose up -d`、`UV_DEFAULT_INDEX` 与 `.env.example` 的
  `UV_DEFAULT_INDEX` 断言。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 文档静态测试 | `uv run --project backend pytest backend/tests/test_ticket5_api.py -q` | 0 | 7 | cb1484f5ef128ac866d64766cbafba15a314c72a |
| 全量回归 | `uv run --project backend pytest backend/tests -q` → `152 passed, 2 skipped`（2 个合同测试按设计跳过） | 0 | 152 | cb1484f5ef128ac866d64766cbafba15a314c72a |
| 静态检查 | `uv run --project backend ruff check backend` → `All checks passed!` | 0 | 未知 | cb1484f5ef128ac866d64766cbafba15a314c72a |
| 类型检查 | `uv run --project backend mypy backend/app` → `Success: no issues found in 27 source files` | 0 | 未知 | cb1484f5ef128ac866d64766cbafba15a314c72a |
| README 复现（干净树） | 工作树快照（排除 `.git`/`.venv`/`.env`/`data`）→ `cp .env.example .env` + 设 `UV_DEFAULT_INDEX` → `docker compose up -d --build` → 轮询至 `healthy`：9s、`/healthz` 200；日志含「迁移 → 启动」序列 | 0 | 未知 | cb1484f5ef128ac866d64766cbafba15a314c72a |

## concerns

- **干净树复现的口径**：验证用工作树快照（排除 `.git`/虚拟环境/本地 `.env`/`data`）模拟干净
  checkout；耗时为热缓存 9s（镜像层与依赖已缓存），README 的 2 分钟估算覆盖的是无缓存的常见区间，
  两者不矛盾。真实首次构建耗时（分钟级）在「不计数入一键起」的口径内。
- 测试与检查命令在离线机器上以 `UV_FROZEN=1 UV_DEFAULT_INDEX=<mirror>` 运行，未改写
  `backend/uv.lock`（哈希保持 `f8b5874c…`）。
- 本地 `.env`（gitignored）仍是占位值；Task 5 前需替换为真实厂商凭证。
