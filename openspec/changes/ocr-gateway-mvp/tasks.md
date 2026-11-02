# Tasks

## 1. 工程骨架与配置

- [ ] 1.1 创建 `backend/` 工程（pyproject、uv、ruff、mypy、`app/` 与 `tests/` 包）；验证 `uv sync`、`uv run --project backend ruff check backend`、`uv run --project backend mypy backend/app` 均通过。
  - R-ID: R-API-06
- [ ] 1.2 实现 `app/config.py`：加载全部环境变量与默认值，启动时校验 `MASTER_KEY`（32 字节）与 `ADMIN_PASSWORD`（≥8 字符）；验证缺失或非法时进程拒绝启动并输出明确原因。
  - R-ID: R-ADM-01
- [ ] 1.3 实现 `app/db.py`、`app/models.py`（users、api_keys、accounts、usage_events、quota_counters 及索引）与 Alembic 初始 revision；验证 `uv run --project backend alembic upgrade head` 与 `downgrade base` 往返成功。
  - R-ID: R-QTA-05
- [ ] 1.4 实现 `GET /healthz`（数据库 `SELECT 1`，1s 超时）与启动日志；验证健康时 200、数据库不可用时 503（ASGITransport 测试）。
  - R-ID: R-API-06

## 2. 管理端鉴权与实体

- [ ] 2.1 实现管理员登录、HKDF 派生签名密钥、12h Bearer token、登录失败限速与 `GET /api/admin/me`；验证正确密码 200、错误密码 401、过期 token 401、1 分钟内第 6 次失败 429。
  - R-ID: R-ADM-01
- [ ] 2.2 实现成员 CRUD（名称唯一、启用/禁用）；验证重名返回 400、禁用成员后其 Key 调用公共 API 返回 401。
  - R-ID: R-ADM-02
- [ ] 2.3 实现 API Key 管理（`ocr_` 前缀、SHA-256、明文仅创建响应返回一次、前缀展示、启用/吊销、日限额与 RPM 字段，默认 `daily_limit=100`/`rpm_limit=30`，显式 `null` 解除）；验证列表响应无明文、吊销后调用返回 401。`[spec-review-amendment Q2/Q3]`
  - R-ID: R-ADM-03
- [ ] 2.4 实现凭证 AES-256-GCM 加解密与账号 CRUD（百度/腾讯凭证 schema 校验、响应脱敏、`qps_limit` 默认 5、显式 `null` 解除）；验证密文往返、缺少 `secret_key` 返回 400、响应不含明文。`[spec-review-amendment Q3]`
  - R-ID: R-ADM-04
- [ ] 2.5 实现公共 API Key 鉴权依赖（hash 查库、Key/成员启用状态、401 语义、全局并发信号量）；验证缺失、无效、Key 禁用、成员禁用四类均 401，并发饱和返回 503。`[spec-review-amendment Q5]`
  - R-ID: R-API-04
- [ ] 2.6 实现每 Key RPM 令牌桶与日限额计数；验证 RPM 超限 429 `RATE_LIMITED`、日限额耗尽 429 `QUOTA_EXCEEDED`、1 分钟后恢复。
  - R-ID: R-QTA-04
- [ ] 2.7 实现内置配额模板（`providers/templates.py`）与 `GET /api/admin/quota-templates`，标注「以官网为准」且不自动套用；验证响应含两家参考额度与凭证字段、创建账号未填配额时保持 NULL。
  - R-ID: R-ADM-07

## 3. 百度链路与调度

- [ ] 3.1 实现共享 `httpx.AsyncClient` 与图片管线（Pillow 真实格式校验、解码前像素上限、EXIF 旋转、JPEG/PNG/BMP 白名单、10MB 入口、按厂商限制缩放转码）；验证伪造图片 400、超限 400、像素炸弹 400、EXIF 旋转与缩放单测通过。`[spec-review-amendment D8]`
  - R-ID: R-API-03
- [ ] 3.2 实现百度适配器（OAuth token 缓存与过期前刷新、110/111 刷新重试一次、`general_basic` form 调用、`words_result` 映射、错误分类、httpx 日志脱敏）；验证 `respx` 测试 token 复用一次、无概率时 confidence 为 null、鉴权错误分类正确、日志不含 `access_token`。`[spec-review-amendment D7/D9]`
  - R-ID: R-ADP-01
- [ ] 3.3 实现结果归一化与 `EMPTY_TEXT` 警告；验证多行顺序与空结果返回 200 的单元测试。
  - R-ID: R-ADP-03
- [ ] 3.4 实现账号注册表内存态、启动时从账号表加载 EWMA/状态与候选过滤（provider、enabled、state、周期配额、in_flight、QPS 令牌）；验证冷却、并发已满、配额耗尽三类账号被排除，重启后 EWMA 恢复。`[spec-review-amendment D23]`
  - R-ID: R-SCH-01, R-SCH-06
- [ ] 3.5 实现候选排序与 EWMA 更新（priority → EWMA → last_used_at → weight）；验证优先级分层、同层低延迟优先、成功请求更新 EWMA 的单元测试。
  - R-ID: R-SCH-02
- [ ] 3.6 实现调度尝试循环（总 deadline、可重试切换、InputError 不切换、503/504/502 区分）；验证 `respx` 集成测试；同时以 0ms mock 跑基准，确认网关自身 p99 <20ms。`[spec-review-amendment D1/D5]`
  - R-ID: R-SCH-03
- [ ] 3.7 实现 `POST /v1/ocr/image` 的 multipart 与 base64 输入、provider 参数、统一响应与错误 envelope；验证两种输入成功、双输入 400、响应字段完整。`[spec-review-amendment D23]`
  - R-ID: R-API-01, R-API-05
- [ ] 3.8 实现成功请求记账（账号与 Key 计数、usage_event 写入、quota_used=1）与失败不扣；验证成功 +1、失败 0、usage_event 内容不含原文。
  - R-ID: R-QTA-01
- [ ] 3.9 实现账号日/月/总量配额上限与 `quota_exhausted` 过滤；验证日额度耗尽后账号不再被选中、三项 NULL 不受限。
  - R-ID: R-QTA-02
- [ ] 3.10 实现周期键与 `Asia/Shanghai` 重置、2s 批量 upsert、启动加载；验证跨日重置单测与重启后计数恢复（允许丢 2s）。
  - R-ID: R-QTA-03
- [ ] 3.11 实现 `GET /v1/providers` 与 `GET /v1/me`；验证响应不含凭证、可用账号计数正确、`/v1/me` 今日用量与限额正确。
  - R-ID: R-API-06
- [ ] 3.12 实现账号状态与冷却（invalid、quota_exhausted、cooling、惰性恢复）；验证 AUTH_FAILED 后 invalid、冷却到期自动恢复、配额周期变化恢复。
  - R-ID: R-SCH-04

## 4. 腾讯链路与切换

- [ ] 4.1 实现腾讯 TC3-HMAC-SHA256 签名并建立官方示例黄金用例；验证固定密钥与时间戳下 Authorization 与期望值一致。
  - R-ID: R-ADP-02
- [ ] 4.2 实现腾讯 `GeneralBasicOCR` 调用、`TextDetections` 映射与 Confidence 保留；验证 `respx` 测试置信度数值与多行顺序。
  - R-ID: R-ADP-02
- [ ] 4.3 实现显式 provider 不回退与 `auto` 跨厂商切换；验证 `provider=baidu` 无可用时 503 且不调腾讯、`auto` 可落到腾讯。
  - R-ID: R-SCH-05
- [ ] 4.4 完成两家厂商错误码到分类的映射表黄金用例与状态联动；验证配额、限流、鉴权、5xx 四类映射正确。
  - R-ID: R-ADP-04
- [ ] 4.5 实现账号测活端点（内置样图或上传图片）；验证成功返回 text/延迟、失败返回分类、且不写 usage、不扣配额、不改状态。
  - R-ID: R-ADP-05
- [ ] 4.6 实现账号 `reset-state` 端点；验证 invalid/cooling 账号恢复 active 并可参与调度。
  - R-ID: R-ADM-05

## 5. 输入补全与可运营性

- [ ] 5.1 实现 URL 输入与 SSRF 防护（scheme、DNS 全解析、IP 段、逐跳重定向复核、10s、10MB）；验证私网/元数据地址 400、超限/重定向过多 400、公网 URL 成功。
  - R-ID: R-API-02
- [ ] 5.2 实现结果缓存键与命中语义；验证重复请求 `cached=true`、`quota.used=0`、无厂商调用、不同 provider 不串用。
  - R-ID: R-CAC-01
- [ ] 5.3 实现缓存边界（空文本不缓存、单条 >256KB 不缓存、TTL 3600s、容量 1000 LRU）；验证边界单测与容量淘汰。
  - R-ID: R-CAC-02
- [ ] 5.4 实现 `POST /api/admin/cache/clear`；验证返回清除条数、清空后同图重新调用厂商。
  - R-ID: R-CAC-03
- [ ] 5.5 实现用量汇总与请求日志查询（group_by、分页、过滤、无原文）；验证按厂商聚合计数与第二页分页。
  - R-ID: R-ADM-06
- [ ] 5.6 实现单 worker 约束检测（`WEB_CONCURRENCY`/`UVICORN_WORKERS`/`--workers` >1 拒绝启动）与运行文档（`.env.example`、README 的 quickstart/部署/环境变量/备份，quickstart 给步骤数与预计耗时）；验证按文档命令可启动、告警可见。`[spec-review-amendment D17/D27]`
  - R-ID: R-SCH-06

## 6. 集成验收

- [ ] 6.1 用真实百度账号识别一张中文截图（凭证只从本地环境变量读取，默认 skip）；记录 `text` 与延迟，验证非空。
  - R-ID: R-ADP-01
- [ ] 6.2 用真实腾讯账号识别一张中文截图（默认 skip）；记录 `text` 与延迟，验证非空。
  - R-ID: R-ADP-02
- [ ] 6.3 故障切换演练：停用首选账号后请求由备用账号返回；核对 usage_event、账号配额与 Key 计数。
  - R-ID: R-SCH-03
- [ ] 6.4 全量质量门：`uv run --project backend pytest backend/tests`、`ruff check`、`mypy` 全绿；0ms mock 基准 p99 <20ms。
  - R-ID: R-API-05

## 测试覆盖图

| Code path | 测试类型 | 覆盖点 |
| --- | --- | --- |
| `app/api/public.py` | API（httpx.ASGITransport） | 输入二选一、鉴权、限额、响应/错误码、缓存、URL |
| `app/api/admin.py` | API | 登录/令牌、CRUD、脱敏、测活、重置、查询分页 |
| `app/api/deps.py` | 单元 + API | Key 哈希查找、禁用、RPM 桶 |
| `app/core/scheduler.py` | 单元 + 集成（respx） | 过滤、排序、deadline、切换、503/504 |
| `app/core/registry.py` | 单元 | 状态机、冷却、in_flight、QPS、EWMA |
| `app/core/quota.py` | 单元 + 故障注入 | 周期键、重置、2s 刷盘、启动加载 |
| `app/core/cache.py` | 单元 | 键、TTL、LRU、大小/空文本边界 |
| `app/providers/baidu.py` | 适配器（respx）+ 契约（真实 key，skip） | token 缓存、form、归一化、错误分类 |
| `app/providers/tencent.py` | 适配器（respx）+ 黄金签名 + 契约（skip） | TC3、JSON、归一化、错误分类 |
| `app/providers/templates.py` | 单元 + API | 模板内容、免责说明、不自动套用 |
| `app/utils/images.py` | 单元 | 格式校验、EXIF、缩放、10MB |
| `app/utils/ssrf.py` | 单元（DNS mock） | scheme、IP 段、重定向、大小/超时 |
| `app/security.py` | 单元 | AES-GCM 往返、token 签名/过期、常量时间比较 |
| `alembic/versions/*` | 迁移 | upgrade/downgrade 往返 |

## Workflow follow-up

- 代码审与 verify 通过后归档本 change，并核对 `openspec/specs/` 生成的能力 spec。
