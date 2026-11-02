---
ticket: 1
title: 脚手架、配置与存储基座
head: a565dfb67e7a957aa9174df3c9bd55691e0d7e5c
status: DONE
suite_scope: {"change": "ocr-gateway-mvp", "domains": ["backend"], "layers": {"backend": ["unit"]}, "commands": {"unit": "uv run --project backend pytest backend/tests"}}
---

# Task 1 实现报告 · 脚手架、配置与存储基座

## 改动

- 建立 `backend/` uv 工程：`pyproject.toml`（FastAPI/httpx/SQLAlchemy/aiosqlite/Alembic/cryptography/itsdangerous/cachetools/Pillow/tzdata + pytest/respx/ruff/mypy）。
- `app/config.py`：pydantic-settings 读取全部设计环境变量与默认值；`MASTER_KEY` 按 hex/base64/32 字符原文解码并要求 32 字节；`ADMIN_PASSWORD` 至少 8 字符；单 worker 守卫检测 `WEB_CONCURRENCY`、`UVICORN_WORKERS`、`--workers`。
- `app/db.py`：SQLAlchemy async engine + session factory；连接时设置 `PRAGMA journal_mode=WAL`、`synchronous=NORMAL`、`foreign_keys=ON`。
- `app/models.py`：users、api_keys、accounts、usage_events、quota_counters 五张表，含设计索引、外键与 CHECK 约束；`usage_events` 不含 OCR 原文/图片字节列。
- `alembic/`：初始 revision（`0001_initial.py`）一次性建表/索引/外键，`downgrade()` 反向删表；`env.py` 支持 `-x db_url` 与 `DATABASE_URL`。
- `app/main.py`：应用工厂 + lifespan（加载账号/配额、共享 httpx client、配额刷盘任务、关闭时刷盘）；`GET /healthz` 做 1s 超时的 `SELECT 1`；统一请求 ID、错误 envelope、JSON 日志。
- `app/logging_setup.py`：结构化 JSON 日志；httpx/httpcore 降到 WARNING，避免 INFO 日志记录含 `access_token` 的 URL。
- `.env.example`：仅占位值。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 单元/集成 | `python -m uv run --project backend pytest backend/tests/test_ticket1_bootstrap.py -q` | 0 | 11 | a565dfb67e7a957aa9174df3c9bd55691e0d7e5c |
| 静态检查 | `python -m uv run --project backend ruff check backend` | 0 | 未知 | a565dfb67e7a957aa9174df3c9bd55691e0d7e5c |
| 类型检查 | `python -m uv run --project backend mypy backend/app` | 0 | 未知 | a565dfb67e7a957aa9174df3c9bd55691e0d7e5c |

覆盖点：配置拒绝非法 `MASTER_KEY`/短密码；`/healthz` 200 与数据库故障 503；单 worker 守卫与 lifespan 拒绝；Alembic `upgrade head`/`downgrade base` 往返；表/列与设计一致；WAL/synchronous pragma；真实 uvicorn 冷启动进程 e2e 返回 200。

## concerns

- 应用不在启动时 `create_all`；部署必须先 `alembic upgrade head`（与设计 Migration Plan 一致），否则 healthz 之外的业务查询会失败。
- `usage_events.provider` 的 CHECK 在设计表（`baidu`,`tencent`）之外额外允许 `auto`：`provider=auto` 且无候选账号时仍要落一条失败事件，事件必须有 provider 值。此扩展会在 Task 3 的报告与 verify 中复述。
- 本机原本没有 `uv`，已用 `pip install uv` 安装（uv 0.13.6）；`uv sync --project backend` 可复现依赖。

## 票外发现

无。
