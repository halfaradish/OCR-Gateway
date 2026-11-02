# Proposal

## Why

团队的云 OCR 免费额度分散在多个厂商账号上：没有统一入口、没有账号级配额与故障切换，额度用不满，单个账号一挂就整体不可用。本 change 交付一个可部署的单实例网关，把百度/腾讯账号聚合成统一 OCR API，成员用各自网关 Key 调用。技术选型已定稿，两家真实账号已就绪，现在先交付最小闭环。

## What Changes

- 新增 Python/FastAPI 后端（`backend/`）：公共 OCR API、管理 API、账号池调度、配额记账、结果缓存。
- 新增 SQLite 数据库与 Alembic 初始迁移：`users`、`api_keys`、`accounts`、`usage_events`、`quota_counters`。
- 新增百度、腾讯适配器（纯 `httpx`，手写 OAuth token 与 TC3-HMAC-SHA256 签名），结果归一化为 `text + lines[]`。
- 新增图片输入管线：multipart / base64 / URL；格式校验、EXIF 旋转、按厂商限制缩放/压缩。
- 新增管理端鉴权（管理员密码换取签名 Bearer token）与成员、API Key、账号、用量、日志管理 API。
- 新增只读配额模板查询（百度/腾讯参考额度，数值标注「以官网为准」）。
- 新增环境配置样例、运行说明与 pytest 测试体系；不含前端与容器化。
- **BREAKING**：无（greenfield，无既有对外契约）。

## Success Metrics

1. **双厂商真实可用** — 基准：无网关（0）→ 目标：百度、腾讯各用真实账号成功识别 ≥1 张中文截图（`text` 非空）— 度量：契约验收记录 + 请求日志。
2. **同厂商故障切换** — 基准：N/A → 目标：首选账号注入 5xx/超时后，请求在总 deadline 内由备用账号成功返回 — 度量：`respx` 集成测试断言调用序列与最终 provider。
3. **配额记账准确** — 基准：N/A → 目标：成功请求账号/Key 各 +1，缓存命中 +0，失败 +0；日/月重置按 Asia/Shanghai — 度量：API 测试 + SQL 断言。

## Non-Goals

- **前端 SPA / 完整管理面板**（技术选型 M3）——假设运营者可用 `/docs` 或 curl 完成全部管理动作。
- **批量接口**——假设 MVP 客户端可逐张调用。
- **本地 OCR 兜底**（技术选型 M4）——假设 MVP 期间至少一家云厂商可用。
- **阿里/华为适配器**——假设两家已足够验证聚合与切换；适配器接口保持可扩展。
- **Docker/Compose**（技术选型 M5）——假设 MVP 可用 `uv run` 直接运行。
- **PDF、表格/版面结构化、多租户计费、成员自助登录、WebSocket、Prometheus `/metrics`**——均不在 MVP 闭环内。
- **`settings` 表与 `/settings` 管理接口**——MVP 用环境变量；假设运营者接受改环境变量后重启。
- **匿名调用（`api_auth_enabled=false`）**——假设公网部署必须始终鉴权。
- **cookie 会话 + CSRF**——改用 Bearer token；假设无浏览器 SPA 时不需要 CSRF 防护（见 `decision-memo.md` D4）。

## Compliance

- 遵守 `docs/tech-selection.md` 已定稿决策；偏离项（厂商范围 4→2、批量/本地 OCR 延后、Bearer 管理鉴权、无 `settings` 表、无匿名模式、无 Docker/Compose）在 `decision-memo.md` D1/D3/D4/D5/D10 与本文 Non-Goals 记录理由，不静默例外。`[spec-review-amendment D18]`
- 数据流：仅 URL 输入会主动出站拉取图片；图片与识别请求会发送给所选厂商（百度/腾讯），不向其他第三方发送；日志与库中不落原文。`[spec-review-amendment D18]`
- 对外合约遵守技术选型的响应结构（`text + lines[{text, confidence}]`，不统一 bbox）与错误码表。
- 安全：凭证 AES-256-GCM、API Key 只存 SHA-256、默认不落 OCR 原文、URL 输入 SSRF 防护、上传体积/格式校验。
- 真实凭证仅本地保管，MUST NOT 进入仓库、日志或任何产物；仓库只保留占位符。
- 规格格式遵守 sdflow-spec-driven schema：每个 Requirement 挂 `#### Scenario`，tasks 与 Requirement ID 双向追溯。

## Capabilities

### New Capabilities

- `ocr-api`: 公共 OCR 契约与输入/响应/错误行为，含 multipart、base64、URL 三种输入，providers、me、healthz。
- `provider-adapters`: 百度/腾讯适配器的调用、签名、结果归一化与错误分类。
- `account-pool-scheduling`: 账号模型与凭证加密、候选过滤、优先级/EWMA 排序、故障切换与冷却。
- `quota-accounting`: 账号与 Key 的配额计数、日/月重置、usage 事件、缓存命中语义。
- `result-cache`: 基于图片哈希的内存 TTL/LRU 结果缓存。
- `admin-api`: 管理员登录（Bearer）、成员、API Key、账号 CRUD/测活/重置、用量与日志查询、配额模板查询。

### Modified Capabilities

（无——`openspec/specs/` 为空，本 change 引入初始能力。）

## 需求优先级

- **P0（MVP 闭环必需）**：公共 OCR API（multipart/base64/URL）、百度/腾讯适配器、账号池调度与切换、配额记账、管理员鉴权、成员与 Key 管理、`/healthz`。
- **P1（可靠性与可运营性）**：结果缓存、`/v1/providers`、`/v1/me`、用量汇总、请求日志、账号测活与重置状态、配额模板查询。
- **P2（可延后）**：`/usage/series` 图表、Prometheus、面板。

## 假设

- 百度/腾讯免费额度在 MVP 使用期内有效且按账号计；官方未公布固定数额，配额模板以官网为准、可编辑。**若不成立**：账号级 `quota_exhausted` 会提前触发，需增加账号或下调规模前提。
- 两家 API 行为与 2026-11-03 官方文档一致（百度 `general_basic`；腾讯 `GeneralBasicOCR` / `2018-11-19`）。**若不成立**：适配器签名/字段映射失效，需按官方变更修适配器并补黄金用例。
- 使用规模 ≤5 人、日均 <60 次（2 个厂商账号 × 1000 次/月；账号增加时按 1000 次/月/账号线性扩容），单实例 SQLite 足够。**若不成立**：需改 Postgres/多实例（`design.md` Non-Goals 已给可证伪阈值）。`[spec-review-amendment Q1]`
- 运营者可用 `/docs`/curl 管理；真实凭证只存本地，不进仓。**若不成立**：管理面不可用，需回补面板（技术选型 M3）。

## 开放问题

无（D1–D14 已关闭；容量口径与默认限流待设计门拍板）。`[spec-review-amendment D26]`

## 利益相关方

- **成员（≤5 人）**：公共 API 消费者；需知晓 Key 限额与缓存语义。
- **账号贡献者**：其厂商账号额度进入共享池；需知晓并同意额度被共享（D1/C1）。
- **运营者/管理员**：用 `/docs` 完成全部管理动作；需知晓单 worker 约束与备份方式。
- **厂商（百度/腾讯）**：外部依赖；无需 sign-off，但受其配额/风控/文档变更影响。`[spec-review-amendment D26]`

## 外部成本

- 厂商调用：MVP 仅消耗免费额度；超量按百度/腾讯标准版按次计费（以官网为准）。缓存命中不产生厂商调用。
- 基础设施：复用现有主机与反代，无新增固定月费，无托管数据库。

## Impact

- 新增 `backend/`（`app/`、`tests/`、`alembic/`、`pyproject.toml`）、`.env.example`、`README.md`；`.gitignore` 已就绪。
- 对外新增 HTTP 契约：`/v1/ocr/image`、`/v1/providers`、`/v1/me`、`/healthz`、`/api/admin/*`。
- 依赖：`fastapi`、`uvicorn[standard]`、`httpx`、`orjson`、`pydantic-settings`、`sqlalchemy[asyncio]`、`aiosqlite`、`alembic`、`cryptography`、`itsdangerous`、`cachetools`、`Pillow`、`python-multipart`；dev：`pytest`、`pytest-asyncio`、`respx`、`ruff`、`mypy`。
- 数据：SQLite 文件与日志落在 `data/`（已 gitignore）；无既有系统迁移。
- 运维：单实例；TLS 由反代终结，应用只信任反代头。
