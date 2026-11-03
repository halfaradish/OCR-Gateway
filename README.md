# OCR Gateway

单实例 OCR 网关：把百度智能云与腾讯云的通用文字识别聚合成一个统一的 HTTP API，按账号优先级与
EWMA 延迟选号、失败自动切换，并按厂商账号与网关 API Key 记账配额。管理端只有管理 API + FastAPI
自带的 `/docs`（无 SPA）。

## 能力边界（MVP）

- 单张图片 OCR：`POST /v1/ocr/image`，支持 multipart 文件、JSON base64、JSON `image_url` 三选一。
- 厂商：百度 `general_basic`、腾讯 `GeneralBasicOCR`；`provider=auto` 可跨厂商切换，显式
  `provider` 不跨厂商回退。
- 账号池：优先级、EWMA 延迟、并发上限、QPS 令牌桶、冷却/失效/配额耗尽状态与惰性恢复。
- 配额：账号日/月/总量、Key 日限额与 RPM；内存计数每 2 秒批量落 SQLite。
- 缓存：进程内 TTLCache，键为 `sha256(image) + language + provider`，空文本与 >256KB 结果不缓存。
- 不做：多实例/多 worker、任务队列、批量接口、PDF、本地 OCR、前端 SPA、Prometheus `/metrics`。

## 快速开始（Docker Compose，约 2 分钟\*）

> \* TTHW 为**估算**：命令数 3 条、步骤数 3 步；热路径假设 = `cp` + 填写 `.env` 约 1 分钟、
> `docker compose up -d` 到容器健康约 30–90 秒。**不含首次镜像构建**（约 3–8 分钟，取决于网络与
> 本地缓存），首次构建耗时单独计入部署总时长，不计入「一键起」。

前置：Docker 与 Docker Compose v2+。

```bash
# 1. 配置环境变量（约 1 分钟；MASTER_KEY 32 字节、ADMIN_PASSWORD ≥8 字符）
cp .env.example .env

# 2. 构建并启动（约 1–2 分钟；容器自动执行迁移后启动服务）
docker compose up -d

# 3. 等待健康（约 30–90 秒），确认 /healthz 返回 200
docker compose ps
curl -i http://127.0.0.1:8000/healthz
```

宿主机端口默认 `8000`，可在 `.env` 中用 `HOST_PORT` 覆盖（容器内始终监听 `8000`）。改端口后，
上面及下文的访问地址、反代目标需一并替换，例如 `HOST_PORT=18000` 对应
<http://127.0.0.1:18000/docs>。

容器主进程以非 root 运行，业务数据落在宿主 `./data`（SQLite），进程日志走 stdout 由容器日志驱动
轮转（`max-size` / `max-file`）。打开 <http://127.0.0.1:8000/docs>，先 `POST /api/admin/login`
拿 Bearer token，再在右上角 Authorize 填入 token，即可完成成员、Key、账号、用量查询等全部运营动作。

健康检查：`GET /healthz`（不鉴权），数据库可用返回 200，否则 503；编排侧以此判定 `healthy`。

## 本机开发（uv 备选路径）

前置：Python 3.11+、`uv`、可用的 SQLite，且默认包索引可达。离线环境下需设 `UV_DEFAULT_INDEX`
指向可达镜像；**避免非 frozen 的 `uv sync` 改写被跟踪的 `uv.lock`**（用 `--frozen` 或
`UV_FROZEN=1`）。

```bash
# 1. 安装依赖（约 1–2 分钟，首次需下载）
uv sync --project backend

# 2. 配置环境变量（把 .env.example 复制为 .env 并填写真实值）
cp .env.example .env
# MASTER_KEY：32 字节，hex / base64 / 32 字符原文均可
# ADMIN_PASSWORD：至少 8 字符

# 3. 建库（约 1 秒）
uv run --project backend alembic -c backend/alembic.ini upgrade head

# 4. 启动（单 worker；约 1–2 秒）
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## 环境变量

| 变量 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `MASTER_KEY` | 是 | — | 32 字节；凭证 AES-256-GCM 与 admin token 派生密钥 |
| `ADMIN_PASSWORD` | 是 | — | ≥8 字符 |
| `HOST_PORT` | 否 | `8000` | 宿主机监听端口（仅 compose 端口映射；容器内固定 `8000`） |
| `DATA_DIR` | 否 | `./data` | SQLite 数据目录（容器内由 compose 固定为 `/data`） |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///<DATA_DIR>/ocr-gateway.db` | 容器内由 compose 置空，强制从 `DATA_DIR` 推导 |
| `UV_DEFAULT_INDEX` | 否 | 空 | **构建期**镜像/包索引（如 `https://pypi.tuna.tsinghua.edu.cn/simple`）；离线环境必填 |
| `DEFAULT_TIMEOUT_MS` | 否 | `8000` | 账号默认超时 |
| `REQUEST_DEADLINE_MS` | 否 | `20000` | 单请求总预算 |
| `CACHE_ENABLED` | 否 | `true` | |
| `CACHE_TTL_SECONDS` | 否 | `3600` | |
| `CACHE_MAX_ENTRIES` | 否 | `1000` | |
| `MAX_UPLOAD_BYTES` | 否 | `10485760` | 解码后图片字节上限 |
| `MAX_IMAGE_PIXELS` | 否 | `40000000` | 解码前像素上限 |
| `MAX_CONCURRENT_REQUESTS` | 否 | `8` | 公共 OCR 全局并发上限 |
| `URL_FETCH_TIMEOUT_SECONDS` | 否 | `10` | |
| `URL_FETCH_MAX_BYTES` | 否 | `10485760` | |
| `SESSION_TTL_SECONDS` | 否 | `43200` | admin token 有效期（12h） |
| `TRUST_PROXY_HEADERS` | 否 | `false` | 反代后启用：登录限速按 `X-Forwarded-For`/`X-Real-IP` 识别客户端 IP |
| `LOG_LEVEL` | 否 | `INFO` | |

真实凭证（百度 `app_id`/`api_key`/`secret_key`、腾讯 `secret_id`/`secret_key`）只能通过本地
`.env`、环境变量或部署平台的密钥管理注入；MUST NOT 写进仓库、测试夹具或日志。本地凭证说明文件
建议加入 `.git/info/exclude`。

## 部署

**主路径：Docker Compose 一键起**（见「快速开始」）。`docker compose up -d` 后容器自动执行
`alembic upgrade head` 再启动服务；迁移失败即退出，不会出现「服务已起但表不存在」的中间态。

- 应用**不终结 TLS**：compose 只把端口绑定到 `127.0.0.1`，由 Caddy/Nginx 反代终结 HTTPS；
  宿主机端口由 `HOST_PORT`（默认 `8000`）控制，反代目标随之调整。
- **必须单 worker**：启动日志与 README 都声明该约束；检测到 `WEB_CONCURRENCY`、`UVICORN_WORKERS`
  或 `--workers` 大于 1 会拒绝启动。内存计数/注册表/缓存都只在一个事件循环内读写。
- 运行身份：entrypoint 以 root 修复数据卷属主后降权到 `app`，**主进程非 root**。
- 自愈与日志：`restart: unless-stopped`；`stop_grace_period: 25s` 给在途请求留出退出窗口；
  日志由 `json-file` 驱动轮转（`max-size` / `max-file`）。
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
    }
}
```

- 默认不信任 `X-Forwarded-*`；只有当应用只监听回环/内网且前面是可信反代时，才设 `TRUST_PROXY_HEADERS=true`（仅用于登录限速的客户端 IP 识别，不用于鉴权）。
- 回滚：无 schema 变更，停容器后用备份覆盖 `./data/ocr-gateway.db`，再以固定 tag 的上一版本镜像启动
  （`latest` 不作为回滚依据）。

## 备份与恢复

```bash
# 每日备份（建议 cron），保留 7 天
mkdir -p data/backup
sqlite3 data/ocr-gateway.db ".backup 'data/backup/ocr-gateway-$(date +%F).db'"
find data/backup -name 'ocr-gateway-*.db' -mtime +7 -delete
```

- RPO：配额计数最多丢 2 秒（内存计数每 2 秒刷盘）；账户/Key/账号配置为上次备份。
- RTO：重启进程（<5 秒）；恢复时停止进程、用备份覆盖 `data/ocr-gateway.db`、再启动。
- 备份文件与 `data/` 一样不得进仓。

## 测试

```bash
uv run --project backend pytest backend/tests          # 单元 + 集成 + e2e（mock 厂商）
uv run --project backend ruff check backend
uv run --project backend mypy backend/app
```

真实百度/腾讯账号契约测试默认 skip，需要本地环境变量（凭证只在本机）：

```bash
BAIDU_APP_ID=... BAIDU_API_KEY=... BAIDU_SECRET_KEY=... \
TENCENT_SECRET_ID=... TENCENT_SECRET_KEY=... \
uv run --project backend pytest backend/tests -m contract
```

## 运营提示

- 配额模板（`GET /api/admin/quota-templates`）只是参考值，**以官网为准**，不会自动套用到账号。
- 账号测活（`POST /api/admin/accounts/{id}/test`）不写用量、不扣配额、不改状态。
- 账号 `reset-state` 会清空该账号的运行时状态与配额计数，用于 invalid/cooling/quota_exhausted 恢复。
- 公共 API 的 `provider` 只接受 `auto`/`baidu`/`tencent`；`local` 等取值返回 400。
- 请求错误统一为 `{"request_id","error":{"code","message"}}`；`/healthz` 不受鉴权保护。
