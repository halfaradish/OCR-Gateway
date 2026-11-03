---
schema_version: 1
change: m3-admin-panel
branch: feat/m3-admin-panel
generated_at: 2026-11-04T00:38:42+08:00
decision_hash: eefc16faa4b9
---

# 决策纪要 · m3-admin-panel

## 目标态

给 OCR Gateway 补上可登录的管理面板（总览 / 账号 / 成员与 Key / 用量 / 日志 / 设置），管理鉴权恢复 cookie + CSRF 双轨（保留 Bearer），前端由 FastAPI 同源托管并进入镜像构建。

## 拍板决策

- **D1 页面范围：登录 + 框架 + 总览 + 六个管理面板** — 依据：人 2026-11-04 明确选择「再加独立总览页」；M0 的「面板壳」从未落地，登录与导航框架必须在本 change 补；**砍掉的候选**：六面板 + 用量页摘要卡（范围更小，但人要求完整总览）、只做六面板（首屏无全局信息）。
- **D2 管理端鉴权：cookie + CSRF 双轨，保留 Bearer** — 依据：`docs/tech-selection.md:349`、`:482-483` 要求 HttpOnly 签名 cookie + CSRF 双提交；MVP 的 D4（`openspec/changes/archive/2026-11-03-ocr-gateway-mvp/decision-memo.md:20`）写明「面板回归时恢复 cookie+CSRF 双轨」；人 2026-11-04 拍板；**砍掉的候选**：Bearer + localStorage / sessionStorage（XSS 可窃取 12h token，偏离安全设计）。
- **D3 设置面板：运行时设置表，不含匿名模式** — 依据：人 2026-11-04 拍板；可编辑并即时生效：缓存开关 / TTL / 容量、请求总预算、账号默认超时；只读展示：鉴权状态、版本、上传限制、配额模板；本地 OCR 设置属 M4；**砍掉的候选**：API 鉴权开关 + 匿名模式 + 按 IP 限流（安全面扩张，MVP D10 已明确砍掉）、仅只读设置（设置页价值不足）。
- **D4 视觉：浅色单主题，深墨蓝主调** — 依据：人 2026-11-04 拍板「极简、高级感、现代、蓝色主调」；只维护一套 token；**砍掉的候选**：浅/深双主题（多一套 token 与回归面）、深色为主（长表格与日志阅读差）。
- **D5 `.zcode/` 加入 `.gitignore`** — 依据：人 2026-11-04 拍板；checkpoint 脚本用 `git add -A`，不忽略会把本地计划文件带进提交；**砍掉的候选**：手动路径限定提交（偏离 skill 默认流程）、先提交、删除本地文件。
- **D6 成员与 Key 合并为单页** — 依据：`docs/tech-selection.md:499` 的页面定义是「成员与 Key」；成员是配额归属实体、Key 挂在成员下，同一操作上下文；**砍掉的候选**：拆成两个顶级导航项（成员只有名字/启停，单页会空）。
- **D7 前端栈按技术选型：React 18 + TypeScript + Vite + Tailwind v4 + shadcn/ui + React Query + Recharts** — 依据：`docs/tech-selection.md:15`、`:111`；本机 npm 官方源不可达、`registry.npmmirror.com` 可达（`npm view react --registry=...` 成功）；Radix / React Router / React Query / Recharts 的 peer 范围均覆盖 React 18（npm view 输出）；**砍掉的候选**：React 19（偏离已定稿选型，无收益）、手写组件库（重复造轮子）。
- **D8 同源静态托管 + 镜像多阶段构建** — 依据：`docker-compose.yml` 单端口 8000；cookie `SameSite=Lax` 与 CSRF 双提交依赖同源；`Dockerfile` 目前无 Node 阶段，面板不进入镜像则部署后不可用；**砍掉的候选**：独立前端容器/域名（多一套反代与 CORS，违背「面板和 API 同域」的技术选型）、只在 dev 可用（交付不完整）。
- **D9 用量与总览的数据面补齐** — 依据：现有 `/usage/summary` 无时间序列、`/logs` 无时间过滤与总数、`/accounts` 无已用配额（`backend/app/api/admin.py:93-117`、`:495-575`）；总览与图表需要这些数据；**方案**：新增 `GET /api/admin/usage/series`、`GET /api/admin/overview`，扩展 `/logs`（from/to + total）与 `/accounts`（quota_usage），不引入新存储；**砍掉的候选**：前端多次拉全量日志自行聚合（分页语义错误、性能差）。
- **D10 缓存设置变更时清空缓存** — 依据：`TTLCache` 的 ttl/maxsize 在构造时固定（`backend/app/core/cache.py:13-17`），热改 TTL 无法只作用于新条目；重建缓存并清空是最可预测的语义；**砍掉的候选**：仅对新条目生效（实现复杂、行为不可解释）、要求重启（设置页价值打折）。
- **D11 用量页 CSV 导出在前端完成** — 依据：`docs/tech-selection.md:500` 要求 CSV 导出；导出内容就是当前筛选后的序列/汇总表，无需新增后端接口；**砍掉的候选**：后端 `?format=csv`（多一套响应协商与测试，收益低）。

## 承重约束

- **C1 管理面鉴权收敛在单一依赖** — 验证方式：`grep -n "require_admin" backend/app/api/admin.py` 与 `grep -c "@router" ...`；证据锚：20 个路由中 19 个非登录路由全部经 `require_admin`，登录是唯一豁免（`backend/app/api/admin.py:143`），改造点集中在 `backend/app/api/deps.py:51`。
- **C2 面板与 API 必须同源** — 验证方式：读 `docker-compose.yml` 端口映射与 `backend/app/main.py:195-200`；证据锚：compose 仅暴露单个 `8000` 端口、FastAPI 同时挂公共/管理路由，无独立前端域名；同源是 `SameSite=Lax` cookie 与 CSRF 双提交成立的前提。
- **C3 当前没有面板、没有静态托管、镜像没有前端阶段** — 验证方式：`ls frontend`（不存在）、`grep -rn "StaticFiles|HTMLResponse|FileResponse" backend/app`（无结果）、通读 `Dockerfile`；证据锚：`.gitignore:18-20` 已预留 `node_modules/` 与 `frontend/dist/`，说明目录结构是计划内、只是未落地。
- **C4 运行时设置没有存储，参数在启动时固化** — 验证方式：`backend/app/models.py` 无 settings 模型、`backend/alembic/versions/` 只有 `0001_initial.py`；证据锚：`backend/app/config.py:58-82` 全为环境变量，`backend/app/main.py:84-95` 构造 `ResultCache` / `Scheduler`，`backend/app/core/scheduler.py:56-73` 在构造时固化 deadline，`backend/app/core/cache.py:13-17` 在构造时固化 TTL/容量。
- **C5 设置项的真实消费点** — 验证方式：逐项 grep；证据锚：`default_timeout_ms` 仅在 `backend/app/config.py:70`，而账号创建默认值硬编码在 `backend/app/schemas.py:41`；`request_deadline_ms` 在 `config.py:71` 与 `scheduler.py:56-73`；`cache_*` 在 `config.py:72-74` 与 `main.py:84-88`；`session_ttl_seconds` 在 `config.py:80` 与 `deps.py:56`。
- **C6 用量/日志/账号接口的数据缺口** — 验证方式：读 `backend/app/api/admin.py` 相关端点；证据锚：`_account_out` 无已用配额（`:93-117`），`usage_summary` 只返回整段聚合行（`:495-535`），`list_logs` 无时间过滤、无 total（`:536-575`）；`QuotaManager.used()` 已能按日/月/总量取值（`backend/app/core/quota.py:61-63`）。
- **C7 npm 与 Docker 构建链路的可达性** — 验证方式：`npm view react version`（官方源超时）、`npm view react version --registry=https://registry.npmmirror.com`（19.3.1 成功）、`docker pull node:22-bookworm-slim`（成功，digest `sha256:4b150b48...`）；证据锚：本机 Docker 配置了 8 个 registry mirror；构建必须像 `UV_DEFAULT_INDEX` 一样把 npm 镜像参数化（`openspec/specs/deployment/spec.md:99-112` R-DEP-07）。
- **C8 前端依赖覆盖 React 18** — 验证方式：`npm view <pkg> peerDependencies --registry=...`；证据锚：`@radix-ui/react-dialog` `^16.8 || ^17 || ^18 || ^19`，`react-router-dom@7.18.5` `react >=18`，`lucide-react` `^16.5.1 || ... || ^18 || ^19`，`sonner` `^18 || ^19`，`recharts@3.10.1` `^16.8 || ^17 || ^18 || ^19`；React 18 在支持范围内。
- **C9 现状无安全响应头** — 验证方式：`grep -rn "Content-Security-Policy|X-Content-Type-Options|Referrer-Policy" backend/app`（无结果）；证据锚：`backend/app/main.py:119` 只写 `X-Request-ID`；`docs/tech-selection.md:489` 要求面板 CSP/`X-Content-Type-Options`/`Referrer-Policy`，本 change 必须补。
- **C10 面板不得拿到明文凭证或 Key** — 验证方式：读现有响应契约；证据锚：`_masked_credentials` 只返回掩码（`backend/app/api/admin.py:85-90`），Key 列表只返回 `key_prefix`、明文仅在创建响应出现一次（`backend/app/api/admin.py:236-260`）；前端不得缓存或回显这些值到列表。
- **C11 日志默认不含 OCR 原文** — 验证方式：读 `UsageEvent` 模型；证据锚：`backend/app/models.py:110-142` 无 text 字段，日志页只能展示元数据；`docs/tech-selection.md:196` 的 `debug_store_text` 属可选排障，不在 M3 范围。
- **C12 DB 迁移面很小但必须走 Alembic** — 验证方式：`ls backend/alembic/versions/`（只有 0001）；证据锚：新增 `settings` 键值表（`key` TEXT PK、`value` TEXT、`updated_at` DATETIME）需要 `0002_*` revision；D-2 要求 design 写 v_old/v_new 列清单。
- **C13 时区与分日口径必须沿用 Asia/Shanghai** — 验证方式：读现有实现；证据锚：`backend/app/core/quota.py:19-26` 与 `backend/app/api/admin.py:483-493` 统一用 `SHANGHAI` 做日/月键与时间过滤；用量序列按本地日分桶，不能用 UTC 直接 `date()`。
- **C14 质量门与部署链路必须保持** — 验证方式：`grep -rn "def test_" backend/tests | wc -l`（137 个测试）、通读 README 的构建/部署步骤；证据锚：`README.md:28-50` 的 Compose 路径、`scripts/deploy.sh:60-61` 的 `docker compose build`；新增 Node 阶段后镜像构建仍须一键通过。
- **C15 鉴权口径的权威源全集** — 验证方式：全仓 grep `Bearer`/`cookie`/`CSRF`；证据锚：`docs/tech-selection.md:349`、`:476-492`（目标态：cookie+CSRF）、`openspec/specs/admin-api/spec.md:8-21`（现契约：Bearer，本次 MODIFIED）、`README.md:43`（现文档：Bearer，本次更新）、`openspec/changes/archive/2026-11-03-ocr-gateway-mvp/decision-memo.md:20`（历史决策，不改，只作为恢复依据）。
- **C16 视觉方向为人拍板的单主题** — 验证方式：人 2026-11-04 明确选择；证据锚：「浅色单主题，深墨蓝主调（推荐）」；不得在实现时自行加入深色主题或渐变/卡片阴影等被 brief 排除的装饰。

## 接受的边角

- **缓存设置保存即清空缓存** — 概率：每次保存 100%；影响：下一个请求 miss、重新消耗一次额度；完美成本：按条目迁移 TTL 需自研 TTL 结构，成本高；**为何接受**：小团队缓存量级 1000 条，清空代价可接受，行为可解释。
- **总览指标是准实时而非实时** — 概率：持续；影响：刚发生的请求最多延迟到下一次刷新可见；完美成本：WebSocket/SSE 属明确的 v1 非目标（`docs/tech-selection.md:656`）；**为何接受**：手动刷新 + 页面聚焦刷新足够。
- **HTTP 本地面板 cookie 不带 Secure** — 概率：仅 http 本地/内网；影响：cookie 可被同网段嗅探；完美成本：强制 Secure 会使 http 环境无法登录；**为何接受**：按请求 scheme 决定 Secure，HTTPS 反代下自动开启，README 说明公网必须 HTTPS。
- **设置页不展示本地 OCR 开关** — 概率：100% 到 M4；影响：用户看不到该配置；完美成本：M4 未实现 worker，假开关会误导；**为何接受**：M4 交付时补真实开关。
- **成员不能登录面板** — 概率：100%；影响：成员只能 curl `/v1/me` 自查；完美成本：成员只读角色属后续里程碑；**为何接受**：`docs/tech-selection.md:134` 明确 v1 仅管理员登录。

## 三镜代价

- **系统镜**：新增 settings 表与前端构建链，耦合面集中在 `main.py`（静态托管 + 安全头）、`deps.py`（双轨鉴权）、`admin.py`（新端点）；可回退：删前端目录与静态挂载即可回到无面板状态，cookie 双轨保留 Bearer 不影响 `/docs` 与 curl。
- **用户镜**：管理员从 `/docs` 升级为可视化操作；登录态走 HttpOnly cookie，刷新不掉线；账号状态、配额进度、错误原因一屏可见；代价是多一次前端构建与静态资源加载。
- **开发循环镜**：新增 `frontend/` 的 `npm run typecheck` 与 `npm run build` 两道门；后端测试仍是一条 `pytest`；Docker 构建多一个 Node 阶段（可缓存依赖层），日常开发可用 Vite dev server 代理后端，心智负担可控。
- **主次判定**：优先保证鉴权安全与数据正确（cookie+CSRF、配额口径、时区分桶），视觉与交互在其次；面板是运营工具，不追求实时推送或复杂可视化。
