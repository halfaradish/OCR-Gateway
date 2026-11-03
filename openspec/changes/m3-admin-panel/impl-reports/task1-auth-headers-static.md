---
ticket: 1
title: 后端鉴权、安全头与静态托管骨架
head: bbeda419f9388edc6731659d6253c17b17c10e81
status: DONE_WITH_CONCERNS
suite_scope: {"domains":["backend"],"layers":["unit"],"base":"bbeda41","mode":"closeout"}
---

# Task 1 · 后端鉴权、安全头与静态托管骨架

## 改动

- **双轨鉴权**（`backend/app/api/deps.py`）：`require_admin` 先读原始 `Authorization` 头——Bearer 有效放行、
  Bearer 存在但无效直接 401（不回退 cookie）；无 Authorization 时读 `ocr_admin_session` cookie，cookie 来源的
  非安全方法校验 `X-CSRF-Token` 与 `ocr_csrf` 常量时间相等，失败 403 `FORBIDDEN`；`HTTPBearer(auto_error=False)`
  单独声明 security scheme，使 `/docs` 的 Authorize 可用。新增 `request_is_https`（直连 TLS 或受信反代的
  `X-Forwarded-Proto: https`）、`set_admin_cookies` / `set_csrf_cookie` / `clear_admin_cookies`。
- **登录 / 当前管理员 / 登出**（`backend/app/api/admin.py`）：登录返回 `token`/`expires_in`/`csrf_token` 并
  设置两个 cookie（session `HttpOnly`、CSRF 可读，均 `SameSite=Lax`、`Path=/`、`Max-Age=session_ttl`、HTTPS 下
  `Secure`）；`/me` 仅 cookie 会话返回 `csrf_token`，缺失时补发 CSRF cookie 且不重发会话 cookie；`/logout`
  清空两个 cookie 并返回 204；登录成功/失败补结构化日志（只记 IP 与原因，不记密码）。
- **安全响应头**（`backend/app/security_headers.py`）：纯 ASGI 中间件，在 `BodyLimitMiddleware` 之后 add（最外层）。
  所有响应加 `X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options`、`Permissions-Policy`；面板 HTML 与
  `/assets` 静态资源加 CSP（`script-src 'self'`）；`/docs`、`/openapi.json`、`/redoc` 与 API 响应不加 CSP；
  管理 API 加 `Cache-Control: no-store`。
- **静态托管**（`backend/app/panel.py`）：产物存在时根路径/深链接返回 `index.html`（`no-store`），`/assets` 由
  `StaticFiles` 托管并覆盖为一年 `immutable` 缓存，根级静态文件按 3600s 缓存；带扩展名的缺失文件、`api/`、`v1/`、
  `healthz` 前缀路径返回 JSON 404 不回退 HTML；`_resolve_within` 拒绝 `..`/越界路径；产物缺失或不可读时根路径
  返回 404 `FRONTEND_NOT_BUILT` 且 API 不受影响。兜底路由注册在所有 API 路由之后。
- **配置与装配**：`FRONTEND_DIST`（默认 `<repo>/frontend/dist`）加入 `Settings`；`main.py` 增加
  `StarletteHTTPException` 处理器把 400/404/405 归一化到统一错误 envelope；`conftest.settings` 把
  `frontend_dist` 指向临时目录，避免本地构建产物影响单测。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `uv run --project backend pytest backend/tests/test_m3_ticket1_panel_auth.py -q` | 0 | 15 | bbeda41 |
| 回归 pytest（管理端 + body limit） | `uv run --project backend pytest backend/tests/test_ticket2_admin.py backend/tests/test_followup_t1_body_limit.py -q` | 0 | 25 | bbeda41 |
| 全量 pytest | `uv run --project backend pytest backend/tests -q` | 1 | 166 passed, 1 failed, 2 skipped | bbeda41 |
| ruff | `uv run --project backend ruff check backend` | 0 | 未知 | bbeda41 |
| mypy | `uv run --project backend mypy backend/app` | 0 | 未知 | bbeda41 |

SHA 为测试运行时的 HEAD（本票改动尚未提交；报告与本票改动在同一 checkpoint 提交入库）。全量 pytest 的
唯一失败是既有红测，见下节。

## 既有红测

- `backend/tests/test_ticket5_api.py::test_run_docs_cover_quickstart_and_operations` 失败：断言 `README.md` 含
  `sqlite3` 与 `.backup`，但 `git show HEAD:README.md | grep -c sqlite3` 为 `0`，即分支起点就红，与本票改动无关。
  处置：fold 到 Task 6（该票本就要重写 README 的部署/备份/回滚段），记录见 `impl-reports/planning-decisions.md` §5；
  本票不顺手改。

## concerns

- **JSON body 端点上的超限请求**：FastAPI 在解析 Pydantic body 时会把 `BodyTooLarge` 转成 `HTTPException(400)`，
  因此这类请求的错误 message 变为统一的 `invalid request`（code 仍是 `BAD_REQUEST`）。body limit 的
  `request body exceeds the size limit` 原文只在自行读取 body 的端点（如 `/v1/ocr/image`）保留。安全头在两条路径上
  都齐备。
- **cookie 会话不滑动续期**：`/me` 只补发 CSRF cookie，不刷新会话 cookie 的 `Max-Age`（避免 GET 改会话时长）。
  管理员在 12h 到期后需重新登录，符合设计。
- **`request.state.admin_auth_source`** 由 `require_admin` 写入、仅 `/me` 消费；所有管理路由都经该依赖，故
  `getattr` 默认值只对理论上的绕过路径生效。
- **`/healthz` 不加 CSP**：CSP 只作用于面板文档与静态资源，JSON 健康检查响应不带（与设计一致）。
