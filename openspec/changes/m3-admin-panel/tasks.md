# Tasks

> 本表已按 `spec-review-report.md` 的 amendment 更新；与评审起点 `33a0d61` 的差异见报告 Amendments 节。`[spec-review-amendment]`

## 1. 后端鉴权、安全头与托管骨架

- [ ] 1.1 实现管理端双轨鉴权：登录设置会话/CSRF cookie，`require_admin` 接受 Bearer 或 cookie，cookie 写方法校验 `X-CSRF-Token`，`/me` 返回并补发 CSRF，`/logout` 清 cookie；用 `HTTPBearer(auto_error=False)` 声明 security scheme；验证新增 pytest 覆盖 cookie GET、缺/错 CSRF 403、正确 CSRF 成功、Bearer 豁免、Bearer 无效不回退 cookie、登出后 401、cookie 属性（HttpOnly/Secure/CSRF 可读）、`/me` 补发 CSRF、`/docs` OpenAPI 有 Bearer scheme。
  - R-ID: R-ADM-01
- [ ] 1.2 实现安全响应头中间件（面板入口/静态资源/深链接 index CSP；所有响应 `X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options`、`Permissions-Policy`；管理 API `Cache-Control: no-store`）；中间件必须在 `BodyLimitMiddleware` 之后 add（最外层）；验证 `/healthz`、面板入口、`/accounts` 深链接、`/api/admin/login`、超大 body 的 400 响应头断言通过，CSP `script-src` 不含 `'unsafe-inline'`，`/docs` 不被 CSP 阻断。
  - R-ID: R-PANEL-12
- [ ] 1.3 实现静态托管骨架：产物存在时托管 `/assets` 与非 API 无扩展名路径回退 `index.html`，带扩展名的缺失文件返回 JSON 404；`index.html` no-store、assets immutable，API 未知路径保持 JSON 404，产物缺失时 `/` 返回明确 404（`FRONTEND_NOT_BUILT`）；验证用临时 dist 目录的 pytest 覆盖六种情况（含缺失 JS 不回退 HTML、路径穿越）。
  - R-ID: R-PANEL-11
- [ ] 1.4 更新 `conftest` 与既有管理端测试以同时支持 Bearer 与 cookie 客户端，保证原有用例全绿；验证 `uv run --project backend pytest backend/tests/test_ticket2_admin.py` 通过。
  - R-ID: R-ADM-01

## 2. 运行时设置

- [ ] 2.1 新增 `settings` 模型与 Alembic `0002`（upgrade 建表、downgrade 删表，`key TEXT PK`）；验证 `alembic upgrade head` → `downgrade -1` → `upgrade head` 往返成功，列名/类型/约束与 design 的 v_new 一致。
  - R-ID: R-ADM-08
- [ ] 2.2 实现 `RuntimeSettings` 加载与合并（env 默认 + DB 覆盖、非法存量回退并 warning），在启动时接入 `AppState`；验证单测覆盖默认值、DB 覆盖、非法值回退。
  - R-ID: R-ADM-08
- [ ] 2.3 实现 `ResultCache.reconfigure(enabled, max_entries, ttl_seconds)`、`Scheduler` 接收 public 计算好的绝对 deadline、`public.py` 外层从 `RuntimeSettings` 读取预算、账号创建默认超时取运行时设置；验证单测覆盖缓存重建清空、预算调大/调小都改变总耗时、未显式超时的账号使用新默认值。
  - R-ID: R-ADM-08
- [ ] 2.4 实现 `GET/PUT /api/admin/settings`（部分更新、范围校验、未知键 400、显式 null 400、字段级 `error.fields`、单事务 upsert、提交后应用、`cache_cleared`）；验证 pytest 覆盖读取、部分更新、重启后保持、非法值 400（含字段名）、未知键 400、显式 null 400、DB 写失败 500（注入）、缓存参数变更后条目归零、并发 PUT 后 DB/runtime/重启值一致，并记录本机 PUT p95 < 500ms。
  - R-ID: R-ADM-08

## 3. 数据端点

- [ ] 3.1 实现 `GET /api/admin/overview`（今日指标、比率、auto_failures、厂商账号/可用数、账号配额、近 7 日序列、最近 10 条错误含账号名称、缓存状态）；验证 pytest 覆盖有数据、无请求时比率与平均延迟为 null、不可用账号不计入可用数、available 的瞬时口径不触发状态迁移、最近错误含名称且不含原文、auto 失败单独计数。
  - R-ID: R-ADM-09
- [ ] 3.2 实现 `GET /api/admin/usage/series` 并扩展 `usage/summary`（过滤参数、`avg_latency_ms`、`label`、key 升序且 null 最后、仅日期 `to` 含当日、`from > to` 400、summary 也受 90 天上限、默认 7 个日桶、`auto` label）；验证 pytest 覆盖 `Asia/Shanghai` 日分桶与补零、90 天限制 400、三种过滤、平均延迟四舍五入、日期形式 `to` 包含当日且次日 00:00 不计入、已删除实体合并 null 行、auto 失败 label、live+deleted 混合排序。
  - R-ID: R-ADM-06
- [ ] 3.3 扩展 `GET /api/admin/logs`（`from/to/error_code`、`total`、`user_name`、`account_name`、`from > to` 400、90 天上限、`provider=auto`）；验证 pytest 覆盖组合过滤、分页 total、非法时间 400、空结果 `rows=[] total=0`、已删除实体名称为 null、日期形式 `to` 的半开边界。
  - R-ID: R-ADM-06
- [ ] 3.4 扩展 `GET /api/admin/accounts` 的 `owner_name` 与 `quota_usage`（日/月/总量、限额、周期键）；验证 pytest 覆盖成功请求后三周期 +1、限额 null、跨日重置后日用量归零、贡献者删除后 owner_name 为 null、删除账号后配额清理（两个 flush 周期无 FK 错误）。
  - R-ID: R-ADM-10
- [ ] 3.5 加入用量/日志/汇总查询基准测试（10 万条 `usage_events`，批量插入，注册 `slow` marker 并默认 `-m "not slow"`；6.4 显式跑 `-m slow`），输出 p50/p95；目标序列、汇总与日志查询 p95 < 300ms，结果写入 change 的验证记录。
  - R-ID: R-ADM-06

## 4. 前端骨架、设计系统与总览

- [ ] 4.1 初始化 `frontend/`：Vite + React 18 + TypeScript strict + ESLint（react-hooks/jsx-a11y）+ Tailwind v4 + shadcn/ui 基础、pnpm 锁文件、dev 代理、`lint`/`typecheck`/`build` 脚本；验证 `pnpm install --registry=https://registry.npmmirror.com`、`pnpm lint`、`pnpm typecheck`、`pnpm build` 全绿，且构建产物 `index.html` 不含内联脚本（所有 `<script>` 带 `src`）。
  - R-ID: R-PANEL-02
  - R-ID: R-PANEL-02
- [ ] 4.2 落地设计 token（色彩/字号/间距/圆角/动效）、自托管 IBM Plex Sans、基础组件（Button/Input/Dialog/Table/Switch/Sheet/StatusDot/QuotaRuler/MetricStrip/PageHeader/EmptyState/ErrorState/Skeleton）；验证组件在总览或组件预览中渲染，构建无类型错误。
  - R-ID: R-PANEL-10
- [ ] 4.3 实现 API 客户端、AuthProvider、登录页、受保护壳（侧栏/顶栏/移动抽屉）、404 与 401 跳转；API 客户端设 15s 默认超时（测活按账号超时 +5s 覆盖）、204 不解析、login 跳过全局 401 跳转、403 时 `/me` 刷新后单次重试；每路由同尺寸 Suspense fallback，ErrorBoundary 包在 lazy 外层；验证浏览器冒烟覆盖登录、刷新保持、登出、未登录访问 `/accounts` 跳转、密码错误就地显示、其他标签页旧 CSRF 403 恢复，且 localStorage/sessionStorage 无 token。
  - R-ID: R-PANEL-01
- [ ] 4.4 实现总览页（指标条、厂商汇总、近 7 日折线、账号配额标尺、最近错误、空态）；验证有数据与无数据两种截图，控制台无 CSP/渲染错误，记录登录+shell 与总览路由 chunk 的实际 gzip 体积（登录+shell ≤150KB、总览含 Recharts ≤350KB），并记录一次 Lighthouse 移动端 LCP/INP/CLS。
  - R-ID: R-PANEL-03

## 5. 管理页面

- [ ] 5.1 实现账号页（列表字段、厂商过滤、贡献者下拉、新建/编辑按厂商渲染凭证、留空保留、测活、重置确认（含清零配额提示）、启停、删除确认、三项配额全空提示）；编辑时超时留空省略字段（不发 null）；删除账号时同步清理内存配额。验证浏览器冒烟覆盖创建百度/腾讯账号、编辑留空后测活成功、清空超时不报 500、测活失败展示错误码、未配置额度显示提示、重置确认文案、删除确认及删除后配额无 FK 错误。
  - R-ID: R-PANEL-04
- [ ] 5.2 实现成员与 Key 页（成员创建/启停/删除级联提示、Key 创建/限额/RPM/启停/吊销、明文只显示一次）；验证冒烟覆盖创建成员、创建 Key 后列表无明文、删除有 Key 成员提示级联。
  - R-ID: R-PANEL-05
- [ ] 5.3 实现用量页（时间/成员/厂商/账号过滤进 URL、筛选下拉数据、指标切换、分组切换、折线图、汇总表、CSV 导出含 RFC 4180 转义与公式注入防护）；筛选变化用 `placeholderData: keepPreviousData` 保留上一结果；验证切换筛选/分组后 URL 与图表同步、刷新保持、CSV 行与汇总表一致、空范围空态、非法时间保留上一结果。
  - R-ID: R-PANEL-06
- [ ] 5.4 实现日志页（时间/状态/厂商/错误码过滤进 URL、分页、详情、空态、UTC 时间按 Asia/Shanghai 展示）；验证冒烟覆盖筛选失败记录、翻页、详情不含原文、时间无 8 小时偏移、清除筛选。
  - R-ID: R-PANEL-07
- [ ] 5.5 实现设置页（可编辑/只读分区、字段校验、保存、缓存清空提示、清空缓存按钮、配额模板与免责声明）；验证合法保存后刷新保持、非法值字段错误、缓存参数保存提示清空、清空缓存显示条数。
  - R-ID: R-PANEL-08
- [ ] 5.6 统一三态、写操作 pending 防双提交（`isPending` + mutation `scope`/guard，不用 mutationKey 串行）、GET 仅对网络/5xx 重试一次、全局/路由错误边界与错误文案、脏表单离开确认；验证慢请求与断网场景显示可恢复错误，快速双击只发一次请求，401/403/400 不重试。
  - R-ID: R-PANEL-09

## 6. 交付、镜像与验收

- [ ] 6.1 增加 Dockerfile 前端构建阶段（Node 22 + pnpm + `NPM_REGISTRY`）、复制 dist 到运行镜像、`.dockerignore` 排除 `frontend/node_modules` 与 `frontend/dist`；镜像版本升 `0.2.0`，保持 `0.1.0` tag 不被覆盖；扫描 dist 不含 `MASTER_KEY`/`ADMIN_PASSWORD`/凭证/Key 明文；验证离线镜像构建成功且镜像内 `/app/static/index.html` 存在。
  - R-ID: R-DEP-07
- [ ] 6.2 更新 `docker-compose.yml` 构建参数与版本 tag、`.env.example`（`NPM_REGISTRY`、`FRONTEND_DIST`）、README（面板入口、前端开发/构建、`NPM_REGISTRY`、`DEFAULT_TIMEOUT_MS` 语义变化、`TRUST_PROXY_HEADERS` 新用途、HTTPS/cookie、nginx 的 `X-Forwarded-Proto`、升级/回滚、私有凭证代称约定）；验证按 README 命令可起面板，`NPM_REGISTRY` 说明位置正确。
  - R-ID: R-DEP-07
- [ ] 6.3 镜像冒烟：`docker compose build && up -d` 后验证 `/healthz`、`/` 返回 HTML、`/assets/*` 200、登录 cookie+CSRF（反代 HTTPS 下 cookie 带 Secure）、创建成员/Key/账号、总览/用量/日志有数据；无真实凭证时用预置 `usage_events` 种子数据或 mock provider；记录截图与命令输出。
  - R-ID: R-DEP-09
- [ ] 6.4 全量质量门：`uv run --project backend pytest backend/tests`、`uv run --project backend pytest -m slow`（基准）、`uv run --project backend ruff check backend`、`uv run --project backend mypy backend/app`、`pnpm lint`、`pnpm typecheck`、`pnpm build` 全绿。
  - R-ID: R-PANEL-09
- [ ] 6.5 视觉验收：七个路由截图对照 design 的 token/结构/黑名单（无渐变、无卡片投影、状态圆点、配额刻度标尺、文字对比度），记录通过项与偏差修正。
  - R-ID: R-PANEL-10
- [ ] 6.6 回滚演练：`git checkout` 上一提交（compose 指向 `ocr-gateway:0.1.0`，确认该 tag 未被本次 build 覆盖）+ `scripts/rollback.sh <部署前备份>` 恢复 DB 到 0001 → 旧镜像 `/healthz` 200、`/api/admin/login` 正常、`/` 返回旧镜像的 404；再切回 `0.2.0` 并迁移，面板恢复。
  - R-ID: R-DEP-09

## 测试覆盖图

| Code path | 测试类型 | 覆盖点 |
| --- | --- | --- |
| `app/api/deps.py` | API | Bearer/cookie 双轨、Bearer 无效不回退、CSRF 缺失/不符/正确、cookie 属性、`/me` 补发、过期、登出、OpenAPI Bearer scheme |
| `app/main.py`（静态/安全头） | API | `/assets`、SPA 回退、缺失 JS 404、API 404 不吞、产物缺失、CSP/安全头/深链接/超限 body |
| `app/api/admin.py`（设置/总览/用量/日志/账号） | API | 设置字段级 400/null/DB 失败/并发、缓存清空、总览序列/比率/auto、日序列补零/上限/null 排序、日志过滤/总数/名称、账号归属/配额/删除清理 |
| `app/api/public.py` | API | 运行时总预算调大/调小、信号量等待受同一 deadline 约束 |
| `app/core/cache.py` | 单元 | reconfigure 重建与清空、参数不变不重建、参数顺序 |
| `app/core/scheduler.py` | 单元 | 传入绝对 deadline、预算调大/调小生效 |
| `app/core/quota.py` + registry | 单元 + API | 周期键、账号配额用量一致性、删除账号清理 |
| `app/models.py` + `alembic/versions/0002_*` | 迁移 | upgrade/downgrade 往返、列约束、`key TEXT` |
| `frontend/` 路由与页面 | 浏览器冒烟 + typecheck/build | 登录/刷新/登出、七路由、三态、`/me` 并行、筛选 URL、CSV、表单校验、Key 明文一次、CSRF 403 恢复 |
| `frontend/` 设计系统 | 截图目检 | token、字体、无渐变/投影、刻度标尺、窄屏 360px |
| `Dockerfile` + compose | 构建/部署 | 干净检出构建、镜像内 dist、`NPM_REGISTRY`、0.2.0/0.1.0 tag、回滚演练、产物扫密 |

## Workflow follow-up

- 代码审与 verify 通过后归档本 change，并核对 `openspec/specs/` 的 admin-panel/admin-api/deployment 变更。
- 归档后把本机实际测试命令与截图路径补进 verify 记录。
