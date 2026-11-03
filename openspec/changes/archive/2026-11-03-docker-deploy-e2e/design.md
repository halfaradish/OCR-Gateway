# Design

## Context

动机与范围见 [`proposal.md`](./proposal.md)。本节只列**塑造方案**的现状与约束：

- 应用是**单进程单 worker** 架构：内存里的账号注册表、配额计数、结果缓存都只在一个事件循环内读写（`backend/app/config.py:108-130` 的 `enforce_single_worker` 会在检测到多 worker 时抛 `RuntimeError`）。
- **启动期不跑迁移**：`lifespan` 只做 `select(Account)`（`backend/app/main.py:51-63`），表不存在即崩；迁移必须由外部先跑（`README.md` 的「启动前先跑 `alembic upgrade head`」）。
- **配置在导入期就被强制**：`app = create_app()` 在模块导入时执行（`backend/app/main.py:204`），而 `Settings` 的 `master_key` / `admin_password` 是必填字段（`backend/app/config.py:66-67`）⇒ 缺配置时进程起不来，而非运行期 500。
- **SQLite 路径由 `DATA_DIR` 推导**：`database_url` 缺省时取 `Path(data_dir)/"ocr-gateway.db"`（`backend/app/config.py:89-92`），相对路径会随 CWD 漂移。
- **迁移工具可重定位且幂等**：`alembic.ini:2` 用 `%(here)s/alembic`，`env.py:29-42` 按 `-x db_url` → `DATABASE_URL` → ini → `DATA_DIR` → 默认 的顺序解析并剥离 `+aiosqlite`，`env.py:56` 会自动建 SQLite 父目录；当前只有一条迁移（`backend/alembic/versions/0001_initial.py:16`，`revision = '01b12c86bd76'`）。
- **构建环境离线**：`pypi.org` 与 `files.pythonhosted.org` 均不可达（curl exit 28），Docker Hub 直连亦不可用；只有国内 PyPI 镜像与 Docker registry mirror 可达（见 `decision-memo.md` C1/C7）。
- **`uv.lock` 锁定的是下载 URL 而非仅版本**：1292 处 `files.pythonhosted.org` 硬编码 ⇒ `uv sync --frozen` 在离线环境不可用（ADR-0001）。

## Goals / Non-Goals

**Goals:**

- 交付一个**可构建、可一键起、可搬迁**的容器产物，并把「起得来」变成可观测事实（`/healthz` + compose healthcheck）。
- 让**启动期迁移**成为容器自身的职责，消除「忘了跑 `alembic upgrade head`」这类部署事故。
- 用**真机端到端**证明网关链路（鉴权/调度/配额/缓存/切厂商）在真实厂商下成立，而不只是适配器级。

**Non-Goals（设计层边界）:**

- 不引入反向代理、TLS 终结、多实例、编排平台（K8s）——理由与可证伪假设见 `proposal.md` 的 Non-Goals。
- 不改 `backend/app/**` 的业务逻辑、数据模型或任何 HTTP 契约。
- 不做镜像分层的高级优化（如 BuildKit cache mount 之外的精细裁剪）。

## Decisions

本 change 的**决策全文、砍掉的候选与承重约束**见 [`decision-memo.md`](./decision-memo.md)；跨 change 复用的技术裁决见 ADR-0001。本节只记**设计层**的选择：

- **多阶段构建 + 依赖层独立** — 依赖层只 COPY `pyproject.toml` / `uv.lock`，代码层再 COPY `app/` 与 `alembic/`。理由：代码改动不会让依赖层缓存失效，本机首次构建后迭代是秒级。备选：单阶段（每次改代码都重装依赖，离线环境下代价极高）。
- **依赖安装走 `uv export --frozen --no-emit-project` → `uv pip install --index-url`** — 见 ADR-0001。理由：保留锁文件的版本精确性，同时不把区域镜像写进被跟踪的 `uv.lock`。`[spec-review-amendment]` `uv export` 默认会输出 `-e .`，依赖层只有 `pyproject.toml`/`uv.lock` 时会构建失败，故 MUST 加 `--no-emit-project`；构建阶段 MUST 先创建 `/app/.venv`（或显式 `UV_SYSTEM_PYTHON=1`），并显式安装固定版本的 uv。
- **迁移放在 entrypoint，而不是 compose 的 `command`** — entrypoint 内顺序执行「迁移 → 启动」，迁移失败即 `exit`，不会出现「uvicorn 起来了但表不存在」的中间态。备选：compose 里用两个 service / 依赖 `depends_on`（多一层编排、且 `depends_on` 只保证启动顺序不保证成功）。
- **healthcheck 用 `python -c` 而非 `curl`/`wget`** — `python:3.12-slim` 不含 curl/wget，装它们只为探活不划算。用标准库 `urllib.request` 请求 `/healthz`，非 200 即非零退出。
- **数据卷用 bind mount `./data`** — 与 `README.md` 既有的备份脚本（`sqlite3 data/ocr-gateway.db ".backup ..."`）路径一致，运维无需改习惯。备选：命名卷（备份需先进容器取文件，反而更绕）。
- **运行身份与数据卷权限（Q1=A，人 2026-11-03 拍板）** — entrypoint 以 root 启动，先 `chown -R app:app /data`，再 `exec setpriv --reuid=app --regid=app --init-groups uvicorn ...` 降权；最终主进程非 root。理由：bind mount 下镜像期 `chown /data` 不作用于宿主目录，这是 Linux 目标态下不牺牲「一键起」的路径。
- **镜像平台与 tag（Q3=A，人 2026-11-03 拍板）** — 仅构建 `linux/amd64`；镜像名 `ocr-gateway`，tag `0.1.0` + `latest`；不发布 registry；arm64 为 non-goal。理由：本机 daemon 是 linux/amd64，多架构构建超出「一键起」；回滚用固定 `0.1.0`，`latest` 不作回滚依据。
- **容器内 `DATA_DIR=/data`（绝对路径）** — 规避 CWD 漂移（`backend/app/config.py:89-92`）。
- **不设 `WEB_CONCURRENCY` / `UVICORN_WORKERS`** — 保持 `enforce_single_worker` 合规（`backend/app/config.py:108-130`）；uvicorn 默认单 worker 即满足。

## 组件与依赖图

```
宿主 / 部署环境
┌───────────────────────────────────────────────────────────────────┐
│ docker compose                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ service: ocr-gateway（单容器，非 root）                     │  │
│  │                                                             │  │
│  │  entrypoint.sh                                              │  │
│  │   ① alembic upgrade head ─────▶ SQLite /data/ocr-gateway.db │  │
│  │   ② exec uvicorn app.main:app --workers 1                   │  │
│  │        └─ lifespan: enforce_single_worker → 加载 accounts    │  │
│  │                    与 quota → 启动 2s 刷盘循环               │  │
│  │                                                             │  │
│  │  GET /healthz ◀──── healthcheck（python urllib，10s/3s/5）   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│        ▲ env_file: .env（MASTER_KEY / ADMIN_PASSWORD，运行期）    │
│        ▲ build.args: UV_DEFAULT_INDEX（构建期，.env 插值）        │
│        ▲ volume: ./data ──▶ /data                                 │
└───────────────────────────────────────────────────────────────────┘
   出站（运行期）：aip.baidubce.com、ocr.tencentcloudapi.com
   构建期：registry mirror（python:3.12-slim）+ PyPI mirror（38 个锁定包）
```

`[spec-review-amendment]` `env_file` 只注入运行期容器环境，**不会**成为构建参数；构建期镜像源 MUST 经
compose `build.args: UV_DEFAULT_INDEX: ${UV_DEFAULT_INDEX:-}`（Compose 从项目根 `.env` 插值）传入。

## 失败模式与可观测性

| 失败模式 | 表现 | 处理 | 可观测信号 |
| --- | --- | --- | --- |
| 缺 `MASTER_KEY` / `ADMIN_PASSWORD` | 导入期抛错退出 | fail-fast，不进入服务态 | 容器退出码非 0 + stderr 的 `ValidationError` |
| 迁移失败（卷权限 / 磁盘满） | entrypoint 第一步失败 | `set -e` 立即退出，**不启动 uvicorn** | 退出码非 0 + alembic stderr |
| 迁移成功后 uvicorn 起不来（端口占用） | 容器退出 | `restart: unless-stopped` 触发重启并暴露问题 | 退出码 + `docker compose logs` |
| 数据库不可用 | `/healthz` 返回 503 | compose 标记 `unhealthy` | `curl /healthz` 的 body（`{"status":"error","db":"error",...}`） |
| 构建期 mirror 不可达 | 构建中断 | 无部分镜像产出 | 构建日志中的 `Failed to fetch` |
| 锁与导出不一致 | 依赖版本漂移 | `--frozen` 保证导出一致，不一致即失败 | 构建日志 |
| 运行期厂商不可用 | 请求返回 502/503/504 | 既有调度器逻辑（本次不改） | 响应 `error.code` + `request_id` |
| 容器停止时仍有在途请求 | 请求被截断 | compose `stop_grace_period: 25s`（大于 `REQUEST_DEADLINE_MS=20000`），给 uvicorn 留出优雅退出窗口 | 退出码 + 日志 |

**可观测性基线**：应用已有结构化请求日志（`backend/app/main.py:120-131`，含 `request_id`/`latency_ms`）与 `/healthz`；本 change 新增的是**容器层**信号——compose healthcheck 状态、容器退出码、以及日志轮转（`max-size`/`max-file`）防止磁盘被写满。

## 非功能需求（数字化）

- **冷启动（镜像已构建、空卷含迁移）** ≤ 90s（Q2=A；首次镜像构建耗时单列记录，不计入）；**稳态启动**（表已存在）≤ 10s。
- **healthcheck**：`interval=10s`、`timeout=3s`、`retries=5`、`start_period=30s` ⇒ 最迟约 80s 内判定 `healthy`。
- **镜像大小** ≤ 400MB（`python:3.12-slim` + 运行期依赖，不含 dev 依赖与测试）。
- **RTO / RPO**：沿用既有口径——重启进程 < 5s；配额计数最多丢 2 秒（`README.md` 备份与恢复段）。
- **单实例上限**：1 容器、1 worker、全局并发上限 `MAX_CONCURRENT_REQUESTS=8`（`backend/app/config.py:77`）。

## 安全与数据保护

- **凭证**：只经 `env_file` / 环境变量注入；`.dockerignore` 必须排除 `.env`、`data/`、`docs/`（本地凭证文档所在目录）；镜像层 MUST NOT 含任何真实凭证（验收含镜像内容扫描）。
- **运行身份**：最终主进程以非 root 用户运行；entrypoint 以 root 完成 `/data` 属主修复后降权。`[spec-review-amendment]` bind mount 下镜像构建期的 `chown /data` **不作用于宿主目录**；Linux 上宿主 `./data` 通常由 root 创建，非 root 容器用户迁移时会 EACCES。**Q1 已拍板 A（人 2026-11-03）**：entrypoint 以 root 启动 → `chown -R app:app /data` → `exec setpriv --reuid=app --regid=app --init-groups` 降权，最终主进程 uid 非 0。
- **网络暴露**：容器只暴露应用端口，不终结 TLS（D13）；生产由外层反代终结 HTTPS。
- **数据**：`/data` 内是 SQLite 明文（与现状一致）；`usage_events` 仍不落 OCR 原文（C7），本 change 不改变这一点。
- **构建供应链**：基础镜像经 mirror 拉取并固定 digest（`sha256:b18b261e...`）；依赖版本由 `uv.lock` 锁定。

## 切片与依赖

本 change 拆 5 个垂直切片。**真正的 `Blocked-by` 台账在 `tickets.md`**（由 `/sdflow-lite-ship` 出票阶段生成），本节只是语义来源。`[spec-review-amendment]` 注明 `tickets.md` 当前尚不存在，避免读者误以为遗漏。

| 切片 | 交付行为 | 依赖 |
| --- | --- | --- |
| **S1 镜像构建层** | `docker build` 成功，镜像内 `python -c "import app"` 通过，且不含 dev 依赖/测试 | — |
| **S2 启动契约** | 空卷启动自动建表、`/healthz` 200；缺配置或迁移失败时快速退出 | S1 |
| **S3 编排与运行身份** | `docker compose up -d` 后达到 `healthy`；非 root、restart 策略、日志轮转、数据卷、凭证注入 | S2 |
| **S4 文档与配置面** | 按 README 从干净 checkout 复现一键起；`.env.example` 覆盖构建期与运行期变量 | S3 |
| **S5 真机端到端验收** | 建成员/Key/百度+腾讯账号 → 三种输入 + 缓存 + 配额 + 显式不回退 + auto 切换全部通过；记录证据 | S3、S4 |

## Compliance

- **ADR-0001 遵守**：容器依赖安装走 `uv export --frozen` + `uv pip install --index-url`，不改动被跟踪的 `uv.lock`。
- **D13 遵守**：应用不终结 TLS；容器只绑回环/内网端口，由外层反代终结 HTTPS。
- **D14 遵守**：单实例规模前提（≤5 人、日均 <500 次）未变，不引入多实例或 Postgres。
- **C7 遵守**：默认不落 OCR 原文，本次不改 `usage_events` 结构。
- **单 worker 约束遵守**：不设 `WEB_CONCURRENCY` / `UVICORN_WORKERS`（`backend/app/config.py:108-130`）。
- **D-2（DB schema 迁移）不适用**：本 change 无 schema 变更，沿用 `0001_initial.py`。
- **D-4（外部依赖超时 / 写操作回滚）**：运行期外部依赖不变，既有超时（`backend/app/main.py:69` 的 `httpx.Timeout(connect=3.0, read=8.0, write=8.0, pool=3.0)`、`DEFAULT_TIMEOUT_MS` / `REQUEST_DEADLINE_MS`）继续生效；构建期网络操作的边界与回滚见下节。
- **D-6（架构边界）**：无跨产品/跨模块共享数据模型变更，未越界。

## Risks / Trade-offs

- **构建强依赖 mirror** → 缓解：镜像源参数化（`ARG UV_DEFAULT_INDEX`），并文档化取值；mirror 不可达时构建快速失败而非产出半成品。
- **entrypoint 内跑迁移意味着容器需要写权限** → 缓解：`/data` 显式归属非 root 用户；迁移失败即退出，不留中间态。
- **`restart: unless-stopped` 与 fail-fast 的交互** → 取舍：配置错误或迁移持续失败会形成**重启循环**（Docker 退避重试）。接受理由：循环期间不进入服务态、退出码与日志可见；修复配置后自动恢复，无需人工 `up`。若要抑制循环需引入额外守卫，与「一键起」的简单性相悖。
- **非 root + Windows bind mount 的权限行为未验证（A1）** → 缓解：若验收失败，降级为命名卷或调整 uid，并把结论回写到 design。`[spec-review-amendment]` A1 只覆盖 Windows Docker Desktop；目标态「搬到任意 Linux 服务器」的 bind mount 权限未覆盖，见安全与数据保护节；Q1 已拍板 A（entrypoint root→chown→drop）。
- **`uv export` 与 `uv.lock` 之间靠 `--frozen` 维持一致** → 缓解：`--frozen` 不一致即报错；升级依赖时仍用 `uv lock` 正常维护锁文件。
- **healthcheck 只探数据库连通性** → 取舍：不额外探厂商可用性（会把外部故障误判为容器不健康，触发无意义重启）。
- **bind mount 在 Windows 上 I/O 较慢** → 取舍：规模极小（日均 <500 次），可接受；若后续变慢再评估命名卷。

## Migration Plan

**部署步骤**

1. `cp .env.example .env`，填入 `MASTER_KEY`（32 字节）、`ADMIN_PASSWORD`（≥8 字符），以及 `UV_DEFAULT_INDEX`（离线环境必填）。
2. `docker compose up -d` —— 容器自动执行 `alembic upgrade head` 后启动。
3. 等待 `docker compose ps` 显示 `healthy`；`curl -i http://127.0.0.1:8000/healthz` 应返回 200。
4. 经管理 API 建成员 / Key / 账号（`POST /api/admin/users`、`POST /api/admin/api-keys`、`POST /api/admin/accounts`）。

**回滚策略**

- **无 schema 变更** ⇒ 不需要 `alembic downgrade`；回滚 = 停容器（`docker compose down`）+ 用备份覆盖 `data/ocr-gateway.db` + 起上一版本镜像。
- 备份沿用 `README.md` 的 `sqlite3 ... ".backup ..."` 脚本，RPO 为最多 2 秒配额计数。
- 镜像回滚靠固定 tag；`latest` 不作为回滚依据。

## Open Questions

- ~~镜像 tag / 目标平台策略~~ —— **已拍板（2026-11-03，Q3=A）**：仅 `linux/amd64`，`ocr-gateway:0.1.0` + `latest`，不发布 registry；arm64 为 non-goal。`[spec-review-amendment]` 关闭该问题。
