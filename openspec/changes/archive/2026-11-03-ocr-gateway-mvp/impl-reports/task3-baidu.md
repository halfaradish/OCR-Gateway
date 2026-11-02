---
ticket: 3
title: 百度链路与调度核心
head: 997018ccd58a8172d0c54198abd5a045f74a7c2a
status: DONE
suite_scope: {"change": "ocr-gateway-mvp", "domains": ["backend"], "layers": {"backend": ["unit"]}, "commands": {"unit": "uv run --project backend pytest backend/tests"}}
---

# Task 3 实现报告 · 百度链路与调度核心

## 改动

- `app/utils/images.py`：Pillow 真实格式校验（仅 JPEG/PNG/BMP）、10MB 入口、解码前像素/最长边闸门、EXIF 旋转、按厂商限制（百度 base64+urlencode ≤8MB、最短边 ≥15px、最长边 ≤4096px）等比缩放/转 JPEG。
- `app/providers/baidu.py`：OAuth token 缓存（过期前 5 分钟刷新）、110/111 刷新重试一次、form-urlencoded `general_basic`、`words_result` 映射、错误码分类、`Retry-After` 上限、httpx 日志降到 WARNING。
- `app/providers/base.py` / `app/core/registry.py`：账号内存态、候选过滤（provider/enabled/active/周期配额/并发/QPS 令牌）、惰性恢复、排序（priority → EWMA → last_used_at → weight 降序）、EWMA 0.2/0.8、失败状态机、启动加载。
- `app/core/scheduler.py`：总 deadline、可重试切换、`InputError` 不切换、503/504/502 区分、失败原因与最后账号上下文。
- `app/core/quota.py`：日/月/总量内存计数、`Asia/Shanghai` 日周期、`reset_day` 月周期、每 2s 批量 upsert、启动加载、管理员重置。
- `app/api/public.py`：`POST /v1/ocr/image`（multipart/base64 二选一、provider/language 校验、统一响应与错误 envelope、全局并发信号量 503、成功/失败 usage_event 写入、成功 +1 配额）、`GET /v1/providers`、`GET /v1/me`。
- `app/api/deps.py`：日限额按 `usage_events.quota_used` 合计（缓存命中不占）。
- `app/core/registry.py`：厂商配额耗尽区分总量/周期；冷却常量命名化。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 单元/集成/e2e | `python -m uv run --project backend pytest backend/tests/test_ticket3_images.py backend/tests/test_ticket3_baidu.py backend/tests/test_ticket3_scheduler.py backend/tests/test_ticket3_quota.py backend/tests/test_ticket3_ocr_api.py -q` | 0 | 59 | 997018ccd58a8172d0c54198abd5a045f74a7c2a |
| 全量回归 | `python -m uv run --project backend pytest backend/tests -q` | 0 | 90 | 997018ccd58a8172d0c54198abd5a045f74a7c2a |
| 静态检查 | `python -m uv run --project backend ruff check backend` | 0 | 未知 | 997018ccd58a8172d0c54198abd5a045f74a7c2a |
| 类型检查 | `python -m uv run --project backend mypy backend/app` | 0 | 未知 | 997018ccd58a8172d0c54198abd5a045f74a7c2a |

覆盖点：伪造图片/超限/像素炸弹/EXIF 旋转/缩放/BMP→JPEG；百度 token 复用、110 刷新重试、错误码与 HTTP 状态分类、空文本 `EMPTY_TEXT`；候选过滤（冷却/并发/配额/QPS）、排序、EWMA；调度切换、`InputError` 不切换、503/504/502；multipart/base64/双输入 400/provider/language 400；成功记账（quota_used=1、image_hash 16 位、无原文字段）、失败不扣；账号日配额耗尽排除；停用首选账号后用备用账号并核对 usage_event/配额/Key 计数；全局并发饱和 503；2s 后台刷盘落库；0ms mock 基准 p99 <20ms。

## concerns

- `usage_events.provider` 的 CHECK 额外允许 `auto`（Task 1 已记录）；无候选的 `auto` 失败请求以 `auto` 落事件。
- 编码后大小驱动的二次缩放（9MB PNG 场景）走的是与最大边缩放相同的循环；单测以最大边超限覆盖，未构造 9MB 真实 PNG（避免测试内存/耗时膨胀）。
- 缓存边界（空文本/256KB/LRU）与 URL 输入属 Task 5；本票的 `POST /v1/ocr/image` 在缓存启用时已可命中，但空文本仍会写入缓存，Task 5 会收紧。
- 账号 `reset-state` 与测活属 Task 4；本票只验证了状态机与惰性恢复。

## 票外发现

无。
