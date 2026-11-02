---
ticket: 4
title: 腾讯链路与跨厂商切换
head: c4d42669b9e90ae3843a42d0fb2c87dc2458b404
status: DONE
suite_scope: {"change": "ocr-gateway-mvp", "domains": ["backend"], "layers": {"backend": ["unit"]}, "commands": {"unit": "uv run --project backend pytest backend/tests"}}
---

# Task 4 实现报告 · 腾讯链路与跨厂商切换

## 改动

- `app/providers/tencent.py`：TC3-HMAC-SHA256 签名（`content-type;host;x-tc-action`，action 小写进规范头）、`GeneralBasicOCR` JSON 调用（Version `2018-11-19`、域名 `ocr.tencentcloudapi.com`）、`TextDetections[].Confidence` 映射、错误码分类、`AuthFailure.SignatureExpire` → `PROVIDER_ERROR` 且冷却 30s、HTTP 429/401/5xx/超时映射。
- `app/core/scheduler.py` / `app/core/registry.py`：显式 `provider` 只取该厂商候选；`auto` 可跨厂商；错误上下文（最后厂商/账号）落 usage_event。
- `app/api/admin.py`：账号测活（内置样图或上传图片，不写 usage/不扣配额/不改状态）与 `reset-state`（清 invalid/cooling、恢复 active、清零配额计数）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 单元/集成/e2e | `python -m uv run --project backend pytest backend/tests/test_ticket4_tencent.py backend/tests/test_ticket4_switching.py -q` | 0 | 22 | c4d42669b9e90ae3843a42d0fb2c87dc2458b404 |
| 全量回归 | `python -m uv run --project backend pytest backend/tests -q` | 0 | 112 | c4d42669b9e90ae3843a42d0fb2c87dc2458b404 |
| 静态检查 | `python -m uv run --project backend ruff check backend` | 0 | 未知 | c4d42669b9e90ae3843a42d0fb2c87dc2458b404 |
| 类型检查 | `python -m uv run --project backend mypy backend/app` | 0 | 未知 | c4d42669b9e90ae3843a42d0fb2c87dc2458b404 |

覆盖点：官方文档示例黄金签名（payload hash `35e9c5b0…`、canonical hash `7019a55b…`、signature `10b1a37a…`）；`TextDetections` 顺序/Confidence；腾讯错误码全表与 HTTP 状态映射；`SignatureExpire` 冷却 30s 且不置 invalid；`provider=auto` 落腾讯、`provider=baidu` 有腾讯也不回退、`provider=tencent` 有百度也不回退；腾讯配额错误置 `quota_exhausted`；测活成功/失败分类且无副作用；`reset-state` 恢复 invalid 账号并用备用请求验证；`reset-state` 清零总量配额后重新可调度。

## concerns

- `reset-state` 对 `quota_exhausted` 账号会清零日/月/总量三类计数器（管理员的显式覆盖）。设计只显式要求总量配额经 reset-state 恢复；清零日/月计数是让「quota_exhausted 账号恢复 active 并可参与调度」在验收上成立的必要动作，已在本票记录。
- 腾讯 `Region` 按设计 D21 不传；`X-TC-Region` 头未出现。
- 测活使用 PIL 默认字体生成的内置样图，真实厂商是否稳定识别取决于厂商；接口行为（成功/失败分类、无副作用）已由 mock 覆盖。
- 真实腾讯账号契约测试（Task 6.2）默认 skip，需本地凭证才能跑。

## 票外发现

无。
