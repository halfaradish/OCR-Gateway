---
ticket: 4
title: 前端骨架、设计系统与总览
head: 8a389b83cfd2179f52baa894e316b4aaefe20654
status: DONE_WITH_CONCERNS
suite_scope: {"domains":["frontend","backend"],"layers":["lint","typecheck","build","e2e"],"base":"8a389b8","mode":"ticket"}
---

# Task 4 · 前端骨架、设计系统与总览

## 改动

- **工程骨架**（`frontend/`）：Vite 7 + React 18 + TypeScript strict（`noUncheckedIndexedAccess`）+
  Tailwind v4（`@tailwindcss/vite`）+ ESLint（typescript-eslint、react-hooks、jsx-a11y）；pnpm 锁文件；
  dev 代理 `/api`、`/v1`、`/healthz` 到 `127.0.0.1:8000`；`lint`/`typecheck`/`build` 三个脚本；
  `build.modulePreload.polyfill=false` 且 `assetsInlineLimit=0`（不留内联脚本/字体 data URI，配合 CSP）。
- **设计系统**（`src/index.css` + `src/components/`）：D-A6 token 落地为 `@theme`（paper/surface/ink/
  muted/line/mist/navy/blue/success/warn/danger、28/20/15/13/12 字号、4/6px 圆角）；自托管
  IBM Plex Sans Variable；组件 Button/Input/Select/Dialog/Table/Switch/Label/Skeleton 及
  StatusDot（圆点+文字）、QuotaRuler（25/50/75 刻度 + 位置标记）、MetricStrip、PageHeader、
  EmptyState/ErrorState；无渐变、无投影、无 emoji 图标、组件内无裸色值（图表色在 `lib/palette.ts` 注明同步）。
- **鉴权与数据层**：`apiFetch` 统一 `credentials: same-origin`、写方法从 `ocr_csrf` 读 token 加
  `X-CSRF-Token`、15s 超时（可按请求覆盖）、204 不解析、错误 envelope 归一化、401 抛
  `SessionExpiredError` 并广播全局事件、403 写请求刷新 `/me` 后单次重试；`AuthProvider` 启动请求
  `/me`、维护 booting/authed/anon/error 四态，登出清 React Query 缓存；`createQueryClient` 设定
  30s staleTime、窗口聚焦刷新、仅网络/5xx 重试一次、写操作不重试。
- **路由与外壳**：`/login`、`/`、`/accounts`、`/members`、`/usage`、`/logs`、`/settings`、`*`（404）；
  页面级 `React.lazy`，每路由 `RouteBoundary`（ErrorBoundary 包在 Suspense 外层，fallback 与最终尺寸同高）；
  侧栏 232px（1280+）/208px（768–1279），`<768` 抽屉导航；顶栏 56px；内容最大宽 1280px。
- **登录页**：360px 居中列、wordmark、RHF+zod 单字段校验、错误就地显示（`skipAuthRedirect` 使 401
  显示「密码不正确」而不是会话过期）、`returnTo` 同源相对回跳。
- **总览页**：指标条（今日请求/成功率/缓存命中/平均延迟）、厂商行、近 7 日折线（Recharts，固定 220px
  高度、发丝网格、`isAnimationActive=false` 保证确定性渲染与 reduced-motion）、账号配额标尺
  （月为主、`<details>` 展开日/总量、三项全空显示「未配置额度，可能超用」）、最近错误表、缓存页脚；
  加载骨架/空态/错误重试三态齐备。
- **e2e 冒烟**（`frontend/e2e/smoke.mjs`，puppeteer-core 驱动系统 Chrome）：14 项检查，截图落在
  `openspec/changes/m3-admin-panel/review/e2e-task4/`。
- **后端配合修复**：`app/panel.py` 的 `index.html` 改为**每请求读取**（原先启动时缓存字节，重建后
  进程仍在返回引用已删除 hash 资源的旧外壳，页面白屏）；补 `test_panel_index_is_reread_after_rebuild`。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| frontend lint | `pnpm --dir frontend lint` | 0 | 未知 | 8a389b8 |
| frontend typecheck | `pnpm --dir frontend typecheck` | 0 | 未知 | 8a389b8 |
| frontend build | `pnpm --dir frontend build`（经 `registry.npmmirror.com` 安装） | 0 | 未知 | 8a389b8 |
| e2e 冒烟 | `E2E_BASE_URL=http://127.0.0.1:8765 E2E_ADMIN_PASSWORD=… pnpm --dir frontend e2e` | 0 | 14 checks | 8a389b8 |
| 后端面板回归 | `uv run --project backend pytest backend/tests/test_m3_ticket1_panel_auth.py -q` | 0 | 16 | 8a389b8 |
| 后端全量 | `uv run --project backend pytest backend/tests -q` | 1 | 213 passed, 1 failed（既有红测）, 2 skipped, 1 deselected | 8a389b8 |
| backend ruff / mypy | `uv run --project backend ruff check backend` / `mypy backend/app` | 0 | 未知 | 8a389b8 |

e2e 覆盖：密码错误就地提示、登录进入总览、web storage 无 token、总览指标与配额标尺渲染、刷新保持登录、
**旧 CSRF cookie 下写操作（登出）刷新后重试成功**、**会话 cookie 失效后 401 统一跳登录**、未登录深链接跳登录、
登录回跳原路由、六个受保护路由可达、未知路径 404、无 CSP 违规、控制台无错误。

**体积**（Vite 构建输出 gzip）：

| 产物 | gzip |
|---|---|
| 登录 + 壳（`index` + `login-page` chunk） | 105.78 + 38.26 = **144.04 kB**（预算 ≤150 kB） |
| 总览路由 chunk（含 Recharts） | **112.26 kB**（预算 ≤350 kB） |
| CSS | 5.81 kB |

**Lighthouse**（2026-11-04，移动端模拟 4G，第 1 次运行，对象 `/login`，报告
`review/lighthouse-login.json`）：Performance 100；FCP 0.9s、**LCP 0.9s**（≤2.5s）、**CLS 0**（≤0.1）、
TBT 0ms；**INP 无 lab 实测值**（见 concerns）。

## concerns

- **INP 无法在 lab 中测量**：Lighthouse lab 模式不采样交互，报告里没有 INP 字段。已记录 TBT=0ms 作为
  代理指标，并在 Task 6 的视觉/镜像验收中保留真实浏览器交互冒烟；未虚构 INP 数值。字段级 INP 只能在
  真实用户监控里得到，本 change 不引入 RUM。
- **e2e 依赖系统 Chrome**：脚本按 `CHROME_PATH` → 常见安装路径探测；镜像/CI 环境需安装 Chrome。已写入
  README 的前端开发说明（Task 6 复核）。
- **Task 5 页面在本票里是占位页**：路由与 404 在 Task 4 已可达，五个管理页由 Task 5 替换为真实实现，
  占位文案不会进入交付态。
- **Lighthouse 只测 `/login`**：受保护页需要会话，lab 模式无法带 cookie；首屏入口即登录页，体积与 LCP
  以它为准，总览 chunk 体积另行计量。
- **图表颜色常量**：`lib/palette.ts` 与 `index.css` 的 token 需手工同步（Recharts 只接受字面值），
  已在文件头注明。

## 票外发现

- **`test_ticket5_api.py::test_run_docs_cover_quickstart_and_operations`** 仍是既有红测（README 缺
  `sqlite3`），按 Task 1 的 fold 决策留到 Task 6 修。
