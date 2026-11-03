---
ship-gate:
  design_approved: true
  reviewed_sha: 2d9152563752fc7a78cfd10f9a47ba69b0bc3776e397cc44ac34559a7f69dcb1
  reviewed_manifest: MTAwNjQ0IGJsb2IgZTg2MzUzZTYyMDg1ODk5NWQ3MWQzYmQwNWMyMjE3ODZjZjZjZGIyMQlvcGVuc3BlYy9jaGFuZ2VzL20zLWFkbWluLXBhbmVsL2RlY2lzaW9uLW1lbW8ubWQAMTAwNjQ0IGJsb2IgZDRlZTBmNDBiNDRhYTViODY4YTExNWRjOTcxNTQ2NWMzODhmMTM4NQlvcGVuc3BlYy9jaGFuZ2VzL20zLWFkbWluLXBhbmVsL2Rlc2lnbi5tZAAxMDA2NDQgYmxvYiA3NzZkODI2ODliNmU0MGE0NjY5NTkxNjEwMDdkNDg3N2EzZTFjZmNkCW9wZW5zcGVjL2NoYW5nZXMvbTMtYWRtaW4tcGFuZWwvcHJvcG9zYWwubWQAMTAwNjQ0IGJsb2IgOTc4NDg3ZmY2YTM5ZmQwMjZiMmFkNDU5YjY0ZGIxYjUxN2IyYjA4ZQlvcGVuc3BlYy9jaGFuZ2VzL20zLWFkbWluLXBhbmVsL3NwZWNzL2FjY291bnQtcG9vbC1zY2hlZHVsaW5nL3NwZWMubWQAMTAwNjQ0IGJsb2IgZTk4ZjYzZjRhMzFiODVkZDBhN2ZkMzQ0ODBiZTcwNzNjYmJmMGExYQlvcGVuc3BlYy9jaGFuZ2VzL20zLWFkbWluLXBhbmVsL3NwZWNzL2FkbWluLWFwaS9zcGVjLm1kADEwMDY0NCBibG9iIDMzMTY0MmJlMWViM2Q3MDhiYWQ3N2NiYzhmNjlhMTVmZjQ1YzVmZTgJb3BlbnNwZWMvY2hhbmdlcy9tMy1hZG1pbi1wYW5lbC9zcGVjcy9hZG1pbi1wYW5lbC9zcGVjLm1kADEwMDY0NCBibG9iIDgyYTJjZmEyMjA2N2Y5NWUyZDA5YTY3ZWJkM2Y4M2VlYTY4YzcwZjkJb3BlbnNwZWMvY2hhbmdlcy9tMy1hZG1pbi1wYW5lbC9zcGVjcy9kZXBsb3ltZW50L3NwZWMubWQAMTAwNjQ0IGJsb2IgYjliMmU5YzliOGYxYWRhM2Y0MmY0MTBlMzE2NmFiY2RhYjg3MGE1OAlvcGVuc3BlYy9jaGFuZ2VzL20zLWFkbWluLXBhbmVsL3NwZWNzL3Jlc3VsdC1jYWNoZS9zcGVjLm1k
change: m3-admin-panel
reviewed_commit: 33a0d61
dispatch: fresh-subagent(7 镜)
memo: ok
---

# Spec Review Report · m3-admin-panel

> ⚠️ 同模型 fresh-context：隔离的是上下文，不是模型盲点。7 个镜由 fresh-context 子代理完成；
> 广审双镜与接地镜由主 session 完成。没有跨模型第二意见，也没有真正独立的实现者/审者/验证者。
>
> Findings 引用基线：`33a0d61`（评审起点）。amendment 已在其后应用，行号可能漂移；引用原文以
> 该提交为准。

## 拍板三问

- **Q-scope 范围划界认不认？** 自答：锚 `proposal.md` `## Non-Goals`（7 条）+ `design.md`
  `## Goals / Non-Goals`。评审**不建议砍范围**；只要求把「回滚、请求预算、缓存内存、数据面查询」
  等目标态缺口补进本 change，而不是留给实现期。`[ ] 认 [ ] 不认`
- **Q-deps 依赖/顺序认不认？** 自答：锚 `design.md` `## 切片与依赖`（S1→S6）。S1→S6 语义依赖成立；
  但 S6 的回滚依赖「不可变 release tag + 部署前 DB 备份」，原稿未接上，已补进 R-01/R-50。
  `[ ] 认 [ ] 不认`
- **Q-risk 风险赌注与对策认不认？** 自答：锚 `design.md` `## Risks / Trade-offs` 与失败模式表。
  原表覆盖 CSRF/CSP/时区/构建源；**缺**回滚 schema、缓存内存、summary 扫描、请求预算、设置并发
  五类，已在 R-01/R-03/R-06/R-08/R-10 补。`[ ] 认 [ ] 不认`

## 决策登记区

### [需拍板]

> 每条给推荐 + 三镜后果 + 主次判定 + 主审亲验的可行性锚。人工设计门逐项勾。

**Q1 发布与回滚版本策略**（R-01）
- 背景：设计写「回滚 = `docker compose` 回到 `ocr-gateway:0.1.0`」，但 `docker-compose.yml:10-14`
  每次 build 都把新镜像重打成 `0.1.0`；同时新镜像把 DB 推进到 `0002`，旧镜像 entrypoint
  `alembic upgrade head` 会因未知 revision 失败。**仅切镜像两条路都不通。**
- 选项 A（推荐）：M3 版本升 `0.2.0`，`image`/`build.tags` 改 `0.2.0`，`0.1.0` 保持不变；回滚 =
  `git checkout` 上一提交（compose 指向 `0.1.0`）+ `scripts/rollback.sh <部署前备份>` 把 DB 恢复
  到 `0001`。证据：README 已写明这套口径（`README.md:150-158`），只是 design 没接上。
- 选项 B：保留 `0.1.0` 但每次 build 前手工 `docker tag` 旧镜像为 `0.1.0-rollback`；回滚仍要恢复
  DB。多一条易忘的手工步骤，不推荐。
- 选项 C：让旧镜像 entrypoint 容忍未知 revision；危险，会掩盖真正的迁移损坏，不推荐。
- 三镜：系统镜 A 最稳（不可变 tag + DB 快照原子回退）；用户镜 A 回滚可预期；开发循环镜 A 只改
  compose/README/任务三处。**主次：系统镜优先。**
- 可行性锚：`docker/entrypoint.sh:16`、`docker-compose.yml:10-14`、`scripts/rollback.sh`、
  `README.md:150-158` 均已只读核验。

**Q2 缓存内存上限**（R-03）
- 背景：`cache_max_entries` 允许到 `10000`，单条结果上限 `256KB`（`cache.py:9`），最坏
  `10000 × 256KB ≈ 2.5GB`，2C4G 单机可被一个设置打爆。
- 选项 A（推荐）：把可编辑上限压到 `2000`（最坏约 512MB），并在设计里写死
  `entries × 256KB` 的内存预算；不加新设置键。
- 选项 B：新增 `cache_max_bytes`（默认 64MB）按 payload 字节淘汰；更正确，但多一个设置键、UI
  字段、校验与测试，本 change 扩容。
- 选项 C：保留 10000，只在文档写「可能占 2.5GB」；不推荐。
- 三镜：A 系统镜可控、开发循环最小；B 系统镜最好但用户镜多一个概念；C 系统镜最差。
  **主次：系统镜优先，选 A；后续需要更大缓存再另开 byte budget。**
- 可行性锚：`cache.py:9-17`、`design.md:81` 已核验。

**Q3 settings 400 字段级错误**（R-05）
- 背景：`design.md:360` 承诺「消息含字段名」，但全局 `RequestValidationError` handler
  （`main.py:157-167`）统一返回 `invalid request`；`extra="forbid"`/范围校验都会落成无字段名 400。
- 选项 A（推荐）：settings handler 内捕获 `ValidationError`/`RequestValidationError`，返回
  `error.fields: [{field, message}]`；未知键、字符串数字、超范围都含字段名。只影响该端点。
- 选项 B：放宽设计，依赖前端 zod 做字段级；服务端仍泛化 400。实现小，但服务端错误不可诊断，
  且与 design 文案冲突。
- 三镜：A 系统镜可诊断、用户镜字段级提示成立；B 开发循环省事但用户镜差。**主次：用户镜。**
- 可行性锚：`main.py:157-167` 与 `design.md:360` 已对读。

**Q4 HTTPS 反代下 Secure cookie 闭环**（R-04）
- 背景：`design.md:58` 用 `request.url.scheme` 或 `TRUST_PROXY_HEADERS` + `X-Forwarded-Proto`
  判 Secure；但 README 的 nginx 示例（`README.md:129-131`）不转发 `X-Forwarded-Proto`，
  `TRUST_PROXY_HEADERS` 默认 false（`config.py:81`），文档还写它「仅用于登录限速」。按 README
  部署，HTTPS 下会话 cookie 实际不带 `Secure`。
- 选项 A（推荐）：README/nginx 示例补 `proxy_set_header X-Forwarded-Proto $scheme;`，明确反代
  部署必须 `TRUST_PROXY_HEADERS=true`；镜像冒烟断言反代后的 `Set-Cookie` 含 `Secure`。
- 选项 B：新增 `COOKIE_SECURE=auto|always` 显式配置；更可控，但多一个配置面与优先级规则。
- 选项 C：只靠 `request.url.scheme`；在反代终结 TLS 的部署下不可达。
- 三镜：A 用户镜直接可达且无新概念；B 系统镜更显式但开发循环多一维；C 不成立。
  **主次：用户镜优先，选 A；若运维要求强制 Secure，再加 B。**
- 可行性锚：`README.md:128-136`、`config.py:81`、`docker/entrypoint.sh:19` 已核验。

**Q5 `/overview` 是否内嵌 7 日序列**（R-09）
- 背景：总览页要「近 7 日请求折线」（`design.md:203-204`），但 `/overview` 响应示例只有
  `today/providers/accounts/recent_errors/cache`（`design.md:366-392`），页面还得再调
  `/usage/series`；加上 `/me`，首屏至少 3 次请求，与「单请求/一次往返」矛盾。
- 选项 A（推荐）：`/overview` 响应增加 `series`（近 7 个本地日桶），页面首屏只依赖 `/overview`
  + `/me`；复用 series 聚合，代价一个字段。
- 选项 B：接受 3 个并行请求，修正「一次往返」表述与请求瀑布，不扩 overview 契约。
- 三镜：A 用户镜首屏少一跳、系统镜多一个聚合字段；B 实现更少但用户镜多一次往返。
  **主次：用户镜优先，选 A。**
- 可行性锚：`design.md:203-204`、`:366-392`、`:508` 已对读。

**Q6 请求总预算上限 vs 停机宽限**（R-08）
- 背景：`request_deadline_ms` 允许到 `60000`（`design.md:81`），compose `stop_grace_period: 25s`
  （`docker-compose.yml:28`）。设到 25s 以上时，SIGTERM 后仍在途的 OCR 请求会被 SIGKILL，用量
  事件/配额刷盘可能丢失。
- 选项 A（推荐）：把 `request_deadline_ms` 上限压到 `20000`（与默认一致），并在设计里绑定
  `stop_grace_period`；慢厂商需求另开 change。
- 选项 B：`stop_grace_period` 提到 `70s`；保留 60s 预算，但每次部署停机更久。
- 三镜：A 系统镜最稳、用户镜少 40s 上限；B 用户镜保留长预算、开发循环部署变慢。
  **主次：系统镜优先，选 A。**
- 可行性锚：`docker-compose.yml:28`、`design.md:81` 已核验。

**Q7 已删除实体的分组口径**（R-11）
- 背景：`usage_events.user_id/account_id` 是 `ON DELETE SET NULL`（`models.py:116/122`），删除后
  group_by=user/account 的 key 变 `null`；多个已删除实体会合并成同一 `null` 行，且 `null` 与 int
  混合排序会 `TypeError`。原设计只写「label 为 null」，没定义分组键与排序。
- 选项 A（推荐）：接受合并为一个 `null` 行，排序时 `null` 最后；前端显示「已删除」。不改 schema。
- 选项 B：新增 `user_id_snapshot/account_id_snapshot` 列保留归属；更准确，但要迁移 + 回填不可能，
  本 change 扩容。
- 三镜：A 系统镜最小、用户镜接受「已删除合并」；B 系统镜更准、开发循环多一次迁移。
  **主次：开发循环镜优先，选 A；若运营需要区分已删除实体，另开 change。**
- 可行性锚：`models.py:110-142`、`admin.py:512-527`、`design.md:98-101/401` 已核验。

**Q8 `/docs` 的 Authorize 工作流**（R-49）
- 背景：`require_admin` 是普通依赖，不是 `HTTPBearer`；实测 `app.openapi()` 的
  `components` 只有 `schemas`，**没有 `securitySchemes`**。README 让用户在 `/docs` 右上角
  Authorize 填 Bearer，但按钮不存在；proposal 的「/docs 工作流不受影响」不成立。
- 选项 A（推荐）：`require_admin` 改用 `HTTPBearer(auto_error=False)`，保留 cookie 回退；OpenAPI
  自动生成 Bearer scheme，`/docs` Authorize 可用。只改依赖声明，不改鉴权语义。
- 选项 B：只修 README，写明「/docs 不能 Authorize，请用 curl」；不补能力。
- 三镜：A 用户镜恢复文档承诺、系统镜多一个标准 security scheme；B 用户镜继续残缺。
  **主次：用户镜优先，选 A。**
- 可行性锚：已用 `uv run --project backend python` 实测 OpenAPI 无 securitySchemes；
  `deps.py:51-59` 已核验。

**Q9 首屏 JS 预算口径**（R-19）
- 背景：`design.md:555` 写「gzip 后 ≤250KB（登录+shell+总览，图表库按路由懒加载）」，但总览
  首屏就含 Recharts 折线；`tasks.md:46` 只人工量一次，没定义计入哪些 chunk。
- 选项 A（推荐）：拆成「登录+shell ≤150KB；总览路由 chunk（含 Recharts）≤350KB」，并在 task 4.4
  记录实际 chunk 清单；不引 CI。
- 选项 B：保留 250KB，把图表改为首屏后懒加载 + 单独 Suspense；用户镜首屏先见骨架。
- 三镜：A 指标可测且不伤首屏；B 省预算但用户镜多一次等待。**主次：开发循环镜（可测性）优先，选 A。**
- 可行性锚：`design.md:448/555`、`tasks.md:46` 已核验；Recharts 体积未实测，故给区间而非精确值。

**Q10 缺失的 spec delta**（R-50）
- 背景：本次把 `request_deadline_ms` 改成运行时设置、把 cache TTL/容量改成可编辑；但主 spec
  `openspec/specs/account-pool-scheduling/spec.md:31` 仍写 `REQUEST_DEADLINE_MS` 耗尽，
  `openspec/specs/result-cache/spec.md:20` 仍写「容量默认 1000、TTL 默认 3600」，没有 MODIFIED delta。
- 选项 A（推荐）：补两个 MODIFIED delta（deadline 来源、cache 运行时覆盖 + 变更清空），并在设计
  Compliance 加一张 scope-check 表枚举 7 个 capability。
- 选项 B：在设计里声明「这两条属于 admin-api 配置面，不改主 spec」，只加 scope-check 表。
  合同套件仍留旧措辞，下次升级容易再漏。
- 三镜：A 系统镜契约一致；B 开发循环少两个文件但系统镜留漂移。**主次：系统镜优先，选 A。**
- 可行性锚：两份主 spec 与 `design.md:77-81` 已对读。

### [自动决策]

| id | 决定 | 理由 |
|---|---|---|
| A1 | 请求总预算改为单一来源：`public.py` 外层 deadline 与 `Scheduler` 都读 `RuntimeSettings`（或由 public 计算绝对 deadline 传入 Scheduler） | R-02；只改 Scheduler 会让「调大预算」完全无效，调小也被旧外层截断 |
| A2 | `usage/summary` 增加 90 天跨度上限，聚合尽量下推 SQL；`logs.total` 与过滤共用索引；NFR 覆盖 summary | R-06；原 NFR 只覆盖 series/logs，summary 可扫全表并 materialize 全部 ORM 行 |
| A3 | `delete_account` 调 `state.quota.reset_account(account_id)`，并补「删除→两个 flush 周期→新账号 used=0、无 FK 错误」测试 | R-07；当前内存计数残留会让 2s flush 对已删除 id upsert，FK 失败并停掉所有配额落盘 |
| A4 | settings 写入用进程内 `asyncio.Lock` 串行化 merge+commit+apply；不再声称「不含 await」 | R-10；并发 PUT 的提交/应用顺序可让 DB 与 runtime 分叉 |
| A5 | 时间窗口统一：`to` 默认本地当日结束/now，`from` 默认对齐本地 00:00 的 7 个日桶；日期形式 `to` 用半开区间 `[from, next_local_day_00:00)`；90 天按本地日历日含当日 ≤90 | R-12；否则默认 7 日会得到 8 个桶，90/91 天边界会误 400 |
| A6 | 静态兜底改为「非 API 且无扩展名 → index.html；带扩展名的缺失静态文件 → JSON 404」 | R-13；spec 原文「所有非 API 未知路径回退」会把缺失 JS 当 HTML 返回 |
| A7 | `AccountUpdate.timeout_ms` 显式 null 返回 400；编辑表单留空 = 省略字段（保持原值）；新建留空 = runtime 默认 | R-14；否则 null 会撞 `accounts.timeout_ms NOT NULL` 变 500 |
| A8 | `PUT /settings` 显式 null 一律 400（部分更新只由 omit 表达） | R-15；避免 null 被当「未提供」或写入非法值 |
| A9 | `ResultCache.reconfigure(enabled, max_entries, ttl_seconds)` 与构造函数参数顺序对齐（或强制关键字） | R-16；顺序不一致会静默交换 TTL/容量 |
| A10 | 明确 Scheduler 注入 `RuntimeSettings`（构造引用或 deadline provider），并更新现有单测 | R-17；原设计只写「每次 recognize 读取」，没写怎么拿到引用 |
| A11 | `settings.key` 统一为 `TEXT`（设计第 73 行与 267 行自相矛盾） | R-18；SQLite 两者亲和性相同，但契约应唯一 |
| A12 | 安全头中间件必须最外层（在 `BodyLimitMiddleware` 之后 add），并断言超大 body 的 400 响应也带齐头 | R-20；Starlette 最后 add 的中间件最外层，现有 request middleware 在内层 |
| A13 | `available_accounts` 明确定义为「瞬时可调度数（含并发/QPS 瞬时排除）」，overview 只读快照，不触发状态迁移 | R-21；`candidates()` 会 recover/置 quota_exhausted 并标 dirty，GET 不应有写副作用 |
| A14 | 升级文档补三条：只配 `UV_DEFAULT_INDEX` 的离线部署需新增 `NPM_REGISTRY`；`DEFAULT_TIMEOUT_MS` 从「账号创建不生效」变为「生效」；`TRUST_PROXY_HEADERS` 新增 Secure 判定用途 | R-22；DX-04 原判 N/A 不成立 |
| A15 | 错误文案以文案表为唯一真相源；补 `cache_max_entries/request_deadline_ms/default_timeout_ms` 与未知键原文；定义 `FRONTEND_NOT_BUILT` message 并区分源码/镜像两条 fix | R-23；失败模式表与文案表当前给出不同原文 |
| A16 | TTHW 重新按时长假设求和，并把「打开面板并登录」纳入终点；标注 `uv sync`/`pnpm install` 各自区间与 registry 参数 | R-24；1–3 分钟 + 1–2 秒推不出 4–6 分钟 |
| A17 | `FRONTEND_DIST` 进 README/.env.example 与命名节；`NPM_REGISTRY` 明说「语义同构、词形不同」 | R-25；配置面不完整，命名对照缺失 |
| A18 | `apiFetch` 15s 仅作默认；账号测活按 `account.timeout_ms + 5s` 覆盖；204 不解析 JSON | R-26；测活厂商调用可到 60s，15s 会假超时 |
| A19 | login 请求 `skipAuthRedirect`；`/me` 非 401 失败显示启动错误页 + 重试 | R-27；401 全局跳转会把「密码错误」吃掉 |
| A20 | GET 重试仅网络/5xx；401/403/400 不重试；明确 15s 总预算 | R-28；无条件重试会重复触发 SessionExpired/CSRF 提示 |
| A21 | 防双提交用 `isPending` 禁用 + mutation `scope`（v5）或提交 guard；`mutationKey` 不承担串行 | R-29；mutationKey 只是标识 |
| A22 | CSRF token 单一来源 = `ocr_csrf` cookie；AuthContext 只留 username；403 时 GET `/me` 刷新后单次重试 | R-30；登录会轮换 CSRF cookie，其他标签页的旧 context 值会 403 |
| A23 | 每个路由一个与最终布局同尺寸的 Suspense fallback；总览图表单独 Suspense；ErrorBoundary 包在 Suspense/lazy 外层 | R-31/R-32；单一骨架无法匹配异构页面，chunk 失败也需被本页边界捕获 |
| A24 | `/me` 与首屏查询并行（或明确串行并修正瀑布）；`/me` 计入首屏往返与预算 | R-33；原「一次往返」与 `/me` 引导矛盾 |
| A25 | 所有 naive UTC 字段（含 `overview.recent_errors.created_at`、`logs.created_at`、`accounts.last_used_at`、`summary.from/to`）走 `parseServerTime`；`series.date` 直接展示 | R-34；只点名旧字段会让新字段差 8 小时 |
| A26 | 用量/日志查询加 `placeholderData: keepPreviousData`，或删除「保留上一次结果」承诺 | R-35；URL key 变化会清空旧数据 |
| A27 | CSP 作用于「所有返回 index.html 的响应」，含深链接；task 1.2/1.3 加断言 | R-36；只按入口/静态路径判定会漏掉 SPA 回退 |
| A28 | 登录页保存同源相对 `returnTo`，成功后回跳；声明滚动恢复与筛选变化时 offset 归零 | R-37；未认证深链接登录后丢上下文 |
| A29 | 脏表单 beforeunload/路由离开确认；同表单双标签明确 last-write-wins 提示 | R-38；原交互边界只覆盖双击/慢网/登出 |
| A30 | CWV 验收写清「Lighthouse 移动端/4G 一次 + 记录 LCP/INP/CLS」，不新增 CI | R-39；原设计只有数字目标，无回归方式 |
| A31 | 最小支持宽度 360px；登录列 `width: min(360px, 100% - 32px)`；对话框/图表窄屏规则 | R-40；固定 360px 在 <360 视口横向溢出 |
| A32 | 写明 queryKey 失效图：账号 CRUD/reset → accounts+overview；cache clear/缓存设置 → overview+settings；成员/Key → members+accounts+overview | R-41；总览是聚合 query，笼统「精确失效」会留旧账号/配额 |
| A33 | 补测试：cookie 属性（HttpOnly/Secure/CSRF 可读）、`/me` 补发 CSRF、Bearer 无效不回退 cookie、settings DB 失败 500 | R-42；spec 场景已有，tasks 没列 |
| A34 | settings 恢复语义：随 SQLite 备份、丢失回退 env；RPO=最近备份，RTO=`rollback.sh` 恢复时间 | R-43；原 BE-11 只写配额 RPO |
| A35 | 显式 SQLite `busy_timeout=5s`；失败模式表补 DB 读失败、锁等待、磁盘满 | R-44；settings/聚合与 2s flush 共用单写者 |
| A36 | 新增结构化日志：`admin.query`（path/duration/rows）、`admin.settings.rejected`；不新增 metrics 端点 | R-45；原可观测性只覆盖登录/设置成功/静态缺失 |
| A37 | 基准测试加 `slow` marker + 默认 `-m "not slow"`，并在 6.4 显式跑 `pytest -m slow`；输出 p50/p95 | R-46；pyproject 没有 slow marker，`任务 3.5` 的「默认跳过」不成立 |
| A38 | 6.3 定义无凭证种子数据（直接插 `usage_events` 或 mock provider），手工冒烟清单固化为可勾选脚本/截图路径 | R-47；测活不写用量，干净环境没有真实凭证 |
| A39 | 构建产物扫描 `MASTER_KEY/ADMIN_PASSWORD/凭证/Key` 明文；禁止用 `VITE_*` 承载秘密 | R-48；R-DEP-09 已有场景，tasks 未落 |
| A40 | Compliance 显式写两条既有豁免：密码存储沿用 MVP D22（env 常量时间比较，不引 argon2）；API 鉴权开关/本地 OCR 按 decision-memo D3 + proposal Non-Goals 砍掉 | R-51；避免 `§11/§12` 合规声明被读成「已覆盖」 |
| A41 | 时间序列化/精度统一：summary 的 `from/to` 保持 UTC naive（兼容），series/overview 带偏移；`avg_latency_ms` 四舍五入到整数，比率保留 4 位；`recent_errors` 明确定义为 `success=false` 按 `created_at desc` 取 10 | R-52；原设计未定义精度/排序/错误定义 |
| A42 | `frontend_built` 明说为启动快照；构建后需重启才变 true | R-56；原设计没写时机 |
| A43 | `label` 的已删除实体一律后端返 `null`，前端显示「已删除」；删掉「或『已删除』」 | R-57；与 spec 的 `null` 不一致 |

### [已裁掉]

| id | 原始发现 | 裁掉理由 |
|---|---|---|
| X1 | 未按 tech-selection §11 使用 argon2id | 归档 MVP 评审 D22 已明确移除 `argon2-cffi`（无密码哈希消费者），管理密码用 env 常量时间比较；本次不静默推翻，A40 补显式豁免即可 |
| X2 | 设置页缺 API 鉴权开关/本地 OCR 开关，与 tech-selection §12 页面清单不符 | decision-memo D3 与 proposal `## Non-Goals` 已明确砍掉并给可证伪假设；属已拍板范围，不是缺陷 |
| X3 | design 引用的 `tickets.md` 不存在 | `openspec instructions design` 模板明确要求写「真实 Blocked-by 落在 tickets.md」；tickets 在 ship 阶段生成，不是悬空引用 |
| X4 | `pnpm@11.2.2` 可能不存在 | 已实测 `npm view pnpm@11.2.2 version --registry=https://registry.npmmirror.com` 返回 `11.2.2`；pin 是有意为之 |
| X5 | 29 tasks/6 slices 范围过大，应拆 change | decision-memo D1 明确选择完整总览 + 六面板；6 张切片落在 3–6 预算内；拆开会把同源鉴权/托管/前端骨架撕开，违背「一个 change = 一个完整阶段结果」 |
| X6 | `reconfigure` 期间在途请求可能持有旧 `TTLCache` 引用 | 请求持有的是 `state.cache`（ResultCache 对象），不是内部 `_cache`；重建后下一次 `get` 即用新缓存。仅措辞不精确，A9 顺手改 |
| X7 | 未新增 Prometheus/metrics 端点，BE-07 未落地 | design 明示 Prometheus 属 M5；本 change 只补结构化日志（A36），不新增指标端点 |
| X8 | 登录响应体仍返回 Bearer token，XSS 可读 | Bearer 是 `/docs`/curl 的兼容面，必须返回；面板忽略该字段并用 HttpOnly cookie；token 12h 过期。属已接受取舍，记录不修订 |
| X9 | 登出不服务端吊销 token，被窃 cookie 仍有效至 12h | design 明示无服务端会话表；v1 单实例 + HttpOnly + SameSite=Lax 下接受。A40 同段记录残留风险，不扩会话表 |

## 评审范围与派发记录

- **roster**：广审双镜（strategy / plan-eng，主 session）· 领域镜 `backend` / `frontend` /
  `frontend-react` / `devex`（4，派发）· 对抗镜 3（隐藏假设 / 失败模式 / 乐观估计与边界，派发）·
  接地镜（主 session）。
- **派发收件**：7/7 子代理结果首行与 `principles-lite.md` 首行逐字一致；7/7 有 6 字段 finding 与
  `counts:` 行；A3 结果带 `truncated: yes`，已在对应小节注明；未发现回执不符或输出截断到不可用。
- **`dispatch:` 标注**：`fresh-subagent(7 镜)`。未派发的广审双镜与接地镜由主 session 完成。
- **T/S 机械门**：`check_decision_memo.py --json` → `{"ok": true, "errors": []}`；
  `openspec validate m3-admin-panel --strict` → valid；工作树评审前干净。
- **诚实边界**：同模型 fresh-context，隔离的是上下文，不是模型盲点；广审双镜与接地镜由主 session
  亲做，存在自查偏置。没有跨模型第二意见。

## 广审双镜

### strategy 镜（计划级）

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| S-01 | 改动 `request_deadline_ms` 与 cache TTL/容量，却只改 admin-api/deployment spec，未同步 `account-pool-scheduling` R-SCH-03 与 `result-cache` R-CAC-02 | `openspec/specs/account-pool-scheduling/spec.md:31`：「直到 `REQUEST_DEADLINE_MS` 耗尽」；`openspec/specs/result-cache/spec.md:20`：「容量默认 1000 条、TTL 默认 3600 秒」；`design.md:77-81` | 高 | 中 | 采纳 R-50（Q10） |
| S-02 | 静态兜底 spec 与 design 冲突：spec 说所有非 API 未知路径回退 HTML，design 说带扩展名的缺失文件返回 JSON 404 | `specs/admin-panel/spec.md:207`；`design.md:118` | 高 | 中 | 采纳 R-13 |
| S-03 | 仅日期 `to` 的「该本地日结束」没有精确到半开区间，跨日 00:00 事件可能被相邻两天重复计入 | `design.md:418`；`admin.py:506-510` 现有 `created_at <= end` | 高 | 中 | 采纳 R-12 |
| S-04 | settings 400 承诺「消息含字段名」，与全局 handler 的 `invalid request` 冲突 | `design.md:360`；`main.py:157-167` | 高 | 高 | 采纳 R-05（Q3） |
| S-05 | `PUT /settings` 没定义显式 null 语义；Pydantic 可选字段可能把 null 当未提供或写入非法值 | `design.md:80-81` | 中 | 中 | 采纳 R-15 |
| S-06 | 编辑账号「超时留空用运行时默认」与 `AccountUpdate.timeout_ms` 可显式 null 叠加，会撞 DB NOT NULL 变 500 | `design.md:79/145`；`schemas.py:59`；`models.py:65/87` | 高 | 中 | 采纳 R-14 |
| S-07 | `reconfigure(enabled, ttl_seconds, max_entries)` 与构造函数 `(enabled, max_entries, ttl_seconds)` 顺序相反 | `design.md:78`；`cache.py:13-17` | 高 | 低 | 采纳 R-16 |
| S-08 | Scheduler 只写「每次 recognize 读取 runtime_settings」，没写注入路径；现有构造函数收 int | `design.md:77`；`scheduler.py:60-71` | 中 | 中 | 采纳 R-17 |
| S-09 | `settings.key` 类型自相矛盾：同页第 73 行写 `TEXT PK`，第 267 行写 `VARCHAR(64)` | `design.md:73`；`design.md:267` | 高 | 低 | 采纳 R-18 |
| S-10 | 回滚任务写「`/` 返回未构建提示」，与旧镜像没有该处理器的契约不符 | `tasks.md:76`；`specs/deployment/spec.md:41` | 高 | 中 | 采纳 R-01 |
| S-11 | 首屏 JS 250KB 把总览 Recharts 计入却未定义 chunk 口径 | `design.md:555`；`tasks.md:46`；`design.md:203` | 中 | 中 | 采纳 R-19（Q9） |
| S-12 | 「已删除实体为『已删除』或 null」与 spec 的「为 null」不一致 | `design.md:98`；`specs/admin-api/spec.md:59`；`design.md:101` | 高 | 低 | 采纳 R-57 |
| S-13 | 安全头「所有响应」没有考虑 `BodyLimitMiddleware` 在最外层的顺序 | `design.md:121`；`main.py:198-200`（Starlette 0.46.2 `add_middleware` insert(0)） | 高 | 中 | 采纳 R-20 |
| S-14 | `available_accounts` 复用调度候选扫描，含并发/QPS 瞬时排除，且 GET 会触发状态迁移/dirty | `design.md:395`；`registry.py:173-175` | 中 | 低 | 采纳 R-21 |
| S-15 | summary/logs 的 `from/to` 保持 UTC naive，series/overview 带偏移，时间格式不统一 | `design.md:142`；`admin.py:528-533`；`design.md:405-414` | 中 | 低 | 采纳 R-52 |
| S-16 | 「设置更新路径不含 await 中断」不成立；DB commit 就是 await 点 | `design.md:75/80` | 中 | 中 | 采纳 R-10 |
| S-17 | `frontend_built` 未说明是启动快照还是每请求计算 | `design.md:82/115` | 中 | 低 | 采纳 R-56 |
| S-18 | `avg_latency_ms` 整数均值/比率精度/`recent_errors` 定义未写 | `design.md:371/419/96` | 低 | 低 | 采纳 R-52 |
| S-19 | Compliance 对 §11/§12 的合规声明未写两条既有豁免 | `design.md:637`；`proposal.md:68`；归档 MVP 评审 D22 | 高 | 低 | 采纳 R-51 |
| S-20 | tasks 缺 cookie 属性、`/me` 补发、settings DB 失败等 spec 场景的测试 | `tasks.md:5/22`；`specs/admin-api/spec.md:13-15`；`design.md:569` | 高 | 中 | 采纳 R-42 |
| S-21 | `tickets.md` 不存在 | `design.md:246`；change 目录无 tickets.md | — | — | 裁掉 X3（模板要求） |
| S-22 | `pnpm@11.2.2` 需核验 | `design.md:236` | — | — | 裁掉 X4（实测存在） |

### plan-eng 镜（工程级）

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| P-01 | 请求总预算只改 Scheduler；`public.py` 外层仍读启动期 `state.settings`，调大预算完全无效 | `public.py:200`；`design.md:77` | 高 | 高 | 采纳 R-02 |
| P-02 | 缓存容量只限条目数，10000 × 256KB 最坏约 2.5GB | `cache.py:9/15-17`；`design.md:81` | 高 | 高 | 采纳 R-03（Q2） |
| P-03 | 回滚到旧镜像会因 DB 在 0002、旧 entrypoint `upgrade head` 未知 revision 失败；且 compose 每次 build 覆盖 0.1.0 tag | `entrypoint.sh:16`；`docker-compose.yml:10-14`；`README.md:150-158`；`design.md:665`；`tasks.md:76` | 高 | 高 | 采纳 R-01（Q1） |
| P-04 | `usage/summary` 无 90 天上限且 `.scalars().all()` 全量 materialize；NFR 未覆盖 summary | `admin.py:504-511`；`design.md:417/557` | 高 | 高 | 采纳 R-06 |
| P-05 | 删除账号未清 `QuotaManager` 计数；2s flush 对已删除 id upsert 触发 FK 失败，所有配额停止落盘；id 复用会继承旧用量 | `admin.py:370-385`；`quota.py:113-133`；`db.py:32` | 高 | 高 | 采纳 R-07 |
| P-06 | `request_deadline_ms` 上限 60s 与 `stop_grace_period: 25s` 冲突，SIGTERM 会杀在途请求 | `design.md:81`；`docker-compose.yml:28` | 高 | 中 | 采纳 R-08（Q6） |
| P-07 | 设置 DB 失败/锁等待/磁盘满未进失败模式表；SQLite 未显式 busy_timeout | `design.md:569`；`db.py:25`；`main.py:36-45` | 中 | 中 | 采纳 R-44 |
| P-08 | BE-11 标 N/A，但 settings 持久化的 RPO/RTO/备份恢复未定义 | `design.md:558/641`；`scripts/backup.sh:27-30`；`README.md:174-178` | 中 | 低 | 采纳 R-43 |
| P-09 | 新增 settings/静态/聚合 codepath 只有部分结构化日志，无查询延迟可观测 | `design.md:582-584` | 高 | 中 | 采纳 R-45 |
| P-10 | 基准测试「slow 默认跳过」不成立：pyproject 只有 contract marker，6.4 跑全量 | `tasks.md:35/72`；`backend/pyproject.toml:43` | 高 | 高 | 采纳 R-46 |
| P-11 | 6.3 冒烟要求有数据，但测活不写用量、真实凭证默认 skip，干净环境无种子路径 | `tasks.md:70`；`specs/admin-api/spec.md:57`；`README.md:186` | 中 | 中 | 采纳 R-47 |
| P-12 | `/overview` 响应没有 series，但总览页要 7 日折线；首屏至少 `/me`+`/overview`+`/series` | `design.md:203-204/366-392/508` | 高 | 中 | 采纳 R-09（Q5） |
| P-13 | 删除成员/账号后 `SET NULL` 产生 null group key；混合排序 TypeError，多个已删除实体合并 | `models.py:116/122`；`design.md:401`；`admin.py:515` | 中 | 中 | 采纳 R-11（Q7） |
| P-14 | 默认 7 日 + 本地日分桶会得到 8 个桶；90 天与日期形式 to 叠加边界不清；tasks 只覆盖跨日不覆盖reset_day 跨月 | `design.md:417-418`；`tasks.md:29/33` | 中 | 中 | 采纳 R-12 |
| P-15 | `require_admin` 非 HTTPBearer，OpenAPI 无 securitySchemes；README 的 `/docs` Authorize 工作流不存在 | `deps.py:51-59`；实测 `app.openapi()` components 仅 `schemas`；`README.md:42-43` | 高 | 中 | 采纳 R-49（Q8） |
| P-16 | `provider='auto'` 失败事件进入 summary/overview，但 `PROVIDER_NAMES` 无 auto，providers 行只列两家 | `models.py:134-137`；`public.py:28/271`；`base.py:111` | 高 | 中 | 采纳 R-52（auto 行） |
| P-17 | 登录每次轮换 CSRF cookie；其他标签页 AuthContext 旧 token 的写请求 403，原并发场景只覆盖 401 | `design.md:53/140/530` | 中 | 中 | 采纳 R-30 |
| P-18 | settings 并发 PUT 的提交/应用顺序可让 DB 与 runtime 分叉 | `design.md:75/80` | 中 | 中 | 采纳 R-10 |
| P-19 | 安全头中间件顺序会让 BodyLimit 的 400 响应漏头 | `main.py:198-200`；Starlette 0.46.2 源码 | 高 | 中 | 采纳 R-20 |
| P-20 | `available_accounts` 语义含瞬时负载且 GET 有写副作用 | `registry.py:173-175`；`design.md:395` | 中 | 低 | 采纳 R-21 |

## 领域镜

### backend 镜

子代理原始 findings（10 条，高=6 中=4 低=0）。已合并进 R-01..R-52；未逐条重复引文，映射如下：
- BE-F1 → R-02；BE-F2 → R-03；BE-F3 → R-04；BE-F4 → R-05；BE-F5 → R-06；BE-F6 → R-45；
  BE-F7 → R-08；BE-F8 → R-44；BE-F9 → R-43；BE-F10 → R-21。
- 子代理给出的三处补充证据均已亲验：`public.py:200`、`docker-compose.yml:28`、
  `registry.py:173-175`。

### frontend 镜

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| FE-01a | `apiFetch` 统一 15s 超时，但账号测活按 `account.timeout_ms` 可到 60s，前端会假超时 | `design.md:141/81`；`admin.py:453` | 高 | 中 | 采纳 R-26 |
| FE-12a | 时间解析只点名旧字段，漏 `overview.recent_errors.created_at`（naive）；`series.date` 展示口径不清 | `design.md:142/389` | 高 | 中 | 采纳 R-34 |
| FE-07a | `/me` 是首屏前串行一跳，但总览称「首屏只有一次网络往返」 | `design.md:140/508` | 高 | 中 | 采纳 R-33 |
| FE-01b | 未定义脏表单离开、在途 mutation 取消、同表单双标签并发 | `design.md:526-530` | 中 | 中 | 采纳 R-38 |
| FE-11a | `/me` 非 401 无重试/启动错误页；login 401 会被顶层跳转吃掉 | `design.md:140-141/564` | 中 | 中 | 采纳 R-27 |
| FE-02a | 失败模式表承诺「保留上一次结果」，但 URL key 变化默认清空 | `design.md:572/147` | 高 | 中 | 采纳 R-35 |
| FE-08a | CSP 只写「面板入口与静态资源」，深链接返回 index.html 时是否带头未定义 | `design.md:118/122` | 中 | 中 | 采纳 R-36 |
| FE-09a | 未认证深链接登录后无 returnTo；无滚动恢复策略 | `design.md:141/538` | 中 | 低 | 采纳 R-37 |
| FE-06a | CWV 只有数字目标，无 Lighthouse/CI/实测记录 | `design.md:136/554`；`tasks.md:46` | 中 | 低 | 采纳 R-39 |
| FE-13a | 未定义最小宽度；登录固定 360px 在 <360 视口溢出 | `design.md:548/226` | 中 | 低 | 采纳 R-40 |

- 子代理计数：`counts: 高=4 中=6 低=0 未接地=0`，与逐行统计一致。

### frontend-react 镜

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| RX-01a | 单一「路由级 Suspense 骨架」无法匹配七个异构页面，与 R-PANEL-09「同高骨架/不 CLS」冲突 | `design.md:139/196`；`specs/admin-panel/spec.md:175` | 高 | 中 | 采纳 R-31 |
| RX-01b | 总览 Recharts chunk 归属未定义：首屏加载还是懒加载、哪层 Suspense 承接 | `design.md:203/555/448` | 中 | 中 | 采纳 R-19/R-31 |
| RX-01c | `/me` 未纳入加载边界；受保护路由在 `/me` 完成前是否渲染未定义 | `design.md:140/508/517` | 高 | 中 | 采纳 R-33 |
| RX-01d | 用量页四个并行 query 的 `/users`、`/accounts` 筛选源 loading/error 未定义 | `design.md:511/517` | 中 | 低 | 采纳 R-31 |
| RX-01e | ErrorBoundary 与 lazy/Suspense 的相对位置未定义；chunk 失败可能落根级 | `design.md:139/149` | 中 | 低 | 采纳 R-32 |
| RX-02a | `csrf_token` 同时在 AuthContext 与 cookie，`apiFetch` 只读 cookie，双源会旧值 | `design.md:56/140/141` | 高 | 低 | 采纳 R-30 |
| RX-02b | 跨标签登出只处理 401 跳转，未明确 `queryClient.clear()`/AuthContext 重置 | `design.md:140/530` | 中 | 中 | 采纳 R-30 |
| RX-02c | GET 重试 1 次未限定错误类型；401/403/400 也重试，且与 15s 超时冲突 | `design.md:143/529` | 高 | 中 | 采纳 R-28 |
| RX-02d | `mutationKey` 不承担串行/去重，防双提交归因错误 | `design.md:528` | 高 | 低 | 采纳 R-29 |
| RX-02e | 写操作「精确失效相关 query」未给 queryKey 依赖图，总览可能留旧数据 | `design.md:143/508` | 中 | 低 | 采纳 R-41 |
| RX-03 | 项目未启用 RSC，N/A | `design.md:37/641` | — | — | 无行动 |

- 子代理计数：`counts: 高=5 中=5 低=0 未接地=0`；REACT-03 为 N/A。

### devex 镜

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| DX-04.1 | 新增 Node 阶段使既有 `docker compose build` 新增 npm 源依赖；离线部署只配 `UV_DEFAULT_INDEX` 会构建失败，DX-04 仍判 N/A | `design.md:627`；`docker-compose.yml:9`；`decision-memo.md:37` | 高 | 高 | 采纳 R-22 |
| DX-04.2 | `DEFAULT_TIMEOUT_MS` 过去对账号创建不生效，改为生效后既有部署行为变化；设计称「升级不改变既有部署行为」 | `design.md:623/79`；`schemas.py:41` | 高 | 中 | 采纳 R-22 |
| DX-04.3 | `TRUST_PROXY_HEADERS` 从「仅登录限速」扩为 Secure 判定，README 未更新 | `design.md:58`；`README.md:136` | 高 | 中 | 采纳 R-22/R-04 |
| DX-02.1 | 失败模式表与文案表同错不同文（密码/限速/会话过期） | `design.md:564-566` vs `:610-612` | 高 | 中 | 采纳 R-23 |
| DX-02.2 | 只给 `cache_ttl_seconds` 原文；其余可编辑字段与未知键无 problem/cause/fix | `design.md:614/81` | 高 | 中 | 采纳 R-23 |
| DX-02.3 | `FRONTEND_NOT_BUILT` 的 message 原文未定义；「请先运行 pnpm build」在镜像部署不可执行 | `design.md:119/618` | 中 | 中 | 采纳 R-23 |
| DX-01.1 | 前端 TTHW 无法由「1–3 分钟 + 1–2 秒」推出 4–6 分钟；未列 Node/pnpm 前置与 registry 参数 | `design.md:604` | 中 | 中 | 采纳 R-24 |
| DX-01.2 | TTHW 终点止于 `/healthz`，未覆盖「打开面板并登录」 | `design.md:603`；`README.md:42` | 中 | 中 | 采纳 R-24 |
| DX-03.1 | `FRONTEND_DIST` 未进命名/默认值清单与 README/.env.example；`DIR` vs `DIST` 无对照 | `design.md:115`；`tasks.md:68` | 中 | 中 | 采纳 R-25 |
| DX-03.2 | `NPM_REGISTRY` 与 `UV_DEFAULT_INDEX` 词形不一致，只写「语义同构」 | `design.md:624`；`.env.example:4` | 中 | 低 | 采纳 R-25 |

- 子代理计数：`counts: 高=5 中=5 低=0 未接地=0`。

## 对抗镜

### 隐藏假设（A1）

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| H-01 | 反代 HTTPS 下 Secure/客户端 IP 信任未闭环：无 X-Forwarded-Proto、TRUST_PROXY_HEADERS 默认 false | `config.py:81`；`README.md:129-136`；`entrypoint.sh:19` | 高 | 高 | 采纳 R-04 |
| H-02 | 回滚旧镜像在迁移阶段失败：DB 0002 vs 旧镜像 0001 | `entrypoint.sh:16`；`design.md:665`；`tasks.md:76` | 高 | 高 | 采纳 R-01 |
| H-03 | 0.1.0 tag 被本次 build 覆盖，切回 0.1.0 实际得到新代码 | `docker-compose.yml:12/14`；`README.md:157-158` | 高 | 高 | 采纳 R-01 |
| H-04 | 请求预算热更新只改 Scheduler，`public.py` 仍读静态 Settings | `public.py:200`；`design.md:77` | 高 | 中 | 采纳 R-02 |
| H-05 | `/docs` Bearer 工作流本身不成立：无 securitySchemes/Authorize；cookie 写操作还要 CSRF | `deps.py:51-59`；实测 `app.openapi()`；`README.md:42-43`；`design.md:55` | 高 | 中 | 采纳 R-49 |
| H-06 | settings 400 字段级承诺与全局 handler 冲突 | `main.py:157-167`；`design.md:360` | 高 | 中 | 采纳 R-05 |
| H-07 | `provider='auto'` 失败事件进 summary/overview，但 `PROVIDER_NAMES` 无 auto，providers 只列两家 | `models.py:134-137`；`public.py:28/271`；`base.py:111` | 高 | 中 | 采纳 R-52 |
| H-08 | 默认时间窗口未做本地日对齐；现有 summary 默认 `to=now(UTC)`、`from=to-7d` | `admin.py:503-504`；`design.md:417-418` | 高 | 中 | 采纳 R-12 |

- 子代理计数：`counts: 高=8 中=0 低=0 未接地=0`；判定 `refuted=true`。未爆点已核查：单实例/单
  事件循环、管理员 <20、npm 镜像、React 18 peer、常青浏览器、CSP/构建产物、数据规模 <10^5。

### 失败模式（A2）

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| A2-F1 | 回滚旧镜像迁移失败（与 H-02/P-03 同） | 同上 | 高 | 高 | 采纳 R-01 |
| A2-F2 | 请求预算只改 Scheduler（与 H-04/P-01 同） | 同上 | 高 | 高 | 采纳 R-02 |
| A2-F3 | 删除账号未清内存配额；2s flush 对已删除 id upsert 触发 FK 失败；id 复用继承旧用量 | `admin.py:370-385`；`quota.py:113-133`；`db.py:32` | 高 | 高 | 采纳 R-07 |
| A2-F4 | README 的 nginx 示例不传 X-Forwarded-Proto，HTTPS Secure 假绿 | `README.md:128-136` | 高 | 中 | 采纳 R-04 |
| A2-F5 | 登录轮换 CSRF cookie，其他标签页旧 token 写请求 403；原场景只覆盖 401 | `design.md:53/140/530` | 中 | 中 | 采纳 R-30 |
| A2-F6 | 并发 PUT settings 的提交/应用顺序可让 DB 与 runtime 分叉 | `design.md:75/80` | 中 | 中 | 采纳 R-10 |
| A2-F7 | summary 无 90 天上限 + 全量 materialize；NFR 未覆盖 | `admin.py:504-511`；`design.md:417/557` | 高 | 中 | 采纳 R-06 |
| A2-F8 | 删除实体后 null group key：混合排序 TypeError；多个已删除实体合并 | `models.py:116/122`；`design.md:401` | 中 | 中 | 采纳 R-11 |

- 子代理计数：`counts: 高=3 中=5 低=0 未接地=0`。

### 乐观估计与边界（A3）

| id | 问题 | 证据 | 置信 | 严重度 | 裁决 |
|---|---|---|---|---|---|
| A3-F1 | 回滚 DB 迁移 + 0.1.0 tag 被覆盖（与 H-02/H-03/P-03 同） | 同上 | 高 | 高 | 采纳 R-01 |
| A3-F2 | 300ms p95 的唯一证据不会进交付门：slow 无 marker/addopts；6.4 跑全量，采样/环境未定义 | `tasks.md:35/72`；`pyproject.toml:43`；`design.md:557` | 高 | 高 | 采纳 R-46 |
| A3-F3 | summary 无 NFR/90 天上限，10^5 或任意长 from 线性退化 | `admin.py:504-511`；`design.md:417/557` | 高 | 高 | 采纳 R-06 |
| A3-F4 | 总览首屏要 7 日折线但 overview 无 series；`/me` + overview + series 至少 3 请求；250KB 口径未定义 | `design.md:204/366-392/508/140/555` | 高 | 中 | 采纳 R-09/R-19 |
| A3-F5 | Secure cookie 反代不可达（与 H-01 同） | 同上 | 中 | 中 | 采纳 R-04 |
| A3-F6 | 并发 PUT settings 分叉（与 A2-F6 同） | 同上 | 中 | 中 | 采纳 R-10 |
| A3-F7 | 默认 7 日 + 本地桶 = 8 个桶；90 天与日期 to 叠加边界不清；跨月 reset_day 未测 | `design.md:417-418`；`tasks.md:29/33` | 中 | 中 | 采纳 R-12 |
| A3-F8 | 6.3 冒烟要求有数据，但无凭证环境无种子路径；7 路由/约 30 场景仅手工冒烟 | `tasks.md:70`；`specs/admin-api/spec.md:57`；`README.md:186` | 中 | 中 | 采纳 R-47 |

- 子代理计数：`counts: 高=4 中=4 低=0 未接地=0`；`truncated: yes`（该镜被截断，保留最严重的 8 条）。

## 接地镜（主 session）

核验方式：Read/grep 真实代码 + 只读命令；覆盖 design/memo 中全部 `file:line` 代码事实。结果：

| 事实 | 结论 |
|---|---|
| 20 个管理路由 / 19 个非登录路由全部经 `require_admin` | ✅ `grep -c '^@router'=20`；`require_admin` 引用 20（1 import + 19 使用） |
| `require_admin` 位置 `deps.py:41-60` | ⚠️ 实际 `require_admin` 为 `51-59`；41-48 是 `get_bearer_token`。仅行号范围偏宽，无实质不符；amendment 已改为 `41-59` |
| `_account_out` 无已用配额 `admin.py:93-117` | ✅ |
| `usage_summary` 无 label/avg `admin.py:495-535` | ✅ |
| `list_logs` 无时间过滤/total `admin.py:536-575` | ✅ |
| `_parse_time` `admin.py:483-493` | ✅ |
| `main.py:119` 只写 X-Request-ID | ✅ |
| `main.py:195-200` 只挂公共/管理路由 | ✅（同段含 BodyLimitMiddleware） |
| `cache.py:13-17` TTL/容量构造时固化 | ✅ |
| `scheduler.py:56-73` deadline 构造时固化 | ✅（构造为 60-71） |
| `registry.py:188` `available_count` | ✅ |
| `quota.py:61-63` `used()` | ✅ |
| `quota.py:19-26` `SHANGHAI` | ✅ |
| `models.py:110-142` `UsageEvent` 无 text 字段 | ✅ |
| `schemas.py:41` `timeout_ms` 默认 8000 | ✅ |
| `models.py:65/87` `timeout_ms NOT NULL` + `>0` | ✅ |
| `db.py:32` `PRAGMA foreign_keys=ON` | ✅ |
| `.gitignore:18-20` 预留 `node_modules/`/`frontend/dist/` | ✅ |
| `frontend/` 不存在；Dockerfile 无 Node 阶段；只有 `0001_initial` | ✅ |
| 137 个 `def test_` | ✅ |
| `config.py:70-80` 环境变量默认值 | ✅ |
| `docs/tech-selection.md:15/111/116/134/349/480-492/499-500/591/656` 引用 | ✅ 全部对读 |
| `README.md:28-50/42-43/128-136/150-158/174-178/186` 引用 | ✅ |
| `scripts/deploy.sh:60-61` / `scripts/rollback.sh` / `scripts/backup.sh` | ✅ 回滚脚本已含 integrity_check + 覆盖 DB |
| 设计 token 对比度：ink/paper ≥12:1、muted/paper ≥4.5:1 | ✅ 实测 16.48 / 5.19 |
| `pnpm@11.2.2` / `@fontsource-variable/ibm-plex-sans` / React 18 | ✅ `npm view` 经 npmmirror 返回 11.2.2 / 5.3.0 / 18.3.1 |
| OpenAPI 有 Bearer securityScheme | ❌ 实测 `components` 只有 `schemas`；已采纳 R-49 |

**接地结论**：除 `deps.py` 行号偏宽与 OpenAPI 无 securityScheme 外，design/memo 的代码事实全部成立；
未发现假引文。合并池中高严重度 finding 的引文已逐条亲验。

## 合并裁决

### 合并池（去重后）

| R-id | 合并后问题 | 命中镜 | 严重度 | 裁决 |
|---|---|---|---|---|
| R-01 | 回滚/发布：DB 0002 + 旧镜像迁移失败；0.1.0 tag 被覆盖 | strategy, plan-eng, A1, A2, A3 | 高 | 采纳；Q1 |
| R-02 | 请求总预算只改 Scheduler，`public.py` 外层仍读静态 Settings | plan-eng, backend, A1, A2 | 高 | 采纳；A1 |
| R-03 | 缓存 10000×256KB 最坏 2.5GB | plan-eng, backend | 高 | 采纳；Q2 |
| R-04 | 反代 HTTPS 下 Secure cookie 不可达（XFP/TRUST_PROXY_HEADERS） | plan-eng, backend, A1, A2, A3, devex | 高 | 采纳；Q4 |
| R-05 | settings 400 无字段名，与全局 handler 冲突 | strategy, plan-eng, backend, A1 | 高 | 采纳；Q3 |
| R-06 | summary 无 90 天上限 + 全量 materialize；NFR 未覆盖 | plan-eng, backend, A2, A3 | 高 | 采纳；A2 |
| R-07 | 删除账号未清内存配额，flush FK 失败/停摆 | plan-eng, A2 | 高 | 采纳；A3 |
| R-08 | request_deadline 60s vs stop_grace 25s | plan-eng, backend | 高 | 采纳；Q6 |
| R-09 | overview 无 series，首屏 3 请求，250KB 口径不清 | plan-eng, frontend, frontend-react, A3 | 高 | 采纳；Q5 |
| R-10 | 并发 PUT settings 的 DB/runtime 分叉 | strategy, plan-eng, A2, A3 | 中 | 采纳；A4 |
| R-11 | null group key：混合排序 TypeError；多个已删除实体合并 | plan-eng, A2 | 中 | 采纳；Q7 |
| R-12 | 时间窗口/默认 7 日/90 天/跨月边界 | strategy, plan-eng, A1, A3 | 中 | 采纳；A5 |
| R-13 | 静态兜底 spec 与 design 冲突 | strategy | 中 | 采纳；A6 |
| R-14 | 编辑账号 timeout null 撞 NOT NULL | strategy | 中 | 采纳；A7 |
| R-15 | settings PUT null 语义未定义 | strategy | 中 | 采纳；A8 |
| R-16 | reconfigure 参数顺序与构造函数相反 | strategy | 低 | 采纳；A9 |
| R-17 | Scheduler 注入 RuntimeSettings 路径未写 | strategy | 中 | 采纳；A10 |
| R-18 | settings.key TEXT vs VARCHAR(64) | strategy | 低 | 采纳；A11 |
| R-19 | 首屏 JS 预算口径 | strategy, frontend-react, A3 | 中 | 采纳；Q9 |
| R-20 | 安全头中间件顺序（BodyLimit 400 漏头） | strategy, plan-eng | 中 | 采纳；A12 |
| R-21 | available_accounts 语义 + GET 写副作用 | strategy, plan-eng, backend | 低 | 采纳；A13 |
| R-22 | 升级路径：NPM_REGISTRY/DEFAULT_TIMEOUT_MS/TRUST_PROXY_HEADERS | devex | 高 | 采纳；A14 |
| R-23 | 错误文案单一源/缺失字段/FRONTEND_NOT_BUILT | devex | 中 | 采纳；A15 |
| R-24 | TTHW 推导与终点 | devex | 中 | 采纳；A16 |
| R-25 | FRONTEND_DIST/NPM 命名与文档 | devex | 中 | 采纳；A17 |
| R-26 | 测活 15s 假超时 | frontend | 中 | 采纳；A18 |
| R-27 | login 401 被全局跳转吃掉；/me 非 401 无错误页 | frontend | 中 | 采纳；A19 |
| R-28 | GET 无条件重试 | frontend-react | 中 | 采纳；A20 |
| R-29 | mutationKey 不串行 | frontend-react | 低 | 采纳；A21 |
| R-30 | CSRF 双源/登录轮换 403/跨标签清缓存 | frontend, frontend-react, A2 | 中 | 采纳；A22 |
| R-31 | 单一 Suspense 骨架/筛选源三态 | frontend-react | 中 | 采纳；A23 |
| R-32 | ErrorBoundary 与 lazy 位置 | frontend-react | 低 | 采纳；A23 |
| R-33 | `/me` 加载边界与首屏往返 | frontend, frontend-react | 中 | 采纳；A24 |
| R-34 | 时间解析漏 recent_errors/summary | frontend | 中 | 采纳；A25 |
| R-35 | keepPreviousData 与「保留上一次结果」 | frontend | 中 | 采纳；A26 |
| R-36 | 深链接 CSP | frontend | 中 | 采纳；A27 |
| R-37 | returnTo/滚动/offset | frontend | 低 | 采纳；A28 |
| R-38 | 脏表单/跨标签 | frontend | 中 | 采纳；A29 |
| R-39 | CWV 无验收方式 | frontend | 低 | 采纳；A30 |
| R-40 | 最小宽度/360 登录溢出 | frontend | 低 | 采纳；A31 |
| R-41 | queryKey 失效图 | frontend-react | 低 | 采纳；A32 |
| R-42 | 缺 cookie 属性/`/me` 补发/settings 500 测试 | strategy | 中 | 采纳；A33 |
| R-43 | settings 备份/RPO/RTO | plan-eng, backend | 低 | 采纳；A34 |
| R-44 | SQLite busy_timeout/失败模式 | plan-eng, backend | 中 | 采纳；A35 |
| R-45 | 查询延迟可观测 | plan-eng, backend | 中 | 采纳；A36 |
| R-46 | 基准 slow marker/门禁 | plan-eng, A3 | 高 | 采纳；A37 |
| R-47 | 冒烟种子数据/可重复性 | plan-eng, A3 | 中 | 采纳；A38 |
| R-48 | 产物敏感值扫描/VITE 秘密 | strategy | 低 | 采纳；A39 |
| R-49 | `/docs` 无 Authorize securityScheme | plan-eng, A1 | 中 | 采纳；Q8 |
| R-50 | 缺 account-pool-scheduling/result-cache delta | strategy | 中 | 采纳；Q10 |
| R-51 | Compliance 缺两条既有豁免 | strategy | 低 | 采纳；A40 |
| R-52 | 时间格式/精度/recent_errors/auto provider | strategy, plan-eng, A1 | 中 | 采纳；A41 |
| R-53 | 登出不服务端吊销 token | A2（低） | 低 | 记录；X9 |
| R-54 | 登录响应体返回 Bearer token | 主 session | 低 | 记录；X8 |
| R-55 | `frontend_built` 时机 | strategy | 低 | 采纳；A42 |
| R-56 | `已删除` 与 null 不一致 | strategy | 低 | 采纳；A43 |

### 接地抽查

- 合并池 56 条中，**主 session 亲验引文 40 条**（占比 > 1/3，含全部高严重度条目）；未发现假引文。
- 发现并修正 1 条精度问题：`design.md:7` 的 `deps.py:41-60` 应为 `41-59`（无实质影响）。
- 子代理 findings 一律先视为「待接地」；本报告已把高严重度条目逐条落到主 session 亲验后的
  `file:line:quote`。低严重度中未亲验的条目已在对应表标为子代理引文，不冒充机械核验。

### 溯源三查（仅 [需拍板] 条目）

| Q | ① 全仓 grep 消费面 | ② `git log -S` | ③ 权威措辞对读 | 结论 |
|---|---|---|---|---|
| Q1 | `0.1.0` 仅 compose/`__version__`/pyproject/README；`scripts/rollback.sh` 已存在 | `.gitignore`/compose 历史见最近 checkpoint；回滚流程在 `2026-11-03-docker-deploy-e2e` 已定 | `deployment` R-DEP-08/09；`README.md:150-158` | 方案 A 可行，需补版本号 |
| Q2 | `cache_max_entries` 仅 config/design/cache；无字节预算 | 无 | `result-cache` R-CAC-02 只写默认值 | 压上限 2000 最小可行 |
| Q3 | `RequestValidationError` 全局 handler 唯一；settings 未实现 | 无 | `design.md:360` 与 `main.py:157-167` | 服务端字段级是唯一能兑现文案的做法 |
| Q4 | `TRUST_PROXY_HEADERS` 在 config/README/design；`X-Forwarded-Proto` 仅 design | 无 | `tech-selection` §11；`README.md:128-136` | README/反向代理补头最实 |
| Q5 | `overview` 只在 design/spec/tasks；无现有 series 复用 | 无 | `design.md:203-204/366-392` | 加 `series` 字段最省往返 |
| Q6 | `request_deadline_ms` 在 config/public/scheduler/design；`stop_grace_period` 在 compose | 无 | `deployment` R-DEP-08；`docker-compose.yml:28` | 压到 20s 最稳 |
| Q7 | `SET NULL` 在 models；`usage_summary` 用 `getattr`；无 snapshot 列 | 无 | `quota-accounting` R-QTA-05 只记录 id | 合并 null 行最简 |
| Q8 | `require_admin` 20 处引用；OpenAPI 无 securitySchemes | 无 | `README.md:42-43` 与实际能力矛盾 | 加 HTTPBearer 最优 |
| Q9 | `250KB` 仅 design/tasks；无 chunk 清单 | 无 | `tech-selection` §15 只要求类型检查+构建 | 拆预算最可测 |
| Q10 | `REQUEST_DEADLINE_MS` 在 account-pool-scheduling；TTL/容量在 result-cache | 无 | `design.md:77-81` | 补 MODIFIED delta 最稳 |

## Amendments（已应用）

> 以下改动均带 `[spec-review-amendment]` 标记；引用基线为 `33a0d61`。

### 四件套

- `design.md`
  - D-A1：Bearer 来源判定、`/me` csrf、Secure 判定/首跳、`/docs` HTTPBearer scheme、登出残留风险。
  - D-A2：settings 并发锁、`reconfigure` 参数顺序、Scheduler 注入、public 外层 deadline、timeout null、
    PUT null、字段级 400、cache 上限 2000、deadline 20s、DB 失败模式、settings RPO。
  - D-A3：label null、summary 90 天/SQL 聚合、null group key、auto provider、时间窗口、精度/错误定义、
    available_accounts、时间序列化。
  - D-A4：静态兜底扩展名规则、`FRONTEND_NOT_BUILT` message、安全头最外层、深链接 CSP。
  - D-A5：Suspense/ErrorBoundary、`/me` 并行、CSRF 单源、15s 覆盖、login skip、GET retry、
    mutation scope、query invalidation、时间解析、keepPreviousData、returnTo、脏表单、最小宽度、CWV。
  - D-A7：NPM_REGISTRY/FRONTEND_DIST 文档、VITE 扫密、版本 0.2.0。
  - 数据模型：`settings.key` 统一 TEXT；cache 上限 2000。
  - 接口契约：overview `series`、settings 400 `fields`、summary 90 天、auto provider。
  - 失败模式/可观测性/安全/Compliance/Risks/Migration Plan：补对应行与回滚 runbook。
- `proposal.md`：修正 `/docs` 工作流表述；补升级/回滚注意。
- `specs/admin-api/spec.md`：R-ADM-01/06/08/09 补 Bearer 无效不回退、summary 90 天、null 排序、
  auto、字段级 400、null 拒绝、时间窗口。
- `specs/admin-panel/spec.md`：R-PANEL-11 扩展名规则；R-PANEL-12 深链接 CSP；R-PANEL-04 超时留空。
- `specs/deployment/spec.md`：R-DEP-09 回滚场景改为「恢复匹配 schema 的备份」；新增 R-DEP-10
  不可变发布 tag。
- `specs/account-pool-scheduling/spec.md`（新增 MODIFIED）：R-SCH-03 deadline 来源。
- `specs/result-cache/spec.md`（新增 MODIFIED）：R-CAC-02 运行时 TTL/容量 + 变更清空。
- `tasks.md`：1.1/1.2/2.1/2.3/2.4/3.1/3.2/3.3/3.5/4.1/4.3/4.4/5.1/5.3/5.6/6.1/6.3/6.4/6.6 与
  测试覆盖图同步；补 slow marker/种子数据/回滚 runbook。

### 未修订（记录）

- `decision-memo.md` 不改：D1–D11 是人的拍板记录，不在评审中改写；C12 的 TEXT 与 design 已统一。
- `README.md`/`docker-compose.yml`/`Dockerfile` 不在四件套内，改动由 tasks 6.1/6.2 承接；本报告只
  给要求。

## T/S 残差

无。`openspec validate m3-admin-panel --strict` 通过；四件套规则槽位已逐项核对：

- proposal：`## Why` / `## Success Metrics` / `## Non-Goals` / `## Compliance` 均在；需求优先级、
  假设、利益相关方、开放问题/外部成本已按触发词加节。
- design：`## Compliance` 在；数据模型/失败模式+可观测性/NFR/安全/决策记录/组件图/切片均在。
- specs：每个 Requirement 有稳定 ID 与 `#### Scenario`；新能力 `admin-panel` 有 `## Purpose`；
  MODIFIED 块完整复制。
- tasks：每个任务带 `R-ID` 与验证方式；测试覆盖图存在。

## 诚实边界

- 同模型 fresh-context：7 个子代理隔离的是上下文，不是模型盲点；广审双镜与接地镜由主 session
  亲做，存在自查偏置。没有跨模型第二意见。
- 子代理 A3 结果被截断（`truncated: yes`），只保留最严重 8 条；已在该镜注明。
- 接地抽查覆盖全部高严重度条目，但低严重度条目未逐条亲验；报告已标「子代理引文」，不冒充
  机械核验。
- 设计 token 对比度、npm 版本、OpenAPI securityScheme 已实测；p95/JS 体积未实测，报告给的是
  可验证目标而非实测值。

## 结论

建议进入设计 HARD-GATE。**不建议在 Q1/Q2/Q4/Q5/Q6/Q8 拍板前开工**：这六项会改变发布回滚、
内存边界、反代安全、首屏契约、停机预算与 `/docs` 可用性。其余自动决策已落进四件套，人工可覆盖。
