---
schema_version: 1
change: docker-deploy-e2e
branch: feat/docker-deploy-e2e
generated_at: 2026-11-03T11:32:07+08:00
decision_hash: 74815c6df227
---

# 决策纪要 · docker-deploy-e2e

## 目标态

把现有 OCR Gateway MVP 打成可一键起的 Docker Compose 部署（含自动迁移、健康检查、数据卷、镜像源参数化），并用本机真实百度/腾讯凭证跑通端到端 HTTP 验收。

> **术语旁注（「一键起」的边界）**：本项目无 `openspec/CONTEXT.md`，故按 reference 降级为旁注。
> 「一键起」= 从干净 checkout 执行 `docker compose up -d` 后，容器自动完成迁移且 `/healthz` 返回 200，
> **不含**创建成员/Key/账号——那些属于验收步骤，需显式调用管理 API。「一键起」与「开箱可用」不是同义词。

## 拍板决策

- **D1 部署形态：Docker Compose 一键起** — 依据：本机 Docker CLI 29.4.3 + Compose v5.1.3 已安装（`docker --version` / `docker compose version`）；路线图 M5 验收口径即「一键起服务」（`docs/tech-selection.md:634`）；镜像可搬到任意 Linux 服务器，不依赖本机 Python 与 uv。**砍掉的候选**：纯本机脚本（搬到服务器仍需手工装 Python/uv，达不到「一键起」）、两者都做（两套启动路径都要维护与验收，本次体量明显变大）。
- **D2 验收口径：端到端 HTTP 硬门** — 依据：契约测试只证明适配器可用，网关路径（鉴权/调度/配额/缓存/切厂商）从未跑过真厂商；这才是产品真实链路。硬门内容：起服务 → 经管理 API 建成员/Key/百度+腾讯账号 → 真 Key 调 `POST /v1/ocr/image` 的 multipart/base64/URL 三种输入 → 校验 `text+lines`、quota 记账、缓存命中、显式 provider 不回退、`auto` 跨厂商切换。**砍掉的候选**：仅部署冒烟（调度/配额/缓存/切厂商在真厂商下仍未验证）、端到端 + 全部运营动作（测活/reset-state/用量汇总/日志查询已由 mock 测试覆盖，真机增量价值低）。
- **D3 镜像源：参数化，仓内默认留空** — 依据：本机 `pypi.org/simple/hatchling/` 不可达（curl exit 28 超时），清华 TUNA 与阿里云镜像均 200。Dockerfile 用 `ARG`，compose/`.env` 提供取值，仓内默认留空 ⇒ 不把区域镜像写死进仓。**砍掉的候选**：仓内 `backend/uv.toml` 固化清华源（换地区/CI 会莫名走国内镜像）、不处理仅文档说明（本机 quickstart 仍失败，本次「一键起」验收做不成）。
- **D3a 依赖安装机制修正（D3 的实现层修订，意图不变）** — `uv sync --frozen` **不可用**：`backend/uv.lock` 内有 1292 处 wheel 下载 URL 硬编码到 `files.pythonhosted.org`，且所有 `source` 均为 `registry = "https://pypi.org/simple"`；`UV_DEFAULT_INDEX` 只改索引解析、改不了锁文件里的下载 URL，容器内实测报 `Failed to download certifi==2026.10.23 ... files.pythonhosted.org ... operation timed out`。改用 `uv export --frozen --no-dev --format requirements-txt` 导出 38 个精确锁定版本 → `uv pip install --index-url <mirror> -r` 从镜像下载 → `uv pip install --index-url <mirror> --no-deps .` 装项目自身；容器内实测 `imports ok 0.1.0`。**取舍**：保留锁文件的版本锁定，同时不把区域镜像写进被跟踪的 `uv.lock`。**砍掉的候选**：对镜像重生成 `uv.lock`（会把 mirror URL 固化进被跟踪文件，违背 D3 的可移植意图）、镜像内删锁自由解析（丢失版本锁定）。**已落 ADR**：`openspec/adr/0001-container-deps-use-uv-export-not-uv-sync.md`（人 2026-11-03 确认落盘）。

- **D4 compose 只起应用单服务，不带反代** — 依据：D13 已定「应用不终结 TLS、由反代终结」，反代属于部署环境而非产品；README 给 Caddy/Nginx 配置片段即可。**砍掉的候选**：加一个 Nginx 纯 HTTP 反代（能真机验 `TRUST_PROXY_HEADERS` 与客户端 IP 识别，但多一个服务与一层配置，验收面变大）、带 Caddy + TLS（证书与信任链会成为验收前置，明显超出「一键起」必要范围）。**残留**：`TRUST_PROXY_HEADERS=true` 的 `X-Forwarded-For` 路径不在真机验收覆盖内，仅有 mock 测试（`backend/tests/test_ticket2_admin.py::test_login_uses_forwarded_ip_when_trusted`）。
- **D5 容器加固：最小生产项** — 包含：非 root 用户运行、`restart: unless-stopped`、日志轮转（`max-size`/`max-file`）、healthcheck、数据卷、镜像内不含 dev 依赖与测试。依据：这几项都是容器部署的最低常识，成本低且直接防「宿主机重启后服务不自恢复」「日志把磁盘写满」两类真实事故。**砍掉的候选**：只要能跑（不设非 root/重启策略/日志轮转，真实部署会踩）、完整加固（再加 read-only rootfs、CPU/内存限额、自定义 seccomp——调试成本上升，对 ≤5 人、日均 <500 次规模收益低，属通则④的过度设计）。

## 承重约束

- **C1 容器内可完成依赖安装** — 验证方式：`docker run python:3.12-slim` 内实测安装链路；**证据锚**：`grep -c "files.pythonhosted.org" backend/uv.lock` = 1292、`grep -o 'registry = "[^"]*"' backend/uv.lock | sort -u` = 仅 `https://pypi.org/simple`；容器内 `uv export --frozen --no-dev` 得 38 个 `==` 锁定项，`uv pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r` 全部装通，`python -c "import fastapi, sqlalchemy, aiosqlite, alembic, PIL, cryptography, app"` → `imports ok 0.1.0`。反例：同容器内 `uv sync --frozen --no-dev` 失败于 `files.pythonhosted.org` 超时。
- **C2 迁移可用同一 `DATABASE_URL` 在任意 CWD 跑通且幂等** — 验证方式：用临时库跑 `alembic upgrade head` 并重跑；**证据锚**：`DATABASE_URL="sqlite:///<tmp>/probe.db" python -m alembic -c backend/alembic.ini upgrade head` 建出 `['accounts','alembic_version','api_keys','quota_counters','usage_events','users']`，二次执行无输出（幂等）；`backend/alembic.ini:2`（`script_location = %(here)s/alembic` 可重定位）、`backend/alembic/env.py:29-45`（URL 解析顺序 `-x db_url` → `DATABASE_URL` → ini → `DATA_DIR` → 默认）、`:52-58`（自动建 SQLite 父目录）。
- **C3 应用导入期即要求凭证，缺则直接失败** — 验证方式：读代码；**证据锚**：`backend/app/main.py:204`（`app = create_app()` 在模块导入执行）、`backend/app/config.py:66-67`（`master_key` / `admin_password` 为必填字段）、`:84-88`（校验 MASTER_KEY 32 字节、ADMIN_PASSWORD ≥8 字符）。⇒ 容器必须注入这两项，否则进程起不来；这也让「缺配置」变成启动即失败而非运行期 500。
- **C4 lifespan 不跑迁移，空数据卷首启必崩** — 验证方式：读代码；**证据锚**：`backend/app/main.py:51-63`（lifespan 只 `select(Account)`，无 `alembic upgrade`）、`README.md`「启动前先跑 `alembic upgrade head`」。⇒ entrypoint 必须先迁移；`/healthz`（`backend/app/main.py:180-193`）不能替代迁移。
- **C5 `DATA_DIR` 必须是绝对路径** — 验证方式：读代码 + 推导；**证据锚**：`backend/app/config.py:89-92`（`database_url` 由 `Path(data_dir)/"ocr-gateway.db"` 推导，相对路径随 CWD 漂移）、`backend/app/main.py:55`（`data_path.mkdir`）。⇒ 容器内设 `/data` 绝对路径并挂卷。
- **C6 单 worker 约束在容器内成立** — 验证方式：读代码；**证据锚**：`backend/app/config.py:108-130`（`enforce_single_worker` 读 `WEB_CONCURRENCY`/`UVICORN_WORKERS`/`--workers`，>1 抛 `RuntimeError`）；uvicorn 默认单 worker ⇒ compose 只要不设这两个变量即合规。
- **C7 本机 Docker 可用且基础镜像可经 mirror 拉取** — 验证方式：实跑；**证据锚**：`docker info` → `server=29.4.3 os=linux arch=x86_64`；`docker pull python:3.12-slim` 成功（`Digest: sha256:b18b261e...`）；`~/.docker/daemon.json` 配 8 个 `registry-mirrors`；直连 `registry-1.docker.io/v2/` 与 `auth.docker.io/token` 均 curl exit 28 超时 ⇒ **必须依赖 mirror，不能假定直连可用**。
- **C8 URL 输入验收需要公网可达图片** — 验证方式：实测 + 读代码；**证据锚**：`curl https://baidu-ai.bj.bcebos.com/ocr/general.png` → 200 / 1581730 bytes；SSRF 策略拒绝私网/回环/链路本地（`backend/app/utils/ssrf.py`，D7）⇒ 验收不能用本机或内网图片服务，只能用公网图。

## 接受的边角

- **首次构建需从 mirror 下载全部依赖** — 概率确定/影响小（一次性耗时）/完美成本高（无本地缓存时无法避免）；**为何接受**：构建缓存分层后可复用，且这是唯一不牺牲版本锁定的路径。
- **端到端验收消耗真实厂商额度** — 概率确定/影响小（个位数调用）/完美成本高（不调真厂商就无法验网关真链路）；**为何接受**：人 2026-11-03 明确批准跑真机契约与端到端验收。
- **`uv.lock` 的 `files.pythonhosted.org` URL 在无外网环境永远不可直用** — 概率确定/影响小/完美成本高（要改被跟踪的锁文件）；**为何接受**：export 路径已覆盖，锁文件保持原样以免把区域镜像固化进仓。

## 三镜代价

本次无 TG-23 命中（无跨系统架构选型，仅在既有单实例架构上加部署形态）。
