---
ticket: 6
title: 交付、镜像与验收
head: 6cade4b5fd188ab2c2d38a49a03d442cb054d05a
status: DONE
suite_scope: {"domains":["backend","frontend","docs"],"layers":["unit","slow","quality"],"base":"6cade4b","mode":"closeout"}
---

# Task 6 · 交付、镜像与验收

## 改动

- **镜像**（`Dockerfile`）：新增 `frontend-builder` 阶段（`NODE_IMAGE` 可参数化的 Node 22 + pnpm 11.2.2，
  `NPM_REGISTRY` 同时用于安装 pnpm 与依赖，先拷 `package.json`/`pnpm-lock.yaml`/`pnpm-workspace.yaml`
  再拷源码，依赖层可缓存）；运行阶段 `COPY --from=frontend-builder /app/frontend/dist /app/static` 并
  `ENV FRONTEND_DIST=/app/static`；`.dockerignore` 排除 `**/node_modules` 与 `frontend/dist`。
- **版本与 tag**：`app.__version__` 与 `backend/pyproject.toml` 升 `0.2.0`（`uv.lock` 同步），
  `docker-compose.yml` 的 `image`/`build.tags` 改为 `ocr-gateway:0.2.0` + `latest`，**`0.1.0` 保持不覆盖**
  （构建前后 `docker image inspect` 的 image id 一致：`sha256:985e2871…`）。
- **配置与文档**：`docker-compose.yml` 增加 `NPM_REGISTRY` 构建参数；`.env.example` 增加 `NPM_REGISTRY`、
  `FRONTEND_DIST`、`TRUST_PROXY_HEADERS` 与说明；`README.md` 重写面板入口、前端开发/构建、环境变量表
  （含 `DIST` vs `DIR`、`DEFAULT_TIMEOUT_MS` 语义变化、`TRUST_PROXY_HEADERS` 新用途）、nginx 的
  `X-Forwarded-Proto`、HTTPS/cookie、升级/回滚顺序、`sqlite3 .backup` 备份命令、测试命令、私有凭证文档代称。
- **质量门配置**：`openspec/sdflow-lite.json` 增加 `frontend/` 域与 `quality` 层（lint+typecheck+build），
  使收尾验证能机械覆盖前端改动（无用例计数 → 报告为「用例数不可得」）。
- **响应式修正（视觉验收发现）**：表格 `min-width` 改为 `md:` 以上生效；窄屏隐藏次要列（账号页保留
  名称/状态/操作，操作用 `<details>` 折叠；日志保留时间/状态/错误码；用量保留维度/请求）。
- **`pnpm-workspace.yaml`**：设置 `minimumReleaseAge: 0`（锁文件已固定 integrity；release-age 策略会让
  镜像里基于 mirror 的 `pnpm install --frozen-lockfile` 直接失败）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 后端全量 | `uv run --project backend pytest backend/tests -q` | 0 | 214 passed, 2 skipped, 1 deselected | 6cade4b |
| 后端基准 | `uv run --project backend pytest -m slow -q` | 0 | 1 | 6cade4b |
| 后端 ruff | `uv run --project backend ruff check backend` | 0 | 未知 | 6cade4b |
| 后端 mypy | `uv run --project backend mypy backend/app` | 0 | 未知 | 6cade4b |
| 前端 lint / typecheck / build | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build` | 0 | 未知 | 6cade4b |
| e2e 鉴权/骨架 | `E2E_BASE_URL=http://127.0.0.1:8765 … node e2e/smoke.mjs` | 0 | 14 checks | 6cade4b |
| e2e 管理页 | `E2E_BASE_URL=http://127.0.0.1:8765 … node e2e/admin.mjs` | 0 | 32 checks | 6cade4b |
| e2e 窄屏视觉 | `E2E_BASE_URL=http://127.0.0.1:8765 … node e2e/visual.mjs` | 0 | 6 checks | 6cade4b |
| 镜像构建 | `NPM_REGISTRY=https://registry.npmmirror.com docker compose build` | 0 | 未知 | 6cade4b |

**镜像冒烟**（`ocr-gateway:0.2.0`，临时数据卷）：

- `/healthz` 200；`/` 200 `text/html`；`/assets/index-*.js`、`/assets/index-*.css` 200，资源带
  `Cache-Control: public, max-age=31536000, immutable`；缺失资源与 `/api/nope` 均为 JSON 404；`/docs` 200。
- 登录返回会话 + CSRF cookie；带 `X-Forwarded-Proto: https`（`TRUST_PROXY_HEADERS=true`）时两个 cookie
  都带 `Secure`；无该头时不带 `Secure`。
- 通过 API 创建成员 / Key（明文 47 字符、列表只有前缀）/ 账号；灌入 30 条用量事件后 `/overview`、
  `/usage/summary`、`/logs`、`/settings`、`/accounts` 均返回数据。
- `grep -rlE "MASTER_KEY|ADMIN_PASSWORD|<测试密钥>|password123" /app/static/` → 无命中。

**回滚演练**：

1. 用 Alembic 造 0001 库并留「部署前备份」；2. `0.2.0` 启动 → 迁移到 `7c1f0d2a9b31`，`/` 200；
3. 同一库直接起 `0.1.0` → entrypoint 退出 255，日志 `Can't locate revision identified by '7c1f0d2a9b31'`
   （与 README 描述一致）；4. 覆盖部署前备份（0001）后 `0.1.0` → `/healthz` 200、登录 200、`/` 404 JSON；
5. 再起 `0.2.0` → 迁移成功、`/` 200 HTML。全程 `0.1.0` image id 未变。

**视觉验收**：七个路由在 1440px 与 360px 两套截图（`review/e2e-task5/`、`review/e2e-task6/`）逐项核对
token/结构/黑名单：浅色单主题、深墨蓝、发丝线、无渐变/投影、状态点+文字、配额刻度标尺、表格数字右对齐、
360px 无横向页面溢出、侧栏收为抽屉、窄屏保留关键列。发现并修正：表格 `min-width` 在窄屏强制横向滚动、
账号页操作列被挤出视口（改为 `<details>` 折叠）。

## concerns

- **`minimumReleaseAge: 0`**：关闭了 pnpm 的发布时长门禁，否则镜像内的 frozen 安装会被策略拒绝。
  锁文件仍固定每个包的 integrity；如果后续要恢复该策略，需要把当前锁文件的版本逐个写进
  `minimumReleaseAgeExclude`。
- **INP 仍无 lab 实测值**（同 Task 4）：Lighthouse 报告给的是 LCP 0.9s / CLS 0 / TBT 0ms；INP 需真实用户
  监控，本 change 不引入 RUM。
- **镜像体积**：`0.2.0` 约 226 MB（0.1.0 为 225 MB），前端产物与 pnpm 依赖层没有跨阶段保留；增长约 1 MB。
- **窄屏操作折叠用原生 `<details>`**：未引入下拉菜单组件，展开后是纵向按钮组；可访问性依赖原生语义。
- **回滚演练在本机 Docker 完成**：0.1.0/0.2.0 镜像均为本地构建，未经过 registry 分发；异地部署需自行
  准备 0.1.0 镜像。
