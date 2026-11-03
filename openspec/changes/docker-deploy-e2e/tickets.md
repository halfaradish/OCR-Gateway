# Tickets — docker-deploy-e2e

> 出票依据：`design.md`「切片与依赖」的 S1–S5 默认采纳，无实质偏离（承重约束映射与偏离审计见
> `impl-reports/planning-decisions.md`）。执行按 `Blocked-by` 拓扑串行：1 → 2 → 3 → 4 → 5 → 6。

### Task 1: 镜像构建层（S1）

**R-ID:** R-DEP-04, R-DEP-07
**Blocked-by:** none

交付行为：一条 `docker build`（索引可经参数指定）产出只含运行期依赖的镜像；镜像内应用可导入、版本为
0.1.0，不含开发依赖、测试代码或任何本地凭证；产物按 `ocr-gateway:0.1.0` 与 `latest` 标记且平台为
`linux/amd64`。构建不依赖锁文件中记录的默认下载地址可达（承重约束 C1、C7）。

验收标准：

- [x] 构建上下文不含 `.env`、`data/`、`docs/`、`openspec/`、测试代码、虚拟环境与各类缓存目录；可经构建日志或上下文清单核对
- [x] 以可达镜像索引为参数执行构建成功，依赖层只依赖依赖清单与锁文件，安装版本与锁文件一致（导出计 38 个 `==` 锁定项）
- [x] 镜像内 `python -c "import app; print(app.__version__)"` 输出 `0.1.0`
- [x] 镜像内 `python -c "import pytest"` 以非零退出（无 dev 依赖），且镜像内不存在 `tests` 目录
- [x] 对停止态镜像/镜像层做凭证扫描：`MASTER_KEY`、`ADMIN_PASSWORD`、百度与腾讯密钥的实际取值出现 0 次，镜像历史无 `ENV MASTER_KEY` / `ENV ADMIN_PASSWORD`
- [x] 镜像大小 ≤ 400MB，`RepoTags` 含 `ocr-gateway:0.1.0` 与 `ocr-gateway:latest`，平台为 `linux/amd64`

### Task 2: 启动契约（S2）

**R-ID:** R-DEP-01, R-DEP-03, R-DEP-06
**Blocked-by:** 1

交付行为：容器启动序列先迁移后服务——空数据卷首启自动建表并对外返回 200；迁移失败立即非零退出且不监听端口；
重复启动迁移为无操作；必填配置缺失/非法时启动即失败；多 worker 配置被拒绝并给出单实例约束原因
（承重约束 C2、C3、C4、C6）。

验收标准：

- [x] 以空数据卷启动后 `/healthz` 返回 200，且库内存在 `accounts`、`api_keys`、`users`、`quota_counters`、`usage_events` 五张表
- [x] 数据目录不可写时容器以非零码退出，日志中不出现 uvicorn 开始监听端口的信息
- [x] 在同一已迁移卷上二次启动：迁移无升级输出，`/healthz` 仍返回 200
- [x] 不提供 `MASTER_KEY`（或传非 32 字节值）启动：容器非零退出且日志含配置校验错误；不提供 `ADMIN_PASSWORD`（或短于 8 字符）同样失败
- [x] 以 `WEB_CONCURRENCY=2` 启动：容器非零退出且日志含单实例约束的拒绝原因
- [x] 迁移命令可在任意工作目录运行且幂等（同一 `DATABASE_URL` 下二次执行无变更）

### Task 3: 编排与运行身份（S3）

**R-ID:** R-DEP-02, R-DEP-05, R-DEP-08
**Blocked-by:** 2

交付行为：一条编排声明即可拉起单服务容器：端口仅绑回环、健康状态可被编排消费、数据落在宿主机卷、
主进程非 root、异常退出自动重启、日志有大小与份数上限、停止时给在途请求留出优雅窗口
（承重约束 C5、C6）。

验收标准：

- [ ] 编排解析结果：单服务、端口映射到 `127.0.0.1:8000`、构建期索引参数来自环境插值、运行期 `DATA_DIR=/data` 为绝对路径且 `DATABASE_URL` 为空、根目录 `.env` 提供运行期变量
- [ ] 健康探测参数为 `interval=10s`、`timeout=3s`、`retries=5`、`start_period=30s`，探测命令只用镜像内 Python 标准库；`docker compose up -d` 后容器状态达到 `healthy`
- [ ] 主进程 `id -u` 不为 0，且迁移与配额刷盘均无权限错误（entrypoint 先修复数据卷属主再降权）
- [ ] 编排含 `restart: unless-stopped`、`stop_grace_period: 25s` 与显式 `json-file` 日志驱动的 `max-size` / `max-file`；强杀主进程后容器自动重启并重新达到 `healthy`
- [ ] 经管理 API 创建成员后执行 `down` 与 `up -d`，该成员仍可经 `GET /api/admin/users` 查到

### Task 4: 文档与配置面（S4）

**R-ID:** R-DEP-07
**Blocked-by:** 3

交付行为：按 README 从干净 checkout 可复现「一键起」；示例环境变量文件覆盖构建期与运行期变量且不含真实凭证；
既有文档静态测试随新主路径更新后全绿；全量回归无新增问题。

验收标准：

- [ ] README 部署段以 compose 一键起为主路径、本机 uv + uvicorn 为备选，含镜像索引说明、反代配置片段、TTHW 估算（步骤数/命令数 + 每步耗时假设 + 标注「估算」）与 uv 备选路径的前置说明
- [ ] README 的 `DATA_DIR` 描述为「SQLite 数据目录」，日志描述为 stdout；保留原有 `uv sync` / `alembic upgrade head` / `--workers 1` / 备份与回滚口径
- [ ] `.env.example` 含 `UV_DEFAULT_INDEX`（构建期，默认留空）与容器内 `DATA_DIR=/data` 由编排覆盖的注释；`DATA_DIR` 保持宿主机默认、`DATABASE_URL` 保持空、无真实凭证片段
- [ ] 文档静态测试更新后断言 `docker compose up -d` 与 `UV_DEFAULT_INDEX`，且原有断言针全部保留；该测试文件全绿
- [ ] 全量回归：`pytest backend/tests` 全绿，`ruff check backend` 与 `mypy backend/app` 无新增问题

### Task 5: 真机端到端验收（S5）

**R-ID:** R-DEP-01, R-DEP-02, R-DEP-03, R-DEP-04, R-DEP-05, R-DEP-06, R-DEP-07, R-DEP-08, R-ADM-02, R-ADM-03, R-ADM-04, R-API-01, R-API-02, R-CAC-01, R-QTA-01, R-QTA-05, R-SCH-03, R-SCH-05
**Blocked-by:** 3, 4

交付行为：在真实百度/腾讯凭证下，用容器化部署跑通网关真实链路并归档可审计证据；本票只做验证，不重定义
既有能力（承重约束 C8）。

验收标准：

- [ ] [e2e] 镜像已构建前提下清空数据卷，`docker compose up -d` 到 `healthy` 且 `/healthz` 200 的总耗时 ≤90s，记录时间戳
- [ ] [e2e] 经 `POST /api/admin/login` 取 token → 建成员 → 建 Key（明文只出现一次）→ 建百度与腾讯账号（真实凭证经环境注入，不写入任何文件）；`GET /api/admin/accounts` 返回两家且不含明文凭证
- [ ] [e2e] 用真 Key 分别提交 multipart 文件、base64、公网 `image_url`（`https://baidu-ai.bj.bcebos.com/ocr/general.png`）：三次均 200 且 `text` 非空、`lines` 为非空数组，记录每次 `text` 片段与 `latency_ms`
- [ ] [e2e] 重复提交同一图片且 `language`/`provider` 不变：第二次 `cached=true` 且 `quota.used=0`
- [ ] [e2e] `GET /api/admin/usage/summary` 与 `GET /api/admin/logs` 反映本次调用（成功计数 +1、缓存命中 +0），日志不含 OCR 原文
- [ ] [e2e] 禁用全部百度账号后请求 `provider=baidu`：返回错误而非由腾讯完成
- [ ] [e2e] 禁用全部百度账号后请求 `provider=auto`：由腾讯账号完成，响应 `provider` 为 `tencent`
- [ ] 验收证据写入本 change 目录（命令、时间戳、响应片段、镜像扫描结果、`docker inspect` 健康状态），逐条对应上述场景；证据中不含任何密钥明文，编排解析输出只保留过滤后的非敏感字段

### Task 6: 实现验证（收尾）

**R-ID:** all
**Blocked-by:** 1, 2, 3, 4, 5

交付行为：对本 change 命中域运行全部层的聚合测试套件，并汇总为可机验的收尾证据。

验收标准：

- [ ] 运行本 change 命中域的全部层聚合套件并全部通过（层集取自收尾范围解析，MUST NOT 手抄）；实跑层通过行用例数非 0 且各通过行 SHA 一致
