---
ticket: 2
title: 公共路由、兜底与迁移
head: 3e6c319c2d7714374dc0ef0c49febe7ce08e5940
status: DONE
suite_scope: {"domains":["backend"],"layers":["unit"],"base":"3e6c319","mode":"closeout"}
---

# Task 2 · 公共路由、兜底与迁移

## 改动

- **迁移**：新增 Alembic `0003_usage_provider_local.py`（revision `9d2c4b7e1a63`，down_revision `7c1f0d2a9b31`）：batch 重建 `usage_events`，`ck_usage_provider` 放宽为 `('baidu','tencent','auto','local')`；downgrade 先把 local 行 `UPDATE` 为 auto 再恢复旧约束。`app/models.py` 的 ORM 约束同步为四值（`Base.metadata.create_all` 建库可直接插 local）。
- **Scheduler**：`local_engine` 注入 + `LocalEngineLike` Protocol；`provider=local` 直通本地；`auto` 且本地可用时按 `reserve_eff = min(reserve, max(0, total − min_budget))` 扣减云阶段 deadline，云 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 后剩余 ≥ min_budget 则兜底（`fallback=True`），不足则抛云原错误；`InputError` 与显式云厂商不兜底；`ScheduleResult.account_id` 改可空；本地结果转换为 `Line`。
- **public.py**：`VALID_PROVIDERS` 增 `local`；`_ensure_provider_enabled` 在解析后、缓存读取前做 403 门禁（区分「未启用」/「依赖未安装」两种文案）；`LocalOcrError` 统一映射 403/502/503/504 并写 `usage_event(provider='local', account_id=NULL)`，用户可见 message 走 `_LOCAL_ERROR_COPY`；成功响应的 `quota.used` 与事件 `quota_used` 由实际 provider 派生（local→0），`account_id=None` 时不查 registry；`/v1/providers` 增 local 条目（`enabled = installed && enabled`，不含账号数）。
- **images.py**：local 分支用原始 JPEG 字节上限（`MAX_UPLOAD_BYTES`）、最长边 10000、不做 base64 膨胀；仍执行 Pillow 校验、EXIF 旋转与 JPEG 重编码。
- **main.py**：先构造 `LocalEngine` 再构造 `Scheduler`，把 engine 与 reserve/min_budget 注入。
- **测试**：新增 `test_m4_ticket2_public_fallback.py`（迁移往返/local→auto、create_all 插入 local、reserve 15s/1s/0 边界、InputError/显式云不兜底、显式 local 跳过云、10000px 原始字节上限、local 成功 quota=0 与事件字段、禁用后缓存不绕过 403、auto 兜底、502/504 映射、providers local 条目）；更新 `test_ticket3_ocr_api.py`（local 从 400 改为 403，新增 `aliyun` 400）与 `test_m3_ticket2_settings.py`（迁移降级目标从 `-1` 改为 `01b12c86bd76`，因 head 已到 0003）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m4_ticket2_public_fallback.py -q` | 0 | 18 | 3e6c319 |
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 242 | 3e6c319 |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests/test_m4_ticket2_public_fallback.py` | 0 | 未知 | 3e6c319 |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | 3e6c319 |

## concerns

- `provider=local` 在 `state=error` 时 `_ensure_provider_enabled` 放行，进入 Scheduler 后返回 502（符合 design 的失败语义）；`unavailable`/未启用才 403。
- 缓存中已存在的 local 结果在开关关闭后仍可能被 `auto` 命中，直到 T4 的「开关变化清缓存」落地；显式 local 的 403 门禁已在缓存前，已有测试。
- `LocalCancelled`（池重建取消）映射 503 +「本地 OCR 正在重建」文案；该路径由 T1 的 generation 机制产生。
- 本地 worker 也返回 `warnings=["EMPTY_TEXT"]`，但 API 响应的 `EMPTY_TEXT` 仍由既有 `_response_payload` 按空文本生成（单一来源），worker 字段留作后续直连消费者使用。
- 迁移的 batch 重建在空/小表上验证；大表行数与维护窗口评估已在 design 记录，Task 5 部署前复核。
