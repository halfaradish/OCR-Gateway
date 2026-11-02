# Hand-off · ocr-gateway-mvp

## ✅ 完成了什么

- **公共 OCR API**：`POST /v1/ocr/image` 支持 multipart、base64 JSON、URL 三种输入；统一
  `text + lines[{text, confidence}]`、`request_id`、`quota`、`warnings` 与错误 envelope；
  `provider`/`language` 校验；全局并发饱和 503。锚点：`backend/tests/test_ticket3_ocr_api.py`、
  `test_ticket5_api.py::test_url_input_success_and_private_rejection`。
- **百度/腾讯适配器**：百度 OAuth token 缓存与 110/111 刷新重试、`general_basic`；腾讯
  TC3-HMAC-SHA256 官方黄金签名、`GeneralBasicOCR`、`TextDetections[].Confidence`；两家错误码
  分类与状态联动。锚点：`test_ticket3_baidu.py`、`test_ticket4_tencent.py`。
- **账号池调度**：候选过滤（provider/enabled/冷却/配额/并发/QPS）、priority → EWMA →
  last_used_at → weight 排序、总 deadline 切换、503/504/502 区分、显式厂商不回退。锚点：
  `test_ticket3_scheduler.py`、`test_ticket4_switching.py`。
- **配额与记账**：账号日/月/总量、Key 日限额/RPM、`Asia/Shanghai` 周期、2s 批量 upsert、
  启动加载；成功 +1、失败/缓存 +0；`usage_events` 不含原文。锚点：`test_ticket3_quota.py`、
  `test_ticket3_ocr_api.py::test_background_quota_flush_reaches_database`。
- **结果缓存**：`sha256(image)+language+provider`、命中 `cached=true`/`quota.used=0`、空文本/
  >256KB 不缓存、TTL/LRU、管理端清空。锚点：`test_ticket5_ssrf_cache.py`、`test_ticket5_api.py`。
- **URL 输入与 SSRF**：scheme/userinfo、全量 DNS 解析、私网/回环/链路本地/元数据拒绝、逐跳重定向
  复核、10s/10MB。锚点：`test_ticket5_ssrf_cache.py`。
- **管理 API**：Bearer 登录/限速、成员/Key/账号 CRUD、凭证 AES-GCM 脱敏、配额模板、测活、
  `reset-state`、用量汇总、请求日志。锚点：`test_ticket2_admin.py`、`test_ticket4_switching.py`、
  `test_ticket5_api.py::test_usage_summary_and_logs`。
- **运维**：`/healthz`、单 worker 守卫、WAL + 外键、Alembic 初始迁移、`.env.example`、
  README quickstart/部署/备份/RPO-RTO。锚点：`test_ticket1_bootstrap.py`、README 静态核对测试。
- **质量门**：聚合套件 148 passed / 2 skipped / 0 failed；ruff/mypy 绿；0ms mock p99 <20ms。
  证据：`verify-evidence-closeout.json`、`verify-evidence-retest.json`。

## ⏳ 未完成延后

按 `openspec/issues/open/*.md` 的 `source_change == ocr-gateway-mvp` 逐条列出：

- **T1** chunked/无 `Content-Length` 请求的流式 body 上限（`openspec/issues/open/T1.md`）。
- **T2** 百度 OAuth token 并发刷新合并（`openspec/issues/open/T2.md`）。

另有一项环境性未执行（非 defer 台账）：`tasks.md` 6.1/6.2 的真实百度/腾讯账号识别——契约测试
已就位并默认 skip，本机未配置凭证，未记录真实 `text`/延迟。设计 D12 接受该默认 skip。

## ▶ 下一阶段建议

1. 在持有凭证的本机运行 `pytest -m contract`，补记两家真实识别的 `text` 与延迟，勾掉 tasks 6.1/6.2。
2. 视公网暴露面处理 T1（应用侧流式 body 上限）；T2 可在首次真实并发压测时顺手合并 token 刷新。
3. 后续 change 可评估 M3 面板（cookie+CSRF 双轨恢复）、`/usage/series`、Postgres/多实例阈值触发。
