# OCR Gateway

单实例 OCR 网关：把百度智能云与腾讯云的通用文字识别聚合成一个统一的 HTTP API，按账号优先级与
EWMA 延迟选号、失败自动切换，并按厂商账号与网关 API Key 记账配额。管理端提供 Web 管理面板
（登录、总览、账号、成员与 Key、用量、日志、设置），同时保留 Bearer token + `/docs` 的脚本工作流。

## 能力边界

- 单张图片 OCR：`POST /v1/ocr/image`，支持 multipart 文件、JSON base64、JSON `image_url` 三选一。
- 厂商：百度 `general_basic`、腾讯 `GeneralBasicOCR`；`provider=auto` 可跨厂商切换，显式
  `provider` 不跨厂商回退。
- 账号池：优先级、EWMA 延迟、并发上限、QPS 令牌桶、冷却/失效/配额耗尽状态与惰性恢复。
- 配额：账号日/月/总量、Key 日限额与 RPM；内存计数每 2 秒批量落 SQLite。
- 缓存：进程内 TTLCache，键为 `sha256(image) + language + provider`，空文本与 >256KB 结果不缓存。
- 管理面板：SPA 由 FastAPI 同源托管，cookie + CSRF 双轨登录（Bearer 仍然可用），七个路由
  （登录/总览/账号/成员与 Key/用量/日志/设置），运行时设置热更新，CSV 导出。
- 本地 OCR：RapidOCR（onnxruntime CPU）随发布镜像内置，模型随 wheel 分发、不联网下载；默认关闭，
  设置页开启后由 `provider=auto` 在云厂商全部不可用时兜底，显式 `provider=local` 需先开启。
- 不做：多实例/多 worker、任务队列、批量接口、PDF、Prometheus `/metrics`、SSR、
  深色主题、实时推送（WebSocket/SSE）。

## 快速开始（Docker Compose，约 2 分钟\*）

> \* TTHW 为**估算**：命令数 3 条、步骤数 3 步；热路径假设 = `cp` + 填写 `.env` 约 1 分钟、
> `docker compose up -d` 到容器健康约 30–90 秒、打开面板并登录约 10 秒。**不含首次镜像构建**
> （约 5–10 分钟：Python 依赖 + 前端 pnpm 依赖，取决于网络与本地缓存），首次构建耗时单独计入部署
> 总时长，不计入「一键起」。

前置：Docker 与 Docker Compose v2+。

```bash
# 1. 配置环境变量（约 1 分钟；MASTER_KEY 32 字节、ADMIN_PASSWORD ≥8 字符）
cp .env.example .env

# 2. 构建并启动（容器自动执行迁移后启动服务；前端在镜像内构建）
docker compose up -d

# 3. 等待健康（约 30–90 秒），然后打开面板登录
curl -i http://127.0.0.1:8000/healthz
# 浏览器访问 http://127.0.0.1:8000/ ，用 ADMIN_PASSWORD 登录
```

宿主机端口默认 `8000`，可在 `.env` 中用 `HOST_PORT` 覆盖（容器内始终监听 `8000`）。改端口后，
上面及下文的访问地址、反代目标需一并替换，例如 `HOST_PORT=18000` 对应
<http://127.0.0.1:18000/>。

本地 OCR 无需额外部署步骤：发布镜像已内置 `local` extra 与模型，管理员在设置页开启后约 1–3 秒
预热到 `ready`（本机实测约 2.4s，**估算**）；随后 `provider=auto` 在云厂商全部不可用时自动兜底。

容器主进程以非 root 运行，业务数据落在宿主 `./data`（SQLite），进程日志走 stdout 由容器日志驱动
轮转（`max-size` / `max-file`）。

两种操作方式并存：

- **面板**：<http://127.0.0.1:8000/>，cookie + CSRF，适合日常运营。
- **脚本/curl**：<http://127.0.0.1:8000/docs>，`POST /api/admin/login` 拿 Bearer token，再在右上角
  Authorize 填入，即可完成全部管理动作。Bearer 路径不校验 CSRF。

健康检查：`GET /healthz`（不鉴权），数据库可用返回 200，否则 503；编排侧以此判定 `healthy`。
面板产物不存在时根路径返回 404 `FRONTEND_NOT_BUILT`，API 不受影响。

## 本机开发（uv + pnpm）

前置：Python 3.11+、`uv`、Node 22 + pnpm 11、可用的 SQLite，且默认包索引可达。离线环境下需设
`UV_DEFAULT_INDEX`（Python）与 `NPM_REGISTRY`（npm，构建期）；**避免非 frozen 的 `uv sync` 改写
被跟踪的 `uv.lock`**（用 `--frozen` 或 `UV_FROZEN=1`）。

```bash
# 1. 后端依赖（首次约 1–3 分钟）
uv sync --project backend

# 1b. 需要本地 OCR 时再装 optional extra（发布镜像已内置，本机开发可选）
uv sync --project backend --extra local

# 2. 配置环境变量（把 .env.example 复制为 .env 并填写真实值）
cp .env.example .env

# 3. 建库
uv run --project backend alembic -c backend/alembic.ini upgrade head

# 4. 启动后端（单 worker）
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1

# 5. 前端（另开一个终端；首次安装约 1–3 分钟）
pnpm --dir frontend install --registry https://registry.npmmirror.com
pnpm --dir frontend dev      # http://127.0.0.1:5173 ，/api /v1 /healthz 代理到 8000
```

首次上手约 4–6 分钟（按上表区间相加，估算），后续热启动 <1 分钟。默认 npm 源不可达时用
`--registry` 或仓库外的本地 `.npmrc`。

生产形态不需要 dev server：`pnpm --dir frontend build` 产出 `frontend/dist`，后端启动时读取
`FRONTEND_DIST`（默认 `<repo>/frontend/dist`）同源托管。

前端质量门：

```bash
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build
# 本地 OCR 面板 e2e（需服务端已安装 local extra 并运行中）
pnpm --dir frontend e2e:local
```

## 本地 OCR

- **依赖与模型**：`rapidocr` + `onnxruntime` 作为 optional extra `local` 声明在
  `backend/pyproject.toml`，发布镜像用 `uv export --extra local` 安装；PP-OCRv6 small 模型随
  wheel 分发，识别路径不发起网络请求。模型许可证为 Apache-2.0（PaddleOCR），再分发时保留本说明。
- **开关**：设置页「本地 OCR」开关（`local_ocr_enabled`，默认关闭，热更新）；关闭时显式
  `provider=local` 返回 403。依赖缺失时状态为 `unavailable`，开关禁用。
- **路由**：`provider=auto` 在云厂商无候选/全部可重试失败后兜底本地；云阶段为本地预留
  5s（预算不足 6s 时自动收缩，见 design 的 `reserve_eff` 不变量）；显式 `provider=local`
  直接走本地，不回退云厂商。
- **配额**：本地成功 `quota.used=0`、`account_id=NULL`、`provider='local'`，不计入用户日限额；
  仅受 Key RPM 与全局并发约束（M4 接受的边角，后续若需本地限额另开 change）。
- **观测**：`GET /api/admin/local-ocr/status` 返回 worker 状态、模型、最近耗时/错误、有效超时与
  预留、请求/兜底计数；`/v1/providers` 与用量/日志标签包含「本地 RapidOCR」。
- **镜像冒烟**：`backend/.venv/Scripts/python.exe scripts/smoke_local_ocr.py --port 18080`
  会起一个临时容器，验证 `ready`、显式 local、auto 兜底与关闭后的 403。
- **镜像体积**：0.3.0 镜像约 559MB，较 0.2.0（约 226MB）增加约 333MB（本机实测；`/app/.venv`
  432MB，主要来自 onnxruntime/opencv/numpy + 模型约 32MB）；worker 常驻约 200–300MB（估算）。
  默认关闭时不占 CPU/内存。
- **回滚**：先关闭本地开关，再停 0.3.0 容器；用 0.3.0 镜像执行
  `alembic -c /app/alembic.ini downgrade -1`（local 行映射为 `auto`，需 `--entrypoint` 覆盖）
  后启动 0.2.1；或直接用部署前备份恢复数据库。

## 环境变量

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `MASTER_KEY` | 是 | — | 32 字节；凭证 AES-256-GCM 与 admin token 派生密钥 |
| `ADMIN_PASSWORD` | 是 | — | ≥8 字符 |
| `HOST_PORT` | 否 | `8000` | 宿主机监听端口（仅 compose 端口映射；容器内固定 `8000`） |
| `DATA_DIR` | 否 | `./data` | SQLite 数据目录（容器内由 compose 固定为 `/data`） |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///<DATA_DIR>/ocr-gateway.db` | 容器内由 compose 置空，强制从 `DATA_DIR` 推导 |
| `FRONTEND_DIST` | 否 | `<repo>/frontend/dist` | 面板构建产物目录；容器内由镜像设为 `/app/static`。`DIST`=构建产物，`DIR`=数据目录 |
| `UV_DEFAULT_INDEX` | 否 | 空 | **构建期** Python 索引（如 `https://pypi.tuna.tsinghua.edu.cn/simple`）；离线环境必填 |
| `NPM_REGISTRY` | 否 | 空 | **构建期** npm 索引（如 `https://registry.npmmirror.com`）；与 `UV_DEFAULT_INDEX` 同构 |
| `APT_MIRROR` | 否 | 空 | **构建期** Debian 镜像（runtime 安装 `libgomp1`）；离线环境如 `https://mirrors.tuna.tsinghua.edu.cn` |
| `DEFAULT_TIMEOUT_MS` | 否 | `8000` | 新建账号的默认超时；**M3 起对账号创建生效**（此前硬编码 8000），已有账号不受影响 |
| `REQUEST_DEADLINE_MS` | 否 | `20000` | 单请求总预算（含信号量等待）；可在设置页热更新 |
| `LOCAL_OCR_ENABLED` | 否 | `false` | 本地 OCR 开关的启动默认值；持久化后由设置页的值覆盖 |
| `LOCAL_OCR_MAX_CONCURRENCY` | 否 | `1` | 本地 worker 并发上限；变更需重启容器（建池时生效） |
| `LOCAL_OCR_TIMEOUT_MS` | 否 | `30000` | 本地单次识别上限；实际值 = `min(该值, 剩余预算)` |
| `LOCAL_OCR_RESERVE_MS` | 否 | `5000` | `auto` 云阶段为本地预留的预算；总预算不足时按 `reserve_eff` 收缩 |
| `LOCAL_OCR_MIN_BUDGET_MS` | 否 | `1000` | 剩余预算低于此值不再尝试本地 |
| `CACHE_ENABLED` | 否 | `true` | 缓存开关的启动默认值；可在设置页热更新 |
| `CACHE_TTL_SECONDS` | 否 | `3600` | 同上 |
| `CACHE_MAX_ENTRIES` | 否 | `1000` | 同上 |
| `MAX_UPLOAD_BYTES` | 否 | `10485760` | 解码后图片字节上限 |
| `MAX_IMAGE_PIXELS` | 否 | `40000000` | 解码前像素上限 |
| `MAX_CONCURRENT_REQUESTS` | 否 | `8` | 公共 OCR 全局并发上限 |
| `URL_FETCH_TIMEOUT_SECONDS` | 否 | `10` | |
| `URL_FETCH_MAX_BYTES` | 否 | `10485760` | |
| `SESSION_TTL_SECONDS` | 否 | `43200` | 管理会话（token 与 cookie）有效期（12h） |
| `TRUST_PROXY_HEADERS` | 否 | `false` | 反代后启用：登录限速按 `X-Forwarded-For`/`X-Real-IP` 识别客户端 IP；**M3 起还用于判定 `X-Forwarded-Proto: https` 并给 cookie 加 `Secure`** |
| `LOG_LEVEL` | 否 | `INFO` | |

设置页里保存的运行时设置（缓存开关/TTL/容量、请求总预算、账号默认超时、本地 OCR 开关）优先于上面
同名的环境变量；数据库里的值非法时回退环境变量并记 warning。

真实凭证（百度 `app_id`/`api_key`/`secret_key`、腾讯 `secret_id`/`secret_key`）只能通过本地
`.env`、环境变量或部署平台的密钥管理注入；MUST NOT 写进仓库、测试夹具或日志。本机私有凭证说明
请留在**仓库外的本地私有凭证文档**中（不要提交到仓库）。

## 部署

**主路径：Docker Compose 一键起**（见「快速开始」）。`docker compose up -d` 后容器自动执行
`alembic upgrade head` 再启动服务；迁移失败即退出，不会出现「服务已起但表不存在」的中间态。
镜像包含前端构建阶段，`/app/static` 即面板产物；`docker compose build` 需要能访问 npm 索引
（离线环境用 `NPM_REGISTRY`）。

- 应用**不终结 TLS**：compose 只把端口绑定到 `127.0.0.1`，由 Caddy/Nginx 反代终结 HTTPS；
  宿主机端口由 `HOST_PORT`（默认 `8000`）控制，反代目标随之调整。
- **必须单 worker**：启动日志与 README 都声明该约束；检测到 `WEB_CONCURRENCY`、`UVICORN_WORKERS`
  或 `--workers` 大于 1 会拒绝启动。内存计数/注册表/缓存都只在一个事件循环内读写。
- 运行身份：entrypoint 以 root 修复数据卷属主后降权到 `app`，**主进程非 root**。
- 自愈与日志：`restart: unless-stopped`；`stop_grace_period: 25s` 给在途请求留出退出窗口
  （`REQUEST_DEADLINE_MS` 上限 20000ms，须小于该宽限）；日志由 `json-file` 驱动轮转。
- 数据卷：宿主 `./data` 挂到容器 `/data`，容器销毁重建不丢数据；备份见下节。
- 本机路径仍需手工 `alembic upgrade head`（见「本机开发」）。

反代示例（由反代终结 HTTPS，应用只监听回环）：

```caddyfile
# Caddy
ocr.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

```nginx
# Nginx
server {
    listen 443 ssl;
    server_name ocr.example.com;
    # ssl_certificate / ssl_certificate_key 指向你的证书
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- 默认不信任 `X-Forwarded-*`；只有当应用只监听回环/内网且前面是可信反代时，才设
  `TRUST_PROXY_HEADERS=true`（用于登录限速的客户端 IP 识别，以及 HTTPS 反代下会话 cookie 的
  `Secure` 判定）。
- **HTTPS 部署 MUST 转发 `X-Forwarded-Proto` 并设 `TRUST_PROXY_HEADERS=true`**，否则会话 cookie
  不会带 `Secure`。公网部署必须走 HTTPS；HTTP 直连时 cookie 不带 `Secure` 是本地/内网的可接受行为。

### 发布与回滚

以下脚本可在任意 cwd 调用（cron 友好），自动定位仓库根；默认路径均相对仓库根。

```bash
# 发布新版本（在目标服务器执行）：git pull → 预部署备份 → compose build → 起服务 → 等待健康 → 校验 /healthz
scripts/deploy.sh               # 自动 git pull --ff-only；服务器无 git 远程时加 --skip-pull
```

每次发布自动做一次预部署备份，并把「时间戳 + git SHA + 备份路径」追加到 `data/backup/deploy-log`
（回滚台账）。

```bash
# 回滚：停容器 → 校验备份 → 覆盖数据库 → 起服务 → 等待健康；不传参数则取最新备份
scripts/rollback.sh [data/backup/ocr-gateway-<日期>-<时间>.db]
```

- **版本锚**：`docker-compose.yml` 的 `image`/`build.tags` 为 `ocr-gateway:0.3.0`；**`0.1.0`、
  `0.2.0` 与 `0.2.1` tag 必须保持不可变**，它们是镜像回滚的锚点（`latest` 不作回滚依据）。构建
  0.3.0 不会覆盖 0.1.0/0.2.0/0.2.1。
- **回滚顺序（0.3.0 起）**：先关闭本地 OCR 开关（避免新 local 事件）→ 停 0.3.0 容器 → 用 0.3.0
  镜像执行 `alembic -c /app/alembic.ini downgrade -1`（或 revision `7c1f0d2a9b31`；local 行映射为
  `auto`；需 `--entrypoint` 覆盖，否则 entrypoint 启动即 `upgrade head`）→ 启动 `0.2.1`。也可用
  部署前备份跑 `scripts/rollback.sh` 恢复 0002 数据库。**不可先启旧镜像再降级**：0.2.1 的 Alembic
  脚本目录不认识 `0003`。
- 镜像不发布 registry，仅存在于服务器本地；如需对外发布，届时引入 registry 并按 digest 固定镜像。

## 备份与恢复

```bash
# 每日备份（建议 cron），保留 7 天；联机备份，WAL 安全，无需停容器
scripts/backup.sh
# cron 示例（每天 03:00，日志落在 data/backup/backup.log）：
# 0 3 * * * /path/to/ocr-gateway/scripts/backup.sh >> /path/to/ocr-gateway/data/backup/backup.log 2>&1

# 手工快照（等价于 scripts/backup.sh 内部使用的 SQLite 联机备份命令）
sqlite3 data/ocr-gateway.db ".backup 'data/backup/manual-$(date +%F).db'"
```

备份文件 `data/backup/ocr-gateway-<日期>-<时间>.db`，保留天数可用 `BACKUP_RETENTION_DAYS`
调整（默认 7）。

- 备份内容：整库，含账号、Key、用量事件、配额计数与运行时 `settings` 表。
- `settings` 丢失时回退环境变量默认值（不会阻塞启动）。
- RPO：配额计数最多丢 2 秒（内存计数每 2 秒刷盘）；账户/Key/账号/设置配置为最近一次备份。
- RTO：重启进程（<5 秒）；恢复用 `scripts/rollback.sh`（停容器、覆盖 `data/ocr-gateway.db`、再启动）。
- 备份文件与 `data/` 一样不得进仓。

## 测试

```bash
uv run --project backend pytest backend/tests          # 单元 + 集成 + e2e（mock 厂商）
uv run --project backend pytest -m slow                # 10 万条用量事件的查询基准
uv run --project backend ruff check backend
uv run --project backend mypy backend/app

pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

浏览器冒烟（需要本机 Chrome/Edge，或设置 `CHROME_PATH`；先起一个可登录的实例）：

```bash
E2E_BASE_URL=http://127.0.0.1:8000 E2E_ADMIN_PASSWORD=... pnpm --dir frontend e2e
```

真实百度/腾讯账号契约测试默认 skip，需要本地环境变量（凭证只在本机）：

```bash
BAIDU_APP_ID=... BAIDU_API_KEY=... BAIDU_SECRET_KEY=... \
TENCENT_SECRET_ID=... TENCENT_SECRET_KEY=... \
uv run --project backend pytest backend/tests -m contract
```

## 运营提示

- 面板路由：`/`（总览）、`/accounts`、`/members`、`/usage`、`/logs`、`/settings`、`/login`；
  筛选与分页状态在地址栏里，刷新/分享链接保持当前视图。
- 会话是 `HttpOnly` cookie + `SameSite=Lax`，写操作带 `X-CSRF-Token`；登出只清客户端 cookie，
  已签发的 token 在有效期内仍可用（无服务端会话表，v1 接受的残留风险）。
- 保存缓存相关设置会清空现有缓存（提示会说明）；「清空缓存」按钮会显示清除条数。
- 配额模板（`GET /api/admin/quota-templates`）只是参考值，**以官网为准**，不会自动套用到账号。
- 账号测活（`POST /api/admin/accounts/{id}/test`）不写用量、不扣配额、不改状态。
- 账号 `reset-state` 会清空该账号的运行时状态**与配额计数**（面板的确认框写明了这一点）。
- 公共 API 的 `provider` 接受 `auto`/`baidu`/`tencent`/`local`；显式 `local` 在未开启本地 OCR
  或依赖缺失时返回 403，其它未知值返回 400。
- 请求错误统一为 `{"request_id","error":{"code","message"}}`；设置校验失败额外带
  `error.fields[]`；`/healthz` 不受鉴权保护。
