---
ship-gate:
  code_review: pass
  reviewed_sha: a64272da86b0bc147d93634bad21ccd21247a930745421585a3cacd858905e1c
  reviewed_manifest: MTAwNjQ0IGJsb2IgZjg1NDFmYzJmMjU5YjkxNDU0MjdlZDM3NTZjNGY5YzRmODNiZTE4ZgkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIDk5OTI5YjI0MzRjODNiODZlZDYwYTAxOGQ3NTY3YzdlZGI0M2I1MzYJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIGU1MDE5ZmU3NmE4MTU4NGMzZWU3ZDU3M2Q1ZGYyZTE5NTJhOWIxMWUJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiBjNTRmY2I4NTUxZmMwM2Q1N2ExNTE0ZmZkYThlOTY5Mzc0MDVlYmFkCUFHRU5UUy5tZAAxMDA2NDQgYmxvYiA2Yjc2OGUwZjhjMmJhMjdlYTY0MjFkYTI5MDM0N2JmZWZhNTY4MjBjCURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgNzYxODA4NTI1NTMyYTM2YTg2MzAxNTIzYzA2OTM1ZmIwMWJlYjBlNQlSRUFETUUubWQAMDQwMDAwIHRyZWUgMjk3NDczZTZlYTNjNzEyODRlYjdiZTY4OGYwYmJlMmEyNTAwNTI4NwliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIGQ0MmM5NTJhNDc5YjIwMTJhZDkwZTM2M2QyMDYzNTM4MjE3MWQ2YTcJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDE4MGNkNjA0ZjNmZmJkM2YyMGRlNzNlZDBlZGY2NDMxYTcwM2NlNWYJZG9jcwAwNDAwMDAgdHJlZSA5OWQxYjk0MzMwMjg5NTQ2ZWE0OGZiNGU0ZmMxYzZlMGY0NzBkM2MxCWZyb250ZW5kADA0MDAwMCB0cmVlIDViOGM1Njg2MjRjMmRiMzIwNWRjNDgwZWEwOWMwODBhMDU5YzVhODkJc2NyaXB0cw==
---
# 代码审报告 · m4-local-ocr

> ⚠️ 单 session 自查：实现者与审阅者为同一上下文；同模型、不同上下文，非独立评审。
> dispatch: single-session
> 完成度来源: tickets.md

## 结论

pass（自动修 7 项；无 Critical 残留；无 defer）

## scope 审计

**完成度（tickets.md 单一源）**

| 票 | 五态 | 证据 |
|---|---|---|
| Task 1 本地引擎与进程池 | DONE | `3e6c319`；extra/worker/engine/13 项单测 + 4 项 slow |
| Task 2 公共路由、兜底与迁移 | DONE | `f6ab40e`；0003/models.py/scheduler/public/images/18 项 API 测试 |
| Task 3 记账标签与总览对账 | DONE | `a494435`；local 行/标签/筛选/类型拆分 + 3 项 API 测试 |
| Task 4 管理端开关、状态与面板 | DONE | `fcbdfab`；settings/status/设置卡 + 7 项 API + 13 项 e2e |
| Task 5 镜像、文档与集成验收 | DONE | `249fd49`；0.3.0 镜像 559MB、镜像冒烟、离线 ready、回滚 + p95 |
| Task 6 实现验证 | DONE | `d6f38b5`；closeout 252+3（修复后 255+3） |

**scope-drift**：无 `SCOPE-CREEP`。`Dockerfile` 的 `APT_MIRROR` 是 Task 5「缺 libgomp1 构建期安装」的离线镜像参数；`frontend/package.json` 的 `e2e:local` 与 `scripts/smoke_local_ocr.py` 是 Task 5 的验收工具；`frontend/e2e/admin.mjs` 增量是 Task 4 的 e2e 检查。均落在 proposal `What Changes` / tickets 内。

**切片偏离对账**：`impl-reports/planning-decisions.md` 申报「0003/models.py 迁移前移到 Task 2、T3 收缩为标签与对账」；实际 diff 与申报一致（0003 在 Task 2 提交 `f6ab40e`，Task 3 只改 admin 标签/overview/前端）。无未申报偏离。

**对账差异**：`tasks.md` 的复选框尚未勾选（计划/追溯用途），`tickets.md` 是执行单一源；两者 R-ID 无冲突，留待 verify 阶段回填 tasks.md。

## Spec 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| 1 | 识别超时后只 terminate 池并置 `starting`，没有重建 warmup；后续请求等一个永远不会 set 的 `_ready`，local 永久不可用 | Critical | `backend/app/core/local_engine.py` 的 `_run_in_pool` 超时分支 / `recognize`；修复见 `7064fae` | 采纳（已修） |
| 2 | warmup 失败时 `_mark_error` 不唤醒正在等 `starting` 的请求，白等最多 10s | Important | `local_engine.py` `_mark_error`；修复见 `7064fae` | 采纳（已修） |
| 3 | disable 与 warmup 失败竞态：`_start_pool` 的宽泛 except 会把 `stopped` 覆盖成 `error` | Important | `local_engine.py` `_start_pool`；修复见 `7064fae` | 采纳（已修） |
| 4 | `_terminate_pool` 无上限；native worker 卡死时关闭可能超过 design 的 20s 上限 | Important | `local_engine.py` `_terminate_pool`；修复见 `7064fae` | 采纳（已修） |
| 5 | local 未知错误码回退到 `exc.message`，可能把内部异常文本透给客户端 | Minor | `backend/app/api/public.py` `_LOCAL_ERROR_COPY.get(..., exc.message)`；修复为通用文案 | 采纳（已修） |

## Standards 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| 1 | design §可观测性列了 `local_ocr.fallback`，Scheduler 兜底路径未记该事件（CR-07） | Important | `backend/app/core/scheduler.py` 的 `except (NoCandidate, …)`；修复见 `7064fae` | 采纳（已修） |
| 2 | 后端若返回 `local_ocr_enabled` 字段错误，设置页开关处不显示（CR-FE-08） | Minor | `frontend/src/pages/settings-page.tsx` 开关；修复见 `7064fae` | 采纳（已修） |
| 3 | 既有测试改动（local 400→403、迁移 downgrade 目标）是否削弱（CR-12） | Minor | `test_ticket3_ocr_api.py`、`test_m3_ticket2_settings.py` | 裁掉：spec 变更（local 成为合法 provider；head 到 0003），断言未被放宽 |
| 4 | 状态卡加载中开关仍可点，可能先于 installed 判定提交 local 字段 | Minor | `settings-page.tsx` `disabled={statusQuery.data?.installed === false}` | 裁掉：后端会校验/持久化偏好；installed=false 时引擎保持 unavailable，不是运行期错误 |

## 自动修

- [impl-review-fix] 识别超时后 `recognize` 触发 `_spawn_warmup()`，池回收后自动重建（`local_engine.py`）。
- [impl-review-fix] `_mark_error` set `_ready`，等就绪的请求快速失败（`local_engine.py`）。
- [impl-review-fix] `_start_pool` 区分 `LocalCancelled` 与真实失败；disabled 时不再覆盖 `stopped`（`local_engine.py`）。
- [impl-review-fix] `_terminate_pool` 加 5s 上限，超时记 `local_ocr.terminate_timeout`（`local_engine.py`）。
- [impl-review-fix] 未知 local 错误码使用通用文案，不回显 `exc.message`（`public.py`）。
- [impl-review-fix] Scheduler 兜底记 `local_ocr.fallback`（含 `from_reason`）（`scheduler.py`）。
- [impl-review-fix] 设置页开关下显示 `local_ocr_enabled` 字段错误（`settings-page.tsx`）。

复审：修复后重跑票级/全量/slow/ruff/mypy/前端质量门（见下），无新增 Critical/Important；修复 diff 即 `7064fae`，报告锚该提交。

## 修复后验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 255 | 7064fae |
| slow 套件 | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q -m slow` | 0 | 6 | 7064fae |
| 前端质量门 | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build` | 0 | 3 | 7064fae |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests scripts/smoke_local_ocr.py` | 0 | 未知 | 7064fae |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | 7064fae |

## defer 台账

<!-- sdflow-lite:defer-ledger -->
| ID | 问题 | 去向 |
|---|---|---|

无 defer 条目。

## 既有问题

| # | 问题 | 证据锚 |
|---|---|---|
| 1 | `frontend/e2e/admin.mjs` 用量页依赖外部种子「Ming」，全新库上该全量 e2e 会失败；本 change 用独立的 `local-ocr.mjs` 覆盖本地 OCR 场景 | `frontend/e2e/admin.mjs:171`（该行不在本 change 改动行内；未由本 change 触发） |

## 诚实边界

- 单 session 自查：实现者与审阅者为同一上下文；同模型、不同上下文，非独立评审。
- 引文与语义对应无机械核验；本报告的 file:line 均已亲验，但没有 `ref-check` 机械门。
- 未启用派发（用户未要求代码审派发）；scope 审计、领域、对抗与历史镜均由主 session 亲做。历史镜触发判据：`uv.lock` 有 602 行新增（生成物），对生成物无历史审查价值；对 `scheduler.py` 的既有云路径做了 `git log -S` 抽查，未见被本次重蹈的旧修复。
- 镜像构建/冒烟是本地 Docker 证据（0.3.0 559MB、0.2.1 从 tag 重建），未 push。
- 全量 `admin.mjs` 的外部种子缺口列为既有问题，未伪造种子或跳过断言。
