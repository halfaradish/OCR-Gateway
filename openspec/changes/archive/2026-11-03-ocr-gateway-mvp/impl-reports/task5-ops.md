---
ticket: 5
title: 输入补全与可运营性
head: 3099f3e10515c973bcf8169bc69322bb94920447
status: DONE
suite_scope: {"change": "ocr-gateway-mvp", "domains": ["backend"], "layers": {"backend": ["unit"]}, "commands": {"unit": "uv run --project backend pytest backend/tests"}}
---

# Task 5 实现报告 · 输入补全与可运营性

## 改动

- `app/utils/ssrf.py`：URL scheme/userinfo 校验、`getaddrinfo` 全量解析、私网/回环/链路本地/组播/保留/`169.254.169.254` 拒绝、逐跳重定向复核（≤3）、10s、10MB、失败不回显内网细节。
- `app/api/public.py`：`image_url` 输入接入 SSRF 拉取；`UrlFetchError` 统一映射 400；缓存键/命中/写回（`cached=true`、`quota.used=0`、无厂商调用）。
- `app/core/cache.py`：空文本与单条 >256KB 不缓存；TTL/容量/LRU 由 `TTLCache` 提供；`clear()` 返回条数。
- `app/api/admin.py`：`POST /api/admin/cache/clear`、`GET /api/admin/usage/summary`（`from`/`to` 按 `Asia/Shanghai` 解释、`group_by=user|provider|account`）、`GET /api/admin/logs`（分页/过滤、无原文）。
- `README.md`：quickstart（步骤数与预计耗时）、环境变量表、反代 HTTPS + 单 worker 部署、SQLite `.backup` 备份与保留 7 天、RPO/RTO、真实凭证本地化说明。
- `.env.example`：仅占位值。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 单元/集成/e2e | `python -m uv run --project backend pytest backend/tests/test_ticket5_ssrf_cache.py backend/tests/test_ticket5_api.py -q` | 0 | 27 | 3099f3e10515c973bcf8169bc69322bb94920447 |
| 全量回归 | `python -m uv run --project backend pytest backend/tests -q` | 0 | 139 | 3099f3e10515c973bcf8169bc69322bb94920447 |
| 静态检查 | `python -m uv run --project backend ruff check backend` | 0 | 未知 | 3099f3e10515c973bcf8169bc69322bb94920447 |
| 类型检查 | `python -m uv run --project backend mypy backend/app` | 0 | 未知 | 3099f3e10515c973bcf8169bc69322bb94920447 |

覆盖点：私网/回环/元数据/内嵌凭证/非 http(s) 拒绝且不发出站请求；公网 URL 成功；私网重定向在第二次请求前被拒；重定向超限、10MB 超限、超时、非 200 映射 400；缓存命中 `cached=true`/`quota.used=0`/厂商只调用一次；provider 隔离；空文本不缓存；`>256KB` 不缓存；LRU 淘汰；TTL 过期；管理端清空缓存后重新调用厂商；用量按 provider 聚合与 7 天窗口；日志分页/过滤且无原文；README 关键运营段落存在。

## concerns

- 缓存命中在全局并发信号量之前返回：这是有意的廉价路径（不调用厂商、不占 OCR 并发）；若需要缓存也受并发限制，后续可调整。
- SSRF 仍是「解析后校验 + 逐跳复核」，请求时 httpx 会再次解析 DNS；DNS rebinding 残余风险按设计接受。
- 用量汇总在 Python 内聚合；按 D14 规模（日均 <60 次）足够，若未来数据量增长可改 SQL 聚合。
- README 的备份脚本是运维示例，未纳入自动测试执行；测试仅校验文档覆盖关键段落与命令。

## 票外发现

无。
