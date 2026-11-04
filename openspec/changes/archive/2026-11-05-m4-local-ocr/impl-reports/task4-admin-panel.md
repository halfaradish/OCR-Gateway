---
ticket: 4
title: 管理端开关、状态与面板
head: a494435ff7318ec08bba67fa2b795ec4e29a048d
status: DONE
suite_scope: {"domains":["backend","frontend"],"layers":["unit","quality"],"base":"a494435","mode":"closeout"}
---

# Task 4 · 管理端开关、状态与面板

## 改动

- **运行时设置**：`RuntimeSettings`/`FIELD_RULES` 增 `local_ocr_enabled`（bool、默认 false、类型错误文案「本地 OCR 开关必须是布尔值。」）；`_apply_settings` 在 commit 后调用 `LocalEngine.set_enabled`（引擎侧幂等，ready/starting 重复 true 不建第二池），开关变化清空缓存并返回 `cache_cleared=true`。
- **状态接口**：新增 `GET /api/admin/local-ocr/status`（管理员鉴权），透传 `LocalEngine.status(total_budget_ms=runtime.request_deadline_ms)`：enabled/installed/state/concurrency/timeout+effective/reserve+effective/model/last_latency/last_error/next_retry/requests_total/fallback_total；`last_error` 已脱敏。
- **启动恢复**：lifespan 按 `runtime.local_ocr_enabled` 建池（Task 1 已有 `start()`，Task 4 接通设置持久化值）。
- **设置页**：可编辑表单增「本地 OCR」开关（`Controller` 绑定 `local_ocr_enabled`），同一白色主面板内新增状态区：
  - 独立 `useQuery`（`["local-ocr-status"]`）+ 同高骨架；加载/错误（带重试）/依赖缺失/正常四态；
  - `starting` 时 `refetchInterval` 1s 轮询，`ready`/`stopped` 停止；
  - 开关草稿以表单为唯一来源，状态卡只读；保存只提交 `dirtyFields`，`installed=false` 时剔除该字段；
  - 状态点 + 文字（扩展 `StatusDot` 的 local 状态文案）、模型/最近耗时/请求与兜底/最近错误（截断 + `title`）、窄屏单列。
- **e2e**：新增 `frontend/e2e/local-ocr.mjs`（登录 → 设置页 → 开关可见且可点 → 保存 → starting→ready → 刷新后仍 ready 且开关保持 → 关闭后 stopped）；`admin.mjs` 的设置段也增加同样的本地 OCR 开启/就绪检查。
- **测试**：新增 `test_m4_ticket4_admin_local.py`（状态默认值/401、开关启用+清缓存+幂等、类型错误、重启恢复、依赖缺失、预热失败脱敏与退避）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m4_ticket4_admin_local.py -q` | 0 | 7 | a494435 |
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 252 | a494435 |
| 前端质量门 | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build && echo "frontend quality gates passed: 3"` | 0 | 3 | a494435 |
| 本地 OCR e2e | `E2E_BASE_URL=http://127.0.0.1:8011 node frontend/e2e/local-ocr.mjs` | 0 | 13 | a494435 |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests/test_m4_ticket4_admin_local.py` | 0 | 未知 | a494435 |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | a494435 |

## concerns

- **`admin.mjs` 全量 e2e 依赖外部种子数据**：脚本在用量页等待「Ming」（仓库内无种子脚本），在全新临时库上会失败；这是既有测试基建缺口，不是本 change 引入。本轮用独立的 `local-ocr.mjs` 覆盖本票的 e2e 场景（7 项全过），并在 `admin.mjs` 的设置段补了同样的检查，待有种子数据时可随全量套件跑。
- **`installed=false` 时开关禁用但持久化值可能仍为 true**：API 允许保存 true（偏好持久化），引擎保持 `unavailable` 且不建池；面板按 spec 禁用开关并不提交该字段。重启后若镜像补上 extra，会按持久化 true 自动建池。
- **状态卡与设置表单的双源**：开关只读表单值，状态卡只读 status；保存成功后 invalidate status，避免 status 反向改动表单草稿。
- **e2e 覆盖**：13 项检查含「状态慢时设置区仍可编辑」「加载骨架」「内联错误+重试恢复」「刷新后开关保持/ready」「480px 开关可见」；`last_error` 的截断/展开与窄屏单列是 CSS 层（`truncate` + `title`、`flex-col`/`md:grid-cols-2`），e2e 只验证可见性，未做像素级断言。
- **e2e 临时服务器**：用临时 DATA_DIR + 本地 dist + 端口 8011 启动（8000 被旧容器占用），跑完已停止；未污染仓库数据。
