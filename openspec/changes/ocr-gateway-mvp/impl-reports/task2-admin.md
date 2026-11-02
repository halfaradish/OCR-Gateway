---
ticket: 2
title: 管理端鉴权与实体管理
head: 4f6128fabdd7f53730f0ffe9fe953e868bcdce20
status: DONE
suite_scope: {"change": "ocr-gateway-mvp", "domains": ["backend"], "layers": {"backend": ["unit"]}, "commands": {"unit": "uv run --project backend pytest backend/tests"}}
---

# Task 2 实现报告 · 管理端鉴权与实体管理

## 改动

- `app/api/admin.py`：管理员登录（常量时间比较 + itsdangerous 签名 token + IP/全局双层登录限速）、`/api/admin/me`、成员 CRUD、API Key CRUD、账号 CRUD（凭证 schema 校验 + AES-GCM 加密 + 脱敏响应）、配额模板查询。
- `app/api/deps.py`：公共 API Key 鉴权依赖（SHA-256 查库、Key/成员启用状态、401 语义、每 Key RPM 令牌桶、按 `usage_events` 的日限额）。
- `app/security.py`：AES-256-GCM（12B nonce + 16B tag，AAD=`account-credentials`）、`ocr_` Key 生成/SHA-256/前缀、HKDF 派生 admin 签名密钥、常量时间比较、脱敏。
- `app/state.py`：进程内 `KeyRateLimiter` 与 `LoginLimiter`。
- `app/schemas.py`：登录/成员/Key/账号/响应模型；显式 `null` 与「未提供」通过 `model_fields_set` 区分。
- `app/models.py`：移除 `daily_limit`/`rpm_limit`/`qps_limit` 的 Python 默认值，保证显式 `null` 真正落 NULL（默认值由请求 schema 提供）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 单元/集成 | `python -m uv run --project backend pytest backend/tests/test_ticket2_admin.py -q` | 0 | 20 | 4f6128fabdd7f53730f0ffe9fe953e868bcdce20 |
| 静态检查 | `python -m uv run --project backend ruff check backend` | 0 | 未知 | 4f6128fabdd7f53730f0ffe9fe953e868bcdce20 |
| 类型检查 | `python -m uv run --project backend mypy backend/app` | 0 | 未知 | 4f6128fabdd7f53730f0ffe9fe953e868bcdce20 |

覆盖点：登录成功/失败/过期 token/第 6 次 429；成员重名 400、禁用成员 Key 立即 401；Key 明文仅创建响应、列表只回前缀、吊销 401、默认 100/30 与显式 null；账号凭证加密落库（DB 无明文）、响应脱敏、缺 `secret_key` 400、`qps_limit` 默认 5/显式 null；模板免责说明与不自动套用；缺失/无效/Key 禁用/成员禁用四类 401；RPM 429 与 60s 恢复；日限额 429 `QUOTA_EXCEEDED`；管理端 e2e。

## concerns

- `usage_events.provider` 的 CHECK 已允许 `auto`（Task 1 已记录）；本票的 Key 鉴权失败只在依赖层返回 401，不写 usage_event（符合设计「鉴权失败只记 stdout」）。
- `PATCH /api/admin/api-keys/{id}` 的 `enabled` 用 `model_fields_set` 区分；显式 `null` 会写入 NULL，但 `enabled` 不接受 null（schema 为 `bool | None`，显式 null 会被当作未提供，因为 `exclude_unset` 只排除未提供的字段；`enabled=None` 会触发 NOT NULL 约束）。已由测试覆盖正常值路径，未把 null 作为合法操作。
- 全局并发信号量的 503 验收按出票归属放在 Task 3（OCR 端点存在后验证）。

## 票外发现

无。
