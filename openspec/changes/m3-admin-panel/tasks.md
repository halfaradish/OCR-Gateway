# Tasks

## 1. 后端鉴权、安全头与托管骨架

- [ ] 1.1 实现管理端双轨鉴权：登录设置会话/CSRF cookie，`require_admin` 接受 Bearer 或 cookie，cookie 写方法校验 `X-CSRF-Token`，`/me` 返回并补发 CSRF，`/logout` 清 cookie；验证新增 pytest 覆盖 cookie GET、缺/错 CSRF 403、正确 CSRF 成功、Bearer 豁免、登出后 401。
  - R-ID: R-ADM-01
- [ ] 1.2 实现安全响应头中间件（面板入口/静态资源 CSP；所有响应 `X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options`、`Permissions-Policy`；管理 API `Cache-Control: no-store`）；验证 `/healthz`、面板入口与 `/api/admin/login` 响应头断言通过，CSP `script-src` 不含 `'unsafe-inline'`，`/docs` 不被 CSP 阻断。
  - R-ID: R-PANEL-12
- [ ] 1.3 实现静态托管骨架：产物存在时托管 `/assets` 与非 API 路径回退 `index.html`，`index.html` no-store、assets immutable，API 未知路径保持 JSON 404，产物缺失时 `/` 返回明确 404；验证用临时 dist 目录的 pytest 覆盖四种情况。
  - R-ID: R-PANEL-11
- [ ] 1.4 更新 `conftest` 与既有管理端测试以同时支持 Bearer 与 cookie 客户端，保证原有用例全绿；验证 `uv run --project backend pytest backend/tests/test_ticket2_admin.py` 通过。
  - R-ID: R-ADM-01

## 2. 运行时设置

- [ ] 2.1 新增 `settings` 模型与 Alembic `0002`（upgrade 建表、downgrade 删表）；验证 `alembic upgrade head` → `downgrade -1` → `upgrade head` 往返成功，列名/类型/约束与 design 的 v_new 一致。
  - R-ID: R-ADM-08
- [ ] 2.2 实现 `RuntimeSettings` 加载与合并（env 默认 + DB 覆盖、非法存量回退并 warning），在启动时接入 `AppState`；验证单测覆盖默认值、DB 覆盖、非法值回退。
  - R-ID: R-ADM-08
- [ ] 2.3 实现 `ResultCache.reconfigure()`、`Scheduler` 按请求读取 `request_deadline_ms`、账号创建默认超时取运行时设置；验证单测覆盖缓存重建清空、预算变更生效、未显式超时的账号使用新默认值。
  - R-ID: R-ADM-08
- [ ] 2.4 实现 `GET/PUT /api/admin/settings`（部分更新、范围校验、未知键 400、单事务 upsert、提交后应用、`cache_cleared`）；验证 pytest 覆盖读取、部分更新、重启后保持、非法值 400、未知键 400、缓存参数变更后条目归零，并记录本机 PUT p95 < 500ms。
  - R-ID: R-ADM-08

## 3. 数据端点

- [ ] 3.1 实现 `GET /api/admin/overview`（今日指标、比率、厂商账号/可用数、账号配额、最近 10 条错误含账号名称、缓存状态）；验证 pytest 覆盖有数据、无请求时比率与平均延迟为 null、不可用账号不计入可用数、最近错误含名称且不含原文。
  - R-ID: R-ADM-09
- [ ] 3.2 实现 `GET /api/admin/usage/series` 并扩展 `usage/summary`（过滤参数、`avg_latency_ms`、`label`、key 升序、仅日期 `to` 含当日、`from > to` 400）；验证 pytest 覆盖 `Asia/Shanghai` 日分桶与补零、90 天限制 400、三种过滤、平均延迟计算、日期形式 `to` 包含当日、已删除实体 label 为 null。
  - R-ID: R-ADM-06
- [ ] 3.3 扩展 `GET /api/admin/logs`（`from/to/error_code`、`total`、`user_name`、`account_name`、`from > to` 400）；验证 pytest 覆盖组合过滤、分页 total、非法时间 400、空结果 `rows=[] total=0`、已删除实体名称为 null。
  - R-ID: R-ADM-06
- [ ] 3.4 扩展 `GET /api/admin/accounts` 的 `owner_name` 与 `quota_usage`（日/月/总量、限额、周期键）；验证 pytest 覆盖成功请求后三周期 +1、限额 null、跨日重置后日用量归零、贡献者删除后 owner_name 为 null。
  - R-ID: R-ADM-10
- [ ] 3.5 加入用量/日志查询基准测试（10 万条 `usage_events`，批量插入，标记 `slow` 默认跳过）并记录本机 p95；目标序列与日志查询 p95 < 300ms，结果写入 change 的验证记录。
  - R-ID: R-ADM-06

## 4. 前端骨架、设计系统与总览

- [ ] 4.1 初始化 `frontend/`：Vite + React 18 + TypeScript strict + ESLint（react-hooks/jsx-a11y）+ Tailwind v4 + shadcn/ui 基础、pnpm 锁文件、dev 代理、`lint`/`typecheck`/`build` 脚本；验证 `pnpm install --registry=https://registry.npmmirror.com`、`pnpm lint`、`pnpm typecheck`、`pnpm build` 全绿，且构建产物 `index.html` 不含内联脚本（所有 `<script>` 带 `src`）。
  - R-ID: R-PANEL-02
- [ ] 4.2 落地设计 token（色彩/字号/间距/圆角/动效）、自托管 IBM Plex Sans、基础组件（Button/Input/Dialog/Table/Switch/Sheet/StatusDot/QuotaRuler/MetricStrip/PageHeader/EmptyState/ErrorState/Skeleton）；验证组件在总览或组件预览中渲染，构建无类型错误。
  - R-ID: R-PANEL-10
- [ ] 4.3 实现 API 客户端、AuthProvider、登录页、受保护壳（侧栏/顶栏/移动抽屉）、404 与 401 跳转；验证浏览器冒烟覆盖登录、刷新保持、登出、未登录访问 `/accounts` 跳转，且 localStorage/sessionStorage 无 token。
  - R-ID: R-PANEL-01
- [ ] 4.4 实现总览页（指标条、厂商汇总、近 7 日折线、账号配额标尺、最近错误、空态）；验证有数据与无数据两种截图，控制台无 CSP/渲染错误，首屏 JS gzip 体积 ≤ 250KB。
  - R-ID: R-PANEL-03

## 5. 管理页面

- [ ] 5.1 实现账号页（列表字段、厂商过滤、贡献者下拉、新建/编辑按厂商渲染凭证、留空保留、测活、重置确认（含清零配额提示）、启停、删除确认、三项配额全空提示）；验证浏览器冒烟覆盖创建百度/腾讯账号、编辑留空后测活成功、测活失败展示错误码、未配置额度显示提示、重置确认文案、删除确认。
  - R-ID: R-PANEL-04
- [ ] 5.2 实现成员与 Key 页（成员创建/启停/删除级联提示、Key 创建/限额/RPM/启停/吊销、明文只显示一次）；验证冒烟覆盖创建成员、创建 Key 后列表无明文、删除有 Key 成员提示级联。
  - R-ID: R-PANEL-05
- [ ] 5.3 实现用量页（时间/成员/厂商/账号过滤进 URL、筛选下拉数据、指标切换、分组切换、折线图、汇总表、CSV 导出含 RFC 4180 转义与公式注入防护）；验证切换筛选/分组后 URL 与图表同步、刷新保持、CSV 行与汇总表一致、空范围空态。
  - R-ID: R-PANEL-06
- [ ] 5.4 实现日志页（时间/状态/厂商/错误码过滤进 URL、分页、详情、空态、UTC 时间按 Asia/Shanghai 展示）；验证冒烟覆盖筛选失败记录、翻页、详情不含原文、时间无 8 小时偏移、清除筛选。
  - R-ID: R-PANEL-07
- [ ] 5.5 实现设置页（可编辑/只读分区、字段校验、保存、缓存清空提示、清空缓存按钮、配额模板与免责声明）；验证合法保存后刷新保持、非法值字段错误、缓存参数保存提示清空、清空缓存显示条数。
  - R-ID: R-PANEL-08
- [ ] 5.6 统一三态、写操作 pending 防双提交、全局/路由错误边界与错误文案；验证慢请求与断网场景显示可恢复错误，快速双击只发一次请求。
  - R-ID: R-PANEL-09

## 6. 交付、镜像与验收

- [ ] 6.1 增加 Dockerfile 前端构建阶段（Node 22 + pnpm + `NPM_REGISTRY`）、复制 dist 到运行镜像、`.dockerignore` 排除 `frontend/node_modules` 与 `frontend/dist`；验证离线镜像构建成功且镜像内 `/app/static/index.html` 存在。
  - R-ID: R-DEP-07
- [ ] 6.2 更新 `docker-compose.yml` 构建参数、`.env.example`、README（面板入口、前端开发/构建、`NPM_REGISTRY`、HTTPS 与 cookie 说明、私有凭证代称约定）；验证按 README 命令可起面板，`NPM_REGISTRY` 说明位置正确。
  - R-ID: R-DEP-07
- [ ] 6.3 镜像冒烟：`docker compose build && up -d` 后验证 `/healthz`、`/` 返回 HTML、`/assets/*` 200、登录 cookie+CSRF、创建成员/Key/账号、总览/用量/日志有数据；记录截图与命令输出。
  - R-ID: R-DEP-09
- [ ] 6.4 全量质量门：`uv run --project backend pytest backend/tests`、`uv run --project backend ruff check backend`、`uv run --project backend mypy backend/app`、`pnpm lint`、`pnpm typecheck`、`pnpm build` 全绿。
  - R-ID: R-PANEL-09
- [ ] 6.5 视觉验收：七个路由截图对照 design 的 token/结构/黑名单（无渐变、无卡片投影、状态圆点、配额刻度标尺、文字对比度），记录通过项与偏差修正。
  - R-ID: R-PANEL-10
- [ ] 6.6 回滚演练：切回 `ocr-gateway:0.1.0` 后 `/healthz` 与 `/api/admin/login` 正常、`/` 返回未构建提示；再切回新镜像面板恢复。
  - R-ID: R-DEP-09

## 测试覆盖图

| Code path | 测试类型 | 覆盖点 |
| --- | --- | --- |
| `app/api/deps.py` | API | Bearer/cookie 双轨、CSRF 缺失/不符/正确、过期、登出 |
| `app/main.py`（静态/安全头） | API | `/assets`、SPA 回退、API 404 不吞、产物缺失、CSP/安全头 |
| `app/api/admin.py`（设置/总览/用量/日志/账号） | API | 设置校验与持久化、缓存清空、总览比率与账号名称、日序列补零/上限、日志过滤/总数/名称、账号归属与配额用量 |
| `app/core/cache.py` | 单元 | reconfigure 重建与清空、参数不变不重建 |
| `app/core/scheduler.py` | 单元 | 运行期 deadline 读取 |
| `app/core/quota.py` + registry | 单元 + API | 周期键、账号配额用量一致性 |
| `app/models.py` + `alembic/versions/0002_*` | 迁移 | upgrade/downgrade 往返、列约束 |
| `frontend/` 路由与页面 | 浏览器冒烟 + typecheck/build | 登录/刷新/登出、七路由、三态、筛选 URL、CSV、表单校验、Key 明文一次 |
| `frontend/` 设计系统 | 截图目检 | token、字体、无渐变/投影、刻度标尺、窄屏 |
| `Dockerfile` + compose | 构建/部署 | 干净检出构建、镜像内 dist、`NPM_REGISTRY`、回滚 |

## Workflow follow-up

- 代码审与 verify 通过后归档本 change，并核对 `openspec/specs/` 的 admin-panel/admin-api/deployment 变更。
- 归档后把本机实际测试命令与截图路径补进 verify 记录。
