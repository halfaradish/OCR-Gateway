---
ship-gate:
  code_review: pass
  reviewed_sha: 7afb87a609c628d29da11bea3b8ce423cb784999d3ed7dc082cfaa5ed0dbde14
  reviewed_manifest: MTAwNjQ0IGJsb2IgZjg1NDFmYzJmMjU5YjkxNDU0MjdlZDM3NTZjNGY5YzRmODNiZTE4ZgkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIGFhYzlmZjJlNWM2OTUxYjFiYWFhZjI1NDhiYTYxYjFkOTBlNWJhZTcJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIGU1MDE5ZmU3NmE4MTU4NGMzZWU3ZDU3M2Q1ZGYyZTE5NTJhOWIxMWUJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiBjNTRmY2I4NTUxZmMwM2Q1N2ExNTE0ZmZkYThlOTY5Mzc0MDVlYmFkCUFHRU5UUy5tZAAxMDA2NDQgYmxvYiA2OGI2N2RmMzMwMjY0ZTJlOGJjNDY2YTkxNTUyYTdjY2Q3M2NjZGYyCURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgYzg0NzMxNmYxMWNiMjliZTViYjQ3YzNlOGZlYTE3M2FiYjhlYjMzNwlSRUFETUUubWQAMDQwMDAwIHRyZWUgYTJmOWI1ZjkwZTZkNjkxZGM0Y2U5NTRlMWYwYWNmYjgwZjM1NTFlMgliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIGY2ZDBlNDAwZjM5ODc2NmU4ZDAzYjNjN2E1NjRlZDZmMGVlNjhhYTMJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDZhMDdhNTdjNTRiYmVhOGUxNGZhNzY0YjhmNzc2OGEwYzVlZjhhNmQJZG9jcwAwNDAwMDAgdHJlZSAyNDk3NmIzY2MzMjY1NDljNzE2OGM0ZmZhMWMxZTI1NzJkYTY0YWI0CWZyb250ZW5kADA0MDAwMCB0cmVlIGQxZmI2NzhkMGMyOWQwN2MyMmRjMDVhMTU1NzQyOTg5ZjA2OGEyYTYJc2NyaXB0cw==
---
# 代码审报告 · m3-admin-panel

> ⚠️ 单 session 自查：实现者与审阅者为同一上下文；同模型、不同上下文，非独立评审。
> dispatch: single-session
> 完成度来源: tickets.md
> diff base: `5704a1b`（`main` 的 merge-base），被审盘面：`704d8b3`（含本轮自动修复）

## 结论

**pass**

7 张票全部 DONE 且有 diff 内证据；scope 与 proposal/Non-Goals 一致；未发现 Critical。本轮采纳
4 条自动修复（会话过期提示、启动 401 不误报、CSRF 重试网络错误归一化、CSV 撤销时机 + 滚动恢复），
修复后复审干净；2 条 Minor 进 defer 台账；1 条既有观察。

## scope 审计

| # | 类型 | 证据 | 严重度 |
|---|---|---|---|
| 1 | scope-drift | 无出圈改动：diff 集中在后端管理面（鉴权/设置/数据端点/静态托管/安全头）、`frontend/`、`Dockerfile`/compose/README/.env.example，与 proposal 的 What Changes 一一对应 | — |
| 2 | Non-Goals | 未实现 SSR/全局状态库/服务端 CSV/i18n/深色主题/WebSocket/账号成员分页/多角色/aliyun-huawei 表单 | — |
| 3 | 完成度 | 7/7 DONE（逐票见下表） | — |
| 4 | 切片偏离 | `planning-decisions.md` 申报「无偏离」；实际 diff 与 S1–S6 对应。唯一设计层偏离：登录表单未用 RHF/zod（见 Spec 轴 #3，已在 Task 5 报告声明） | — |
| 5 | 对账差异 | `tasks.md` 复选框未按任务逐条勾选（ship 以 tickets.md 为执行计划单一源；tasks.md 只用于 R-ID 追溯），不据此判未完成 | — |

逐票五态（`tickets.md`，证据均可在 diff/报告内定位）：

| 票 | 状态 | 关键证据 |
|---|---|---|
| 1 后端鉴权/安全头/静态托管 | DONE | `app/api/deps.py` cookie+CSRF、`security_headers.py`、`panel.py`；`test_m3_ticket1_panel_auth.py` 16 例 |
| 2 运行时设置 | DONE | `runtime_settings.py`、`0002_settings.py`、`/settings` 端点；`test_m3_ticket2_settings.py` 24 例 |
| 3 数据端点 | DONE | `analytics.py` + overview/series/summary/logs/accounts；`test_m3_ticket3_analytics.py` 22 例 + slow 基准 |
| 4 前端骨架/总览 | DONE | `frontend/` 工程、token/组件、登录/总览；smoke e2e 14 checks |
| 5 管理页面 | DONE | 五个页面 + 跨页规则；admin e2e 32 checks |
| 6 交付/镜像/验收 | DONE | Dockerfile 前端阶段、compose 0.2.0、README/env；镜像冒烟 + 回滚演练 + 窄屏截图 |
| 7 实现验证 | DONE | `task7-verification.md`：unit 214 passed + quality 全绿 |

## Spec 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| 1 | 会话过期跳转登录页时没有任何提示，与文案表「登录已过期，请重新登录。」不一致 | Minor | `frontend/src/auth/AuthProvider.tsx:65-70`（修复前只清状态） | 采纳 → 自动修（toast） |
| 2 | 设计要求「声明滚动恢复策略」（FE-09），实现里没有滚动恢复 | Minor | `frontend/src/App.tsx` / `app-shell.tsx`（修复前无 `ScrollRestoration`） | 采纳 → 自动修（`<ScrollRestoration/>`） |
| 3 | 登录表单未用 react-hook-form + zod（design D-A5 的表单约定） | Minor | `frontend/src/pages/login-page.tsx:15-18` 注释 | 裁掉：登录只有一个必填字段，首屏 150 kB 预算是同一设计里的硬约束；冲突时取预算并在 Task 5 报告声明。管理页表单仍全部用 RHF+zod |

## Standards 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| 1 | 403 CSRF 重试路径里刷新 `/me` 的 `fetch` 在 try 之外，网络失败会抛出原始 `TypeError` 而不是统一的 `ApiError(NETWORK_ERROR)`，上层按 `ApiError` 分支展示的逻辑会漏掉 | Important | `frontend/src/lib/api.ts:110-117`（修复前 `await fetch` 在 try 外） | 采纳 → 自动修 |
| 2 | CSV 导出在 `anchor.click()` 后立刻 `revokeObjectURL`，部分浏览器（Firefox）可能在异步读取前 URL 已失效 | Minor | `frontend/src/lib/csv.ts:27-29` | 采纳 → 自动修（`setTimeout(...,0)`） |
| 3 | 应用启动时的 `/me` 401 会触发全局 `expired` 事件；加提示后会变成「匿名首访就弹会话过期」 | Important | `frontend/src/auth/AuthProvider.tsx:38-46` | 采纳 → 自动修（启动请求 `skipAuthRedirect`，401 视为匿名） |
| 4 | 窄屏下表格 `min-width` 强制横向滚动，账号页的「状态/操作」被挤出 360px 视口（设计要求窄屏保留名称/状态/操作） | Important | `frontend/src/components/ui/table.tsx:8`、`pages/accounts-page.tsx` 表格类 | 采纳 → 已在 Task 6 实现期修复（`md:` 前缀 + 次要列隐藏 + 操作折叠） |
| 5 | 筛选文本框逐字符发请求（日志错误码） | Minor | `frontend/src/pages/logs-page.tsx:33-41` | defer → 台账 T5 |
| 6 | 管理表单字段错误未设 `aria-invalid`/`aria-describedby` | Minor | `frontend/src/pages/accounts-page.tsx` 表单块 | defer → 台账 T4 |
| 7 | `QuotaManager.flush` 单条外键失败会让整批写入失败（既有代码，本 change 未改；`delete_account` 已同步清理计数，当前无产生孤儿计数的路径） | Minor | `backend/app/core/quota.py:129-150` | 既有（不修，见「既有问题」） |

## 自动修

- [impl-review-fix] `frontend/src/auth/AuthProvider.tsx`：启动 `/me` 用 `skipAuthRedirect`，401 记为
  匿名；全局 `expired` 事件补会话过期 toast（文案取自文案表）。
- [impl-review-fix] `frontend/src/lib/api.ts`：CSRF 刷新与重试都包进 try，网络失败统一成
  `ApiError(0, "NETWORK_ERROR", …)`。
- [impl-review-fix] `frontend/src/lib/csv.ts`：`revokeObjectURL` 延迟到下一轮事件循环。
- [impl-review-fix] `frontend/src/components/app-shell.tsx`：加 `<ScrollRestoration />`，声明按路由
  恢复滚动位置的策略。

修复后复审（第 1 轮，范围限定 `704d8b3` 的修复 diff）：未发现新的 Critical/Important；`SessionExpiredError`
分支保留为防御（启动路径已不再触发）。复审干净，提前结束。

## defer 台账

<!-- sdflow-lite:defer-ledger -->
| ID | 问题 | 去向 |
|---|---|---|
| T4 | 管理表单字段错误缺 `aria-invalid`/`aria-describedby` | `openspec/issues/open/T4.md` |
| T5 | 日志/用量筛选输入逐字符触发请求 | `openspec/issues/open/T5.md` |

## 既有问题

| # | 问题 | 证据锚 |
|---|---|---|
| 1 | `QuotaManager.flush` 一次事务写全部计数，任一条外键失败会整批回滚（flush 循环会记 exception 并在 2 秒后重试，不会静默丢失，但会一直失败直到重启）。本 change 的删除路径已清理内存计数，未新增触发面 | `backend/app/core/quota.py:129-150` |
| 2 | 设计把 INP 列为 CWV 目标，但 lab 工具拿不到 INP；已记录为不可得（Task 4/6 报告），不是实现缺口 | `openspec/changes/m3-admin-panel/impl-reports/task4-frontend-shell-overview.md` |

## 诚实边界

- 单 session 自查：实现者与审阅者同一上下文，存在自查偏置；未做跨模型第二意见。
- 引文与断言的语义对应、非局部 finding 的分类均无机械核验；本轮所有 finding 都真打开过对应
  文件核对（含修复后复审）。
- 浏览器 e2e 不属于 `sdflow-lite.json` 的自动层；本轮修复后重新跑了 smoke(14)/admin(32)/visual(6)
  三套冒烟，均为通过（截图在 `review/e2e-review/`）。
