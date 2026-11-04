---
ship-gate:
  verify: PASS
  reviewed_sha: a64272da86b0bc147d93634bad21ccd21247a930745421585a3cacd858905e1c
  reviewed_manifest: MTAwNjQ0IGJsb2IgZjg1NDFmYzJmMjU5YjkxNDU0MjdlZDM3NTZjNGY5YzRmODNiZTE4ZgkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIDk5OTI5YjI0MzRjODNiODZlZDYwYTAxOGQ3NTY3YzdlZGI0M2I1MzYJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIGU1MDE5ZmU3NmE4MTU4NGMzZWU3ZDU3M2Q1ZGYyZTE5NTJhOWIxMWUJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiBjNTRmY2I4NTUxZmMwM2Q1N2ExNTE0ZmZkYThlOTY5Mzc0MDVlYmFkCUFHRU5UUy5tZAAxMDA2NDQgYmxvYiA2Yjc2OGUwZjhjMmJhMjdlYTY0MjFkYTI5MDM0N2JmZWZhNTY4MjBjCURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgNzYxODA4NTI1NTMyYTM2YTg2MzAxNTIzYzA2OTM1ZmIwMWJlYjBlNQlSRUFETUUubWQAMDQwMDAwIHRyZWUgMjk3NDczZTZlYTNjNzEyODRlYjdiZTY4OGYwYmJlMmEyNTAwNTI4NwliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIGQ0MmM5NTJhNDc5YjIwMTJhZDkwZTM2M2QyMDYzNTM4MjE3MWQ2YTcJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDE4MGNkNjA0ZjNmZmJkM2YyMGRlNzNlZDBlZGY2NDMxYTcwM2NlNWYJZG9jcwAwNDAwMDAgdHJlZSA5OWQxYjk0MzMwMjg5NTQ2ZWE0OGZiNGU0ZmMxYzZlMGY0NzBkM2MxCWZyb250ZW5kADA0MDAwMCB0cmVlIDViOGM1Njg2MjRjMmRiMzIwNWRjNDgwZWEwOWMwODBhMDU5YzVhODkJc2NyaXB0cw==
---
# Verify Report · m4-local-ocr

> ⚠️ 单 session 自证：测试由主 session 触发；同模型、不同上下文，非独立验证。
> 证据: verify-evidence-closeout.json @ 6f71ca8；verify-evidence-retest.json 未生成（closeout 后无代码改动，未触发重跑）。

## 结论

**PASS**（Minor 缺口 3 项，不阻塞）

## 逐条需求

| 需求 | 判定 | 证据锚 |
|---|---|---|
| R-LOC-01 引擎与模型来源 | ✅ | `backend/pyproject.toml` extra `local`；`backend/app/workers/local_ocr.py`；`test_real_engine_recognizes_text` + `test_real_engine_does_not_open_sockets`（slow） |
| R-LOC-02 进程隔离与并发 | ✅ | `local_engine.py` `SPAWN_CONTEXT.Pool` + `worker_init`；`test_spawn_context_is_used`、`test_worker_module_does_not_import_application_modules`、`test_real_pool_runs_two_tasks_in_parallel` |
| R-LOC-03 输出归一化 | ✅ | `local_ocr.py` `run_ocr`（txts/scores → text/lines）；`test_real_engine_recognizes_text`、`test_worker_empty_text_reports_warning` |
| R-LOC-04 超时、取消与恢复 | ✅ | `local_engine.py` `_run_in_pool`/`_terminate_pool`/generation；`test_timeout_terminates_pool_and_leaves_starting_state`、`test_recognize_recovers_after_timeout`、`test_rebuilt_pool_cancels_in_flight_request`、`test_real_pool_timeout_terminates_workers` |
| R-LOC-05 开关与就绪状态 | ✅ | `local_engine.py` 状态机/startup restore/status；`test_startup_restores_enabled_and_set_enabled_is_idempotent`、`test_disable_during_warmup_stays_stopped`、`test_status_unavailable_when_dependencies_missing`、`test_restart_restores_enabled_engine` |
| R-SCH-03 故障切换与总预算 | ✅ | `scheduler.py` `_recognize_cloud` 子 deadline；`test_auto_reserve_budget_boundaries`（1/3/5/20s） |
| R-SCH-05 显式厂商不回退 | ✅ | `scheduler.py` 分支；`test_explicit_local_skips_cloud`、`test_explicit_cloud_does_not_fall_back` |
| R-SCH-07 auto 兜底与预算预留 | ✅ | `scheduler.py` `reserve_eff` + fallback；`test_auto_reserves_budget_and_falls_back`、`test_auto_without_min_budget_returns_cloud_error`、`test_input_error_is_not_fallen_back` |
| R-API-01 单张图片识别 | ✅ | `public.py` `VALID_PROVIDERS` + `_ensure_provider_enabled`（缓存前）；`test_api_local_disabled_403_wins_over_cache`、`test_invalid_provider_and_language_rejected` |
| R-API-03 图片规范化 | ✅ | `utils/images.py` local 分支（raw JPEG/10000px/no base64）；`test_local_images_use_raw_jpeg_limits` |
| R-API-05 统一响应与错误码 | ✅ | `public.py` `quota_used` 派生 + `_LOCAL_ERROR_COPY`；`test_api_local_success_records_zero_quota`、`test_api_local_error_mapping` |
| R-API-06 服务元数据 | ✅ | `public.py` `/v1/providers` local 条目；`test_providers_includes_local_entry` |
| R-QTA-01 成功请求记账 | ✅ | `models.py` 四值约束 + `0003_usage_provider_local.py`；`test_migration_roundtrip_maps_local_to_auto`、`test_create_all_accepts_local_event`、`test_api_local_success_records_zero_quota` |
| R-CAC-01 缓存键与命中 | ✅ | `public.py` 门禁先于 `cache.get`；`test_api_local_disabled_403_wins_over_cache` |
| R-CAC-02 缓存边界 | ✅ | `admin.py` `_apply_settings` 开关变化 `cache.clear()`；`test_toggle_enables_engine_clears_cache_and_is_idempotent` |
| R-CAC-03 管理端清空 | ✅ | 既有 `/cache/clear` 未改；全量套件通过 |
| R-ADM-06 用量与日志查询 | ✅ | `admin.py` `dict(PROVIDER_NAMES)` + `_event_conditions`；`test_local_provider_label_in_summary_and_logs` |
| R-ADM-08 运行时设置读写 | ✅ | `runtime_settings.py` + `admin.py` `_apply_settings`；`test_toggle_enables_engine_clears_cache_and_is_idempotent`、`test_toggle_type_error_reports_field`、`test_restart_restores_enabled_engine` |
| R-ADM-09 总览聚合 | ✅ | `admin.py` overview local 行；`test_overview_includes_local_row_and_reconciles`、`test_overview_omits_local_row_without_events` |
| R-ADM-11 本地 OCR 状态查询 | ✅ | `admin.py` `/local-ocr/status`；`test_local_status_defaults`、`test_local_status_requires_admin`、`test_status_error_is_sanitized` |
| R-PANEL-08 设置界面 | ✅ | `settings-page.tsx` 开关/状态卡/轮询/dirty 提交；`local-ocr.mjs` 13 项 e2e |
| R-DEP-11 运行镜像内置本地依赖 | ✅ | `Dockerfile` `--extra local` + libgomp1 + import 校验；镜像构建 559MB、镜像冒烟 4 项、离线 ready、回滚演练 |

## tasks.md 对账

17 项全部勾选（0 项未完成）；tasks 的 R-ID 与 delta spec 一一对应，无幽灵任务。

## 缺口（Minor，不阻塞）

1. **design NFR 的实测值未回填 design.md**：design 写「下载约 110–130MB / 安装后约 350MB（估算，实施后回填）」；实测镜像 559MB（较 0.2.1 的 226MB 增加 333MB）、`/app/.venv` 432MB。README 已回填；改 design 会让已批准的设计锚失鲜，需走重审，故留作后续文档小改。
2. **全量 `frontend/e2e/admin.mjs` 依赖外部种子「Ming」**：全新库上会失败；本 change 用独立的 `local-ocr.mjs` 覆盖本地 OCR e2e。属既有测试基建缺口。
3. **镜像冒烟的「子进程数」未在状态接口显式返回**：状态报 `concurrency=1`；设计没要求子进程计数字段，作为运维细节留待需要时加。

## 证据摘要

- closeout：`unit` 255 passed（exit 0，171s）；`quality` 3 gates（exit 0，13s）；clean_tree=true。
- 代码审修复后：全量 255、slow 6、frontend 3、ruff/mypy 0（见 `code-review-report.md`）。
- 镜像：0.3.0 559MB；`import rapidocr, onnxruntime` ok；冒烟 ready/显式 local/auto 兜底/关闭 403；`--network none` 下 ready；回滚 `downgrade -1` → local 行变 auto；0.2.1 镜像在该库上 healthz ok。
