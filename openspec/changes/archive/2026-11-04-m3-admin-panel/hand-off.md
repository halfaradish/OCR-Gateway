# Hand-off · m3-admin-panel

## ✅ 完成了什么

每条都复核过锚点存在（代码/测试/证据文件），不只搬运 verify 的结论：

- **管理端 cookie + CSRF 双轨鉴权**（保留 Bearer）：登录/`/me`/登出、会话与 CSRF cookie 属性、403
  写保护、OpenAPI Bearer scheme。锚：`backend/app/api/deps.py`、`admin.py`；16 个端点用例。
- **安全响应头与同源静态托管**：nosniff/Referrer-Policy/X-Frame-Options/Permissions-Policy 全覆盖，
  面板 CSP（`script-src 'self'`）、管理 API `no-store`，SPA 兜底规则与产物缺失 404
  （`FRONTEND_NOT_BUILT`），`index.html` 每请求读取（重建后不再白屏）。锚：`security_headers.py`、
  `panel.py`；浏览器冒烟无 CSP 违规。
- **运行时设置**：`settings` 表 + `0002` 迁移、env 默认合并、非法值回退、单事务 upsert + 锁串行化、
  提交后应用、缓存重建、字段级错误、DB 失败 500 且不生效。锚：`runtime_settings.py`、24 个用例。
- **数据面**：总览、日序列、汇总扩展（label/平均延迟/null 排序/90 天上限）、日志过滤与总数与名称、
  账号配额与归属、删除账号清理配额。锚：`analytics.py`、22 个用例 + 10 万条 slow 基准
  （p95 8–24ms）。
- **前端面板**：Vite/React 18/TS strict/Tailwind v4，设计 token 与自建组件（状态点、配额刻度标尺、
  指标条），登录/总览/账号/成员与 Key/用量/日志/设置七个路由，URL 即状态、CSV 导出（BOM+CRLF+RFC4180）、
  三态、写操作防双击、脏表单离开确认、窄屏抽屉与关键列保留。锚：`frontend/`；smoke 14 + admin 32 +
  visual 6 项浏览器检查与 1440/360 两套截图。
- **交付**：镜像新增前端构建阶段（`NPM_REGISTRY` 可参数化）、运行镜像内置 `/app/static`、版本升
  `0.2.0` 且 `0.1.0` 不可变、README/.env.example 全面更新（含 nginx `X-Forwarded-Proto`、升级与
  回滚顺序、`sqlite3 .backup`）。锚：`Dockerfile`、compose、镜像冒烟与回滚演练记录。

## ⏳ 未完成延后

扫 `openspec/issues/open/*.md` 中 `source_change: m3-admin-panel`：

- **T4**（todo，OPEN）：管理表单字段级错误未设 `aria-invalid`/`aria-describedby`。
- **T5**（todo，OPEN）：日志/用量筛选输入逐字符触发请求，建议 300ms 防抖。

两条都是 Minor、不阻塞交付；本 change 的 verify 判 PASS 时它们仍是未交付项，故状态保持 OPEN。

另外两处「已知但不算交付缺口」：

- INP 没有 lab 实测值（Lighthouse 给 LCP 0.9s / CLS 0 / TBT 0ms）；要拿 INP 需引入真实用户监控，
  不在本 change 范围。
- `QuotaManager.flush` 整批失败的老问题未改（既有代码；当前无产生孤儿计数的路径）。

## ▶ 下一阶段建议

1. **收掉 T4/T5**（半个工作段的量）：表单 a11y 统一 + 筛选防抖，顺手补一轮 e2e 断言。
2. **M4 本地 OCR**：设置页已预留结构，M4 落地后补真实开关与 worker 状态；届时 `default_timeout_ms`
   之外可能需要新的运行时项（如本地并发）。
3. **观测性**：`admin.query` 已有结构化日志，M5 接 Prometheus 时可直接把这些事件转成指标
   （面板查询耗时、缓存命中、设置变更）。
4. **多实例**：当前设置热更新是单进程语义；若将来多实例，需要 settings 变更广播（或每请求读 DB），
   已在设计代价里注明。服务端会话吊销（登出即时失效）也可作为独立 change。
