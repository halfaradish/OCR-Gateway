---
ship-gate:
  verify: PASS
  reviewed_sha: d5d1e8793651b5ef8a32dd5262e85dc38353368e3a93b02e6aa1bd74f1c1e676
  reviewed_manifest: MTAwNjQ0IGJsb2IgYmUzMGQyNjU5NWIzODM1M2EwYmJmZjBiMGRlNTE4MGFjZWM1YTFiNAkuZW52LmV4YW1wbGUAMTAwNjQ0IGJsb2IgMjgzMzdlNWJkNTc3YzU5YTc3ZTAzZDUxZjZmZDI2NDE0ZTU3NjU2YwkuZ2l0aWdub3JlADEwMDY0NCBibG9iIDQ2NjY3N2Y0NTdhMTJiNTgxYzQxMTQ4MmQzZWQxOTQzMTQyNjI1OTkJQUdFTlRTLm1kADEwMDY0NCBibG9iIDcxNjM5MGVmMDNkNTNlMTI3ODFhNzVhZTU1YWQ4ZmE3YmQ5MGNkOTEJUkVBRE1FLm1kADA0MDAwMCB0cmVlIDVkYzIxNGM5MzJhOTkwMGU3ZjdhZGMwYWY4NDFiYmFiYzc2Nzg3OWUJYmFja2VuZAAwNDAwMDAgdHJlZSA2YTA3YTU3YzU0YmJlYThlMTRmYTc2NGI4Zjc3NjhhMGM1ZWY4YTZkCWRvY3M=
---
# Verify 报告 · ocr-gateway-mvp

> ⚠️ 单 session 自证：测试由主 session 触发；同模型、不同上下文，非独立验证。
证据: verify-evidence-closeout.json @ 0475da5；verify-evidence-retest.json @ 0db87a3（两 SHA 之间 `git diff -- . ':!openspec'` 为空，代码内容一致）

## 结论

**PASS**（附环境性缺口：真实百度/腾讯账号识别因本地凭证未配置未执行，契约测试默认 skip）。
closeout 与 retest 的 `unit` 层均 exit=0、count=148、0 failed；ruff/mypy 绿。收尾票报告
`impl-reports/task6-closeout.md` 通过 `check_impl_report.py`。

## 需求逐条核对

### provider-adapters

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-ADP-01 百度通用文字识别适配 | ✅ | `backend/app/providers/baidu.py:122`（token 缓存/刷新）；`backend/tests/test_ticket3_baidu.py::test_token_is_cached_across_calls`、`::test_auth_error_110_refreshes_token_once`、`::test_language_mapping_uses_chn_eng` |
| R-ADP-02 腾讯通用印刷体识别适配 | ✅ | `backend/app/providers/tencent.py`（TC3/`GeneralBasicOCR`）；`backend/tests/test_ticket4_tencent.py::test_tc3_golden_signature_matches_official_example`、`::test_tencent_success_maps_confidence_and_order` |
| R-ADP-03 结果归一化 | ✅ | `backend/app/api/public.py`（text/lines + `EMPTY_TEXT`）；`backend/tests/test_ticket3_ocr_api.py::test_empty_text_returns_warning`、`::test_multipart_success_and_accounting` |
| R-ADP-04 厂商错误分类 | ✅ | `backend/app/providers/baidu.py`/`tencent.py` 映射表；`backend/tests/test_ticket3_baidu.py::test_error_codes_map_to_kinds`、`backend/tests/test_ticket4_tencent.py::test_tencent_error_codes_map_to_kinds`、`::test_signature_expire_is_provider_error_with_30s` |
| R-ADP-05 单账号测活 | ✅ | `backend/app/api/admin.py:420`；`backend/tests/test_ticket4_switching.py::test_account_probe_success_has_no_side_effects`、`::test_account_probe_failure_reports_classification` |

### admin-api

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-ADM-01 管理员登录与令牌 | ✅ | `backend/app/api/admin.py` 登录/限速；`backend/tests/test_ticket2_admin.py::test_login_and_me`、`::test_login_rejects_wrong_password_and_rate_limits`、`::test_admin_token_expiry`、`::test_login_uses_forwarded_ip_when_trusted` |
| R-ADM-02 成员管理 | ✅ | `backend/tests/test_ticket2_admin.py::test_user_crud_and_duplicate_name`、`::test_disabled_user_invalidates_key` |
| R-ADM-03 API Key 管理 | ✅ | `backend/tests/test_ticket2_admin.py::test_api_key_plaintext_only_once_and_defaults`、`::test_api_key_explicit_null_limits`、`::test_revoked_key_returns_401` |
| R-ADM-04 账号管理与凭证保护 | ✅ | `backend/app/security.py` AES-GCM；`backend/tests/test_ticket2_admin.py::test_account_credentials_are_encrypted_and_masked`、`::test_account_missing_secret_key_returns_400` |
| R-ADM-05 账号测活与状态重置 | ✅ | `backend/app/api/admin.py:389`；`backend/tests/test_ticket4_switching.py::test_reset_state_recovers_invalid_account`、`::test_reset_state_clears_quota_counters` |
| R-ADM-06 用量与日志查询 | ✅ | `backend/app/api/admin.py` summary/logs；`backend/tests/test_ticket5_api.py::test_usage_summary_and_logs` |
| R-ADM-07 配额模板查询 | ✅ | `backend/app/providers/templates.py`；`backend/tests/test_ticket2_admin.py::test_quota_templates_and_no_auto_apply` |

### ocr-api

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-API-01 单张图片识别 | ✅ | `backend/app/api/public.py`；`backend/tests/test_ticket3_ocr_api.py::test_multipart_success_and_accounting`、`::test_base64_success`、`::test_both_inputs_rejected`、`::test_invalid_provider_and_language_rejected` |
| R-API-02 URL 图片输入 | ✅ | `backend/app/utils/ssrf.py`；`backend/tests/test_ticket5_ssrf_cache.py` 全套、`backend/tests/test_ticket5_api.py::test_url_input_success_and_private_rejection` |
| R-API-03 图片规范化 | ✅ | `backend/app/utils/images.py`；`backend/tests/test_ticket3_images.py::test_applies_exif_rotation`、`::test_downscales_to_baidu_max_side`、`::test_rejects_pixel_bomb_before_decode`、`::test_accepts_bmp_and_emits_jpeg` |
| R-API-04 API Key 鉴权与限额 | ✅ | `backend/app/api/deps.py`；`backend/tests/test_ticket2_admin.py::test_api_key_auth_errors`、`::test_rpm_limit_returns_429`、`::test_daily_limit_returns_quota_exceeded`、`::test_rpm_bucket_recovers_after_window` |
| R-API-05 统一响应与错误码 | ✅ | `backend/app/api/public.py`；`backend/tests/test_ticket3_ocr_api.py::test_provider_5xx_returns_502_and_does_not_charge`、`::test_global_concurrency_returns_503`、`backend/tests/test_ticket3_scheduler.py::test_scheduler_deadline_returns_504` |
| R-API-06 服务元数据与健康检查 | ✅ | `backend/app/main.py:/healthz`；`backend/tests/test_ticket1_bootstrap.py::test_healthz_ok`、`::test_healthz_reports_database_error`、`backend/tests/test_ticket3_ocr_api.py::test_providers_and_me` |

### account-pool-scheduling

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-SCH-01 候选过滤 | ✅ | `backend/app/core/registry.py:candidates`；`backend/tests/test_ticket3_scheduler.py::test_cooling_accounts_are_excluded_and_recover_lazily`、`::test_concurrency_limit_excludes_account`、`::test_quota_exhaustion_excludes_account`、`::test_qps_bucket_excludes_account` |
| R-SCH-02 候选排序 | ✅ | `backend/tests/test_ticket3_scheduler.py::test_provider_filter_and_priority_sorting`、`::test_sorting_uses_ewma_last_used_and_weight`、`::test_ewma_updates_on_success` |
| R-SCH-03 故障切换与总预算 | ✅ | `backend/app/core/scheduler.py`；`backend/tests/test_ticket3_scheduler.py::test_scheduler_switches_on_retryable_error`、`::test_scheduler_input_error_does_not_switch`、`::test_scheduler_all_provider_errors_return_502`、`backend/tests/test_ticket3_ocr_api.py::test_disabled_primary_uses_backup_account` |
| R-SCH-04 状态与冷却 | ✅ | `backend/tests/test_ticket3_scheduler.py::test_failure_marks_account_state`、`backend/tests/test_ticket3_ocr_api.py::test_auth_failure_marks_account_invalid`、`::test_cooling_account_recovers_after_cooldown`、`backend/tests/test_ticket4_switching.py::test_signature_expire_cools_not_invalid` |
| R-SCH-05 显式厂商不回退 | ✅ | `backend/tests/test_ticket4_switching.py::test_explicit_baidu_does_not_use_tencent`、`::test_explicit_tencent_does_not_use_baidu`、`::test_auto_falls_back_to_tencent` |
| R-SCH-06 单进程运行时状态 | ✅ | `backend/app/core/registry.py:load`；`backend/tests/test_ticket1_bootstrap.py::test_single_worker_guard`、`::test_lifespan_refuses_multiple_workers`、`::test_sqlite_pragmas`、`backend/tests/test_ticket3_scheduler.py::test_ewma_updates_on_success` |

### quota-accounting

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-QTA-01 成功请求记账 | ✅ | `backend/app/api/public.py:_record_event`；`backend/tests/test_ticket3_ocr_api.py::test_multipart_success_and_accounting`、`backend/tests/test_ticket5_api.py::test_repeated_request_hits_cache`、`backend/tests/test_ticket3_ocr_api.py::test_provider_5xx_returns_502_and_does_not_charge` |
| R-QTA-02 账号配额上限 | ✅ | `backend/app/core/quota.py`；`backend/tests/test_ticket3_quota.py::test_quota_available_and_exhausted`、`::test_total_quota_pins_to_total`、`backend/tests/test_ticket3_ocr_api.py::test_daily_account_quota_excludes_account` |
| R-QTA-03 周期重置与刷盘 | ✅ | `backend/app/core/quota.py`；`backend/tests/test_ticket3_quota.py::test_daily_key_rolls_at_shanghai_midnight`、`::test_monthly_key_uses_reset_day`、`::test_quota_flush_and_load`、`backend/tests/test_ticket3_ocr_api.py::test_background_quota_flush_reaches_database` |
| R-QTA-04 Key 日限额与 RPM | ✅ | `backend/app/api/deps.py`；`backend/tests/test_ticket2_admin.py::test_daily_limit_returns_quota_exceeded`、`::test_rpm_limit_returns_429`、`::test_rpm_bucket_recovers_after_window`、`::test_usage_event_daily_limit_counts_quota_used` |
| R-QTA-05 用量事件内容 | ✅ | `backend/app/models.py:136`（无原文字段）；`backend/tests/test_ticket3_ocr_api.py::test_multipart_success_and_accounting`（image_hash 16 位、无 text 属性）、`backend/tests/test_ticket5_api.py::test_usage_summary_and_logs`（日志无 text） |

### result-cache

| Requirement | 判定 | 证据锚 |
| --- | --- | --- |
| R-CAC-01 缓存键与命中 | ✅ | `backend/app/core/cache.py:build_key`；`backend/tests/test_ticket5_api.py::test_repeated_request_hits_cache`、`::test_cache_is_isolated_by_provider` |
| R-CAC-02 缓存边界 | ✅ | `backend/tests/test_ticket5_api.py::test_empty_text_is_not_cached`、`backend/tests/test_ticket5_ssrf_cache.py::test_cache_rejects_empty_text`、`::test_cache_rejects_oversized_results`、`::test_cache_lru_eviction`、`::test_cache_ttl_expiry` |
| R-CAC-03 管理端清空 | ✅ | `backend/app/api/admin.py:cache/clear`；`backend/tests/test_ticket5_api.py::test_cache_clear_forces_vendor_call` |

## 缺口与如实记录

- **真实账号契约（tasks 6.1/6.2）**：⚠️ 未执行。契约测试 `backend/tests/test_contract_real_accounts.py`
  存在且默认 skip（凭证仅本地环境变量）；本次未配置凭证，2 skipped。设计 D12 明确接受默认 skip；
  不计为代码缺口，但真实厂商识别能力未在本机验证。`tasks.md` 保留 `[ ]` 并注明。
- **docs 域**：`suite_scope` 命中 `docs` 但该域没有配置自动测试层；README/`.env.example` 的关键
  命令与段落由 `backend/tests/test_ticket5_api.py::test_run_docs_cover_quickstart_and_operations`
  静态核对，未在真实反代/备份环境执行。
- **defer 项**：T1（chunked body 上限）、T2（百度 token 并发刷新合并）已在
  `openspec/issues/open/` 台账，非本 change 交付要求，verify 不判缺口。
- **关键偏差（已记录）**：`usage_events.provider` 允许 `auto`（Task 1/3 报告）；`reset-state` 清零
  三类配额计数（Task 4 报告）；新增 `TRUST_PROXY_HEADERS` 默认 false（代码审报告）。均不阻塞交付。

## 既有红测

无。聚合套件 148 passed / 2 skipped / 0 failed。

## 证据与命令

- closeout: `python verify_runner.py --root . --change ocr-gateway-mvp --base df1ddea --head 0475da5 --mode closeout` → `unit` exit=0 count=148 @ `0475da5`。
- retest: `python verify_runner.py --root . --change ocr-gateway-mvp --base df1ddea --head 0db87a3 --mode retest` → `unit` exit=0 count=148 @ `0db87a3`。
- 静态：`uv run --project backend ruff check backend` → 0；`uv run --project backend mypy backend/app` → 0。
- 两证据 SHA 之间 `git diff --stat 0475da5..0db87a3 -- . ':!openspec'` 为空，代码内容一致；差异仅为
  openspec 证据文件提交。
