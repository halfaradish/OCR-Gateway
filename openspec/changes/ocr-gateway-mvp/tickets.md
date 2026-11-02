# Tickets · ocr-gateway-mvp

> 来源：`design.md`「切片与依赖」S1–S5（默认采纳，无切片增删/合并/阻塞边变更）+ `tasks.md` 的
> 1.x–6.x 任务分解 + `decision-memo.md` 承重约束 C1–C9。承重约束 → 票的映射见
> `impl-reports/planning-decisions.md`。
>
> 执行顺序：按下方依赖拓扑串行（Task 1 → 2 → 3 → 4 → 5 → 6）；每票实现后过双轴审再 checkpoint。
> 每票验收标准中的 `[e2e]` 条目即该票声明的端到端场景。

| 切片 | 对应票 | 依赖 |
| --- | --- | --- |
| S1 脚手架与存储 | Task 1 | 无 |
| S2 管理端鉴权与实体 | Task 2 | Task 1 |
| S3 百度链路与调度 | Task 3 | Task 1, 2 |
| S4 腾讯链路与切换 | Task 4 | Task 3 |
| S5 输入补全与可运营性 | Task 5 | Task 3, 4 |
| 收尾（强制） | Task 6 | Task 1–5 |

### Task 1: 脚手架、配置与存储基座

**R-ID:** R-API-06, R-QTA-05, R-ADM-01, R-SCH-06
**Blocked-by:** none
**范围预估：** 一个工作段内可完成（工程骨架、配置、五张表迁移、健康检查、单 worker 守卫）。

- [ ] `uv sync` 可用；`ruff check` 与 `mypy` 全绿；测试命令可发现并运行至少一个冒烟用例
- [ ] 全部环境变量按设计默认值加载；`MASTER_KEY` 缺失或非 32 字节、`ADMIN_PASSWORD` 缺失或短于 8 字符时，进程拒绝启动并输出明确原因
- [ ] SQLite 以 WAL 与 `synchronous=NORMAL` 打开；Alembic 初始 revision 建出 users、api_keys、accounts、usage_events、quota_counters 及设计所列索引与外键；`upgrade head` 与 `downgrade base` 往返成功
- [ ] `usage_events` 表结构可承载 `request_id`、user/key/account 关联、provider、success、error_code、latency_ms、quota_used、cached、image_hash、created_at，且不含 OCR 原文或图片字节列
- [ ] `GET /healthz` 在数据库可用时返回 200（含 `status`、`db`、`version`），数据库不可用时返回 503 且 `db=error`（ASGITransport 测试，1s 超时）
- [ ] 启动日志与运行文档声明单 worker；`WEB_CONCURRENCY`、`UVICORN_WORKERS` 或命令行 `--workers` 大于 1 时拒绝启动（fail-loud）
- [ ] 配置与测试夹具不含任何真实凭证；凭证只从环境变量读取，示例环境变量文件只含占位值
- [ ] `[e2e]` 按迁移后的配置冷启动应用进程，`GET /healthz` 返回 200

### Task 2: 管理端鉴权与实体管理

**R-ID:** R-ADM-01, R-ADM-02, R-ADM-03, R-ADM-04, R-ADM-07, R-API-04, R-QTA-04
**Blocked-by:** 1
**范围预估：** 一个工作段内可完成（登录/token、成员/Key/账号 CRUD、凭证加密、配额模板、Key 鉴权与 RPM/日限额）。

- [ ] 管理员登录用常量时间比较校验密码，正确密码返回签名 Bearer token 与 `expires_in`（默认 12h）；`GET /api/admin/me` 返回管理员标识；错误密码 401；过期或无效 token 401
- [ ] 登录失败按 IP + 全局双层限速：1 分钟内第 6 次失败返回 429，全局层只增加延迟、不永久阻断
- [ ] 成员 CRUD：名称唯一（重名 400）、启用/禁用；成员被禁用后其所有 Key 调用公共 API 立即返回 401
- [ ] API Key 管理：`ocr_` 前缀；明文仅在创建响应出现一次，列表只回 `key_prefix`；禁用/吊销后调用返回 401；`daily_limit` 默认 100、`rpm_limit` 默认 30，显式 `null` 表示不限
- [ ] 账号 CRUD：百度/腾讯凭证按厂商 schema 校验，缺 `secret_key` 等必需字段返回 400；凭证以 AES-256-GCM 加密落库，任何管理响应只含脱敏字段；`qps_limit` 默认 5，显式 `null` 不限
- [ ] 配额模板查询返回百度/腾讯参考额度、凭证字段与「以官网为准」免责说明；创建账号未显式提供配额时保持 `NULL`，不自动套用模板
- [ ] 公共 API Key 鉴权依赖：缺失、无效、Key 禁用、成员禁用四类均返回 401；每 Key RPM 超限返回 429 `RATE_LIMITED`，日限额耗尽返回 429 `QUOTA_EXCEEDED`，1 分钟后 RPM 恢复
- [ ] `[e2e]` 通过管理 API 完成登录 → 建成员 → 建 Key（拿到一次性明文）→ 建百度账号；随后列表响应不含明文 Key 或明文凭证

### Task 3: 百度链路与调度核心

**R-ID:** R-API-01, R-API-03, R-API-05, R-API-06, R-ADP-01, R-ADP-03, R-SCH-01, R-SCH-02, R-SCH-03, R-SCH-04, R-QTA-01, R-QTA-02, R-QTA-03, R-QTA-05
**Blocked-by:** 1, 2
**范围预估：** 一个工作段内可完成（图片管线、百度适配器、归一化、注册表/排序/尝试循环、OCR 端点、记账与配额、状态冷却、providers/me）。

- [ ] 图片管线：Pillow 校验真实格式，仅接受 JPEG/PNG/BMP；入口上限 10MB（解码后图片字节）；解码前拒绝超过 40M 像素或最长边超过 10000 的图片；按 EXIF 方向旋转；按厂商限制（百度 base64+urlencode 后 ≤8MB、最短边 ≥15px、最长边 ≤4096px）等比缩放/转 JPEG，仍超限返回 400
- [ ] 百度适配器：以 `client_credentials` 获取 access_token 并在过期前 5 分钟刷新缓存；110/111 时刷新 token 重试一次，仍失败才抛 `AUTH_FAILED`；以 form-urlencoded 提交 `general_basic`；`words_result[].words` 映射为文本行；无概率时 `confidence` 为 `null`；httpx 日志不含 `access_token`
- [ ] 结果归一化：多行按原顺序以换行连接；厂商成功但无文本时返回 200、`text=""` 且 `warnings` 含 `EMPTY_TEXT`
- [ ] 账号注册表与候选过滤：provider 匹配、enabled、active（冷却到期与周期变化惰性恢复）、周期配额未耗尽、`in_flight < max_concurrency`、QPS 令牌可用；启动时从账号表加载 EWMA 与状态，无记录时用厂商种子 1000ms
- [ ] 候选排序：`priority` 升序 → EWMA 升序 → `last_used_at` 升序（NULLS FIRST）→ `weight` 降序；成功请求按 0.2×本次 + 0.8×旧值更新 EWMA 并更新 `last_used_at`
- [ ] 尝试循环：可重试失败标记账号后切下一候选，直到成功或总预算 20s 耗尽；`InputError` 不切换账号；无候选返回 503、最后一次失败为 `PROVIDER_ERROR` 返回 502、预算耗尽返回 504；0ms mock 厂商下网关自身 p99 <20ms
- [ ] `POST /v1/ocr/image`：multipart 与 base64 JSON 二选一（同现 400）；`provider` 默认 `auto`；`language` 仅 `zh`/`en`/`auto` 并按厂商映射；成功响应含 `request_id`、`provider`、`text`、`lines[{text,confidence}]`、`latency_ms`、`cached`、`quota{unit,used}`、`warnings`；错误响应为 `{request_id,error:{code,message}}`
- [ ] 全局并发：OCR 请求进入管线前获取全局信号量（默认 8），等待超过剩余预算时返回 503 `PROVIDER_UNAVAILABLE`，message 标注 gateway at capacity
- [ ] 成功请求记账：账号与 Key 计数各 +1，写入一条 `usage_event`（`quota_used=1`）；失败记 `quota_used=0`；事件不含 OCR 原文与图片字节，`image_hash` 仅前 16 位
- [ ] 账号配额上限：日/月/总量三类，`NULL` 不限；达到上限的账号置 `quota_exhausted` 并被排除；周期键按 `Asia/Shanghai` 00:00 与 `reset_day` 计算；内存计数每 2 秒批量 upsert，启动加载，崩溃最多丢 2 秒
- [ ] 账号状态与冷却：`AUTH_FAILED` → `invalid`（仅 reset-state 恢复）、`QUOTA_EXCEEDED` → `quota_exhausted`（周期重置恢复）、`RATE_LIMITED`/`TIMEOUT`/网络 → `cooling` 30s、5xx → `cooling` 10s；到期在下次选择时惰性恢复
- [ ] `GET /v1/providers` 返回厂商与可用账号计数且不含凭证；`GET /v1/me` 返回当日 `requests`、`quota_used` 与限额
- [ ] `[e2e]` 经百度（respx mock）完成 multipart 请求 → 200 且 `text`/`lines`/`quota.used=1`；停用首选账号后由备用百度账号返回，核对 `usage_event`、账号配额与 Key 计数

### Task 4: 腾讯链路与跨厂商切换

**R-ID:** R-ADP-02, R-ADP-04, R-ADP-05, R-ADM-05, R-SCH-05
**Blocked-by:** 3
**范围预估：** 一个工作段内可完成（TC3 签名、腾讯适配器、跨厂商切换、错误码黄金表、测活与 reset-state）。

- [ ] TC3-HMAC-SHA256 签名：固定密钥与时间戳下生成的 Authorization 与官方示例期望值一致；`host` 与 `content-type` 参与规范请求
- [ ] 腾讯 `GeneralBasicOCR` 调用（Version `2018-11-19`、域名 `ocr.tencentcloudapi.com`、JSON 请求）；`TextDetections` 映射为文本行并保留 0–100 的 `Confidence`；多行顺序一致
- [ ] 显式 provider 不回退：`provider=baidu` 且无可用百度账号时返回 503 且不调用腾讯；`provider=auto` 在百度不可用而腾讯可用时成功返回 `provider="tencent"`
- [ ] 两家厂商错误码映射黄金用例：鉴权、配额、限流、5xx、输入错误逐类映射正确；腾讯 `AuthFailure.SignatureExpire` 映射为 `PROVIDER_ERROR`（冷却 30s），不置 `invalid`
- [ ] 账号测活：用内置样图或上传图片调用指定账号，成功返回文本、延迟与厂商，失败返回错误分类；测活不写 `usage_events`、不扣账号/Key 配额、不改变账号状态
- [ ] 账号 `reset-state`：`invalid`/`cooling`/`quota_exhausted` 账号恢复 `active` 并可参与调度
- [ ] `[e2e]` `provider=auto`、百度候选不可用、腾讯可用 → 200 且 `provider="tencent"`；同一盘面下 `provider=baidu` → 503 且无腾讯出站请求

### Task 5: 输入补全与可运营性

**R-ID:** R-API-02, R-CAC-01, R-CAC-02, R-CAC-03, R-ADM-06, R-SCH-06, R-QTA-01
**Blocked-by:** 3, 4
**范围预估：** 一个工作段内可完成（URL/SSRF、缓存与清空、用量与日志查询、运行文档）。

- [ ] URL 输入：仅 http/https；`getaddrinfo` 解析全部 A/AAAA 并拒绝私网/回环/链路本地/组播/保留地址与 `169.254.169.254`；逐跳复核重定向且最多 3 跳；10s 超时、10MB 上限；失败返回 400 且不回显内网细节；被拒地址不发起出站请求
- [ ] 缓存：键为 `sha256(image_bytes)` + `language` + `provider`（或 `auto`）；命中返回 `cached=true`、`quota.used=0` 且无厂商调用；不同 provider 的键不串用
- [ ] 缓存边界：空文本不缓存、单条结果超过 256KB 不缓存、TTL 默认 3600s、容量默认 1000 条并按 LRU 淘汰
- [ ] 管理端清空缓存返回 `cleared` 条数；清空后相同图片请求重新调用厂商
- [ ] 用量汇总支持 `from`/`to`（按 `Asia/Shanghai` 解释）与 `group_by=user|provider|account`；请求日志支持分页、`success`/`provider` 过滤；响应不含 OCR 原文与凭证
- [ ] 运行文档：示例环境变量（仅占位值）、quickstart（步骤数与预计耗时）、部署（反代 HTTPS、单 worker）、环境变量表、SQLite 备份与 RPO/RTO；按文档命令可启动
- [ ] `[e2e]` 同一公网 URL 连续两次请求 → 第二次 `cached=true`；管理端清空后第三次 `cached=false` 且重新调用厂商

### Task 6: 实现验证收尾（聚合套件）

**R-ID:** all
**Blocked-by:** 1, 2, 3, 4, 5
**范围预估：** 一个工作段内可完成（跑聚合套件、记录证据、补充运行文档核对）。

- [ ] 运行本 change 命中域的全部层聚合测试套件（单元 + 集成 + 端到端）并全部通过
- [ ] 真实百度/腾讯账号契约测试默认 skip（凭证仅本地环境变量），报告中如实记录 skip 状态
- [ ] 0ms mock 厂商基准复跑，确认网关自身开销 p99 <20ms
- [ ] 收尾报告按 `suite_scope.py --mode closeout` 给出的层集与命令落盘，含 `## 既有红测` 小节
