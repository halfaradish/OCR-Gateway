---
schema_version: 1
change: ocr-gateway-mvp
branch: feat/ocr-gateway-mvp
generated_at: 2026-11-03T00:48:29+08:00
decision_hash: 15e1d3036344
---

# 决策纪要 · ocr-gateway-mvp

## 目标态

单实例 OCR 网关 MVP：管理员通过管理 API 配置百度/腾讯账号池，成员用网关 API Key 调 `POST /v1/ocr/image`（multipart / base64 / URL），网关按优先级 + EWMA 选号、失败切换、归一化返回 `text + lines`，并按账号与 Key 记账配额；无 SPA，管理操作走 OpenAPI 文档。

## 拍板决策

- **D1 厂商范围：百度 + 腾讯** — 依据：核心价值是聚合免费额度与故障切换；百度（OAuth token）与腾讯（TC3-HMAC-SHA256）两种认证形态能真正验证适配器抽象，两家即可演示主备切换；**砍掉的候选**：仅百度（退化为单厂商代理，聚合/切换价值不成立）、四家全上（阿里/华为签名与配额模板使 MVP 明显变大）。
- **D2 管理端：仅管理 API + OpenAPI 文档，无 SPA** — 依据：核心链路是公共 API，FastAPI 自带 `/docs` 可直接操作，省掉前端构建链；**砍掉的候选**：极简 SPA（多一套 React 构建/静态托管/联调）、完整 v1 面板（超出 MVP）。
- **D3 附加能力：结果缓存 + URL 输入进 MVP；批量与本地 OCR 兜底推迟** — 依据：缓存直接省额度且实现小，URL 是客户端常用输入；**砍掉的候选**：批量接口（并发与逐张结果可后置）、本地 RapidOCR（依赖最重，技术选型排在 M4）。
- **D4 管理端鉴权：登录换签名 Bearer token，不用 cookie + CSRF** — 依据：无浏览器 SPA 时 Bearer 可被 `/docs` 的 Authorize 直接携带，CSRF 面不存在；**偏离** tech-selection 的 cookie+CSRF 设计（`docs/tech-selection.md:349`、`:482-483`），偏离理由记录于此；**砍掉的候选**：cookie 会话（curl/`/docs` 操作笨重，仍需 CSRF 头）、纯静态 `ADMIN_TOKEN`（不可轮换、无登录审计）。面板回归时恢复 cookie+CSRF 双轨。
- **D5 配置来源：环境变量（pydantic-settings），不建 settings 表、不做 `/settings`** — 依据：无 SPA 时设置写操作没有消费界面，启动期配置更简单；**砍掉的候选**：settings 表 + 管理 API（多一条写路径与迁移）。settings 表随面板回归。
- **D6 存储：单实例 SQLite(WAL) + SQLAlchemy async + Alembic；内存计数每 2 秒批量 upsert** — 依据：额度量级与 ≤5 人 / 日均 <500 次规模下单写远非瓶颈，崩溃最多丢 2 秒计数（`docs/tech-selection.md:208`）；**砍掉的候选**：Postgres（MVP 无多实例需求）、Redis（多一个外部依赖）。
- **D7 URL 输入 SSRF 策略** — 依据：仅 http/https；DNS 解析后校验 IP（拒私网/回环/链路本地/云元数据）；逐跳复核重定向（≤3 次）；10s 超时、10MB 上限；失败不回显内网细节；**砍掉的候选**：关闭 URL 输入（用户拍板保留）、依赖系统代理（不可控）。
- **D8 百度用 `general_basic`（标准版），腾讯用 `GeneralBasicOCR`** — 依据：标准版符合「通用文字」能力与免费额度口径；百度标准版不返回 confidence ⇒ 响应允许 `null`；**砍掉的候选**：百度 `accurate_basic`（精度更高但口径/额度不同，后续可按 provider 参数扩展）。
- **D9 图片管线按厂商限制归一化** — 依据：入口 10MB（`docs/tech-selection.md:257`）；Pillow 校验真实格式、EXIF 旋转；百度要求 base64 ≤8MB 且最长边 ≤4096px（官方文档），腾讯 base64 ≤10MB；超限等比缩放/转 JPEG，仍超限返回 400；**砍掉的候选**：只做统一 10MB 校验（百度会因 base64 膨胀必然超限）。
- **D10 API 鉴权始终开启；MVP 不提供 `api_auth_enabled` 开关，无匿名模式** — 依据：公网部署 + 共享额度，匿名模式是风险面，少一条分支；**砍掉的候选**：保留开关（技术选型 `docs/tech-selection.md:29` 的面板告警成本高且暂无面板）。
- **D11 配额用可编辑模板 JSON，数值标「以官网为准」** — 依据：官方未公布固定额度，模板不能当事实，账号级可覆盖；**砍掉的候选**：硬编码官方数字（过时即错）、不提供模板（新账号开箱不可用）。
- **D12 验收锚：真实百度/腾讯账号各识别一张中文截图；契约测试默认 skip** — 依据：签名错误只有真 key 能暴露（`docs/tech-selection.md:615-621`）；**砍掉的候选**：只靠 respx mock（签名黄金用例覆盖不了账户级权限/额度）。
- **D13 部署：公网 + 反代 HTTPS；应用不终结 TLS** — 依据：用户拍板；TLS 由 Caddy/Nginx 终结，应用只信任反代头；**砍掉的候选**：应用内 TLS（证书管理复杂，MVP 不需要）。
- **D14 规模前提：≤5 人、日均 <500 次** — 依据：人 2026-11-03 确认，推算均值 <0.006 QPS，SQLite/单进程足够；**砍掉的候选**：多实例/队列（无规模依据）。

## 承重约束

- **C1 免费额度按厂商账号计、可池化** — 验证方式：官方产品页确认有免费测试资源，具体数额未公布；**证据锚**：`docs/tech-selection.md:4`（项目目标）、`:24`（模板可覆盖）、Baidu 产品页 https://cloud.baidu.com/product/ocr.html（「注册可领取免费测试资源」）、人 2026-11-03 确认两家真实账号可用。**残余风险**：额度数值/活动会变，池化可能触发风控 ⇒ 模板可编辑 + 并发/QPS 限制。
- **C2 百度通用文字识别标准版接口形态** — 验证方式：官方文档逐项核对；**证据锚**：https://cloud.baidu.com/doc/OCR/s/zk3h7xz52（POST `/rest/2.0/ocr/v1/general_basic`；`access_token` 走 query；`image` base64 后 urlencode；≤8MB；最短边≥15px、最长边≤4096px；jpg/jpeg/png/bmp；`words_result` 不含 confidence，`probability=true` 才返回）。
- **C3 腾讯 GeneralBasicOCR 接口形态** — 验证方式：官方文档 + 官方签名示例逐项核对；**证据锚**：https://cloud.tencent.com/document/product/866/33526（Action `GeneralBasicOCR`、Version `2018-11-19`、域名 `ocr.tencentcloudapi.com`、Base64≤10M、PNG/JPG/JPEG/BMP/PDF、`TextDetections[].Confidence`）；https://cloud.tencent.com/document/api/866/33519（TC3-HMAC-SHA256；canonical request 六段；`host`+`content-type` 必选头）。
- **C4 单实例 SQLite 足够** — 验证方式：额度量级推算 + 人确认规模；**证据锚**：`docs/tech-selection.md:16`、`:646`；人 2026-11-03 确认 ≤5 人、日均 <500 次（均值 <0.006 QPS）。
- **C5 无 SPA 的管理端可行** — 验证方式：运营动作均为 JSON CRUD，`/docs` 可携带 Bearer；**证据锚**：人 2026-11-03 拍板（D2）、`docs/tech-selection.md:325-349`（管理 API 清单）、FastAPI 自动 OpenAPI 文档（框架能力）。
- **C6 URL 输入的 SSRF 防护可用标准库实现** — 验证方式：DNS 解析后 `ipaddress` 校验 + 逐跳复核；**证据锚**：`docs/tech-selection.md:258`、`:486`；Python 标准库 `socket.getaddrinfo` + `ipaddress`（无需第三方依赖）。
- **C7 默认不落 OCR 原文** — 验证方式：`usage_events` 只存元数据与 image hash 前 16 位；**证据锚**：`docs/tech-selection.md:196`、`:488`。
- **C8 显式 provider 不跨厂商回退，`auto` 才可切换** — 验证方式：调度器按 `provider` 参数过滤候选；**证据锚**：`docs/tech-selection.md:256`、`:392-409`。
- **C9 真实凭证仅本地保管、不进仓** — 验证方式：本机 `.git/info/exclude` 排除本地凭证清单，`git status --porcelain` 不含它；**证据锚**：人 2026-11-03 明确要求（本地凭证文档首页注明「应放入 .gitignore 严格本地化处理」）、`git status --porcelain` 输出。

## 接受的边角

- **额度模板数值可能过时** — 概率高/影响中/完美成本高（需人工核对官网）；**为何接受**：模板可编辑 + 标「以官网为准」+ 上线前核对（`docs/tech-selection.md:431-440`）。
- **崩溃丢最多 2 秒配额计数** — 概率低/影响小/完美成本高（同步写盘拖慢热路径）；**为何接受**：`docs/tech-selection.md:208` 已定，免费额度场景可容忍。
- **共享账号池触发厂商风控** — 概率中/影响大/无法完美防御；**为何接受**：BYOK + 并发/QPS 限制 + 不对外转售（`docs/tech-selection.md:644`），剩余风险由运营监控承担。
- **管理端无 SPA 的操作摩擦** — 概率确定/影响小/完美成本高；**为何接受**：运营者具备技术背景，`/docs` 足够；完整面板按 M3 回归。
- **契约测试默认 skip 可能漏真实签名问题** — 概率中/影响大/完美成本高（需真人持 key 才能跑）；**为何接受**：上线前手工验收清单（`docs/tech-selection.md:615-621`）。

## 三镜代价

- **系统镜**：优先保证后端链路正确与可验证；放弃多实例/队列与面板，耦合面小、可回退（面板回归时增加 cookie 会话）。
- **用户镜**：成员只感知统一 API 与 Key；运营者感知 `/docs` 操作摩擦（已接受）。
- **开发循环镜**：无前端构建链，测试与实现在同一 Python 工程内闭环；代价是面板体验后置。
- **主次判定**：系统镜优先，开发循环镜受益；用户镜的摩擦被明确接受。
