---
change: ocr-gateway-mvp
reviewed_commit: 5d23ed2
dispatch: single-session
memo: ok
---

# Spec Review Report · ocr-gateway-mvp

> ⚠️ **单 session 自查**：逐镜由主 session 完成；同模型、不同上下文，非独立评审。机械门只保证流程与证据格式，不保证质量；设计拍板的人类阅读是唯一独立检查。
>
> **评审基线**：`5d23ed2`（四件套 + decision-memo 已提交，工作树洁净）。下文所有 `file:line` 均以该基线为准；本次 amendment 落盘后行号会漂移。
>
> **镜子 roster（8 镜）**：广审 2（strategy / plan-eng）· 领域 2（backend / devex，TG-01 + TG-28）· 对抗 3（隐藏假设 / 失败模式 / 乐观估计）· 接地 1。
>
> **机械门**：`check_decision_memo.py` → `ok: true`；`openspec validate ocr-gateway-mvp --strict` → valid。四件套齐备。

---

## 拍板三问（人在设计 HARD-GATE 逐项勾选）

**Q-scope 范围划界认不认？**
自答：锚 `proposal.md:24-34` `## Non-Goals` + `design.md:17-24` `## Goals / Non-Goals`——单实例 MVP，明确砍掉 SPA、批量、本地 OCR、阿里/华为、Docker、`settings` 表、匿名模式；每条附可证伪假设。**但「免费额度耗尽」不是 Non-Goal 也不是行为定义**：按仓内唯一额度口径（2 账号 × 1000 次/月）与「日均 <500 次」（`proposal.md:69`）对不上（见 F-01），范围与容量前提需要拍板。
[ ] 认 [ ] 不认

**Q-deps 依赖/顺序认不认？**
自答：锚 `design.md:508-520` `## 切片与依赖`——S1 脚手架/存储 → S2 管理端鉴权与实体 → S3 百度链路 → S4 腾讯与切换 → S5 输入补全/可运营性，5 张垂直切片落在 3–6 预算内；真实 `Blocked-by` 出票时写入 `tickets.md`。顺序合理，S3 依赖 S2（先能建账号才能测百度）属可接受约束。
[ ] 认 [ ] 不认

**Q-risk 风险赌注与对策认不认？**
自答：锚 `design.md:522-530` `## Risks / Trade-offs` + `decision-memo.md:44-50` 接受的边角——签名手写、额度模板过时、共享池风控、单 worker 被绕过、SQLite 写放大、DNS rebinding、admin token 无法即时吊销。**风控对策写的是「账号级并发/QPS + Key RPM/日限额」，但这三项默认值全是 NULL（不限）**（`design.md:200`、`design.md:183-184`），默认部署等于没有这层对策（见 F-28 / Q3）。
[ ] 认 [ ] 不认

---

## 决策登记区

### [需拍板]（5 项，出票前必须关闭）

**Q1 · 容量口径矛盾（F-01，高）**
仓内唯一的额度口径是 `docs/tech-selection.md:435-436`：百度 1000 次/月、腾讯 1000 次/月；两家账号合计 ≈2000 次/月 ≈ **66 次/日**。而 `proposal.md:69`、`design.md:484` 的规模前提是 **<500 次/日**（≈15,000 次/月），相差约 7.5 倍。按 500/日运行，免费额度约 4 天耗尽；而「额度耗尽」在 spec 里没有一等公民行为（只有账号级 `quota_exhausted` → 503）。
- **选项 A（推荐）**：修正规模前提为「2 账号 ≈ 日均 <60 次」，NFR/成功指标同步；账号增加时按 1000 次/月/账号线性扩容。代价：规模前提变小；收益：口径自洽，MVP 目标不变。
- **选项 B**：保持 500/日，接受额度约 4 天耗尽；把「额度耗尽」当正常运维事件（503/`QUOTA_EXCEEDED` + 管理员加账号）。代价：成功指标不能承诺持续可用。
- **选项 C**：把额度预警/耗尽做成一等管理能力（新增视图/告警）。代价：超出当前 MVP 范围。
- 三镜：系统镜 A 最小（只改文档）；用户镜 B 会让成员频繁遇到 503；开发循环镜 C 成本最高。
- **主次判定**：开发循环镜优先——先让前提自洽，再谈运行期策略；推荐 A，B 作为运行期兜底写进 README。

**Q2 · `daily_limit` 口径与 Key 日计数存储（F-05/F-06，中）**
`api_keys.daily_limit` 存在，但 `api_keys` 没有 `daily_used`，`quota_counters` 只按 `account_id` 建键（`design.md:238-246`）；R-QTA-04 又说「当日成功请求数达到 `daily_limit`」（`specs/quota-accounting/spec.md:50`），而 R-QTA-01 说缓存命中「Key 计数不变」。缓存命中到底占不占日限额，未定义。
- **选项 A（推荐）**：`daily_limit` 按**配额单位**计——只统计 `usage_events.quota_used=1` 的行（已有 `api_key_id, created_at` 索引）；缓存命中不占日限额；`/v1/me.today.requests` 另计全部进入调度的请求。与 tech-selection「该 key 每日最多消耗多少配额单位」（`docs/tech-selection.md:146`）一致。
- **选项 B**：按请求数计——缓存命中与失败也计入；实现简单，但缓存命中会被误伤。
- 代价：A 需要一次带索引的聚合查询（<500/日无压力）；B 语义与 tech-selection 冲突。
- **主次判定**：用户镜优先——缓存的意义就是「不耗额度」，日限额不应惩罚缓存命中；推荐 A。

**Q3 · 默认限流全空（F-28，低中）**
`qps_limit`（账号）、`rpm_limit` / `daily_limit`（Key）默认全为 NULL = 不限（`design.md:183-184`、`design.md:200`）。默认部署下：泄露一个 Key 即可在额度内无限刷；共享池风控对策形同虚设。
- **选项 A（推荐）**：给非空默认——账号 `qps_limit=5`、Key `rpm_limit=30`、`daily_limit=100`；管理员可显式置 NULL 解除。与 `/v1/me` 示例（200/30，`design.md:391`）和 NFR「峰值 ≤5 QPS」（`design.md:484`）同量级。
- **选项 B**：保持 NULL，靠运营者创建时填写；代价：默认不安全。
- **选项 C**：创建时强制必填；代价：管理摩擦大，且与「配额模板不自动套用」的取向冲突。
- **主次判定**：系统镜优先（共享额度是核心资产）；推荐 A。

**Q4 · `AUTH_FAILED` 粒度（F-45，高）**
当前所有鉴权错误 → `invalid`（不自动恢复，只能管理员 reset，`design.md:327`）。但两类错误不是「凭证坏了」：
- 百度 110/111（token 无效/过期）：token 30 天有效，刷新后即可恢复；
- 腾讯 `AuthFailure.SignatureExpire`：官方文档明确「timestamp 必须在服务器时间 5 分钟内」——时钟偏移/VM 暂停会让**全部腾讯账号**同时永久 invalid。
- **选项 A（推荐）**：细分——百度 110/111 先刷新 token 重试一次，仍失败才 `invalid`；腾讯 `SignatureExpire` → `cooling` 30s + 告警（视为配置/时钟问题，不是凭证失效）；其余鉴权错误（`SignatureFailure`、`SecretIdNotFound`、401/403）→ `invalid`。
- **选项 B**：保持现状（一律 invalid）；代价：一次时钟偏移造成全厂商不可用，需人工 reset。
- **主次判定**：用户镜优先（可用性）；推荐 A。百度 110/111 的「刷新一次再判定」属 bug 修复，已按 D7 先行落盘，不依赖本问。

**Q5 · 全局并发/内存上限（F-18，高）**
只有每账号 `max_concurrency=2`（`design.md:199`）；`auto` 跨 N 个账号时峰值并发 = 2N。单请求可同时持有：10MB 原始字节 + ~13MB base64 + 解码位图（4096×4096 RGBA ≈ 67MB）+ 厂商响应。无全局信号量/内存预算（`design.md:337-344`）。
- **选项 A（推荐）**：加 `MAX_CONCURRENT_REQUESTS` 默认 8 的全局信号量；获取超时按剩余预算等待，超时 503。配合 F-17 的像素上限，把峰值内存压到可控范围。
- **选项 B**：不加，只靠账号级并发；代价：小机器 OOM → 单进程全站不可用。
- **选项 C**：把入口上限从 10MB 降到 5MB；代价：牺牲大图，且不解决 4096px 位图的内存。
- **主次判定**：系统镜优先（单实例 OOM = 全站宕机）；推荐 A。

### [自动决策]（已按推荐项落盘，可覆盖）

| ID | 决定 | 依据 |
| --- | --- | --- |
| D1 | 503/504 区分：无候选 → 503；有候选但 deadline 耗尽 → 504 | F-08；`specs/account-pool-scheduling/spec.md:32` |
| D2 | 月周期 `period_key` 改为「周期起始日 `YYYY-MM-DD`」；`quota_total` 耗尽不自动恢复 | F-07；`design.md:242` vs `:205`/`:279` |
| D3 | `usage_events` 只记「进入调度」的请求；鉴权/输入校验失败只记 stdout | F-09；`provider` NOT NULL |
| D4 | `language` 枚举 `zh`(默认)/`en`/`auto` + 厂商映射表；其它值 400 | F-04 |
| D5 | 补 `PROVIDER_ERROR` 502：全部候选失败且最后一次为 PROVIDER_ERROR → 502 | F-03；tech-selection 错误码表 |
| D6 | 百度 OAuth 先解析 body 的 `error`/`error_description`，再判 HTTP 状态 | F-20 |
| D7 | 百度 110/111 → 刷新 token 重试一次，仍失败才 `AUTH_FAILED` | F-45（不依赖 Q4） |
| D8 | 图片解码前校验像素上限（默认 40M 像素），超限 400；显式设置 `PIL.MAX_IMAGE_PIXELS` | F-17 |
| D9 | `httpx` logger 设 WARNING（或加过滤器），避免 INFO 日志记录含 `access_token` 的 URL | F-19 |
| D10 | 百度约束改为「base64 + urlencode 后 ≤8MB」；补最短边 ≥15px 校验 | F-21 |
| D11 | `MAX_UPLOAD_BYTES` 按「解码后的图片字节数」校验；multipart 与 base64 JSON 一致 | F-22 |
| D12 | OAuth token 获取计入账号超时：单次 ≤min(2s, 剩余)，总 ≤4s | F-24 |
| D13 | `Retry-After` 冷却上限 300s | F-25 |
| D14 | 状态/EWMA/`last_used_at` 随请求提交（每请求一次 UPDATE）；配额计数仍 2s 批量 | F-27 |
| D15 | multipart 也接受 `image_base64` 文本字段（与 `file` 同时出现 → 400） | F-32 |
| D16 | 登录限速按 IP + 全局双层；全局层只延迟不永久阻断 | F-29 |
| D17 | 单 worker 守卫改为 fail-loud：检测 `WEB_CONCURRENCY`、`UVICORN_WORKERS` 与 `--workers`，>1 拒绝启动 | F-30 |
| D18 | Compliance 补 D1/D3/D13；补「图片会发往百度/腾讯」的第三方数据声明 | F-02 |
| D19 | `/healthz` 不鉴权（供反代探活）；其余公共 API 强制 Bearer | F-11 |
| D20 | R-ADM-01 改为「除 `/api/admin/login` 外」 | F-12 |
| D21 | 删除腾讯凭证示例中的 `region: null`；注明 Region 可选、MVP 不传 | F-13 |
| D22 | 移除 `argon2-cffi`（无密码哈希消费者） | F-14 |
| D23 | 补任务追溯：3.7 加 `R-API-05`；3.4 加 `R-SCH-06`（EWMA 启动加载） | F-10 |
| D24 | R-ADM-05 补「测活不写用量/不扣配额/不改状态」场景 | F-10 |
| D25 | `from`/`to` 为 ISO-8601，按 `Asia/Shanghai` 解释；默认最近 7 天 | F-16 |
| D26 | proposal 假设补「若不成立如何失效」；补「开放问题：无」与「利益相关方」节 | F-15 |
| D27 | README quickstart 给步骤数 + 预计耗时（TTHW）；错误 `message` 声明为非契约、客户端按 `code` 分支 | F-39/F-40 |
| D28 | 明确客户端超时重试会重复扣配额；并发下允许 ≤`max_concurrency-1` 的瞬时超额 | F-33/F-34 |
| D29 | 补备份/RPO 说明：SQLite 定期备份；配额计数 RPO ≤2s；配置依赖运维备份 | F-31/F-50 |
| D30 | 指定 SQLite `WAL` + `synchronous=NORMAL`；记录缓存最坏内存 1000×256KB≈256MB | F-23/F-26 |
| D31 | design 附录列两家错误码映射表（码值 + 含义 + 官方 URL + 核对日期） | F-43 |

### [已裁掉]（原始发现 + 裁掉理由，供人复核「裁得对不对」）

| ID | 原始发现 | 裁掉理由 |
| --- | --- | --- |
| X1 | `in_flight` 非阻塞探测 → 突发时 503 而非短暂排队（`design.md:340`） | 设计显式选择非阻塞；≤5 人规模下并发冲突概率低；若拍板要排队，后续加等待即可 |
| X2 | BE-07 存活/就绪未分离（`design.md:475`） | 单实例、无编排；design 显式声明「进程存活由 uvicorn 决定」，分离无收益 |
| X3 | BE-08 无指数退避/jitter | 调度模型是「换账号」而非「重试同一账号」，不构成同点雪崩；OAuth 仅 1 次重试 |
| X4 | 账号/成员删除与 in-flight 请求竞态 | 单实例 + FK SET NULL/CASCADE；窗口 ≤8s；最坏一条计数刷新失败，接受 |
| X5 | vendor 成功后进程崩溃 → usage_event 与计数双丢 | 与「崩溃丢 ≤2s 计数」同源（decision-memo:47 已接受）；≤500/日规模下审计行丢失可接受 |
| X6 | `/docs` 暴露 admin schema 未列入威胁模型 | D2 拍板「无 SPA，管理走 `/docs`」的已知代价；无 SPA 时这是唯一管理入口 |
| X7 | 缓存 key 用原图 bytes，不同压缩/EXIF 不共享 | 保守选择，避免误命中；命中率低于理论值属预期，不影响正确性 |
| X8 | 启动 <5s 未计 Alembic 迁移 | 迁移在启动前手工执行（`design.md:534`），不在启动路径 |
| X9 | **`cachetools.TTLCache` 不是 LRU**（原怀疑） | **误报，已证伪**：cachetools 官方文档明确 TTLCache 是「LRU Cache implementation with per-item TTL」，`maxsize` 溢出时淘汰最久未使用项。R-CAC-02 的 LRU 措辞成立 |
| X10 | usage_events 无保留/归档策略 | ≈18 万行/年（`design.md:489`），SQLite 可承受多年；D29 已补一句运维说明，不单列动作 |

---

## 各镜 findings

> 每条 finding 的引文均已真打开核对；库行为类引文标注了来源。严重度：高 / 中 / 低；置信度：高 / 中 / 低。

### 镜 1 · strategy（计划级 base R 项）

覆盖：BASE-01 完整性 · BASE-04 合规 · BASE-08 外部一致性 · BASE-09 清晰度 · BASE-10 范围/YAGNI · BASE-12 ADR · BASE-13 不在范围内 · BASE-14 假设 · BASE-15 开放问题 · BASE-16 NFR · BASE-17 可追踪性 · BASE-18 分解 · BASE-20 利益相关方 · BASE-21 合规 · BASE-22 需求纯度 · BASE-23 优先级 · BASE-26 成本 · BASE-27 时序 · BASE-30 正文即最终态 · BASE-31 切片。

**F-01 [高][高] 容量口径矛盾：500/日 vs 2×1000/月**
- 证据：`proposal.md:69`「使用规模 ≤5 人、日均 <500 次」；`design.md:484`「峰值吞吐 ≤5 QPS；均值 <0.01 QPS（500/日）」；`docs/tech-selection.md:435-436`「百度 月 1000 次」「腾讯 月 1000 次」；`decision-memo.md:30` D14 同口径。
- 影响：按 500/日运行，2000 次/月约 4 天耗尽；「额度耗尽」没有一等行为定义，成员会突然收到 503，而成功指标（`proposal.md:20-22`）仍按「持续可用」表述。
- 建议：见 Q1。

**F-02 [中][高] Compliance 偏离清单不完整 + 第三方数据声明缺失**
- 证据：`proposal.md:38`「偏离项（Bearer 管理鉴权、无 `settings` 表、无匿名模式）在 `decision-memo.md` D4/D5/D10 记录理由」；但 `docs/tech-selection.md:18`（首批四家）、`:28`（含批量）、`:27`（Docker Compose 优先）分别被 D1/D3/D13 偏离，未列入该枚举。
- 影响：读者会以为偏离只有三项；审计时「不静默例外」的声明不成立。另：`proposal.md:40` 只说「默认不落 OCR 原文」，未显式声明「图片会发送给百度/腾讯」这一第三方数据流（BASE-21）。
- 建议：D18。

**F-03 [中][高] `PROVIDER_ERROR` 502 从对外契约消失**
- 证据：`docs/tech-selection.md:362`「`PROVIDER_ERROR` | 502 | 厂商返回异常」；`design.md:320` 尝试循环唯一出口是 `raise PROVIDER_UNAVAILABLE`；`design.md:331` 所有 5xx/协议错误都「全无 → 503」；`design.md:540` 却声称遵守 tech-selection 的错误码表。
- 影响：客户端无法区分「没有账号」与「厂商坏了」；外部一致性与 Compliance 声明冲突。
- 建议：D5。

**F-04 [中][高] `language` 参数无需求、无枚举、无厂商映射**
- 证据：`design.md:361`「`language` 默认 `zh`」、`:364` JSON 示例；`design.md:430` 缓存键含 `language`；但 6 份 delta spec 中没有任何 Requirement 定义 `language` 的取值或映射（`specs/ocr-api/spec.md:10-12` 只列输入形态）。
- 影响：实现者必须自行发明枚举与百度 `language_type` / 腾讯 `LanguageType` 的映射；不同实现会产生不同的厂商行为，缓存键语义也不稳定。
- 建议：D4（`zh`→百度 `CHN_ENG` / 腾讯 `zh`；`en`→`ENG` / `en`；`auto`→百度 `CHN_ENG`（尽力）/ 腾讯 `auto`；其它 400）。

**F-05 [中][高] `daily_limit` 口径未定义（缓存命中是否计入）**
- 证据：`specs/quota-accounting/spec.md:50`「Key 当日成功请求数达到 `daily_limit`」；`specs/quota-accounting/spec.md:19-21`「缓存命中……Key 计数不变」；`design.md:391` `/v1/me` 同时给 `requests` 与 `quota_used`。
- 影响：同一句「成功请求数」既可读作「含缓存命中的全部请求」，也可读作「quota_used=1 的请求」；两种实现会让用户在缓存命中时被限流或不被限流。
- 建议：Q2。

**F-06 [中][高] Key 日计数无存储/刷盘定义**
- 证据：`design.md:171-184` `api_keys` 只有 `daily_limit`，无 `daily_used`；`design.md:238-246` `quota_counters` 主键 `(account_id, period_type, period_key)`，只服务账号；`specs/quota-accounting/spec.md:40` R-QTA-03 只要求账号计数 2s upsert。
- 影响：`/v1/me` 与 429 门都依赖 Key 日计数，但计数存在哪、何时刷、重启是否恢复，全部未定义。
- 建议：Q2（推荐 A：`usage_events` 聚合，复用 `api_key_id, created_at` 索引）。

**F-07 [高][高] 月度 `period_key` 与 `reset_day` 冲突；`quota_total` 无周期**
- 证据：`design.md:242`「`period_key` | TEXT | `YYYY-MM-DD` / `YYYY-MM` / `all`」；`design.md:205`「`reset_day` | INTEGER | 1–28 | 1」；`design.md:279`「月配额 `reset_day` 当天 00:00」；`design.md:263` 状态机「quota_exhausted → active：周期重置」。
- 影响：`reset_day=15` 时月周期是 15 日到次月 14 日，`YYYY-MM` 无法表达；实现者要么忽略 `reset_day`，要么把两个不同周期的计数写进同一个 key。`quota_total` 没有周期，却被状态机的「周期重置」覆盖——总量耗尽的账号永远不会自动恢复，spec 未声明。
- 建议：D2（月 `period_key` = 周期起始日 `YYYY-MM-DD`；`quota_total` 耗尽仅管理员 reset）。

**F-08 [中][高] 503/504 语义矛盾**
- 证据：`specs/account-pool-scheduling/spec.md:32`「无候选可用返回 503，预算耗尽返回 504」；`design.md:309`「`if remaining <= 0: break`」；`design.md:320` 循环后唯一出口 `raise PROVIDER_UNAVAILABLE`。
- 影响：deadline 耗尽会走到 503，504 永远不会出现；R-API-05 的「总预算耗尽 → 504」场景无法通过实现。
- 建议：D1（区分 `had_candidate`；无候选 503，有候选但预算耗尽 504）。

**F-09 [中][高] `usage_events.provider` NOT NULL 与「每请求 INSERT」矛盾**
- 证据：`design.md:226`「`provider` | TEXT | CHECK IN (`baidu`,`tencent`) | — | 否」；`design.md:342`「`usage_events` 每请求 `INSERT` 并 `commit`」；`design.md:130` 序列图在响应前 INSERT。
- 影响：401（无 Key/成员禁用）、400（输入校验失败）、503（无候选）都没有 `provider` 值；「每请求」要么写不进去，要么被迫写假值。
- 建议：D3（只记进入调度的请求；鉴权/输入失败只记 stdout）。

**F-10 [低][高] 追溯缺口：R-API-05 无实现任务；R-SCH-06 EWMA 启动加载无任务；R-ADM-05 缺测活场景**
- 证据：`tasks.md:96-97` R-API-05 只挂在 6.4「全量质量门」；`tasks.md:39` 3.4 只写「注册表内存态与候选过滤」，未提 EWMA 启动加载；`tasks.md:86` 5.6 是单 worker；`specs/admin-api/spec.md:57-58` R-ADM-05 的 MUST NOT 条款只有 reset-state 场景，测活语义在 `specs/provider-adapters/spec.md:57-58` 重复定义。
- 影响：R-API-05（统一响应/错误码）没有实现任务，只有测试门；重启恢复 EWMA（R-SCH-06）无人实现；两个 capability 对测活的定义可能漂移。
- 建议：D23 + D24。

**F-11 [低][高] `/healthz` 是否鉴权未定义**
- 证据：`design.md:350`「统一认证：`Authorization: Bearer ocr_...`」；`design.md:392` 把 `/healthz` 列在公共 API 下；`specs/ocr-api/spec.md:83-84` 只要求 DB 健康。
- 影响：若 `/healthz` 也要 Bearer，反代/uptime 探活无法使用；若不要，则「统一认证」措辞不成立。
- 建议：D19。

**F-12 [低][高] R-ADM-01「所有 `/api/admin/*`」与 login 自相矛盾**
- 证据：`specs/admin-api/spec.md:10`「所有 `/api/admin/*` MUST 校验 token」；同文件 R-ADM-01 的场景又要求「提交正确密码 → 返回 token」。
- 影响：字面上登录端点也必须先有 token，循环依赖；实现者会自行加例外，但 spec 文本不自洽。
- 建议：D20。

**F-13 [低][高] 腾讯 `region` 字段无列、无定义**
- 证据：`design.md:423` 凭证示例含 `"region": null`；`design.md:186-213` `accounts` 表无 `region` 列；任何 Requirement 都未提 Region。接地：腾讯官方文档明确 Region「此参数为可选参数」，本地官方示例 `region = ""` 时不下发 `X-TC-Region`。
- 影响：字段悬空；实现者可能把它塞进 credentials JSON，造成同一账号两种存储形态。
- 建议：D21（删除该字段；如未来需要，加列并定义）。

**F-14 [低][高] `argon2-cffi` 无消费者**
- 证据：`proposal.md:81` 依赖清单含 `argon2-cffi`；`design.md:160-167` `users` 表无 `password_hash`；`design.md:497` 管理员口令来自 `ADMIN_PASSWORD` 环境变量、常量时间比较，不做哈希存储。
- 影响：多一个无消费者的依赖（供应链面 + 安装时间）。
- 建议：D22。

**F-15 [低][高] proposal 假设无失效条款；缺开放问题/利益相关方节**
- 证据：`proposal.md:65-70` 四条假设均未写「若不成立方案如何失效」；全文无「开放问题」与「利益相关方」节。
- 影响：BASE-14/15/20 的显式性要求未满足；账号贡献者（其额度进入共享池）作为受影响方未被点名。
- 建议：D26。

**F-16 [低][高] `from`/`to` 格式与时区未定义**
- 证据：`design.md:409`「`from`、`to`、`group_by=user\|provider\|account`」；`design.md:158` 只说时间戳存 UTC、展示/重置按 `Asia/Shanghai`。
- 影响：查询边界（含/不含）、时区、默认范围都靠实现者猜；用量汇总可能与成员感知的「今天」不一致。
- 建议：D25。

### 镜 2 · plan-eng（工程级 base R 项）

覆盖：BASE-05 可行性 · BASE-06 错误处理 · BASE-07 内部一致性 · BASE-11 可观测性 · BASE-16 NFR · BASE-17 可追踪性 · BASE-19 图表 · BASE-25 组件清单 · BASE-28 安全。

**F-17 [高][高] 图片解码前无像素上限（decompression bomb）**
- 证据：`design.md:144-147` 图片数据流先 `Pillow 验证真实格式` 再 `按 provider 限制`；`design.md:499`「`Pillow.verify()` + 实际解码」；全文无像素数/最长边（解码前）上限。
- 影响：10MB 的 PNG 可以声明 12000×12000（144M 像素）；Pillow 默认 `MAX_IMAGE_PIXELS≈89M` 只发 **warning**，`load()` 仍会分配 ~432–576MB。单进程 + 并发 2 即可 OOM，uvicorn 被杀 → 全站不可用。这是单实例架构下最现实的「一个请求打挂全站」路径。
- 建议：D8（`Image.open()` 后先读 `size`，>40M 像素或最长边 >10000 → 400；显式设置 `PIL.MAX_IMAGE_PIXELS`；再 `load()`）。

**F-18 [高][高] 无全局并发/内存预算**
- 证据：`design.md:199` 每账号 `max_concurrency` 默认 2；`design.md:337-344` 并发与共享状态只描述每账号 `in_flight` 和共享 httpx 连接池（`max_connections=100`）；无全局信号量或内存预算。
- 影响：`auto` 跨 N 个账号时峰值 = 2N；F-17 的位图 + base64 副本 + 厂商响应叠加，小机器 OOM。连接池 100 反而允许更高并发。
- 建议：Q5。

**F-19 [高][高] `httpx` INFO 日志会记录百度 `access_token`（query 参数）**
- 证据：`design.md:9`「`access_token` 走 query」；`design.md:472-473` 结构化日志字段含 `path`，并 MUST NOT 记录凭证。接地：httpx 官方 logging 文档示例显示 `httpx` logger 在 **INFO** 级别输出「HTTP Request: GET https://www.example.com」，包含完整 URL（含 query）。
- 影响：默认 `LOG_LEVEL=INFO`（`design.md:452`）下，每次百度调用都会把 `access_token=...` 写进 stdout 日志，直接违反「MUST NOT 记录凭证」。token 30 天有效，泄露面很大。
- 建议：D9（`logging.getLogger("httpx").setLevel(WARNING)`；或对 URL 做 query 脱敏过滤器；补一条单测断言日志不含 `access_token`）。

**F-20 [中][中] 百度 OAuth 200 + `error` body 未覆盖**
- 证据：`design.md:462`「401/403 → 账号 `invalid`；网络/5xx → `cooling` 30s」；百度 OCR 主接口以 HTTP 200 + `error_code` 返回错误是已知形态（design 已按「厂商错误码」处理），但 token 端点只按 HTTP 状态分类。
- 影响：token 端点若返回 200 + `{"error":"invalid_client",...}`，适配器会把它当成功、拿到空 token，后续调用以 110/111 失败，错误归因错误。**置信度中**：官方 OAuth 文档未给出错误响应示例（已尝试抓取），需实现期用真实错误凭证验证。
- 建议：D6（无论状态码，先解析 body 的 `error`/`error_description`；有则按 `AUTH_FAILED` 处理）。

**F-21 [中][高] 百度 8MB 约束是「base64 + urlencode 后」；最短边 15px 未处理**
- 证据：`design.md:9`「Base64 ≤8MB、最长边 ≤4096px」；`design.md:152` 同；接地：百度官方文档原文「base64编码和urlencode后大小不超过8M，最短边至少15px，最长边最大4096px」。
- 影响：urlencode 会把 `+`/`/`/`=` 转义，约 1–3% 膨胀；按「base64 ≤8MB」归一化仍可能超过 8MB 而被百度拒绝。最短边 <15px 的细条图（截图裁剪常见）会被厂商以输入错误拒绝，而网关没有前置校验。
- 建议：D10（目标改为「base64+urlencode 后 ≤7.8MB」留余量；最短边 <15px → 400 或等比放大）。

**F-22 [中][高] `MAX_UPLOAD_BYTES` 对 base64 JSON 的语义未定义**
- 证据：`design.md:448`「`MAX_UPLOAD_BYTES` | 否 | `10485760` | 入口上限」；`design.md:364` base64 JSON 输入。
- 影响：10MB 图片的 base64 约 13.3MB，JSON body 更大。若按 body 体积卡 10MB，base64 输入的实际可用上限只有 ~7.5MB，与「入口 10MB」的宣传不符；若按解码后字节卡，multipart 与 JSON 又需要两套逻辑。
- 建议：D11（统一按解码后的图片字节数校验；body 体积另设宽松上限防滥用）。

**F-23 [中][中] p99<20ms 与每请求 SQLite commit 的张力；pragma 未指定**
- 证据：`design.md:342`「`usage_events` 每请求 `INSERT` 并 `commit`」；`design.md:482`「mock 厂商 0ms 时 p99 <20ms」；全文未指定 `journal_mode=WAL` / `synchronous`。
- 影响：默认 `synchronous=FULL` 下每次 commit 一次 fsync；慢盘/云盘上单次 5–20ms，p99 目标可能直接失守。WAL 只在 C4 图和 decision-memo 里出现，没有落到 pragma。
- 建议：D30（启动时 `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`；基准测试在目标机器上跑）。

**F-24 [低中][高] OAuth token 获取 5s×2 > 账号 timeout 8s**
- 证据：`design.md:462`「百度 OAuth token | 5s（1 次重试）」；`design.md:198` `timeout_ms` 默认 8000；`design.md:310` `timeout = min(account.timeout_ms, remaining)`。
- 影响：token 获取两次最坏 10s，已经超过该账号 8s 的预算；`adapter.call(account, timeout)` 内部的 token 获取若不受同一 timeout 约束，会突破 deadline。
- 建议：D12。

**F-25 [低中][高] `Retry-After` 无上限**
- 证据：`design.md:329`「`cooling` 30s（或 `Retry-After`）」。
- 影响：厂商或中间层返回 `Retry-After: 86400` 会让账号冷却一天；单实例下等于该账号长时间不可用。
- 建议：D13（`min(Retry-After, 300s)`）。

**F-26 [低中][高] 缓存最坏内存 256MB（按条数不按字节）**
- 证据：`design.md:431`「1000 条 / 3600s……单条结果 >256KB 不缓存」。
- 影响：最坏 1000×256KB≈256MB，未计入图片与解码位图；小机器上叠加 F-18 更危险。实际 OCR 结果通常 <10KB，但上限没有字节预算。
- 建议：D30（记录最坏值；必要时加 `CACHE_MAX_BYTES`）。

**F-27 [低中][中] 账号状态/EWMA/`last_used_at` 持久化时机未定义**
- 证据：`design.md:278`「成功更新 `ewma`、`last_used_at`、内存配额计数；失败按状态机转移并记 `last_error_*`」；`specs/account-pool-scheduling/spec.md:64-68` R-SCH-06 要求启动时从账号表加载 EWMA 与状态。
- 影响：若这些字段只改内存、不落库，重启后 R-SCH-06 的「重启恢复 EWMA/状态」不成立；若每请求 UPDATE，需计入 p99。两者都没写。
- 建议：D14（每请求一次 UPDATE；配额计数仍批量）。

**F-28 [低中][高] 默认无任何限流**
- 证据：`design.md:183-184` Key 的 `daily_limit`/`rpm_limit` 默认 NULL；`design.md:200` `qps_limit` 默认 NULL；`design.md:526` 风控对策写「账号级并发/QPS + Key RPM/日限额」。
- 影响：默认部署下泄露一个 Key 即可无限刷；「共享账号池触发风控」的对策默认关闭。
- 建议：Q3。

**F-29 [中][高] 登录限速可被用来锁死管理员**
- 证据：`design.md:396`「登录失败按进程级滑动窗口限速（5 次/分钟，超限 429）」；`specs/admin-api/spec.md:10` 同。
- 影响：限速是进程级且无 IP 维度；攻击者每分钟发 5 个错误密码，就能让合法管理员持续收到 429——而登录是获取 token 的唯一入口，等于管理面被远程 DoS。无 SPA 时也没有旁路。
- 建议：D16（按 IP + 全局双层；全局层只增加延迟不永久阻断；或对已持有有效 token 的会话豁免）。

**F-30 [低中][高] 单 worker 守卫只查 `WEB_CONCURRENCY`**
- 证据：`design.md:344`「检测到 `WEB_CONCURRENCY>1` 时启动告警」；`design.md:339` 依赖「所有内存态只在单一 asyncio 事件循环内读写，无需锁」。
- 影响：`uvicorn app.main:app --workers 4` 不会设置 `WEB_CONCURRENCY`（该变量是 gunicorn/平台约定，uvicorn 只把它当默认值读取），应用侧看不到；每个 worker 各有一份配额计数/缓存/注册表 → 配额超用、冷却失效、缓存不一致。只告警不阻止也不够。
- 建议：D17（同时检查 `WEB_CONCURRENCY`、`UVICORN_WORKERS`、`sys.argv` 的 `--workers`；>1 直接拒绝启动）。

**F-31 [低中][高] 无备份/RTO/RPO 声明**
- 证据：`design.md:478-490` NFR 表只写「可用性 单实例，无 SLA 承诺」；`design.md:532-536` 迁移/回滚只写 `alembic downgrade base` 或删 `data/`；无备份策略。
- 影响：SQLite 同时承载账号、凭证密文、Key 哈希与用量；磁盘损坏 = 全部配置丢失（凭证密文可用 `MASTER_KEY` 解密，但 `MASTER_KEY` 也在环境变量里）。BE-11 要求的 RTO/RPO 未声明。
- 建议：D29。

**F-32 [低][高] multipart 未列 `image_base64` 字段，但 R-API-01 要求「同时提供」返回 400**
- 证据：`design.md:361` multipart 只列 `file`、`language`、`provider`；`specs/ocr-api/spec.md:20-22` 要求「同时提供 `file` 与 `image_base64`（或 `image_base64` 与 `image_url`）→ 400」。
- 影响：multipart 契约里没有 `image_base64` 字段，这个场景只对 JSON 可测；实现者可能只处理 JSON 的「双输入」。
- 建议：D15。

**F-33 [低][高] 客户端超时重试会重复扣配额（无幂等键）**
- 证据：`design.md:371-384` 成功响应；`design.md:430-433` 缓存只在成功后写入；无 `Idempotency-Key` 或 in-flight 去重。
- 影响：网关 20s deadline 超时但厂商实际成功时，客户端重试会再次调用厂商并再扣一次配额；缓存救不了（首次请求未写入）。
- 建议：D28（文档声明；或后续加 `Idempotency-Key`）。

**F-34 [低][高] 配额检查-递增竞态（并发下可超额 ≤`max_concurrency-1`）**
- 证据：`design.md:295`「当前周期配额未达上限（内存计数）」；`design.md:278`「成功更新……内存配额计数」；`design.md:340` `in_flight` 只限制并发，不预占配额。
- 影响：`used=limit-1` 时两个并发请求都通过检查，最终 `used=limit+1`；单账号 `max_concurrency=2`，最多超额 1。厂商侧会以配额错误兜底，但「免费额度不超用」的承诺有 1 次误差。
- 建议：D28（显式记录容忍度；或选中时预占、失败释放）。

### 镜 3 · backend（领域清单 BE-01..BE-11）

| ID | 判定 | 说明 / 关联 |
| --- | --- | --- |
| BE-01 DB 迁移 | **PASS（带 F-07）** | `design.md:283-285` 有 v_old/v_new 对照与 downgrade；但 `period_key` 与 `reset_day` 冲突（F-07） |
| BE-02 API 合约 | **PASS（带 F-03/F-04/F-16/F-32）** | 请求/响应/错误示例齐全；greenfield 无 breaking；缺幂等声明（F-33）与 `language` 定义（F-04） |
| BE-03 Auth/权限 | **PASS（带 F-11/F-12/F-29）** | 每 endpoint 的鉴权层在 `api/deps.py`；`/healthz` 与 login 例外未写清；登录限速 DoS（F-29） |
| BE-04 错误处理/失败模式 | **PASS（带 F-17/F-20/F-21/F-45）** | 失败模式表覆盖 DB/缓存/厂商/URL/admin token；外部依赖超时齐全；像素炸弹与 OAuth body 错误是缺口 |
| BE-05 数据一致性 | **PASS（带 F-34）** | usage_event 每请求 commit、配额 2s 批量；配额检查-递增竞态已记录 |
| BE-06 性能/容量 | **PASS（带 F-23/F-26）** | 索引齐全（`api_keys.key_hash`、`usage_events.api_key_id, created_at`）；p99 与缓存内存有张力 |
| BE-07 可观测性 | **PASS（X2）** | 结构化日志字段齐全；无 metrics（P2 non-goal）；存活/就绪不分离（单实例，已裁掉） |
| BE-08 退避重试/熔断 | **PASS（X3）** | 故障切换替代同点重试；OAuth 1 次重试；无 jitter（已裁掉） |
| BE-09 优雅退出 | **PASS** | `shutdown` 刷配额（`design.md:342`）；uvicorn 默认 graceful；未写最长等待（低，未单列） |
| BE-10 分发管道 | **N/A** | 无容器/二进制产物；Docker 是 non-goal（`proposal.md:30`） |
| BE-11 SLA/RTO/RPO | **FAIL（F-31）** | 只写「无 SLA」；RTO/RPO/备份未声明 |

**领域镜唯一新增**：无（上述缺口已由 F-17/F-18/F-19/F-20/F-21/F-23/F-26/F-29/F-31/F-34 覆盖；BE-07/08/09 的低风险项进「已裁掉」或一行带过）。

### 镜 4 · devex（TG-28：公共 API + 配置面）

| ID | 判定 | 证据 / 说明 |
| --- | --- | --- |
| DX-01 TTHW | **UNVERIFIABLE** | `design.md:532-536` Migration Plan 有 5 条命令，但无步骤数/每步耗时/TTHW 估算；README 尚未产出（`tasks.md:86` 5.6 才写） |
| DX-02 错误文案三件套 | **FAIL** | `design.md:350-357` 只定义 `code` + 一个示例 `message`（"invalid api key"）；problem/cause/fix 三段未定义。建议：声明 `message` 为非契约、客户端按 `code` 分支（D27） |
| DX-03 命名/默认值 | **PASS** | 新 API 命名与 tech-selection 一致；env 默认值有 decision-memo/tech-selection 依据；`MAX_UPLOAD_BYTES` 语义见 F-22 |
| DX-04 升级路径 | **N/A** | greenfield，无既有 developer-facing 面 |
| DX-05 Skill DX | **N/A** | 不涉及 SKILL.md |

**F-39 [低][UNVERIFIABLE] TTHW 无估算** — 见 DX-01；建议 D27。
**F-40 [低][FAIL] 错误文案未定义** — 见 DX-02；建议 D27。

### 镜 5 · 对抗-隐藏假设（refute=true，找不到爆点才放过）

**F-30（对抗命中）[低中][高] 单 worker 守卫绕过** — 见镜 2；`--workers N` 不设置 `WEB_CONCURRENCY`，内存态分裂。
**F-28（对抗命中）[低中][高] 风控对策默认关闭** — 见镜 2；「共享账号池触发风控」的缓解项默认 NULL。
**F-43 [低][中] 错误码映射未固化到 spec，文档漂移无检测**
- 证据：`design.md:335`「映射表依据官方错误码文档维护」；`tasks.md:66` 4.4 只要求「四类映射正确」；design 未列任何具体码值。
- 影响：实现者需在实现期自行查文档；百度 17/18/19/110/111/216604、腾讯 `AuthFailure.*`/`RequestLimitExceeded`/`ResourceUnavailable.InArrears` 的归类若有偏差，黄金用例也按错误假设写。
- 建议：D31（design 附录列映射表 + 官方 URL + 核对日期；golden case 引用同一张表）。
**X6（对抗命中，已裁掉）** — `/docs` 暴露 admin schema；D2 拍板代价。

### 镜 6 · 对抗-失败模式

**F-45 [高][高] `AUTH_FAILED` 过粗：token 过期 / 时钟偏移 → 永久 invalid**
- 证据：`design.md:327`「`AUTH_FAILED` | 401/403 / 厂商鉴权错误码…… | `invalid`（不自动恢复） | 继续下一个候选；全无 → 503」；接地：百度错误码 110「access token invalid」/111「access token expired」（`cloud.baidu.com/doc/OCR/s/dk3h7y5vr`）；腾讯 `AuthFailure.SignatureExpire` 文档明确「timestamp must be within five minutes of server time」。
- 影响：① 百度 token 过期（30 天）本可刷新自愈，却把账号永久置 invalid；② 主机时钟偏移/VM 暂停会让**全部腾讯账号**同时 `SignatureExpire` → 全部 invalid，且不会自动恢复，只能人工 reset。这是「一次环境抖动打挂一个厂商」的路径。
- 建议：D7（百度 110/111 刷新重试一次）+ Q4（腾讯 `SignatureExpire` 归 cooling 而非 invalid）。
**F-20（对抗命中）[中][中] 百度 OAuth 200+error body** — 见镜 2。
**F-47（与 F-45 合并）** 时钟偏移 → 全腾讯 invalid。
**X4（对抗命中，已裁掉）** 账号/成员删除竞态。
**X5（对抗命中，已裁掉）** vendor 成功后崩溃丢事件。
**F-50（对抗命中，已裁掉）** usage_events 无保留/归档策略 — 见「已裁掉」X10；D29 补运维说明。

### 镜 7 · 对抗-乐观估计与边界

**F-01（对抗命中）[高][高] 容量数学不闭合** — 见镜 1。
**F-23（对抗命中）[中][中] p99<20ms vs SQLite commit** — 见镜 2。
**F-26（对抗命中）[低中][高] 缓存最坏内存 256MB** — 见镜 2。
**F-18（对抗命中）[高][高] 并发内存峰值** — 见镜 2。
**X8（对抗命中，已裁掉）** 启动 <5s 未计 Alembic。
**X7（对抗命中，已裁掉）** 缓存 key 用原图 bytes，命中率低于理论值。

### 镜 8 · 接地（grep/读真实文件核验代码事实）

| 核验项 | 结果 | 证据 |
| --- | --- | --- |
| tech-selection 行号引用（21 处） | **全部命中** | `:4` 目标、`:16` SQLite、`:24` 模板、`:29` 匿名开关、`:196` 不存原文、`:208` 2s 刷盘、`:256` 不跨厂商、`:257` 10MB、`:258` SSRF、`:325-349` 管理 API、`:349` cookie+CSRF、`:392-409` 尝试循环、`:431-440` 模板、`:482-483` 会话/CSRF、`:486` SSRF、`:488` 日志、`:615-621` 上线验证、`:644` 风控、`:646` SQLite 单写、`:653` PDF v2 |
| 百度 `general_basic` 端点/参数 | **命中** | 官方文档：POST `/rest/2.0/ocr/v1/general_basic`、`access_token` query、`image` base64+urlencode、**8M（base64+urlencode 后）**、最短边 15px、最长边 4096px、jpg/jpeg/png/bmp、`probability=true` 才返回置信度 |
| 腾讯 `GeneralBasicOCR` | **命中** | 官方文档：Version `2018-11-19`、域名 `ocr.tencentcloudapi.com`、Base64 ≤10M、PNG/JPG/JPEG/BMP/PDF、`TextDetections[].Confidence`；Region **可选**（本地官方示例 `region=""` 不下发 `X-TC-Region`） |
| TC3-HMAC-SHA256 六段 canonical request | **命中** | design/C3 描述与官方签名示例一致（method/URI/query/headers/signedHeaders/hashedPayload） |
| 百度/腾讯错误码 | **命中（补充证据）** | 百度 110/111/17/18/19/4/216604/100/216201；腾讯 `AuthFailure.SignatureFailure`/`SignatureExpire`/`SecretIdNotFound`/`RequestLimitExceeded`/`ResourceUnavailable.InArrears`/`FailedOperation.ImageDecodeFailed`/`InvalidParameterValue` |
| `.gitignore` / 凭证隔离（C9） | **命中** | `.gitignore` 已跟踪且含 `.env`、`data/`、`*.db`；`docs/已开通的 OCR 服务信息.md` 未被跟踪，且 `.git/info/exclude` 含该文件；`git status --porcelain` 洁净 |
| `openspec validate --strict` | **通过** | Change `ocr-gateway-mvp` is valid |
| `httpx` INFO 日志含完整 URL | **命中（库文档）** | httpx logging 文档示例：`httpx` logger 的 INFO 记录含「HTTP Request: GET https://www.example.com」 |
| `cachetools.TTLCache` 是否 LRU | **误报，证伪** | 官方文档：TTLCache 是「LRU Cache implementation with per-item TTL」，溢出淘汰最久未使用项 → R-CAC-02 的 LRU 措辞成立（X9） |
| `argon2-cffi` 消费者 | **无** | `users` 表无 `password_hash`；管理员口令来自 env（F-14） |

---

## 合并裁决

- **去重**：原始发现去重后保留 **38 条唯一 finding**（F-01–F-45，编号不连续处为合并/裁掉；对抗镜的重复命中并入对应 F 编号，命中镜集合记在各条「命中镜」里）。
- **接地抽查**：全部 finding 的引文均真打开核对（本报告逐条带 `file:line` + 原文）；库行为类（httpx / Pillow / cachetools / uvicorn）标注了来源；其中 cachetools 一条被证伪并落入「已裁掉」。
- **对抗裁决**：F-01/F-07/F-17/F-18/F-19/F-45 为高严重度，均通过「实现期会炸」的反驳（不是顺向 checklist）；X1–X10 为对抗镜提出但被裁掉/降级的项，理由已记录。
- **结论**：**无阻塞项**；6 项高严重度（F-01/F-07/F-17/F-18/F-19/F-45）与 5 个 [需拍板] 问题必须在出票前关闭。其余 32 条为中级/低级，已按 D1–D31 落盘或记录。

| 处置 | 条目 |
| --- | --- |
| **已落盘（D1–D31）** | F-02/F-03/F-04/F-07/F-08/F-09/F-10/F-11/F-12/F-13/F-14/F-15/F-16/F-17/F-19/F-20/F-21/F-22/F-23/F-24/F-25/F-26/F-27/F-29/F-30/F-31/F-32/F-33/F-34/F-39/F-40/F-43 |
| **待拍板（Q1–Q5）** | F-01（Q1）、F-05/F-06（Q2）、F-28（Q3）、F-45 的腾讯部分（Q4）、F-18（Q5） |
| **已裁掉（X1–X10）** | 见「已裁掉」表 |

---

## 已应用的 amendments

> 全部改动处均标 `[spec-review-amendment]`；行号以评审基线 `5d23ed2` 为准。

| 文件 | 改动 |
| --- | --- |
| `design.md` | 尝试循环区分 503/504（D1）；`period_key` 月周期改为起始日 + `quota_total` 不自动恢复（D2）；`usage_events` 只记进入调度的请求（D3）；`language` 枚举与映射（D4）；`PROVIDER_ERROR` 502（D5）；百度 OAuth body 错误（D6）；百度 110/111 刷新重试（D7）；像素上限（D8）；httpx 日志脱敏（D9）；8MB+urlencode / 15px（D10）；`MAX_UPLOAD_BYTES` 语义（D11）；token 超时预算（D12）；Retry-After 上限（D13）；状态持久化时机（D14）；multipart `image_base64`（D15）；登录限速双层（D16）；单 worker fail-loud（D17）；`/healthz` 不鉴权（D19）；region 删除（D21）；`from`/`to`（D25）；SQLite pragma + 缓存内存（D30）；错误码映射附录（D31）；备份/RPO（D29）；幂等/并发超额（D28） |
| `proposal.md` | Compliance 补 D1/D3/D13 + 第三方数据声明（D18）；假设补失效条款 + 开放问题/利益相关方（D26）；移除 `argon2-cffi`（D22） |
| `specs/ocr-api/spec.md` | R-API-01 补 `language` 枚举与场景（D4）；R-API-03 补像素上限与最短边场景（D8/D10）；R-API-05 补 502/504 场景（D1/D5） |
| `specs/account-pool-scheduling/spec.md` | R-SCH-03 补 502/504 语义与场景（D1/D5） |
| `specs/quota-accounting/spec.md` | 未应用（待 Q2 拍板）：R-QTA-04 口径改为 `quota_used` |
| `specs/admin-api/spec.md` | R-ADM-01 排除 login（D20）；R-ADM-05 补测活场景（D24） |
| `specs/provider-adapters/spec.md` | R-ADP-01 补 token 过期刷新场景（D7）；R-ADP-04 补错误码映射表引用（D31） |
| `tasks.md` | 3.7 加 `R-API-05`；3.4 加 `R-SCH-06`；5.6 加 README quickstart/TTHW（D23/D27） |

> **未应用（待 Q1–Q5 拍板）**：容量前提（Q1）、Key 日限额口径与存储（Q2）、默认限流值（Q3）、腾讯 `SignatureExpire` 归类（Q4）、全局并发信号量（Q5）。这 5 项在拍板前保持原文，报告已给出推荐与代价。

---

## T/S 残差

- `openspec instructions <artifact> --change ocr-gateway-mvp --json` 的 `rules` 已逐条核对：proposal 四节齐全；specs 每个 Requirement 挂 Scenario、有稳定 ID、Purpose ≥50 字符；design 有 Compliance/数据模型/失败模式/NFR/安全/决策记录/组件图；tasks 有 R-ID 与测试覆盖图。
- **残差 1**：`tasks.md:33` 3.1 把「共享 httpx client」与「图片管线」两个组件合在一个任务里，与「单任务控制在可独立验证的小粒度」有轻微张力（可拆为 3.1a/3.1b，非阻塞）。
- **残差 2**：proposal 缺「利益相关方」「开放问题」两节（已由 D26 补；补后无残差）。
- `openspec validate ocr-gateway-mvp --strict` 通过；无 schema 结构残差。

---

## 收敛建议

建议进入**设计 HARD-GATE**。请人逐项过：

1. 拍板三问（Q-scope / Q-deps / Q-risk）勾选；
2. 决策登记区的 5 个 [需拍板]（Q1–Q5）；
3. 对「已裁掉」X1–X10 复核裁得对不对（尤其 X9 是证伪记录，不是漏项）。

拍板批准后由主 session 调用 `anchor_writeback.py --domain design --set design_approved=true` 回写锚；若拍板前要求修改四件套，按「窄复核」纪律先审增量再拍板。
