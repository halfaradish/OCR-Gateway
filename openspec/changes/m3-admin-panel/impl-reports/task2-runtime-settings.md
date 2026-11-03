---
ticket: 2
title: 运行时设置
head: 4a355dadf06c3bfe8a13ed5c4b704d4fac4e8a2e
status: DONE
suite_scope: {"domains":["backend"],"layers":["unit"],"base":"4a355da","mode":"closeout"}
---

# Task 2 · 运行时设置

## 改动

- **存储**：新增 `settings` 模型（`key TEXT` 主键 / `value TEXT NOT NULL` / `updated_at DATETIME NOT NULL`，
  值以 JSON 编码）与 Alembic `0002_settings.py`（upgrade 建表、downgrade 删表）；`make_engine` 的 SQLite
  PRAGMA 增加 `busy_timeout=5000`，写锁等待有界后失败可返回 500。
- **运行时对象**（`backend/app/runtime_settings.py`）：`RuntimeSettings`（冻结 dataclass，五个可编辑字段）、
  字段规则表（bool / 整数 + 范围 + 中文字段级文案）、`validate_value`、`load_runtime_settings`
  （env 默认 + DB 覆盖，非法 JSON/越界/未知键记 warning 并回退默认）、`upsert_settings`（单事务内 upsert，
  不自行 commit）。
- **启动接入**：lifespan 内加载运行时设置后构造 `ResultCache`，`AppState` 新增 `runtime`、`settings_lock`
  与 `frontend_built` 快照；`Scheduler` 去掉构造期 deadline，改由调用方传入绝对 deadline。
- **热更新语义**：`ResultCache.reconfigure(enabled, max_entries, ttl_seconds)` 参数变化才重建（清空条目）并
  返回 True；`public.py` 从 `runtime.request_deadline_ms` 计算一次绝对 deadline（覆盖含信号量等待的真实
  总预算）并传给 `Scheduler.recognize`；账号创建未显式给超时时用 `runtime.default_timeout_ms`。
- **端点**：`GET /api/admin/settings` 返回 `editable`/`readonly`（鉴权恒真、版本、上传上限、像素上限、并发、
  会话时长、面板产物就绪快照）；`PUT /api/admin/settings` 接收任意 JSON 对象、逐字段校验（未知键、类型、
  范围、显式 `null` 全部带 `error.fields`），全量通过后 `asyncio.Lock` 串行 merge+commit+apply，提交返回后
  整体替换运行时并重建缓存；DB 失败 500 且运行时不生效；`ApiError` 增加 `fields` 并透传到错误 envelope。
- **账号语义**：`AccountCreate.timeout_ms` 默认改为 `None`（省略 => 运行时默认）；`PATCH` 显式 `null` 返回 400。
- **测试改动**：`test_ticket3_scheduler.py` 跟随新签名（`Blocked-by` 之外唯一改动的既有测试）；
  `test_ticket3_ocr_api.py` 的 monkeypatch `slow_recognize` 补第四个参数。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `uv run --project backend pytest backend/tests/test_m3_ticket2_settings.py -q` | 0 | 24 | 4a355da |
| 回归 pytest（scheduler + 用量/并发接口） | `uv run --project backend pytest backend/tests/test_ticket3_scheduler.py backend/tests/test_ticket3_ocr_api.py -q` | 0 | 38 | 4a355da |
| 全量 pytest | `uv run --project backend pytest backend/tests -q` | 1 | 190 passed, 1 failed, 2 skipped | 4a355da |
| ruff | `uv run --project backend ruff check backend` | 0 | 未知 | 4a355da |
| mypy | `uv run --project backend mypy backend/app` | 0 | 未知 | 4a355da |

全量 pytest 的唯一失败仍是既有红测 `test_run_docs_cover_quickstart_and_operations`（README 缺 `sqlite3`），
已 fold 到 Task 6，见 `planning-decisions.md` §5。

设置保存延迟：`test_settings_save_latency_p95_under_500ms` 跑 20 次 PUT，实测 p95 见该用例 `print` 输出
（本机 SQLite，远低于 500ms 门槛）。

## concerns

- **字段级文案用中文**：设计契约示例给的是英文 `"must be between 60 and 86400"`，但设计同时规定「文案表是
  用户可见文案的唯一真相源」，故 `error.fields[].message` 直接返回文案表原文（如「缓存 TTL 需在 60 到
  86400 秒之间。」）。字段名与结构不变。
- **请求体类型**：`PUT /api/admin/settings` 用 `dict[str, Any]` 接收以便逐字段报错；若请求体不是 JSON 对象，
  走全局 400 `invalid request`（无字段名），这是请求形态错误而非设置项错误。
- **并发 PUT 的最终值**：锁保证「提交顺序 = 应用顺序」，但两个并发请求的胜者不保证是后到的那次调用；测试断言
  DB 值与运行时值一致，而非断言某个特定值。
- **缓存清空标志**：仅当缓存参数（enabled/max_entries/ttl）变化时 `cache_cleared=true`；只改预算或默认超时为 false。
- **`load_runtime_settings` 每次启动读全表**：表只有 5 行量级，无索引需求。
