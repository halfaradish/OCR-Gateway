---
ticket: 3
title: 记账标签与总览对账
head: f6ab40eba7877e3351f4deb64c1165f6110301b7
status: DONE
suite_scope: {"domains":["backend","frontend"],"layers":["unit","quality"],"base":"f6ab40e","mode":"closeout"}
---

# Task 3 · 记账标签与总览对账

## 改动

- **后端标签**：`PROVIDER_NAMES` 已含 `local`（Task 2 增），用量汇总 `group_by=provider` 自动返回 local 行与「本地 RapidOCR」label；`/api/admin/logs` 透传 `provider=local` 过滤（`_event_conditions` 无白名单）。
- **总览对账**：`GET /api/admin/overview` 在今日存在 local 事件时追加一行 `local`（`accounts=0`、`available_accounts=0`），`today_requests`/`today_failures` 取自按 provider 的聚合；无 local 事件时不出现空行，`today.requests` 与厂商行之和继续对账。
- **前端类型拆分**：`types.ts` 新增 `EventProviderCode = ProviderCode | "auto" | "local"`，仅 `ProviderRow.code` 使用；账号域 `ProviderCode` 仍只有 baidu/tencent，账号创建/凭证映射不受影响。
- **前端标签/筛选**：`lib/providers.ts` 的 `PROVIDER_LABELS` 增 `local: "本地 RapidOCR"`；用量页与日志页的厂商筛选均增加 local 选项。
- **测试**：新增 `test_m4_ticket3_accounting_labels.py`（summary local label、summary/logs 的 `provider=local` 过滤、overview local 行与总数对账、series local 过滤、无事件时无 local 行）；前端 `pnpm lint/typecheck/build`。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m4_ticket3_accounting_labels.py -q` | 0 | 3 | f6ab40e |
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 245 | f6ab40e |
| 前端质量门 | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build && echo "frontend quality gates passed: 3"` | 0 | 3 | f6ab40e |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app` | 0 | 未知 | f6ab40e |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | f6ab40e |

## concerns

- `local` 行只在今日有 local 事件时出现；若管理员只想看厂商列表而不想看到 local，需前端按需过滤（当前总览页直接渲染，符合「无事件不出现空行」）。
- `accounts=0` / `available_accounts=0` 是展示占位，前端总览页的「0 / 0 可用」文案对 local 略显多余；Task 4 的面板改动未涉及总览页，若后续要隐藏账号列可另开 UI 小改。
- `ProviderRow.code` 扩为 `EventProviderCode` 只影响总览类型的 key 语义；`overview-page` 不使用 code 做分支，typecheck/build 通过。
