# Proposal

## Why

`docs/tech-selection.md` 的 M3 要求「管理员可完整管理」，但 M0 的「面板壳」实际从未落地：仓内没有 `frontend/`、没有静态托管，管理员只能靠 `/docs` 与 curl 完成全部运营动作。本 change 补齐可登录的管理面板，并把 MVP 阶段刻意延后的 cookie + CSRF 管理端会话恢复回来，让浏览器操作与 API 安全边界同时成立。

## What Changes

- 新增 `frontend/`：管理 SPA，包含登录、总览、账号、成员与 Key、用量、日志、设置七个路由；技术栈沿用 `docs/tech-selection.md` 的已定稿选型。
- 管理端鉴权恢复双轨：`POST /api/admin/login` 在返回 Bearer token 的同时设置 HttpOnly 签名会话 cookie 与 JS 可读的 CSRF cookie；`require_admin` 同时接受 Bearer 与 cookie，cookie 路径的写操作强制校验 `X-CSRF-Token`；新增 `POST /api/admin/logout`。
- 新增运行时设置：`settings` 键值表 + `GET/PUT /api/admin/settings`；可编辑缓存开关/TTL/容量、请求总预算、账号默认超时，保存后即时生效（缓存参数变更会清空缓存）。
- 补齐面板数据面：新增 `GET /api/admin/overview` 与 `GET /api/admin/usage/series`；扩展 `GET /api/admin/usage/summary`（平均延迟与筛选）、`GET /api/admin/logs`（时间过滤与总数）、`GET /api/admin/accounts`（当前周期已用配额）。
- 同源静态托管：FastAPI 在存在构建产物时挂载 `/assets` 并对非 API 的 GET 路径回退 `index.html`；增加 CSP、`X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options` 安全头。
- 镜像与部署：`Dockerfile` 增加 Node 构建阶段，`NPM_REGISTRY` 构建参数与 `UV_DEFAULT_INDEX` 同模式；`docker-compose.yml` 传递该参数；README 与 `.env.example` 更新面板入口、前端开发与构建说明。
- 仓库卫生：`.zcode/` 加入 `.gitignore`（人 2026-11-04 拍板）。

无破坏性变更：Bearer 管理鉴权继续可用，`/docs` 与 curl 工作流不受影响；新增的响应字段与端点均为增量。

## Success Metrics

- 面板核心流程 — 基准：0 个可浏览器访问的管理页面 → 目标：登录后可在面板完成「建成员 → 建 Key → 建账号 → 总览/用量/日志查看 → 改设置」全流程 — 度量方式：构建产物 + 浏览器冒烟截图，7 个路由均成功渲染且无控制台错误。
- 管理端鉴权安全 — 基准：仅 Bearer，无 CSRF 面 → 目标：cookie-only 写请求缺/错 CSRF 100% 返回 403，Bearer 路径回归 100% 通过，登录/登出/过期跳转全部通过 — 度量方式：`pytest` 新增鉴权用例。
- 前端质量门 — 基准：无前端工程 → 目标：`pnpm lint`、`pnpm typecheck` 与 `pnpm build` 全绿，产物被镜像收录 — 度量方式：本地命令 + `docker compose build` 后 `GET /` 返回面板 HTML、`/assets/*` 返回 200。

## 需求优先级

- **P0（必须有）**：登录/会话/CSRF 双轨、登出；同源静态托管与安全头；账号、成员与 Key 的核心 CRUD；设置读写与即时生效；前端构建进入镜像。
- **P1（应当有）**：总览指标；用量时间序列与图表；日志时间过滤/分页/总数；账号周期配额显示；用量 CSV 导出。
- **P2（锦上添花）**：配额刻度标尺与动效细节；窄屏体验优化；查询基准脚本。

## Non-Goals

- **不做匿名接入与「API 鉴权开关」**：本 change 的设置页只展示鉴权强制开启。可证伪假设：所有调用方都必须持有网关 Key；若未来要做公开匿名试用，需另开 change 设计按 IP 限流与滥用防护。
- **不做本地 OCR 开关与模型下载**：本地 OCR worker 属 M4。可证伪假设：M4 之前没有可查询的 worker/模型状态；现在放开关只能是假开关。
- **不做成员登录或成员自助面板**：沿用 `docs/tech-selection.md:134` 的 v1 边界，成员只用 `/v1/me` 自查。可证伪假设：成员不需要浏览器会话；若需要，必须先设计只读角色与权限边界。
- **不做阿里云/华为适配器或对应账号表单**：适配器仍只有百度、腾讯（MVP D1）。可证伪假设：M3 不新增厂商；若适配器先于面板交付，再补表单字段。
- **不做深色主题、实时推送、PDF OCR、表格版面识别**：可证伪假设：手动刷新与浅色单主题满足当前运营场景；若需要秒级监控，另开 SSE/WebSocket change。
- **不在日志里展示 OCR 原文**：可证伪假设：排障只需要 request_id、错误码、耗时与账号归属；`debug_store_text` 属后续可选能力。
- **不引入 Playwright 端到端套件**：可证伪假设：M3 以类型检查、构建、后端 API 测试与浏览器冒烟覆盖关键路径；稳定后再补自动化。

## 假设

- **同源部署**：面板与 API 由同一 FastAPI 提供（单端口或同域反代）。若不成立，`SameSite=Lax` cookie 与 CSRF 双提交需改为跨域方案，登录流程需重做。
- **现代常青浏览器**：管理员使用支持 ES2020+、CSS 变量、`fetch`、`Intl` 的浏览器。若不成立，面板无法运行，需要降级构建或明确支持矩阵。
- **单实例/单 worker**：设置热更新只作用于当前进程。若未来多实例，设置需改为共享存储 + 轮询/失效广播，配额内存计数也需重做。
- **数据规模**：账号/Key/成员 <1000，`usage_events` <10^5。若超出，列表需分页、用量需预聚合，当前查询设计会退化。
- **管理员人数少**：<20 名管理员，无角色/审计需求。若需要多人协作，需补只读角色与操作审计。
- **构建期可达 npm 镜像**：默认源不可达时通过 `NPM_REGISTRY` 指定。若两者都不可达，前端无法构建（R-DEP-07 的失败路径）。
- **React 18 兼容性**：锁定的前端依赖 peer 范围覆盖 React 18。若某依赖升级后放弃 React 18，需回退该依赖或先升级 React 并更新技术选型。
- **无第三方前端脚本**：不接统计/客服/广告；字体自托管。若未来接入，CSP 与隐私声明需同步调整。
- **公网走 HTTPS**：反代负责 TLS；HTTP 下 cookie 不带 `Secure`。若公网裸 HTTP，会话与密码传输不安全，部署不合规。
- **OCR 原文不落库**：日志页只展示元数据。若未来开启 `debug_store_text`，日志接口与页面必须先做脱敏/权限设计。

## 利益相关方与外部依赖

- **管理员**：唯一使用者与验收人（决策权）。
- **团队成员**：继续通过既有网关 Key 调用公共 API，不受面板影响（知情）。
- **运维**：镜像构建新增 Node 阶段，构建时间与 npm 源可达性需知情（知情，需配合 `.env` 的 `NPM_REGISTRY`）。
- **外部依赖**：构建期 npm registry 与 Docker registry；运行期无新增第三方服务，字体自托管。

## 开放问题与外部成本

- **开放问题**：无。影响 specs/方案/切片划分的未知项已在相位 B 解决；实现中若浏览器冒烟发现 CSP 或样式冲突，按 design 的 Risks 表在实现内调整。
- **外部计费服务**：无新增。OCR 厂商调用沿用既有链路；前端字体自托管，不引入 CDN/统计。

## Compliance

- 遵守 `docs/tech-selection.md` §11（会话/CSRF/面板安全头/日志不含原文）、§12（页面清单与交互）、§15（前端先保证类型检查与构建）。
- 遵守 `openspec/specs/admin-api/spec.md` 的既有契约；本次以 MODIFIED delta 更新 R-ADM-01 与 R-ADM-06，并新增设置/总览/账号配额需求。
- 遵守 `openspec/specs/deployment/spec.md` R-DEP-07：构建索引可参数化；npm 与 PyPI 使用同一模式，构建不依赖默认源可达。
- 遵守单实例/单 worker 约束（`docs/tech-selection.md` 风险表），设置热更新只在当前进程生效。
- 遵守 `AGENTS.md`：任何被跟踪文件提及本机私有凭证文档时，只用「仓库外的本地私有凭证文档」代称。
- 不把真实凭证、Key 明文或 OCR 原文写入仓库、日志、前端存储或镜像。

## Capabilities

### New Capabilities

- `admin-panel`: 管理面板的浏览器行为与交付边界——登录/会话、七个路由、设计系统、同源静态托管、前端构建与镜像收录。

### Modified Capabilities

- `admin-api`: 管理端鉴权改为 cookie + CSRF 双轨并保留 Bearer；新增设置读写、总览、用量序列；扩展日志与账号响应的查询能力。
- `deployment`: 镜像新增前端构建阶段与 `NPM_REGISTRY` 构建参数；运行镜像包含并托管面板静态资源。

## Impact

- **后端**：`backend/app/main.py`（静态托管、安全头）、`backend/app/api/deps.py`（双轨鉴权/CSRF）、`backend/app/api/admin.py`（登录/登出/设置/总览/序列/日志/账号配额）、`backend/app/models.py` + `backend/app/alembic/versions/0002_*`（settings 表）、`backend/app/config.py`（构建期/运行期配置）、`backend/tests/`（鉴权、设置、序列、静态托管用例）。
- **前端**：新增 `frontend/`（Vite 工程、路由、页面、组件、设计 token、API 客户端、类型检查与构建脚本）。
- **构建与部署**：`Dockerfile`、`docker-compose.yml`、`.env.example`、`README.md`。
- **API**：`POST /api/admin/logout`、`GET/PUT /api/admin/settings`、`GET /api/admin/overview`、`GET /api/admin/usage/series` 为新增；`GET /api/admin/usage/summary`、`GET /api/admin/logs`、`GET /api/admin/accounts`、`POST /api/admin/login` 为增量字段/参数。
- **依赖**：前端新增 React/Vite/Tailwind/shadcn/React Query/Recharts 等 npm 依赖；后端无新增 Python 运行时依赖。
