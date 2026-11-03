# Proposal

## Why

`ocr-gateway-mvp` 已于 2026-11-03 归档，但服务**从未真实运行过**：本机既无 `.env` 也无 `data/`，README 的 quickstart（`uv sync --project backend`）在当前离线环境直接失败（`pypi.org` 不可达，curl exit 28），而契约测试只证明**适配器**可用——网关 HTTP 路径（鉴权、调度、配额、缓存、跨厂商切换）从未对真实厂商跑过一次。没有可复现的部署产物，「MVP 完成」目前只是代码层面的结论，不是可交付的服务。

## What Changes

- 新增多阶段 `Dockerfile`：依赖层（`uv export --frozen` → `uv pip install --index-url <ARG>`）与代码层分离；运行时镜像不含 dev 依赖与测试；非 root 用户运行。
- 新增 `docker-compose.yml`：单服务、healthcheck 消费 `/healthz`、数据卷、`env_file` 注入凭证、`restart: unless-stopped`、日志轮转（`max-size`/`max-file`）。
- 新增容器 entrypoint：先执行 `alembic upgrade head`（幂等），再以 `uvicorn --workers 1` 启动；迁移失败即退出（fail-fast）。
- 新增 `.dockerignore`：排除 `.venv`、`data/`、`tests/`、`openspec/`、`docs/` 等，避免把本机环境与凭证目录带进构建上下文。`[spec-review-amendment]` 补 `docs/`：本地真实凭证文档位于该目录（`docs/已开通的 OCR 服务信息.md`，仅 `.git/info/exclude` 本地忽略）。
- 修改 `README.md`：部署段以「compose 一键起」为主、本机 uv 路径为备选；补镜像源参数说明与 Caddy/Nginx 配置片段。
- 修改 `.env.example`：补构建期变量（`UV_DEFAULT_INDEX`）与容器内 `DATA_DIR` 绝对路径的说明。
- 新增真机端到端验收记录（落在本 change 目录）：起服务 → 建成员/Key/百度+腾讯账号 → 三种输入 + 缓存 + 配额 + 切厂商逐项结果。
- **不改** `backend/app/**` 业务逻辑（除非启动路径暴露部署相关缺陷，见 Non-Goals 的可证伪假设）。

## Success Metrics

- **一键起可用** — 基准：干净 checkout 上 `uv sync` 因 PyPI 不可达失败、且无 `data/` 目录 → 目标：`docker compose up -d` 后 ≤90s 内 `/healthz` 返回 200 且 `docker compose ps` 显示 `healthy` — 度量方式：验收记录中的启动时间戳 + `curl -i /healthz` 原始输出。
- **真机端到端通过** — 基准：网关 HTTP 路径的真实厂商调用次数为 0 → 目标：验收清单全部场景通过、0 失败 — 度量方式：逐项结果表 + 真 Key 响应中的 `provider`/`text`/`quota`/`cached` 字段。
- **镜像不含凭证** — 基准：不存在镜像产物 → 目标：镜像文件系统内 `MASTER_KEY`、`ADMIN_PASSWORD`、百度/腾讯密钥出现次数为 0 — 度量方式：对镜像内容执行 `grep -r` 扫描并记录命令与输出。

## Non-Goals

- **不带反向代理**（D4）— 可证伪假设：反代属部署环境、不在产品仓内。若验收发现 `TRUST_PROXY_HEADERS=true` 的路径存在非反代无法暴露的缺陷，则该假设被证伪。
- **不做完整生产加固**（D5）— 可证伪假设：≤5 人、日均 <500 次规模下 read-only rootfs / CPU 内存限额 / 自定义 seccomp 的收益低于维护成本。若上线后出现内存无界增长或需要容器隔离，则证伪。
- **不做多实例 / Postgres** — 可证伪假设：规模前提 D14（≤5 人、日均 <500 次）未变。若并发或数据量突破该前提则证伪。
- **不改业务逻辑** — 可证伪假设：现有代码无需改动即可容器化。若启动路径暴露相对路径、CWD 耦合等**部署正确性**缺陷，则证伪，且这类缺陷在本 change 内修（不属于越界）。
- **不覆盖 `TRUST_PROXY_HEADERS=true` 的真机路径** — 已有 mock 测试（`backend/tests/test_ticket2_admin.py::test_login_uses_forwarded_ip_when_trusted`）；真机反代验收留给后续 change。可证伪假设：若上线后发现登录限速的客户端 IP 识别必须在真实反代下才能确认，则该假设被证伪。`[spec-review-amendment]` 补可证伪假设（BASE-13）。
- **不做 M3 管理面板、M2 补齐阿里/华为、M4 本地 OCR 兜底** — 分别受「本机凭证文件只有百度与腾讯」与体量约束，另开 change。

## Compliance

- 遵守既有决策：D13（应用不终结 TLS，只绑回环/内网）、D14（单实例规模前提）、C7（默认不落 OCR 原文）。本 change 不改变这些。
- 遵守 ADR-0001（`openspec/adr/0001-container-deps-use-uv-export-not-uv-sync.md`）：容器依赖安装走 `uv export` + `uv pip install`，**不改动被跟踪的 `uv.lock`**。
- 遵守单 worker 约束（`backend/app/config.py:108-130`）：compose MUST NOT 设 `WEB_CONCURRENCY` / `UVICORN_WORKERS` 大于 1。
- 凭证保护：真实凭证仅经环境变量 / `env_file` 注入，MUST NOT 进入镜像层、MUST NOT 进仓（`.gitignore:1-5`、`.git/info/exclude`）。
- 第三方数据：OCR 图片发往百度/腾讯属既有产品行为，本 change 不改变；验收使用公网样例图，不含 PII；C7（默认不落 OCR 原文）继续生效。`[spec-review-amendment]` 按 BASE-21 补显式声明。
- 数据库变更：本 change **不涉及** schema 迁移（沿用 `backend/alembic/versions/0001_initial.py`），故不适用 D-2。

## 需求优先级

- **P0**（缺一即「一键起」不成立）：启动期自动迁移、`/healthz` 健康检查、凭证环境注入且不进镜像、数据卷持久化、单 worker 约束、真机端到端验收全项通过。
- **P1**（决定「部署可用」）：非 root 运行、`restart: unless-stopped`、日志轮转、构建可复现（锁文件版本 + 参数化镜像源）。
- **P2**（证据与文档）：镜像层凭证扫描记录、README 反代配置片段。

## 假设

- **A1** 非 root 用户 + 绑定挂载在 Windows Docker Desktop 下权限可用 —— **未验证**；若不成立，改用命名卷或调整 uid。
- **A2** registry mirror 可稳定拉取 `python:3.12-slim` —— 已验证一次（digest `sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`），但 mirror 本身无 SLA。
- **A3** 验收用公网样例图保持可达 —— 已验证 200（`https://baidu-ai.bj.bcebos.com/ocr/general.png`，1581730 bytes），属外部资源。
- **A4** 真实厂商免费额度在验收调用量下充足 —— **未验证**具体余量；人 2026-11-03 已批准消耗少量额度。
- **A5** 本机 Docker daemon 在验收时可用 —— 当前 `server=29.4.3 os=linux arch=x86_64`，但依赖 Docker Desktop 保持运行。

## Capabilities

### New Capabilities

- `deployment`: 容器化部署与启动契约——一键起、启动期自动迁移、配置与凭证注入、数据持久化、运行身份与自愈、构建可复现。

### Modified Capabilities

无。本 change 不改变既有能力的 spec 级行为：`/healthz` 的端点契约仍由 `ocr-api` 的 R-API-06 拥有，本 change 只是让容器编排消费它。

## Impact

- **新增文件**：`Dockerfile`、`docker-compose.yml`、`.dockerignore`、容器 entrypoint 脚本。
- **修改文件**：`README.md`（部署 / quickstart 段）、`.env.example`（构建期变量与容器内 `DATA_DIR`）。
- **不改**：`backend/app/**` 业务逻辑、数据库 schema、任何公共 API 契约。
- **构建期外部依赖**：容器 registry mirror（Docker Hub 直连不可用）、PyPI mirror（`pypi.org` 不可用）。
- **运行期外部依赖**：不变（百度 / 腾讯 OCR API）。
