---
ticket: 3
title: 数据端点
head: c2a0b75f501c5ff4cdbfa3d6c127ec91f40e72fc
status: DONE
suite_scope: {"domains":["backend"],"layers":["unit","slow"],"base":"c2a0b75","mode":"closeout"}
---

# Task 3 · 数据端点

## 改动

- **时间窗口单一源**（`backend/app/analytics.py`）：`TimeWindow`（可半开）+ `parse_window`，summary/series/logs
  共用：接受 ISO 时间或 `YYYY-MM-DD`；仅日期形式的 `to` 表示该本地日结束（半开区间，次日 00:00 不计入）；
  默认 `to`=当前时刻、`from`=本地今日 00:00 往前 6 天（7 个日桶）；`from > to` 400；跨度按本地日历日含当日
  > 90 天 400；`LOCAL_DAY_MODIFIER` 为 SQLite `strftime` 的 `+8 hours` 偏移。
- **总览** `GET /api/admin/overview`：今日指标（请求/成功/失败/缓存/配额、成功率、命中率、平均延迟，空窗口为
  `null`）、`auto_failures` 单独计数、厂商账号数与瞬时可调度数（只读快照，不触发 `_recover`/状态迁移）、
  账号配额用量、近 7 个本地日序列、最近 10 条错误（含账号名、不含 OCR 原文）、缓存状态；`generated_at`
  带 `+08:00`。日聚合在 SQL 内完成（`strftime` GROUP BY），缺日补零。
- **序列** `GET /api/admin/usage/series`：本地日分桶、缺日补零、默认 7 桶、支持 `user_id/provider/account_id`
  过滤；`from/to` 带 `+08:00`。
- **汇总** `GET /api/admin/usage/summary`：新增 `avg_latency_ms`（四舍五入整数）、`label`（成员名/账号名/
  厂商名，已删除为 `null`，`auto` 为「自动路由」）与三种过滤；按 key 升序、`null` 最后；保留 UTC naive 的
  `from/to`；受 90 天上限约束；聚合下推 SQL `GROUP BY`。
- **日志** `GET /api/admin/logs`：新增 `from/to/error_code/user_id/account_id` 过滤与 `total`（同条件计数），
  每行新增 `user_name`/`account_name`（可为 `null`）；保持 limit/offset 与 id 倒序。
- **账号**：`GET /api/admin/accounts` 每行新增 `owner_name` 与 `quota_usage`（日/月/总量 + limit + period_key，
  内存计数器为权威，runtime 缺失时 used=0 并 warning）；创建/更新响应同样带 `owner_name`；`delete_account`
  同步 `quota.reset_account`，避免内存计数残留导致 flush 外键失败或 id 复用继承旧用量。
- **可观测性**：overview/series/summary/logs 记结构化 `admin.query`（path、duration_ms、rows）。
- **测试与质量门**：新增 22 个端点用例 + 1 个 slow 基准；`slow` mark 注册并默认 `-m "not slow"`；
  `test_ticket5_api.py::test_usage_summary_and_logs` 按新契约（日志共享 7 天默认窗口）补显式时间窗——
  这是契约变更导致（R-ADM-06），不是放宽断言。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `uv run --project backend pytest backend/tests/test_m3_ticket3_analytics.py -q` | 0 | 22 | c2a0b75 |
| 回归 pytest（用量/日志/账号既有契约） | `uv run --project backend pytest backend/tests/test_ticket5_api.py backend/tests/test_ticket3_ocr_api.py -q` | 1 | 21 passed, 1 failed（既有 README 红测） | c2a0b75 |
| 基准（slow） | `uv run --project backend pytest backend/tests/test_m3_ticket3_bench.py -m slow -q` | 0 | 1 | c2a0b75 |
| 全量 pytest（默认排除 slow） | `uv run --project backend pytest backend/tests -q` | 1 | 212 passed, 1 failed, 2 skipped, 1 deselected | c2a0b75 |
| ruff | `uv run --project backend ruff check backend` | 0 | 未知 | c2a0b75 |
| mypy | `uv run --project backend mypy backend/app` | 0 | 未知 | c2a0b75 |

全量 pytest 的唯一失败仍是既有红测 `test_run_docs_cover_quickstart_and_operations`（README 缺 `sqlite3`），
已 fold 到 Task 6。

基准实测（10 万条 `usage_events`、最近 7 天窗口、5 次采样、本机 SQLite）：

```
bench series: p50=22.1ms p95=24.2ms max=24.2ms n=5
bench summary: p50=15.9ms p95=18.0ms max=18.0ms n=5
bench logs: p50=6.3ms p95=8.0ms max=8.0ms n=5
```

三者 p95 均远低于 300ms 目标。

## concerns

- **日志默认窗口收窄**：此前 `/logs` 无时间过滤（返回全量）；现在与 summary/series 共用 7 天默认窗口。
  这是设计 R-ADM-06 的显式要求，既有测试已按新契约更新。
- **`auto_failures` 口径**：只统计 `provider='auto'` 且失败的今日事件；成功的 `auto` 事件在路由后记录为
  实际厂商，不计入 auto 失败。
- **summary 的 `to` 语义**：日期形式的 `to` 返回的是半开区间上界（次日 00:00），与该查询的实际 SQL 边界一致。
- **`quota_usage` 的 period_key** 复用 `daily_key`/`monthly_key(reset_day)`；runtime 缺失时按 DB 行字段推算，
  不会因内存缺失而报错。
- **`slow` 基准依赖真实 10 万行插入**（约 3 秒），只在显式 `-m slow` 下运行；默认套件 1 条 deselected。
