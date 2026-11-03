---
ship-gate:
  verify: PASS
  reviewed_sha: 7afb87a609c628d29da11bea3b8ce423cb784999d3ed7dc082cfaa5ed0dbde14
  reviewed_manifest: MTAwNjQ0IGJsb2IgZjg1NDFmYzJmMjU5YjkxNDU0MjdlZDM3NTZjNGY5YzRmODNiZTE4ZgkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIGFhYzlmZjJlNWM2OTUxYjFiYWFhZjI1NDhiYTYxYjFkOTBlNWJhZTcJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIGU1MDE5ZmU3NmE4MTU4NGMzZWU3ZDU3M2Q1ZGYyZTE5NTJhOWIxMWUJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiBjNTRmY2I4NTUxZmMwM2Q1N2ExNTE0ZmZkYThlOTY5Mzc0MDVlYmFkCUFHRU5UUy5tZAAxMDA2NDQgYmxvYiA2OGI2N2RmMzMwMjY0ZTJlOGJjNDY2YTkxNTUyYTdjY2Q3M2NjZGYyCURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgYzg0NzMxNmYxMWNiMjliZTViYjQ3YzNlOGZlYTE3M2FiYjhlYjMzNwlSRUFETUUubWQAMDQwMDAwIHRyZWUgYTJmOWI1ZjkwZTZkNjkxZGM0Y2U5NTRlMWYwYWNmYjgwZjM1NTFlMgliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIGY2ZDBlNDAwZjM5ODc2NmU4ZDAzYjNjN2E1NjRlZDZmMGVlNjhhYTMJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDZhMDdhNTdjNTRiYmVhOGUxNGZhNzY0YjhmNzc2OGEwYzVlZjhhNmQJZG9jcwAwNDAwMDAgdHJlZSAyNDk3NmIzY2MzMjY1NDljNzE2OGM0ZmZhMWMxZTI1NzJkYTY0YWI0CWZyb250ZW5kADA0MDAwMCB0cmVlIGQxZmI2NzhkMGMyOWQwN2MyMmRjMDVhMTU1NzQyOTg5ZjA2OGEyYTYJc2NyaXB0cw==
---
# 实现验证报告 · m3-admin-panel

> ⚠️ 单 session 自证：测试由主 session 触发；同模型、不同上下文，非独立验证。
> 证据: verify-evidence-closeout.json @ e8e73db；verify-evidence-retest.json @ e8e73db
> 触发条件：收尾票通过行共同 SHA 为 `4df8684`；`git diff 4df8684..HEAD` 含 `openspec/` 外路径
> （代码审修复 4 个前端文件），故 closeout 与 retest 两套证据都跑。

## 方法

不信任复选框与既有报告措辞：逐条读 `specs/*/spec.md` 的 requirement/scenario，再到代码与测试里找
可机验锚点（测试名 / 文件:行 / 命令输出）。找不到锚点的一律记 gap。`tasks.md` 只用于需求追溯，
完成度以 `tickets.md` 与 impl-reports 为准。

## 需求逐条结论

### R-ADM-01 管理员登录与令牌（MODIFIED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 登录成功 | ✅ | `backend/app/api/admin.py` login 返回 token/expires_in/csrf_token；`test_login_sets_session_and_csrf_cookies` |
| Cookie 属性 | ✅ | `backend/app/api/deps.py:set_admin_cookies`（HttpOnly/session、可读 CSRF、Lax、Path=/、Max-Age）；同上用例断言 |
| 未带令牌访问 | ✅ | `test_cookie_write_requires_matching_csrf` 前置断言 401；`test_admin_endpoints_require_token` |
| Bearer 访问 | ✅ | `test_bearer_write_exempt_from_csrf`；既有 `test_login_and_me` |
| Bearer 无效且存在 cookie | ✅ | `test_invalid_bearer_does_not_fall_back_to_cookie` |
| Swagger Authorize | ✅ | `test_openapi_exposes_bearer_scheme` |
| HTTPS 反代 Cookie | ✅ | `test_secure_cookie_behind_trusted_proxy` / `test_secure_cookie_ignored_when_proxy_headers_untrusted`；镜像冒烟同样验证 |
| Cookie 写请求缺 CSRF | ✅ | `test_cookie_write_requires_matching_csrf`（缺/错 → 403 FORBIDDEN） |
| Cookie 写请求带 CSRF | ✅ | 同上（正确 token → 200） |
| 当前管理员 | ✅ | `test_cookie_session_can_read_admin_api`；`test_me_reissues_missing_csrf_cookie` |
| 登出 | ✅ | `test_logout_clears_cookies_and_revokes_browser_session`（204 + Max-Age=0 + 之后 401） |
| 暴力尝试 | ✅ | `test_login_rejects_wrong_password_and_rate_limits`（5 次后 429） |

### R-ADM-06 用量与日志查询（MODIFIED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 按厂商汇总 / 平均延迟 / 显示名称 | ✅ | `backend/app/api/admin.py:usage_summary`；`test_usage_summary_labels_latency_and_null_last` |
| 已删除实体分组 / 排序 | ✅ | 同上用例（`key=None` 单行且最后） |
| 自动路由失败 | ✅ | `test_overview_counts_auto_failures_separately`；summary `label=自动路由` |
| 汇总跨度上限 / 默认窗口 | ✅ | `test_time_window_validation`（90 天 400）；`test_usage_series_defaults_to_seven_local_days` |
| 日序列 / 仅日期结束值含当日 / 日期边界 | ✅ | `test_usage_series_buckets_by_shanghai_day`（半开区间 + 补零） |
| 时间范围倒置 / 序列跨度上限 | ✅ | `test_time_window_validation` |
| 日志分页 / 过滤 / 显示名称 / 非法时间 | ✅ | `test_logs_filters_pagination_and_names`、`test_logs_date_form_to_includes_whole_day` |
| 查询性能 p95 < 300ms | ✅ | slow 基准输出：series 24.2 / summary 18.0 / logs 8.0 ms（10 万条） |

### R-ADM-08 运行时设置读写（ADDED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 读取设置 / 只读项 | ✅ | `test_get_settings_defaults_and_readonly` |
| 部分更新 / 重启后保持 | ✅ | `test_settings_partial_update_applies_and_persists`、`test_settings_persist_across_process_restart` |
| 非法值 / 显式 null / 未知键 / 容量与预算上限 | ✅ | `test_settings_validation_reports_fields`（9 组参数化，含字段名） |
| 缓存参数变更清空 | ✅ | `test_settings_cache_change_clears_entries`（未变 False / 变更 True 且条目归零） |
| 请求预算生效（含信号量等待） | ✅ | `test_runtime_budget_covers_semaphore_wait`（150ms vs 1200ms 实测耗时差）、`test_scheduler_uses_remaining_budget_as_call_timeout` |
| 账号默认超时生效 | ✅ | `test_account_creation_uses_runtime_default_timeout`；PATCH 显式 null 400 |

### R-ADM-09 总览聚合（ADDED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 有数据 / 无请求（null 比率） | ✅ | `test_overview_aggregates_today_and_recent_errors`、`test_overview_without_requests_returns_nulls` |
| 可用账号数（含瞬时口径） | ✅ | `test_overview_available_accounts_is_read_only_snapshot`（禁用不计入；调用前后 registry 状态不变） |
| 近 7 日序列 | ✅ | 同上有数据用例（7 桶） |
| 自动路由失败计数 | ✅ | `test_overview_counts_auto_failures_separately`（成功 auto 不计） |
| 最近错误 | ✅ | 有账号名、无 OCR 原文（`"text" not in error`） |

### R-ADM-10 账号列表用量与归属（ADDED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 成功请求后用量增加 | ✅ | `test_accounts_quota_usage_and_owner_name`（respx 打真实 OCR 路径，三周期 +1） |
| 贡献者名称 / 删除后 null | ✅ | 同上（创建响应带 owner_name；删除成员后列表为 null） |
| 未配置限额 | ✅ | 账号页 e2e「未配置额度，可能超用」；`limit` 字段为 null |
| 周期切换 | ✅ | `test_account_quota_daily_resets_after_period_change` |
| 删除账号清理配额 | ✅ | `test_delete_account_clears_quota_counters`（两次 flush 无外键错误） |

### R-SCH-03 故障切换与总预算（MODIFIED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 运行时预算生效 | ✅ | `Scheduler.recognize(..., deadline)`；`test_scheduler_uses_remaining_budget_as_call_timeout` |
| 主账号 5xx 切换 / 输入错误不回退 / 厂商持续 5xx | ✅ | 既有 `test_ticket3_scheduler.py` 用例全绿（214 passed 内） |

### R-CAC-02 缓存边界（MODIFIED）

| 场景 | 结论 | 锚点 |
|---|---|---|
| 空文本不缓存 / 容量淘汰 | ✅ | 既有 `test_ticket5_ssrf_cache.py` 全绿 |
| 运行时参数变更 | ✅ | `ResultCache.reconfigure` + `test_cache_reconfigure_clears_entries_only_on_change`；PUT 后 `cache_cleared` |

### R-PANEL-01 ~ R-PANEL-12（ADDED）

| 需求 | 结论 | 锚点 |
|---|---|---|
| R-PANEL-01 登录与会话 | ✅ | e2e smoke：登录/刷新保持/未登录跳转/登出/回跳/过期跳转 |
| R-PANEL-02 路由与导航 | ✅ | e2e smoke「all routes render」「unknown route 404」；`AppShell` 侧栏 + 抽屉 |
| R-PANEL-03 总览 | ✅ | e2e overview 指标/配额标尺；`test_overview_*` |
| R-PANEL-04 账号管理界面 | ✅ | e2e admin：创建/编辑留空凭证/超时保持/测活/重置文案/过滤/删除 |
| R-PANEL-05 成员与 Key | ✅ | e2e admin：创建成员/Key 明文一次/列表仅前缀/级联提示/删除 |
| R-PANEL-06 用量界面 | ✅ | e2e admin：筛选进 URL/分组/CSV（BOM+CRLF+表头） |
| R-PANEL-07 日志界面 | ✅ | e2e admin：状态过滤/详情元数据/分页 |
| R-PANEL-08 设置界面 | ✅ | e2e admin：保存/持久化/字段错误/缓存清空提示/清空条数/只读区 |
| R-PANEL-09 三态与重复提交 | ✅ | e2e：双击只发一次 PUT；三态在各页；GET 重试策略在 `lib/query.ts` |
| R-PANEL-10 视觉与响应式 | ✅ | 1440/360 截图（`review/e2e-task5|6|review`）；无渐变/投影；状态点+文字；360px 无溢出 |
| R-PANEL-11 同源托管与回退 | ✅ | `test_panel_serves_entry_assets_and_fallbacks`、`test_panel_missing_returns_fixed_404`、`test_panel_index_is_reread_after_rebuild`；镜像冒烟 |
| R-PANEL-12 前端安全与数据最小化 | ✅ | CSP/头 e2e；web storage 无 token；Key 明文一次；凭证只回显掩码（`test_account_*` 既有断言） |

### R-DEP-07 / R-DEP-09 / R-DEP-10

| 需求 | 结论 | 锚点 |
|---|---|---|
| R-DEP-07 构建可复现、索引可参数化 | ✅ | Dockerfile `UV_DEFAULT_INDEX` + `NPM_REGISTRY`；离线构建成功（Task 6） |
| R-DEP-09 面板产物随镜像 | ✅ | 镜像内 `/app/static/index.html` + assets；根路径 200 HTML；产物不含敏感值扫描通过 |
| R-DEP-10 版本与回滚锚 | ✅ | compose `0.2.0`；`docker image inspect` 证明 `0.1.0` id 未变；回滚演练（旧镜像 255 失败 → 恢复备份 → 200） |

## 证据汇总

- closeout：`verify-evidence-closeout.json` —— unit 214 passed / quality 3 道门，SHA `e8e73db`。
- retest：`verify-evidence-retest.json` —— 同上，SHA `e8e73db`，`clean_tree=true`、`ok=true`。
- 收尾票证据：`impl-reports/task7-verification.md` 通过 `check_impl_report.py`；层集来自
  `suite_scope.py --mode closeout`（未手抄）。
- 用例数三态：两层均非 0（quality 层回显 3 道质量门：lint/typecheck/build，作为 3 个用例计入）。

## 缺口

- **无核心缺口。**
- Minor（不阻塞）：defer 台账 T4（表单 aria-invalid）、T5（筛选输入防抖）未实现，已列入 hand-off；
  INP 无 lab 实测值（RUM 不在本 change 范围）。
