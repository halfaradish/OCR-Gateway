---
ship-gate:
  design_approved: true
  reviewed_sha: 1af7c2ea0552691e5f63d658b1b2cf9e637d5e5fa458b671af5e06a4dc09f56d
  reviewed_manifest: MTAwNjQ0IGJsb2IgOWEwMjFiNzUyYjY5ODNmY2I2ZDk3YjRlN2RkYzhiZmJmN2ZmM2NkNQlvcGVuc3BlYy9jaGFuZ2VzL2RvY2tlci1kZXBsb3ktZTJlL2RlY2lzaW9uLW1lbW8ubWQAMTAwNjQ0IGJsb2IgMWEzMWQyZTgzYjAxZDY1MjI4ZDllOGNlMmUzZWNlMGM4NTYzY2M2MglvcGVuc3BlYy9jaGFuZ2VzL2RvY2tlci1kZXBsb3ktZTJlL2Rlc2lnbi5tZAAxMDA2NDQgYmxvYiA5ZGI4MjRjM2MyOTVmMjMwZWYyOWQwYzdiZTc2MmRhOGI0MjI2YjU5CW9wZW5zcGVjL2NoYW5nZXMvZG9ja2VyLWRlcGxveS1lMmUvcHJvcG9zYWwubWQAMTAwNjQ0IGJsb2IgNzVkMmNjMTgwY2IzYzQ2ZmU3NDAzOGEwNzYxOGIyODJiN2NhNDVkZglvcGVuc3BlYy9jaGFuZ2VzL2RvY2tlci1kZXBsb3ktZTJlL3NwZWNzL2RlcGxveW1lbnQvc3BlYy5tZA==
---
> ⚠️ **单 session 自查**：逐镜由主 session 完成；同模型、不同上下文，非独立评审。
> 报告头部记 `dispatch: single-session`（本仓无 fresh-subagent 派发能力）。
>
> 评审对象：`openspec/changes/docker-deploy-e2e/` 四件套 @ `4a9ebbf`（下称 **C1**）。
> 本报告同批 amendments 产出 **C2**；对 C2 的窄复核见 §7。
> 人 2026-11-03 批准 **Q1=A / Q2=A / Q3=A**，决策落盘产出 **C3**；拍板记录见 §10，锚写 C3。
> 决策纪要机械门：`check_decision_memo.py` → `{"ok": true}`，exit 0。

# 设计评审报告 · docker-deploy-e2e

## 拍板三问

> 人在设计 HARD-GATE 逐项勾选；每问的自答只指回锚点，不替代人的判断。

**Q-scope 范围划界认不认？**
自答：锚 `proposal.md` `## Non-Goals`（24–31 行）+ `design.md` `## Goals / Non-Goals`（15–27 行）——范围是
「compose 单服务 + 启动期自动迁移 + 最小加固 + 真机 E2E」；明确不做反代/TLS、多实例/Postgres、完整加固、
业务逻辑改动；E2E 只验证既有能力，不重定义。范围自洽，未见蔓延（5 个切片落在 3–6 票预算内）。
[x] 认 [ ] 不认

**Q-deps 依赖/顺序认不认？**
自答：锚 `design.md` `## 切片与依赖`（95–105 行）——S1→S2→S3→S4→S5，S5 依赖 S3/S4。顺序本身合理；
但 **S1 的构建命令有 4 个会直接打断出镜像的缺陷**（D1 `uv export` 输出 `-e .`、D2 无 venv、D3 构建期
镜像源无通路、D14 uv 自身未安装），必须先在 tasks/ADR 修正再出票。
[x] 认 [ ] 不认

**Q-risk 风险赌注与对策认不认？**
自答：锚 `design.md` `## Risks / Trade-offs`（118–126 行）+ `proposal.md` `## 假设`（47–53 行）——主要赌注是
registry/PyPI mirror 可达（A2）与 A1「非 root + bind mount 在 Windows Docker Desktop 下权限可用」。
A1 **只覆盖 Windows，未覆盖目标 Linux 服务器**（Q1）；90s 指标未排除首次构建（Q2）；镜像平台/发布未定义（Q3）。
[x] 认 [ ] 不认

## 决策登记区

### [自动决策]（默认采纳，人可在设计门覆盖）

| ID | 决策 | 依据（主审亲验锚） |
| --- | --- | --- |
| **D1** | `uv export` 必须加 `--no-emit-project` | 亲验：`uv export --frozen --no-dev --format requirements-txt --no-hashes \| head -3` → 首个依赖项行是 `-e .`；加 `--no-emit-project` 后无 `-e .`、38 个 `==` 项。tasks 1.2 的依赖层只 COPY `pyproject.toml`+`uv.lock`，`-e .` 会在无 `app/` 的层里构建失败。 |
| **D2** | 构建期创建 `/app/.venv`（推荐）或显式 `UV_SYSTEM_PYTHON=1`；多阶段下 MUST 把 venv COPY 到运行时层，entrypoint 用 venv 内 console scripts | 亲验：无 venv 时 `uv pip install --dry-run --no-deps .` → `error: No virtual environment found; run 'uv venv' ... or pass '--system'`。`python:3.12-slim` 默认无 venv；ADR-0001 的三条命令未记录该步。多阶段构建不会自动把构建阶段的 venv 带进运行时层。 |
| **D3** | compose 必须用 `build.args: UV_DEFAULT_INDEX: ${UV_DEFAULT_INDEX:-}` 传构建期镜像源 | Docker/Compose 语义：`env_file` 只注入运行期容器环境，**不会**成为构建参数；design 组件图把「镜像源」列在 `env_file` 行（design:58），tasks 3.1 的 compose 字段（tasks:34）无 `build.args` ⇒ 一键起路径在离线环境构建失败。 |
| **D4** | `.dockerignore` 模式改为 `**/.venv`、`**/tests`、`**/data`、`**/__pycache__`、`**/.pytest_cache`、`**/.ruff_cache`、`**/.mypy_cache` | 亲验：`du -sh backend/.venv` → 150M；Docker 的 `.dockerignore` 模式相对**构建上下文根**匹配，`.venv/` 不匹配 `backend/.venv`。tasks 1.1（tasks:8）当前写法会把 150M venv 与测试送进上下文。 |
| **D5** | 凭证扫描改为「对停止态容器/镜像层扫全文件系统 + 用 `.env` 实际值匹配」，不只 `/app` + `AKID` | tasks 1.5（tasks:16）的 `grep -rl "AKID\|MASTER_KEY=" /app` 覆盖不到百度密钥（无 `AKID` 前缀），也只扫 `/app`；R-DEP-04（spec:56–68）要求「镜像内不含百度或腾讯密钥的任何取值」。注意避开 `/proc/*/environ` 的运行时假阳性。 |
| **D6** | 验收证据不得原样粘贴 `docker compose config` 输出 | tasks 3.1/5.8 用 `docker compose config` 验证，Compose 会渲染解析后的 `MASTER_KEY`/`ADMIN_PASSWORD` 明文；改为 `docker compose config \| grep -E 'DATA_DIR\|restart\|healthcheck\|logging'` 之类的过滤输出。 |
| **D7** | compose 增加 `stop_grace_period: 25s`（或 uvicorn `--timeout-graceful-shutdown 20`） | `REQUEST_DEADLINE_MS=20000`（`backend/app/config.py:71`）与 `httpx.Timeout`（`backend/app/main.py:69`）允许 20s 在途请求；Docker 默认 10s 后 SIGKILL，`docker compose down` 会截断在途 OCR 请求。配额最多丢 2s 是已接受 RPO，但请求被硬切不在 RPO 口径内。 |
| **D8** | compose 日志配置显式写 `driver: json-file` | `max-size`/`max-file` 只对所选日志驱动生效；宿主机默认驱动不是 json-file 时这两项静默无效。tasks 3.4（tasks:40）只写两项。 |
| **D9** | R-DEP-02 改为「编排以 `/healthz` 为探测入口」并引用 R-API-06，不重述状态码契约 | `specs/deployment/spec.md:28–40` 与 `openspec/specs/ocr-api/spec.md:103` 形成两个真相源；`proposal.md:63` 自己声明「端点契约仍由 R-API-06 拥有」。 |
| **D10** | R-DEP-05 场景改为「配额计数与用量事件（`usage_events`）落在卷内；进程日志经 stdout 由容器日志驱动轮转」 | 亲验：`backend/app/logging_setup.py:26` 是 `StreamHandler(sys.stdout)`，没有文件 handler；`specs/deployment/spec.md:77–82` 写「请求日志落在挂载卷内」与代码不符/歧义；`README.md` 环境变量表把 `DATA_DIR` 描述为「SQLite 与日志目录」也不准确。 |
| **D11** | tasks 1.3 的 `uv pip install --no-deps .` 补 `--index-url "$UV_DEFAULT_INDEX"` | ADR-0001 Decision 第 3 步已写 `--index-url`，tasks 1.3（tasks:12）漏了；离线环境构建后端 `hatchling` 会去默认 PyPI 拉取而失败。 |
| **D12** | tasks 4.3 的「保留原有断言针」清单补 `uv sync` | 亲验：`backend/tests/test_ticket5_api.py:287–300` 现有断言含 `"uv sync"`；tasks 4.3（tasks:51）列的 10 个针不含它。若 README 备选路径仍保留 `uv sync`，断言应保留。 |
| **D13** | compose 显式 `environment: DATABASE_URL: ""`；`.env.example` 保留 `DATA_DIR=./data` 并注明 compose 覆盖为 `/data` | `backend/app/config.py:89`：`DATABASE_URL` 非空时优先于 `DATA_DIR` 推导。若 `.env` 残留宿主机用的非空 `DATABASE_URL`，容器会把库写到 `/app/data`（容器层），重建即丢。tasks 4.2 的「补容器内 `DATA_DIR=/data` 说明」若被理解成改示例值，会反过来破坏 uv 备选路径。 |
| **D14** | 构建阶段显式安装并固定 uv 版本（如 `pip install --index-url "$UV_DEFAULT_INDEX" uv==0.13.6`） | `python:3.12-slim` 不含 uv；design/tasks 未写 uv 从哪来。`COPY --from=ghcr.io/astral-sh/uv` 依赖 ghcr.io 可达，本机 Docker Hub 直连已不可达（C7），不能假定。固定版本同时补「构建可复现」的一环。 |
| **D15** | tasks 1.2 落基础镜像 digest（`FROM python:3.12-slim@sha256:b18b...`） | design:93 说「固定 digest」，tasks 1.2 只写 tag；不落 digest 则 R-DEP-07 的可复现性少一环。 |
| **D16** | design Open Questions 补 owner/截止，并注明 `tickets.md` 由 ship 出票阶段生成 | design:145 的 tag 问题无负责人/截止（BASE-15），且「可延后」与同句「当前按 0.1.0+latest 双打」自相矛盾；design:97 引用 `tickets.md`，该文件当前不存在（由 `/sdflow-lite-ship` 生成）。 |
| **D17** | 决策纪要「无 TG-23 命中」的偏差只记录、不改 memo | memo:48 称「本次无 TG-23 命中」，但 D1/D3/D4/D5 都记录了 ≥2 候选，按 BASE-12 属 TG-23 命中。memo 的 `decision_hash` 由 `check_decision_memo.py` 按正文重算，直接编辑会使机械门失败；建议后续 change 重跑 memo 时补三镜/主次判定，本 change 不阻塞。 |
| **D18** | proposal Impact 的 `.dockerignore` 清单补 `docs/` | proposal:12 列了 `.venv`、`data/`、`tests/`、`openspec/`，漏了 `docs/`；`docs/已开通的 OCR 服务信息.md` 是本地真实凭证文档（`.git/info/exclude` 末行），design:89 与 tasks 1.1 都已要求排除，proposal 应与之一致。 |
| **D19** | proposal Compliance 补一句第三方数据声明 | BASE-21 要求显式声明「数据是否发往第三方 + 脱敏策略」；现 proposal:33–39 只写 C7（不落 OCR 原文）。补：图片发往百度/腾讯属既有产品行为，本 change 不改变；E2E 用公网样例图，不含 PII。 |
| **D20** | 为无对应验证任务的场景补注释或显式接受 | R-DEP-07 负向（无索引→构建失败）、R-DEP-02 DB 不可用→503、R-DEP-08 日志实际轮转，均无对应验证任务（tasks 1.2/3.2/3.4 只验正向或配置存在）。至少在测试覆盖图里标注「配置级验证，接受」。 |
| **D21** | README 新 quickstart 补 TTHW 推导（步骤/命令数 + 每步耗时假设 + 标注「估算」） | DX-01 触发：本 change 重写首次上手路径。现 README「约 5 分钟」是裸数字无推导；tasks 4.1 未要求补推导。 |
| **D22** | README 注明 uv 备选路径的前置条件（PyPI 可达；离线时需 `UV_DEFAULT_INDEX` 且可能改写 `uv.lock`） | 本机 `pypi.org` 不可达（proposal:5）；`uv sync --frozen` 因锁文件 URL 失败（ADR-0001）。备选路径若不在文档里写清前置，读者会重复踩坑。 |
| **D23** | proposal Non-Goal「不覆盖 `TRUST_PROXY_HEADERS=true` 真机路径」补可证伪假设 | BASE-13 要求每条 defer 附可证伪假设；该条只有「已有 mock 测试」的理由。补：若上线后发现反代场景必须真机验收才能确认登录限速 IP 识别，则证伪。 |

### [需拍板]（设计门逐项勾选）

#### Q1 · 非 root + bind mount 的 `/data` 权限模型

- **事实**：design:90 要求「非 root 用户运行；`/data` 目录归属该用户」；tasks 3.3 要求 `docker compose exec ocr-gateway id -u` 不为 0 且迁移/刷盘无权限错误；compose 用 bind mount `./data:/data`（tasks:34）。
- **为什么会在目标态爆炸**：镜像构建期的 `chown /data` **不作用于宿主 bind mount 目录**。Linux 上 `./data` 由 Docker 以 root:root 创建（或由宿主用户拥有），容器内 uid 10001 迁移时 EACCES → fail-fast 重启循环。Windows Docker Desktop 的权限映射较宽松，**本机验收可能绿，而「搬到任意 Linux 服务器」（D1 的理由）失败**——这正是「现状不能给目标松绑」。
- **选项**：
  - **A（推荐）** entrypoint 以 root 启动 → `chown -R app:app /data` → `exec setpriv --reuid=app --regid=app --init-groups uvicorn ...`。系统镜：需 root 启动 + `setpriv`（debian slim 的 util-linux 自带）；可回退。用户镜：行为不变。开发循环镜：entrypoint 多 2 行，`id -u` 在降权后验证。
  - **B** 命名卷 `ocr-data:/data`。Docker 用镜像内 `/data` 的属主初始化新卷，权限天然正确；代价是备份要 `docker cp`/进容器，与 README 的 `sqlite3 data/...` 习惯不一致（design 已因备份选 bind）。
  - **C** 文档要求宿主 `sudo chown -R 10001:10001 ./data`（或 compose `user: "${UID}:${GID}"`）。零镜像改动，但「一键起」多一步手工，Windows 无 uid。
- **主次判定**：系统镜（目标 Linux 可搬迁）> 开发循环镜（entrypoint 复杂度）> 用户镜（备份习惯）⇒ 推荐 A；若人更看重备份习惯，选 C + 文档。
- **推荐未亲验**：Linux 侧行为未在本机实测（Windows 只能验 Windows 映射）；依据是 Docker bind mount 语义 + tasks 3.3 文本。
- **拍板**：`[ ] A  [ ] B  [ ] C`

#### Q2 · 90s 冷启动指标是否排除首次镜像构建

- **事实**：proposal:20「干净 checkout 上 … `docker compose up -d` 后 ≤90s 内 `/healthz` 返回 200」；tasks 5.1「清空 `data/` 后 `docker compose up -d` 到 `healthy` 的总耗时 ≤90s」。
- **问题**：镜像未构建时 `docker compose up -d` 会先构建（38 个依赖包 + 镜像层，分钟级），90s 不可满足；若镜像已构建，90s 是合理口径。两种解读产出**实质不同的验收产物**。
- **选项**：A（推荐）明确「镜像已构建」前提，冷启动 ≤90s；首次构建单列（建议 ≤10min 或只记录不设上限）。B 把构建纳入 90s（不可行）。C 取消 90s，只记录实测。
- **主次判定**：系统镜（指标可判定）> 用户镜（首次体验）> 开发循环镜（验收脚本）⇒ 推荐 A。
- **拍板**：`[ ] A  [ ] B  [ ] C`

#### Q3 · 镜像目标平台 / 命名 / 发布

- **事实**：本 change 产出容器镜像（BE-10 触发）；design:145 说 tag「当前按 `0.1.0` + `latest` 双打」，但 tasks 无任何 tag/publish/平台任务；本机 daemon `os=linux arch=x86_64`（C7）。
- **问题**：不定义平台，「搬到任意 Linux 服务器」对 arm64 不成立；不定义命名/tag，出票后无法验收「镜像可回滚」（design:141 说回滚靠固定 tag，但无任务产出 tag）。
- **选项**：A（推荐）只支持 `linux/amd64`，镜像名 `ocr-gateway:0.1.0` + `latest`，不发布 registry，arm64 作为 non-goal。B buildx 多架构（amd64+arm64），代价：构建时间翻倍、需 QEMU，超出「一键起」。C 发布到 registry（需命名空间/凭证），本次不做。
- **主次判定**：系统镜（可搬迁范围）> 开发循环镜（构建复杂度）> 用户镜（服务器架构）⇒ 推荐 A。
- **拍板**：`[ ] A  [ ] B  [ ] C`

### [已裁掉]（原始发现 + 裁掉理由，供复核「裁得对不对」）

| ID | 原始发现 | 裁掉理由 |
| --- | --- | --- |
| **X1** | 场景未覆盖「迁移中途失败后的卷状态」（BASE-01 边界） | Alembic 在 SQLite 上单事务执行；R-DEP-01 的「迁移失败→不服务」已覆盖可观察行为；卷半迁移状态不是本 change 的验收面。 |
| **X2** | 外部计费服务成本估算缺失（BASE-26/TG-24） | proposal A4 + 人 2026-11-03 已批准消耗少量额度；一次性 E2E（个位数调用），无月度预算意义。 |
| **X3** | proposal `What Changes` 混入实现细节（BASE-22） | proposal 的 `What Changes` 允许点名产物（Dockerfile/compose）；「怎么做」在 design。不构成返工风险。 |
| **X4** | `.env` 缺失时 compose 报错未写入失败模式表 | Migration Plan 第 1 步已要求 `cp .env.example .env`；Compose 自身的 missing env_file 报错足够明确。 |
| **X5** | healthcheck 只探 DB，不探厂商（A2 失败模式） | design:125 已显式作为 trade-off 接受（探厂商会把外部故障误判为容器不健康）；不再重复。 |
| **X6** | 迁移耗时无 metrics（BE-07） | 容器退出码 + alembic stderr + 启动日志已可观测；规模下加 metrics 属过度设计（通则④）。 |
| **X7** | 构建期 mirror 拉取失败无重试/退避（BE-08） | 构建失败是 fail-fast，无部分镜像；Docker 构建本身可重跑，加应用层重试无收益。 |
| **X8** | 配置错误导致 restart 循环（A2） | design:122 已显式接受（循环期间不服务、退出码/日志可见、修复后自愈）；属已知取舍。 |
| **X9** | Windows bind mount I/O 较慢（A2） | design:126 已显式接受（日均 <500 次）；规模下不构成风险。 |
| **X10** | 400MB 镜像上限可能乐观（A2） | tasks 1.3 会在构建后 `docker image inspect` 实测；未实测前不预判失败。 |
| **X11** | 引用行号轻微漂移（如 design:77 写 `main.py:180-193`，实际 healthz 从 181 行起） | 纯装饰性，不影响任何结论；不为此改四件套。 |
| **X12** | `docs/已开通的 OCR 服务信息.md` 只被本地 `.git/info/exclude` 忽略，未进 `.gitignore` | 既有仓库卫生问题，不是本 change 引入；`.dockerignore` 已排除 `docs/`。建议另开 chore 把该模式加入 `.gitignore`。 |

## 0. 评审范围与镜 roster

- 四件套齐备：`openspec status --change docker-deploy-e2e --json` → `isPlanningComplete: true`；`openspec validate docker-deploy-e2e --strict` → valid。
- 命中触发词：TG-01（后端服务）、TG-08（构建期外部依赖）、TG-15（新 codepath：entrypoint）、TG-16（NFR）、
  TG-17（信任边界/凭证）、TG-18（测试计划）、TG-19（多需求）、TG-21（开放问题）、TG-22（假设）、
  TG-23（≥2 方案）、TG-28（配置面/README）。未命中：TG-04（无 schema 迁移）、TG-25（无版本化契约套件）、
  TG-27（无外部 LLM 产出消费）。
- 镜 roster（8 镜）：广审 **strategy** / **plan-eng**；领域 **backend** / **devex**；对抗 **A1 隐藏假设** /
  **A2 失败模式与乐观估计** / **A3 目标态 vs 现状**；接地 **G**。
- 工作树：评审开始时 `git status --porcelain` 为空（HEAD `4a9ebbf`）。

## 1. strategy 镜（base 计划级）

- **S1 · 90s 成功指标口径歧义**（中，置信高）— `proposal.md:20` / `tasks.md:60`。指标未排除首次镜像构建；
  `compose up` 在镜像缺失时会先构建。→ **Q2**。
- **S2 · 决策纪要自称无 TG-23，但记录了多组 ≥2 候选**（低中，置信高）— `decision-memo.md:48`
  「本次无 TG-23 命中」；同文 D1/D3/D4/D5 均列「砍掉的候选」。按 BASE-12，TG-23 命中时三镜 + 主次判定
  MUST 书面写入。→ **D17**（memo 有 hash 机械门，不在本报告直接改）。
- **S3 · Open Questions 无 owner/截止，且与已写默认值自相矛盾**（低，置信高）— `design.md:145`。
  「可延后」与「当前按 0.1.0 + latest 双打」并存；BASE-15 要求负责人 + 决策截止。→ **D16**。
- **S4 · proposal 的 `.dockerignore` 清单漏 `docs/`**（低，置信高）— `proposal.md:12` vs `design.md:89` /
  `tasks.md:8`；`docs/已开通的 OCR 服务信息.md` 是本地真实凭证文档。→ **D18**。
- **S5 · 合规声明缺「数据发往第三方」**（低，置信高）— `proposal.md:33–39` 只写 C7（不落 OCR 原文）；
  BASE-21 要求显式声明第三方数据与脱敏策略。→ **D19**。
- **S6 · 「不覆盖 `TRUST_PROXY_HEADERS` 真机路径」缺可证伪假设**（低，置信高）— `proposal.md:30`；
  BASE-13 要求每条 defer 附可证伪假设。→ **D23**。
- **S7 · design 引用尚不存在的 `tickets.md`**（低，置信高）— `design.md:97`；该文件由
  `/sdflow-lite-ship` 出票阶段生成（`SKILL.md:265`）。建议注明「出票后生成」。→ **D16**。
- **通过项**：范围/YAGNI（无顺手重构、无「以后可能用得上」的抽象）；需求优先级 P0/P1/P2 齐；
  假设列表 A1–A5 齐；非目标有可证伪假设（除 S6）；切片 5 个落在 3–6 票预算内（BASE-31）。

## 2. plan-eng 镜（base 工程级）

- **E1 · `uv export` 默认输出 `-e .`，依赖层必失败**（高，置信高）— tasks:10 / ADR-0001 Decision 第 1 步。
  亲验：`uv export --frozen --no-dev --format requirements-txt --no-hashes | head -3` → `-e .`；
  加 `--no-emit-project` 后 38 个 `==` 项、无项目行。依赖层只 COPY `pyproject.toml` + `uv.lock`（tasks:10），
  `-e .` 需要 `app/` 源码与 hatchling 构建。→ **D1**。
- **E2 · `uv pip install` 在无 venv 的 slim 镜像内直接报错**（高，置信高）— ADR-0001 Decision 第 2/3 步。
  亲验：`uv pip install --dry-run --no-deps .` 在无 venv 目录 → `error: No virtual environment found; run
  'uv venv' ... or pass '--system'`。`python:3.12-slim` 默认无 venv，ADR/tasks 未记录创建步骤。→ **D2**。
- **E3 · 构建期镜像源没有 compose 通路**（高，置信高）— `design.md:58` 把「镜像源」列在 `env_file` 行；
  `tasks.md:34` 的 compose 字段无 `build.args`。Compose 的 `env_file` 只注入运行期环境，构建参数必须走
  `build.args`（Compose 可用 `.env` 做 `${...}` 插值）。⇒ `docker compose up -d` 在离线环境构建失败，
  「一键起」主路径不成立。→ **D3**。
- **E4 · uv 自身如何进入构建镜像未定义，版本未固定**（中高，置信高）— `design.md:33–34` / `tasks.md:10`；
  `python:3.12-slim` 不含 uv；`COPY --from=ghcr.io/astral-sh/uv` 依赖 ghcr.io 可达（本机 Docker Hub 直连已不可达，
  C7 明确不能假定）。→ **D14**。
- **E5 · `.dockerignore` 模式不匹配嵌套路径**（中，置信高）— `tasks.md:8` 的 `.venv/`、`tests/`、`data/` 只匹配
  上下文根；`backend/.venv` 实存 **150M**（亲验 `du -sh`），`backend/tests` 也会进上下文。→ **D4**。
- **E6 · 凭证扫描不足以证明 R-DEP-04**（中，置信高）— `tasks.md:16` 只扫 `/app` 且只匹配 `AKID`/`MASTER_KEY=`；
  百度密钥无 `AKID` 前缀，且「镜像内」不等于 `/app`。→ **D5**。
- **E7 · `docker compose config` 会把凭证明文带进验收证据**（中，置信中高；无 compose 文件可亲验，语义为
  Compose 既有行为）— `tasks.md:34` / `tasks.md:74`。→ **D6**。
- **E8 · 缺少 `stop_grace_period` / uvicorn graceful shutdown**（中，置信高）— `backend/app/config.py:76`
  允许 20s 预算，`backend/app/main.py:69` 的 read timeout 8s；Docker 默认 10s 后 SIGKILL。→ **D7**。
- **E9 · 日志轮转未指定驱动**（中，置信高）— `tasks.md:40` 只写 `max-size`/`max-file`；非 json-file 驱动下
  两项静默无效。→ **D8**。
- **E10 · 基础镜像 digest 未落到任务**（低中，置信高）— `design.md:93` 说固定 digest，`tasks.md:10` 只写 tag。
  → **D15**。
- **E11 · tasks 1.3 的项目安装缺 `--index-url`**（中，置信高）— `tasks.md:12` vs ADR Decision 第 3 步；
  离线环境 hatchling 从默认 PyPI 拉取失败。→ **D11**。
- **E12 · tasks 4.3 的断言针清单漏 `uv sync`**（低中，置信高）— `tasks.md:51` vs
  `backend/tests/test_ticket5_api.py:288`。→ **D12**。
- **E13 · 三个负向场景无验证任务**（低，置信高）— R-DEP-07 无索引→构建失败（tasks 1.2 只验正向）、
  R-DEP-02 DB 不可用→503（tasks 3.2 只验 healthy）、R-DEP-08 实际轮转（tasks 3.4 只验配置存在）。→ **D20**。
- **E14 · R-DEP-02 与 R-API-06 重复定义 `/healthz`**（中低，置信高）— `specs/deployment/spec.md:28–40` vs
  `openspec/specs/ocr-api/spec.md:103`；proposal:63 自己说契约归 R-API-06。→ **D9**。
- **E15 · R-DEP-05「请求日志落在卷内」与代码不符/歧义**（中低，置信高）— `specs/deployment/spec.md:77–82`；
  `backend/app/logging_setup.py:26` 是 stdout handler。→ **D10**。
- **E16 · `DATABASE_URL` 非空会覆盖 `/data`**（中低，置信高）— `backend/app/config.py:89`；`.env.example:5`
  留空，但宿主机用的 `.env` 可能残留非空值。→ **D13**。
- **E17 · `.env.example` 的 `DATA_DIR` 容器/宿主机语义未写清**（中低，置信中高）— `.env.example:4` 是 `./data`，
  tasks 4.2 说「补容器内 `DATA_DIR=/data` 说明」；若改成 `/data` 会破坏 uv 备选路径。→ **D13**。

## 3. 领域镜

### 3.1 backend 镜（BE-01…BE-11）

- **B1 · BE-09 优雅退出**（中）— 同 E8；`docker compose down` 的 SIGTERM 默认 10s 后 SIGKILL，20s 预算内的
  在途请求被截断。→ **D7**。
- **B2 · BE-10 分发管道**（中）— 新产物是容器镜像，但 tasks 无目标平台（amd64/arm64）、无命名/tag、无发布
  规划；design:145 说回滚靠固定 tag（design:141），但无任务产出 tag。→ **Q3**。
- **B3 · BE-11 RTO/RPO**（通过）— design:84 沿用既有口径（重启 <5s、配额最多丢 2s），与 README 一致；
  90s 冷启动是首次启动指标，不是 RTO，不冲突。
- **B4 · BE-04 失败模式表**（通过）— design:67–75 覆盖缺配置、迁移失败、端口占用、DB 不可用、mirror 不可达、
  锁/导出一致性、厂商不可用；每条有检测/处理/可观测信号。
- **B5 · BE-03 凭证边界**（部分）— 只经 `env_file`/环境变量注入、非 root、镜像扫描方向正确；扫描方法不足
  见 E6/D5。
- **B6 · BE-07 可观测性**（通过）— 既有结构化请求日志（`backend/app/main.py:114–131`）+ `/healthz` + 容器层
  信号（compose healthcheck/退出码/日志轮转）；本 change 的新 codepath 是 entrypoint，其失败经退出码与
  alembic stderr 可观测。
- **B7 · BE-05 / BE-06 / BE-01 / BE-02**（N/A）— 无 schema 变更、无跨服务写、无 API 契约变更（R-DEP-02 的
  重复定义见 E14，不是行为变更）。

### 3.2 devex 镜（TG-28）

- **DX1 · DX-01 TTHW**（中低，置信高）— 本 change 重写首次上手路径（README quickstart/部署段），但
  design/tasks 未要求「步骤数/命令数 + 每步耗时假设 + 估算值 + 标注『估算』」；现 README「约 5 分钟」是
  裸数字。→ **D21**。
- **DX2 · DX-02 错误文案**（N/A）— 未新增/修改面向用户的错误文案；容器失败信息来自既有
  `ValidationError`/alembic/uvicorn。
- **DX3 · DX-03 命名/默认值**（通过，除 E17）— `UV_DEFAULT_INDEX` 沿用 uv 自身环境变量名；默认留空的理由
  在 D3/ADR-0001 写明；`DATA_DIR` 的容器/宿主机双语义见 E17/D13。
- **DX4 · DX-04 升级路径**（N/A）— 未废弃/变更既有 CLI/配置键的语义；`.env.example` 的 `DATA_DIR=./data`
  保持宿主机默认。
- **DX5 · DX-05 skill DX**（N/A）— 不涉及 SKILL.md。
- **DX6 · uv 备选路径的离线前置未写**（中低，置信高）— 本机 `pypi.org` 不可达（proposal:5），
  `uv sync --frozen` 因锁文件 URL 失败（ADR-0001）；README 若不写前置，读者会重复踩坑。→ **D22**。

## 4. 对抗镜

### 4.1 A1 · 隐藏假设（默认 refuted=true）

- **A1-1**「依赖层只 COPY `pyproject.toml`+`uv.lock` 后 `uv export`/`uv pip install` 可用」— **证伪**：
  `-e .` + 无 venv（E1/E2）。
- **A1-2**「镜像期 `chown /data` 对 bind mount 生效」— **证伪**（Linux 语义）：宿主目录属主不被镜像改变
  （Q1）。
- **A1-3**「`env_file` 能把 `UV_DEFAULT_INDEX` 传给构建」— **证伪**：`env_file` 只作用于运行期（E3）。
- **A1-4**「`python:3.12-slim` 自带 uv」— **证伪**：需显式安装（E4）。
- **A1-5**「`.dockerignore` 的 `.venv/` 能排除 `backend/.venv`」— **证伪**：模式相对上下文根（E5）。
- **A1-6**「镜像可搬到任意 Linux 服务器」— **部分证伪**：平台（amd64/arm64）与 `/data` 权限都未覆盖
  （Q1/Q3）。
- **A1-7**「`uv.lock` 的 38 个锁定项 = `uv export` 的全部输出」— **证伪**：输出还含 `-e .`；memo 的
  「38 个 `==` 项」只数了包行（C1 证据）。这解释了为什么 memo 的容器实测没暴露 E1——测试时源码在场。

### 4.2 A2 · 失败模式与乐观估计

- **A2-1 · 90s 乐观估计**（中）— 未排除首次构建（S1/Q2）。
- **A2-2 · restart 循环**（已接受）— design:122 已显式接受；不重复。
- **A2-3 · SIGTERM 截断在途请求**（中）— E8/D7。
- **A2-4 · 验收证据泄露凭证**（中）— E7/D6。
- **A2-5 · healthcheck 只探 DB**（已接受）— design:125 显式 trade-off。
- **A2-6 · 日志驱动未指定**（中）— E9/D8。
- **A2-7 · `.env` 的 `DATABASE_URL` 覆盖 `/data`**（中低）— E16/D13。
- **A2-8 · Windows bind mount I/O 慢**（已接受）— design:126。
- **A2-9 · 400MB 镜像上限**（未实测）— tasks 1.3 会实测；不预判。

### 4.3 A3 · 目标态 vs 现状（本地绿 ≠ 目标可用）

- **A3-1 · 本机 Windows 验收会掩盖 Linux 权限问题**（高）— A1 假设只覆盖 Windows；目标态是「搬到任意
  Linux 服务器」（D1）。→ **Q1**。
- **A3-2 · 本机镜像构建成功 ≠ 目标平台可运行**（中）— 未定义 arm64/amd64 支持面。→ **Q3**。
- **A3-3 · E2E 使用公网样例图 + 真实凭证**（通过）— A3/A4 已验证/已批准；SSRF 策略要求公网图（C8），
  验收图 200/1581730 bytes 已验。
- **A3-4 · 镜像扫描只扫 `/app` 会给出假绿**（中）— E6/D5。

## 5. 接地镜（G）

逐条核验 spec/design/tasks 中的代码事实；以下为亲验结果（命令输出或 `file:line`）：

| 事实 | 结论 |
| --- | --- |
| `uv export` 默认含 `-e .` | **不符**：命令输出首行 `-e .`；`--no-emit-project` 后消失（E1）。 |
| `uv pip install` 无 venv 可用 | **不符**：报 `No virtual environment found`（E2）。 |
| `backend/.venv` 是否存在/大小 | **存在，150M**（E5）。 |
| 日志写 `DATA_DIR` | **不符**：`backend/app/logging_setup.py:26` 是 stdout handler（E15）。 |
| `R-API-06` 存在 | **相符**：`openspec/specs/ocr-api/spec.md:103`（E14）。 |
| 现有文档测试含 `uv sync` | **相符**：`backend/tests/test_ticket5_api.py:288`（E12）。 |
| `docs/已开通的 OCR 服务信息.md` 存在且仅本地忽略 | **相符**：`.git/info/exclude` 末行；`git status --ignored` 可见（D18/X12）。 |
| `uv.lock` 1292 处 `files.pythonhosted.org`、仅 `pypi.org/simple` | **相符**：`grep -c` = 1292；`grep -o 'registry = ...' \| sort -u` = 仅 pypi.org（ADR-0001 依据成立）。 |
| Docker 版本 | **相符**：`Docker version 29.4.3`、`Compose v5.1.3`（D1 依据成立）。 |
| `backend/app/main.py` 行号 | **基本相符**：`app = create_app()` 204、`httpx.Timeout` 69、healthz 181–193、mkdir 55、`select(Account)` 60；design 的 180–193 有 1 行漂移（X11）。 |
| `backend/app/config.py` 行号 | **基本相符**：必填字段 66–67、`MAX_CONCURRENT_REQUESTS` 77、`database_url` 推导 89–92、`enforce_single_worker` 108–130。 |
| `backend/alembic` 行号 | **相符**：`alembic.ini:2` `script_location = %(here)s/alembic`；`env.py:29–42` URL 解析；`0001_initial.py:16` `revision = '01b12c86bd76'`；`env.py` 的 `_ensure_sqlite_parent` 从 56 行起、mkdir 在 63 行（design 说「56 行会自动建父目录」略有压缩）。 |
| `docs/tech-selection.md:634` M5「一键起服务」 | **相符**。 |
| `R-ADM-02/03/04`、`R-API-01/02`、`R-CAC-01`、`R-QTA-01/05`、`R-SCH-03/05` | **全部存在**（`openspec/specs/*/spec.md`）。 |

**接地结论**：核心代码事实成立；**构建链的三个命令事实不成立**（E1/E2/E3），这是本报告最高优先级的发现。

## 6. 合并裁决

- 合并去重后 23 条有效发现；同问题多镜命中已合并（E1/A1-1/G、E2/A1-1/G、E3/A1-3、E5/A1-5、
  E8/B1/A2-3、E14/B7、E15/G 等）。
- 引文抽查：本报告所有 `file:line` 均亲开文件核对；命令类证据（uv export/uv pip install/du/docker version/
  grep）均为本轮实际输出。**未亲验**项已在对应条目标注（Q1 的 Linux 侧、E7 的 compose 渲染、Q3 的平台）。
- 对抗裁决：A1 的 7 条隐藏假设中 6 条证伪/部分证伪；A2 的 9 条中 4 条落为有效发现、4 条为已接受取舍、
  1 条未实测；A3 的 4 条中 3 条落为有效发现、1 条通过。
- 反静默压制：全部 23 条 + 12 条已裁掉项均在册；无静默丢弃。

**裁决汇总**

| 处置 | 条目 |
| --- | --- |
| **阻塞级（必须先改再出票）** | D1（`-e .`）、D2（venv）、D3（build.args）、D14（uv 获取） |
| **高优先（影响目标态正确性）** | Q1（bind mount 权限）、Q2（90s 口径）、Q3（平台/tag）、D5（凭证扫描）、D7（graceful shutdown） |
| **中优先（实现期返工）** | D4、D6、D8、D9、D10、D11、D12、D13、D15、D20 |
| **低优先（文档/流程）** | D16–D19、D21–D23 |
| **已裁掉** | X1–X12 |

## 7. 窄复核（对 C2 amendments 的增量）

> 本报告 findings 针对 C1（`4a9ebbf`）；本报告同批 amendments 产出 C2。按 skill 的「拍板前窄复核」纪律，
> 对增量逐项复核如下（只审增量，不重跑全镜）。

- **C2 变更面**：`proposal.md`（Impact/Compliance/Non-Goal 补句）、`design.md`（构建决策/组件图/安全/失败模式/
  Open Questions）、`specs/deployment/spec.md`（R-DEP-02/R-DEP-05 措辞）、`tasks.md`（1.1–1.5、2.1、3.1、
  3.3–3.4、4.1–4.3、5.1、5.8、覆盖图）、`openspec/adr/0001-...md`（`--no-emit-project`/venv/uv pin）。
- **复核结果**：
  - D1/D2/D14 的修正在 tasks 1.2/1.3/2.1 与 ADR-0001 三处一致（`--no-emit-project`、`/app/.venv`、
    venv 跨阶段 COPY、entrypoint 用 venv console scripts、`uv==0.13.6`）；未引入「依赖层 COPY `app/`」的倒退。
  - D3/D13 的 compose 字段在 tasks 3.1 与 design 组件图一致（`build.args`、`environment: DATABASE_URL: ""`）；
    `.env.example` 保持 `DATA_DIR=./data`，未破坏 uv 备选路径。
  - D9/D10 的 spec 措辞与 `openspec/specs/ocr-api/spec.md:103`、`backend/app/logging_setup.py:26` 对读一致；
    R-DEP-02 不再重述状态码，R-DEP-05 改为 `usage_events` + stdout 日志。
  - D4/D5/D6/D7/D8/D11/D12/D15/D20 均为任务级加固，未新增需求、未扩大范围。
  - Q1/Q2/Q3 在 C2 时**未决**，C2 只在 design 加「待拍板」注记；人 2026-11-03 拍板 A/A/A 后，C3 已把决策落盘（见 §10）。
- **窄复核结论**：C2 与 C1 的发现一致，未发现新增矛盾；可以进入设计 HARD-GATE。

## 8. T/S 残差

- 本仓 `openspec/config.yaml` 的 rules 只覆盖少量槽位；已逐条人工核对：
  - proposal：`## Why`、`## Success Metrics`、`## Non-Goals`、`## Compliance` 齐；需求优先级、假设齐。
  - design：`## Compliance` 齐；失败模式+可观测性、NFR 数字化、安全与数据保护、决策记录齐；组件/依赖图齐。
  - specs：每个 Requirement 挂 Scenario；稳定 ID；`## Purpose` ≥50 字符。
  - tasks：每个任务挂 R-ID；测试覆盖图齐；任务粒度可独立验证。
- **无 T/S 机械失败项**；但本仓没有 T/S 自动扫描脚本，以上为**指令层人工核验**，不是机械保证
  （MUST NOT 声称有锚行机械核验）。
- 决策纪要机械门：`ok: true`（`check_decision_memo.py`，exit 0）。

## 9. 结论与建议

1. **不建议按 C1 直接出票**：S1 的构建链有 4 个阻塞级缺陷（D1/D2/D3/D14），会在第一次 `docker compose up`
   就失败；这些不是「边角失败模式」，而是目标态主路径。
2. **C2 已修**可机械修正的条目（见 §7），并把 3 个需要人判断的问题留在设计门：
   Q1（非 root + bind mount 权限模型）、Q2（90s 指标口径）、Q3（平台/tag/发布）。
3. **设计 HARD-GATE 已通过**：人 2026-11-03 批准 Q1=A / Q2=A / Q3=A；C3 已把决策落盘（见 §10），
   `anchor_writeback.py` 写入 `design_approved=true` 与内容锚后，进入 `/sdflow-lite-ship docker-deploy-e2e`。
4. 出票前请确认：D1/D2/D3/D14 的修正确实落到 tasks 1.2/1.3/2.1 与 ADR-0001；`docker compose up -d` 的
   `build.args` 通路已存在；`.dockerignore` 用 `**/` 模式。

## 10. 拍板记录（2026-11-03）

- **Q-scope = 认**：范围按 `proposal.md` `## Non-Goals` + `design.md` `## Goals / Non-Goals`。
- **Q-deps = 认**：S1→S2→S3→S4→S5；S1 的构建缺陷已在 C2 修正。
- **Q-risk = 认**。
- **Q1 = A**：entrypoint 以 root 启动 → `chown -R app:app /data` → `exec setpriv --reuid=app --regid=app
  --init-groups` 降权；最终主进程非 root。
- **Q2 = A**：90s 冷启动以「镜像已构建」为前提；首次镜像构建耗时单列记录，不计入 90s。
- **Q3 = A**：仅 `linux/amd64`；镜像 `ocr-gateway:0.1.0` + `latest`；不发布 registry；arm64 为 non-goal。
- 决策已落盘到 `design.md`（Decisions / NFR / 安全与数据保护 / Open Questions）、`proposal.md`（Success
  Metrics）、`tasks.md`（1.6 / 3.3 / 5.1 / 覆盖图）；C3 提交后由 `anchor_writeback.py` 写锚。
- **C3 窄复核补记**：Q1=A 使「容器 SHALL 以非 root 用户运行」与「entrypoint 以 root 修 `/data` 属主」产生
  措辞冲突；已把 R-DEP-08 改为「**主进程** SHALL 以非 root 用户运行；entrypoint MAY 在降权前以 root 修复
  数据卷属主」，design 的运行身份同步改为「最终主进程非 root」。场景「主进程 uid 不为 0」不变。

---

*报告生成：单 session 自查 · dispatch: single-session · 评审对象 C1 `4a9ebbf` · amendments 产出 C2*
