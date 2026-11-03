# Tasks

> 追溯：任务 ↔ 需求 ID 双向可查。设计见 [`design.md`](./design.md)，需求见 [`specs/deployment/spec.md`](./specs/deployment/spec.md)。
> 切片对应：第 1 组=S1，第 2 组=S2，第 3 组=S3，第 4 组=S4，第 5 组=S5（集成检查）。

## 1. 镜像构建层（S1）

- [ ] 1.1 新增 `.dockerignore`，排除 `.venv/`、`data/`、`tests/`、`openspec/`、`docs/`、`.env*`、`.git/`；验证：`docker build` 的构建上下文清单中不含这些路径
  - R-ID: R-DEP-04
- [ ] 1.2 新增多阶段 `Dockerfile`：依赖层只 COPY `backend/pyproject.toml` 与 `backend/uv.lock`，用 `ARG UV_DEFAULT_INDEX`（默认空）+ `uv export --frozen --no-dev` → `uv pip install --index-url` 安装；验证：`docker build --build-arg UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .` 构建成功
  - R-ID: R-DEP-07
- [ ] 1.3 运行时层 COPY `backend/app`、`backend/alembic`、`backend/alembic.ini` 并安装项目自身（`uv pip install --no-deps .`）；验证：`docker run --rm <img> python -c "import app; print(app.__version__)"` 输出 `0.1.0`，且 `docker image inspect --format '{{.Size}}'` 不大于 400MB（design 的 NFR）
  - R-ID: R-DEP-07
- [ ] 1.4 确认运行时镜像不含 dev 依赖与测试代码；验证：`docker run --rm <img> python -c "import pytest"` 必须失败（非零退出），且镜像内不存在 `tests/` 目录
  - R-ID: R-DEP-04
- [ ] 1.5 对构建产物做凭证扫描；验证：`docker run --rm <img> sh -c 'grep -rl "AKID\\|MASTER_KEY=" /app 2>/dev/null'` 无输出，且镜像历史中不含 `ENV MASTER_KEY` / `ENV ADMIN_PASSWORD`
  - R-ID: R-DEP-04

## 2. 启动契约（S2）

- [ ] 2.1 新增容器 entrypoint 脚本：`set -e` → `alembic upgrade head` → `exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`；验证：以空卷启动后 `GET /healthz` 返回 200，且容器内可见 `accounts`、`api_keys`、`users`、`quota_counters`、`usage_events` 五张表
  - R-ID: R-DEP-01
- [ ] 2.2 验证迁移失败的 fail-fast 行为；验证：把 `/data` 挂成只读或不可写后启动，容器以非零退出码终止，且日志中不出现 uvicorn 监听端口的信息
  - R-ID: R-DEP-01
- [ ] 2.3 验证重复启动幂等；验证：在同一已迁移的卷上二次启动，`alembic` 无升级输出且 `/healthz` 仍返回 200
  - R-ID: R-DEP-01
- [ ] 2.4 验证必填配置缺失时启动阶段失败；验证：不传 `MASTER_KEY`（或传非 32 字节值）启动，容器非零退出且日志含校验错误；不传 `ADMIN_PASSWORD` 或短于 8 字符时同样失败
  - R-ID: R-DEP-03
- [ ] 2.5 验证多 worker 配置被拒；验证：以 `WEB_CONCURRENCY=2` 启动，容器非零退出且日志含「单实例约束」
  - R-ID: R-DEP-06

## 3. 编排与运行身份（S3）

- [ ] 3.1 新增 `docker-compose.yml`：单服务、端口映射到 `127.0.0.1:8000`、`env_file: .env`、数据卷 `./data:/data`、`environment: DATA_DIR=/data`（绝对路径）；验证：`docker compose config` 通过且解析出的 `DATA_DIR` 为 `/data`
  - R-ID: R-DEP-05
- [ ] 3.2 配置 healthcheck（`interval=10s`、`timeout=3s`、`retries=5`、`start_period=30s`），探测命令用容器内 Python 标准库请求 `/healthz`（镜像无 curl/wget）；验证：`docker compose up -d` 后 `docker inspect --format '{{.State.Health.Status}}'` 返回 `healthy`
  - R-ID: R-DEP-02
- [ ] 3.3 以非 root 用户运行并让 `/data` 归属该用户；验证：`docker compose exec ocr-gateway id -u` 不为 `0`，且配额刷盘与迁移均无权限错误
  - R-ID: R-DEP-08
- [ ] 3.4 配置 `restart: unless-stopped` 与日志轮转（`max-size` / `max-file`）；验证：`docker compose config` 中两项均存在，且强制杀掉主进程后容器自动重启并重新达到 `healthy`
  - R-ID: R-DEP-08
- [ ] 3.5 验证数据持久化；验证：经管理 API 建一个成员后执行 `docker compose down` 与 `docker compose up -d`，该成员仍可通过 `GET /api/admin/users` 查到
  - R-ID: R-DEP-05

## 4. 文档与配置面（S4）

- [ ] 4.1 改写 `README.md` 部署段：以 `docker compose up -d` 一键起为主路径、本机 uv + uvicorn 为备选；补 `UV_DEFAULT_INDEX` 说明与 Caddy/Nginx 反代配置片段；验证：从干净 checkout 按 README 步骤可复现到 `healthy`，并把实际命令与输出记入验收记录
  - R-ID: R-DEP-07
- [ ] 4.2 更新 `.env.example`：补 `UV_DEFAULT_INDEX`（构建期，默认留空）与容器内 `DATA_DIR=/data` 说明，保留 `change-me-please` 占位且不含任何真实密钥；验证：`docker compose config` 能解析该文件，且文件内无 `AKID` 等真实凭证片段
  - R-ID: R-DEP-03
- [ ] 4.3 更新既有静态文档测试 `backend/tests/test_ticket5_api.py::test_run_docs_cover_quickstart_and_operations`：保留原有断言针（`alembic upgrade head`、`MASTER_KEY`、`ADMIN_PASSWORD`、`--workers 1`、`sqlite3`、`.backup`、`以官网为准`、`HTTPS`、`RPO`、`RTO`），新增 `docker compose up -d` 与 `UV_DEFAULT_INDEX` 断言；验证：`pytest backend/tests/test_ticket5_api.py -q` 全绿
  - R-ID: R-DEP-07
- [ ] 4.4 全量回归；验证：`pytest backend/tests -q` 全绿（含 T1/T2 的既有用例），`ruff check backend` 与 `mypy backend/app` 无新增问题
  - R-ID: R-DEP-07

## 5. 集成检查：真机端到端验收（S5）

> 本组只做跨组集成验证；三种输入、缓存、配额、切厂商的行为由既有能力拥有，此处**验证**而非重定义。

- [ ] 5.1 冷启动计时；验证：清空 `data/` 后 `docker compose up -d` 到 `healthy` 且 `/healthz` 200 的总耗时 ≤90s，记录时间戳
  - R-ID: R-DEP-01, R-DEP-02
- [ ] 5.2 经管理 API 完成配置；验证：`POST /api/admin/login` 取 token → 建成员、建 Key（记录唯一一次明文）、建百度与腾讯账号（真实凭证经 `env_file` 注入，不写入任何文件），`GET /api/admin/accounts` 返回两家且不含明文凭证
  - R-ID: R-ADM-02, R-ADM-03, R-ADM-04
- [ ] 5.3 真机三输入识别；验证：用真 Key 分别提交 multipart 文件、base64、公网 `image_url`（`https://baidu-ai.bj.bcebos.com/ocr/general.png`），三次均返回 200 且 `text` 非空、`lines` 为非空数组、`provider` 为实际厂商，记录每次的 `text` 片段与 `latency_ms`
  - R-ID: R-API-01, R-API-02
- [ ] 5.4 缓存命中；验证：重复提交同一图片且 `language`/`provider` 不变，第二次返回 `cached=true` 且 `quota.used=0`
  - R-ID: R-CAC-01
- [ ] 5.5 配额记账；验证：`GET /api/admin/usage/summary` 与 `GET /api/admin/logs` 能反映本次调用（成功计数 +1、缓存命中 +0），且日志不含 OCR 原文
  - R-ID: R-QTA-01, R-QTA-05
- [ ] 5.6 显式厂商不回退；验证：禁用全部百度账号后请求 `provider=baidu`，返回错误而非由腾讯完成
  - R-ID: R-SCH-05
- [ ] 5.7 `auto` 跨厂商切换；验证：禁用全部百度账号后请求 `provider=auto`，由腾讯账号完成，响应 `provider=tencent`
  - R-ID: R-SCH-03, R-SCH-05
- [ ] 5.8 归档验收证据；验证：在本 change 目录写入验收记录（命令、时间戳、响应片段、镜像扫描结果、`docker inspect` 健康状态），并逐条对应本组 5.1–5.7
  - R-ID: R-DEP-01, R-DEP-02, R-DEP-03, R-DEP-04, R-DEP-05, R-DEP-06, R-DEP-07, R-DEP-08

## 测试覆盖图（TG-18）

| 代码路径 / 产物 | 测试类型 | 覆盖方式 |
| --- | --- | --- |
| `Dockerfile` 依赖层（`uv export` + `uv pip install`） | 构建验证 | 1.2：带 `--build-arg` 的构建成功 |
| `Dockerfile` 运行时层（无 dev 依赖 / 无测试） | 构建验证 | 1.4：`import pytest` 必须失败 |
| 镜像与构建上下文（凭证） | 静态扫描 | 1.1 / 1.5：上下文清单 + 镜像内容 grep |
| entrypoint 正常路径（迁移 → 启动） | 容器集成 | 2.1：空卷启动 → `/healthz` 200 + 五张表存在 |
| entrypoint 失败路径（迁移失败 / 缺配置） | 容器集成 | 2.2 / 2.4：非零退出且不监听端口 |
| entrypoint 幂等路径 | 容器集成 | 2.3：二次启动无升级输出 |
| `enforce_single_worker` 容器路径 | 容器集成 | 2.5：`WEB_CONCURRENCY=2` → 非零退出 |
| `docker-compose.yml` 编排契约 | 配置校验 + 运行验证 | 3.1 / 3.2 / 3.4：`compose config` + `inspect` 健康状态 |
| 数据卷持久化 | 容器集成 | 3.5：down/up 后数据仍在 |
| 运行身份 | 容器集成 | 3.3：`id -u` 不为 0 |
| `README.md` / `.env.example` | 单元（pytest 静态断言） | 4.2 / 4.3：更新后的文档测试 |
| 网关真链路（鉴权/调度/配额/缓存/切厂商） | 真机端到端（手工验收 + 证据） | 5.2–5.7：真实凭证下的响应字段核对 |
| 全量回归 | 单元 + 集成（既有套件） | 4.4：`pytest backend/tests` |

## Workflow follow-up

- 评审通过后归档本 change，并同步主 spec（新增 `deployment` 能力）。
- 合并后于 `main` 上单独提交一个 chore，把 `openspec/issues/open/T1.md`、`T2.md`（均已是 `status: RESOLVED`）移入已关闭池。
