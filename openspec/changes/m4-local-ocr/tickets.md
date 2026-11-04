# Tickets · m4-local-ocr

> 唯一管线文件（gate 只读本文件）。切片来源：`design.md` 的 `## 切片与依赖`（T1–T5），
> 一处实质偏离：0003/models.py 迁移前移到 Task 2（审计与 `T10-choice` 复核见
> `impl-reports/planning-decisions.md`）。每票只描述「交付什么行为」，实现位置由实现方判断。

### Task 1: 本地引擎与进程池

可选 extra 可安装，worker 能离线识别并归一化输出；父进程侧状态机、可 kill 的 spawn 进程池、
warmup/超时/重建/退避与计数可被 fake pool 单测覆盖。对应 T1。

- R-ID: R-LOC-01, R-LOC-02, R-LOC-03, R-LOC-04, R-LOC-05
- Blocked-by: none

**验收标准**

- [x] `backend/pyproject.toml` 的 `[project.optional-dependencies].local` 可安装；装好 extra 的环境可 `import rapidocr, onnxruntime`；`uv lock --check --offline` 通过，`uv export --frozen --no-dev --no-emit-project --extra local` 含两包；worker 识别路径不发起网络请求（禁止 socket/断网测试或日志断言）。
- [x] worker `run_ocr(bytes, language)` 返回 `text`（行以换行连接）与 `lines[{text, confidence}]`（confidence 0–1）；成功但无文本返回空 `text` + `EMPTY_TEXT` 警告；worker 模块不导入 `app.state`/`app.main`/`app.config`，可被 spawn 单独导入。
- [x] `LocalEngine` 状态机覆盖 `stopped/starting/ready/error/unavailable`；依赖缺失 → `unavailable` 且不建池；warmup 用含文字小图并断言返回非空，warmup 有超时，失败 → `error` + 脱敏 `last_error` + `next_retry_in_ms`；`set_enabled` 幂等（ready/starting 重复 true 不建第二个池）；enable/disable/rebuild 的 generation 丢弃迟到回调；lifespan 按注入的 `local_ocr_enabled` 恢复建池。
- [x] 单次超时通过 `terminate()` 回收整个池（不是只 cancel future），连续 N 次超时后子进程数不超过并发上限；worker 崩溃后下一次请求可重建并成功；因重建被取消的请求得到可映射的 503/504 错误（不冒泡为 500）。
- [x] 进程池用 `multiprocessing.get_context("spawn").Pool`；worker initializer 清除 `MASTER_KEY`/`ADMIN_PASSWORD` 等敏感 env；默认并发 1，`LOCAL_OCR_MAX_CONCURRENCY=2` 时两个任务并行执行。
- [x] 测试：fake pool 覆盖状态迁移/超时/取消/退避/重启恢复；真实引擎测试标 `slow`、缺 extra 时 skip；`ruff` + `mypy` 通过；报告记录命令、退出码、用例数与 SHA。

### Task 2: 公共路由、兜底与迁移

`provider=local` 可用，显式 local 有 403/502/504 语义，auto 在云端失败时按预算兜底；local 成功写
`provider='local'` 事件，DB 约束与 ORM 同步放宽。对应 T2 + T3 的迁移部分。

- R-ID: R-API-01, R-API-03, R-API-05, R-API-06, R-SCH-03, R-SCH-05, R-SCH-07, R-QTA-01
- Blocked-by: 1

**验收标准**

- [x] Alembic `0003` upgrade → downgrade → upgrade 往返成功（含一条 local 行）；`app/models.py` 的 `ck_usage_provider` 同步为四值；`Base.metadata.create_all` 建库后插入 `provider='local'` 成功；downgrade 先把 local 行更新为 auto 再恢复旧约束。
- [x] `VALID_PROVIDERS` 含 `local`；显式 local 未启用/依赖缺失 → 403 `FORBIDDEN`，且该判定先于缓存读取（禁用后不返回旧缓存 200）；local 运行失败 502 `PROVIDER_ERROR`、超时 504 `TIMEOUT`；未知 provider 400。
- [x] auto 兜底：`reserve_eff = min(reserve, max(0, total − min_budget))`；1000/3000/5000/20000ms 边界下云阶段不会因预留落在过去；仅 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 触发；`InputError` 不兜底；显式 `baidu`/`tencent` 不兜底；预算不足返回云阶段原错误；整个请求不超过总 deadline。
- [x] local 图片规范化：Pillow 校验 + EXIF 旋转 + 重编码 JPEG；上限作用于重编码后的 JPEG 字节（≤ `MAX_UPLOAD_BYTES`），最长边 10000，不做 base64 膨胀检查；9MB PNG 通过、10000px 边界通过、超限 400。
- [x] local 成功响应 `provider="local"`、`quota.used=0`；`usage_event` 写 `provider='local'`、`account_id=NULL`、`quota_used=0`，Key 当日请求条数 +1、账号计数不变；缓存命中 local 事件 quota=0；响应与事件 quota 由实际 provider 派生，不硬编码 1。
- [x] `/v1/providers` 含 `local` 条目（`enabled = installed && enabled`），不含账号数、路径或模型信息；public 的 403/502/504 文案按 design copy 表区分「开关关闭」与「依赖缺失」两种 cause。
- [x] 测试：API 覆盖 200/400/403/502/504、providers、缓存门禁、预算边界（fake clock）；迁移往返；`ruff` + `mypy`；报告记录命令、退出码、用例数与 SHA。

### Task 3: 记账标签与总览对账

用量/日志的厂商标签与筛选接受 local，总览厂商行包含 local 并与今日总数对账；前端类型拆分不污染
账号域。对应 T3 的标签/对账部分。

- R-ID: R-QTA-01, R-ADM-06, R-ADM-09, R-API-06
- Blocked-by: 2

**验收标准**

- [x] `PROVIDER_NAMES` 增 `local` =「本地 RapidOCR」；`group_by=provider` 汇总返回 local 行与 label；日志行 label 正确；用量与日志的厂商筛选均接受 `provider=local`。
- [x] 总览厂商行包含 `local`（`accounts=0`、`available_accounts=0`），今日请求总数与各厂商行请求数之和一致（`auto` 失败仍单独计数）；无 local 事件时不出现空行。
- [x] 前端类型拆分：账号域 `ProviderCode` 仍只有 `baidu`/`tencent`；日志/用量/事件标签用含 `auto`/`local` 的展示联合；`ProviderRow.code` 使用该展示联合；账号创建与凭证映射不受影响。
- [x] 测试：API 断言 group_by/overview/日志 label 与对账；`pnpm --dir frontend typecheck` + `lint` 通过；报告记录命令、退出码、用例数与 SHA。

### Task 4: 管理端开关、状态与面板

设置页可开启/关闭本地 OCR，状态接口与卡片可观测 worker 生命周期；开关热更新、重启恢复、缓存
清理与面板三态/轮询/部分提交按 spec 落地。对应 T4。

- R-ID: R-ADM-08, R-ADM-11, R-PANEL-08, R-LOC-05
- Blocked-by: 1

**验收标准**

- [x] settings 增 `local_ocr_enabled`（bool，默认 false，支持部分更新；显式 null 400；类型错误 400 且 `error.fields[].field="local_ocr_enabled"`）；提交成功后幂等调用 `set_enabled`；开关变化清空缓存并返回 `cache_cleared=true`；重启后按持久化值恢复 worker。
- [x] `GET /api/admin/local-ocr/status` 需管理员会话（401）；返回 enabled/installed/state/concurrency/timeout+effective/reserve+effective/model/last_latency/last_error/next_retry/requests_total/fallback_total；依赖缺失 `installed=false,state=unavailable`；预热失败 `error` + 脱敏 `last_error`；不含绝对路径、凭证或识别原文。
- [x] [e2e] 设置页本地 OCR 卡片：独立 useQuery + 同高骨架 + 加载/空/错误三态；`starting` 轮询 ≤1s 到 `ready`/`error`；开关是表单唯一草稿源，status 只读；保存只提交 dirty 字段，disabled 字段从 payload 剔除；窄屏单列、`last_error` 截断可展开；依赖缺失时禁用开关并说明。
- [x] 测试：设置读写/非法值/持久化/重复保存不重建池；状态接口 200/401/unavailable/error；`pnpm typecheck` + `lint`；e2e 断言 starting→ready 与状态慢时设置区仍可编辑；报告记录命令、退出码、用例数与 SHA。

### Task 5: 镜像、文档与集成验收

镜像内置 local extra，版本与文档落点完整，离线冒烟、云全挂兜底、回滚演练与 p95 基准全部有记录。
对应 T5。

- R-ID: R-DEP-10, R-DEP-11, R-LOC-01, R-SCH-07, R-API-01, R-ADM-11
- Blocked-by: 1, 2, 3, 4

**验收标准**

- [ ] Dockerfile 依赖层 `uv export --extra local`；版本源全部升 `0.3.0`（`backend/pyproject.toml`、`backend/app/__init__.py`、`frontend/package.json`、`backend/uv.lock` project version、README 版本锚）；compose tag 为 `0.3.0`/`latest`，`0.2.1` 不动；基础镜像缺 `libgomp1` 等系统库时构建期安装；镜像内 `import rapidocr, onnxruntime` 通过、`/healthz` ok、`readonly.version == 0.3.0`。
- [ ] [e2e] 镜像冒烟：无外网启动 → 开启开关 → `status` 到 `ready` → 识别一张图返回 200/`provider="local"`；关闭开关 → 显式 local 403；停用全部云账号 → `provider=auto` 返回 200/`provider="local"`；记录请求/响应、状态快照与子进程数。
- [ ] [e2e] 回滚演练：`alembic downgrade -1`（或 `7c1f0d2a9b31`，`--entrypoint` 覆盖）→ local 行变 auto → `0.2.1` 启动成功；记录实际命令与输出。
- [ ] p95：固定 N≥30 基准脚本，最长边 2000px 截图，p95 ≤3s；ready ≤10s（目标 ≤5s）；记录运行环境与原始输出。
- [ ] 文档：README 本地 OCR 说明、`LOCAL_OCR_*` 权威表、许可证、体积、版本锚/回滚、`provider=local`、显式 local 仅受 RPM/并发约束；`.env.example` 默认值；`docs/tech-selection.md` 所有下载相关表述移除；开发快速上手注明 `uv sync --project backend --extra local` 并补 TTHW 估算；`grep` 无 `0.2.1`/「不做本地 OCR」/`local.*400`/`/local-ocr/download` 残留。
- [ ] 测试：装 extra 后 `pytest -m slow`；`ruff` + `mypy`；`pnpm --dir frontend lint/typecheck/build`；镜像冒烟；报告记录命令、退出码、用例数与 SHA。

### Task 6: 实现验证

运行本 change 命中域的全部层聚合套件并确认全部通过，作为交付前的最后一道聚合验证。对应全部需求。

- R-ID: all
- Blocked-by: 1, 2, 3, 4, 5

**验收标准**

- [ ] 按 `suite_scope.py --mode closeout` 返回的层集运行全部聚合套件并全部通过；逐层记录命令、退出码、用例数与 SHA；零用例的通过不算通过。
- [ ] 汇总本 change 的 `slow`、e2e 与镜像冒烟证据，与 defer 台账对账一致（无未记录的失败、无未写盘的延后项）。
