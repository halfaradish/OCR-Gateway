# Design: m4-local-ocr

## Context

当前路由只有云账号：`Scheduler` 从 `AccountRegistry` 取候选（`backend/app/core/registry.py:153-186`），没有账号即 `NoCandidate`；公共 API 的 `VALID_PROVIDERS` 只有 `auto/baidu/tencent`（`backend/app/api/public.py:28`）。运行时设置是 5 个标量键（`backend/app/runtime_settings.py:19-46`），热更新在 commit 后替换 `state.runtime`（`backend/app/api/admin.py:1075-1093`）。镜像用 `uv export --frozen` 安装依赖（`Dockerfile` 依赖层），因此新增 optional extra 必须同步锁文件。

本地引擎的外部事实（均实测）：rapidocr 3.10.0 wheel 内置 PP-OCRv6 small det/rec 与 PP-OCRv4 cls 模型，不联网；`RapidOCR()` 构造不加载模型，首次调用才加载；本机冷启动约 2.4s、热调用 0.49s（900×220）。动机见 `proposal.md`，决策全文见 `decision-memo.md`。

## Goals / Non-Goals

**Goals:**
- 本地引擎在独立进程内运行，事件循环不被 ONNX 推理阻塞；启停与就绪状态可查询、可观测。
- 兜底只在 `auto` 且本地真正可用时生效，且不挤占云端本可成功的预算。
- 记账与错误码语义在改动后仍与既有公共契约自洽（local 无账号、无厂商额度）。

**Non-Goals:**
- 不做模型下载、语言模型切换、GPU、批量本地识别（见 proposal Non-Goals）。
- 不改变云账号的候选/排序/冷却逻辑；`provider=baidu|tencent` 行为完全不变。
- 不引入多进程 worker 的负载均衡或跨实例协调（v1 单实例）。

## Decisions

本 change 的决策全文与砍掉的候选见 [`decision-memo.md`](./decision-memo.md)（D1–D16）；离线更新锁文件的操作决策见 [`ADR-0002`](../../adr/0002-offline-lock-update.md)。本文件只记录由这些决策推导出的技术形状与约束。

## 架构与组件

```
┌────────────────────────── 同一进程（uvicorn 单 worker） ──────────────────────────┐
│                                                                                  │
│  POST /v1/ocr/image                                                              │
│        │                                                                         │
│        ▼                                                                         │
│  public.py ── normalize_image(provider) ── cache ── semaphore                     │
│        │                                                                         │
│        ▼                                                                         │
│  Scheduler.recognize(provider, deadline)                                         │
│    ├─ provider=baidu|tencent ──▶ AccountRegistry 候选 ──▶ ProviderAdapter(HTTP)   │
│    ├─ provider=local ─────────▶ LocalEngine.recognize                            │
│    └─ provider=auto ──▶ 云尝试（截止 = deadline - reserve）                       │
│                          └─ 无候选/全失败 ──▶ LocalEngine.recognize              │
│                                                                                  │
│  LocalEngine（父进程，asyncio 单线程状态机）                                      │
│        │  run_in_executor + wait_for(timeout)                                    │
│        ▼                                                                         │
│  spawn 进程池（可 terminate/kill；max_workers=local_ocr_max_concurrency）         │
│        └─ worker 进程：import rapidocr（懒加载模型），只收 bytes/语言             │
│                                                                                  │
│  admin.py ── /api/admin/settings（local_ocr_enabled）                            │
│           └─ /api/admin/local-ocr/status ──▶ LocalEngine.status()                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

组件职责：
- `app/core/local_engine.py`（新）：父进程侧状态机、进程池、超时、计数与状态快照。
- `app/workers/local_ocr.py`（新）：worker 进程侧，模块级引擎缓存与 `run_ocr`/`warmup`；**不得**导入 `app.state`/`app.main`/配置，避免把凭证带进子进程；必须能被 spawn 单独导入。
- `app/core/scheduler.py`：增加 local 分支与 `auto` 兜底（云阶段截止 = 总 deadline − reserve）。
- `app/api/public.py`：`provider` 枚举、403/502/504 映射、`/v1/providers` 条目。
- `app/runtime_settings.py` / `config.py`：新设置键与环境默认。
- `app/utils/images.py`：local 分支仍走 Pillow 校验 + EXIF 旋转 + 重编码 JPEG；字节上限作用于**重编码后的 JPEG 字节**（`MAX_UPLOAD_BYTES`），最长边 10000，不做 base64 膨胀检查（`[spec-review-amendment R-30]`）。

## 请求路由与预算

`deadline` 仍是请求开始时的绝对 `time.monotonic()` 预算（R-SCH-03）。

| provider | 云阶段截止 | 兜底 | 说明 |
| --- | --- | --- | --- |
| `baidu` / `tencent` | `deadline` | 否 | 既有行为不变 |
| `local` | 不适用 | 不适用 | 直接本地；未启用/依赖缺失 → 403 |
| `auto` 且本地可用 | `deadline - reserve_eff` | 是 | 云 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 时转本地 |
| `auto` 且本地不可用 | `deadline` | 否 | 不为不可用的 local 预留预算 |

「本地可用」判定（`[spec-review-amendment R-09]`）= `installed && enabled`；`starting` 按就绪事件等待，
`unavailable`（依赖缺失，不建池）与 `error`（模型加载失败，按退避重试）不预留、不兜底。
显式 `provider=local` 在 `unavailable`/未启用时 403；`error` 时进入重试并返回 502。

预算不变量（`[spec-review-amendment R-01]`）：进入本地阶段前先算
`reserve_eff = min(LOCAL_OCR_RESERVE_MS, max(0, total_budget - LOCAL_OCR_MIN_BUDGET_MS))`；
只有 `total_budget >= reserve_eff + LOCAL_OCR_MIN_BUDGET_MS` 才启用兜底并扣减云阶段预算。
`total_budget <= LOCAL_OCR_MIN_BUDGET_MS` 时 `reserve_eff = 0`，auto 退化为一律不兜底（等价于本地未启用），
避免 `request_deadline_ms` 取 1000–5000 时云阶段截止落在过去。

本地阶段只算一次 `local_deadline = min(now + LOCAL_OCR_TIMEOUT_MS, deadline)`；ready 等待与识别共用该
deadline，每次 `await` 后重算剩余，确保整个本地阶段不超过总预算。`LOCAL_OCR_TIMEOUT_MS=30000` 是
上限，实际生效值 = `min(30000, deadline - now)`；剩余预算 < `LOCAL_OCR_MIN_BUDGET_MS`（默认 1000）时
不再尝试本地，直接返回云阶段的原始错误（若显式 local 则 504）。

```
provider=auto?
   │否 ──▶ 云路径（不兜底）
   ▼是
本地 installed && enabled?
   │否 ──▶ 云路径（deadline 全额）
   ▼是
云尝试（deadline - reserve_eff）
   │成功 ──▶ 返回云结果
   ▼失败/无候选
剩余 ≥ min_budget? ──否──▶ 返回云错误
   │是
本地识别（timeout = min(30s, local_deadline - now)）
   │成功 ──▶ 返回 local 结果（quota_used=0）
   ▼失败
502 / 504
```

## 请求时序（auto 兜底 + 超时重建）

`[spec-review-amendment R-25]` 跨 public / Scheduler / LocalEngine / worker 四个组件，且有并发与池重建，按
`design-diagrams.md` 补序列图：

```
client     public.py            Scheduler          LocalEngine         worker(process)
  │            │                    │                  │                    │
  │─ POST ────▶│ parse+normalize    │                  │                    │
  │            │ provider gate ─────┼──(显式 local 未启用→403，早于缓存)      │
  │            │ cache.get ─────────┼──(命中→200 cached=true)                │
  │            │ semaphore.acquire  │                  │                    │
  │            │───────────────────▶│ cloud(deadline-reserve_eff)            │
  │            │                    │── NoCandidate/Upstream/Timeout ──┐     │
  │            │                    │                                  ▼     │
  │            │                    │            reserve 够? ─否→ 返回云错误  │
  │            │                    │                  │ ready? ──wait(≤local_deadline)
  │            │                    │                  │─ run_ocr ─────────▶│
  │            │                    │                  │◀─ text/lines ──────│
  │            │◀── ScheduleResult(provider=local) ────│                    │
  │            │ cache.set + usage_event(quota_used=0) │                    │
  │◀─ 200 ─────│                    │                  │                    │
  │            │                    │      local_deadline 到 ──▶ terminate 池│
  │            │                    │                  │ generation++ → starting
  │            │◀── 504 TIMEOUT ────┴──────────────────│                    │
```

竞态约束（`[spec-review-amendment R-10/R-12]`）：每次 enable/disable/rebuild 递增 generation；warmup 与
识别回调先比对 generation，旧池的迟到回调丢弃；超时 owner 单飞重建，被重建取消的兄弟请求映射
503/504 并写 usage_event，不得冒泡为 500。

## 本地 worker 生命周期

```mermaid
stateDiagram-v2
    [*] --> stopped
    [*] --> unavailable: installed=false（依赖缺失，不建池）
    stopped --> starting: set_enabled(true) / lifespan 恢复 enabled=true
    starting --> ready: warmup 完成（含文字小图返回非空）
    starting --> error: warmup 超时/模型加载失败
    starting --> stopped: set_enabled(false)
    ready --> stopping: set_enabled(false)
    ready --> error: worker 崩溃 / 单次超时且池重建失败
    stopping --> stopped: shutdown 完成
    error --> starting: 退避窗口（≥30s）后的下次请求或重新启用
    error --> stopped: set_enabled(false)
    unavailable --> stopped: set_enabled(false)
```

规则（`[spec-review-amendment R-03/R-09/R-10/R-11/R-18]`）：
- **启动恢复**：lifespan 装配后，若 `runtime.local_ocr_enabled && installed` 调用 `set_enabled(true)`，状态从 `starting` 开始；`installed=false` 时为 `unavailable`，不建池。
- `set_enabled` **幂等**：仅在状态变化时执行；`ready`/`starting` 重复收到 `true` 不建第二个池；`disable` 立即清就绪事件并递增 generation。
- `set_enabled(true)` 只负责建池并提交 warmup（不阻塞 HTTP 响应），状态立刻为 `starting`。
- warmup 用**含文字的小图**跑完整 pipeline 并断言文本非空（1×1 白图在检测阶段即返回，不能证明 rec/cls 已加载）；warmup 本身有超时（≤ ready 等待上限），超时置 `error`。
- `starting` 期间的本地请求等待就绪事件，最多等 `min(10s, local_deadline - now)`；超时按不可用处理。
- 单次超时：`terminate()/kill()` 旧池进程并 `join`（不能只取消 future），generation++，重建池并回到 `starting`，本次返回 504；避免一个卡死任务永久占住 worker。
- `error` 后的重试有最小间隔（默认 30s）+ 指数退避；请求路径不重复 spawn 失败池；`status` 暴露 `next_retry_in_ms`。
- `BrokenProcessPool`：状态置 `error`，下次请求（过退避窗口后）重建；错误写入 `last_error`（脱敏）。
- 关闭应用时 `await shutdown()`，上限 20s（< compose `stop_grace_period: 25s`）；超时后 kill 残留 worker。不清空 `usage_event`。

## 并发与共享状态

- 状态只存在于事件循环线程：`LocalEngine` 的字段（state、计数器、last_*）无需锁；进程池回调通过 `run_in_executor` 回到事件循环。
- worker 进程之间不共享内存；并发由 `max_workers` 控制，默认 1，多请求在 executor 队列等待并各自受 deadline 约束。
- 全局 `MAX_CONCURRENT_REQUESTS` 信号量仍在最外层，本地请求也计入（不会因兜底绕过并发上限）。
- **本地专用 gate**（`[spec-review-amendment R-19]`）：显式 local 先取 `local_semaphore`（= `local_ocr_max_concurrency`）再取全局信号量，排队本地请求不占全局槽；auto 兜底阶段在全局槽内取 local gate（兜底是低频路径）。
- 进程池用 `mp_context=multiprocessing.get_context("spawn")`（`[spec-review-amendment R-27]`，不是位置参数）；spawn 避免继承父进程**堆内存**，但子进程仍会继承 `os.environ`——worker initializer 清除 `MASTER_KEY`/`ADMIN_PASSWORD` 等敏感变量，且 worker 代码不读取任何 env 凭证（`[spec-review-amendment R-26]`）。

## 数据模型与生命周期

新增运行时设置键（`settings` 表，key/value，无需 DDL）。`LOCAL_OCR_*` 权威清单（`[spec-review-amendment R-32]`）：

| 键 | 类型 | 默认 | 来源 | 范围 / 说明 |
| --- | --- | --- | --- | --- |
| `LOCAL_OCR_ENABLED` / `local_ocr_enabled` | bool | `false` | env 仅作启动默认；DB 运行时值覆盖（热更新） | 开关；关闭时停池，显式 local 403 |
| `LOCAL_OCR_MAX_CONCURRENCY` | int | `1` | env | 建池时生效；变更需重启容器 |
| `LOCAL_OCR_TIMEOUT_MS` | int | `30000` | env | 单次上限；实际值 = `min(该值, 剩余预算)` |
| `LOCAL_OCR_RESERVE_MS` | int | `5000` | env | auto 云阶段预留；按 R-01 不变量收敛为 `reserve_eff` |
| `LOCAL_OCR_MIN_BUDGET_MS` | int | `1000` | env | 剩余低于此值不尝试本地 |

`usage_event.provider` 取值新增 `local`，仅有 check 约束变化（Alembic `0003`，batch 重建）：

| 对象 | v_old | v_new |
| --- | --- | --- |
| `ck_usage_provider` | `provider IN ('baidu','tencent','auto')` | `provider IN ('baidu','tencent','auto','local')` |
| `usage_events` 列 | 不变：`id, request_id, user_id, api_key_id, account_id, provider, capability, success, error_code, latency_ms, quota_used, cached, image_hash, created_at` | 同左（无增删列/类型/默认值变化） |
| `ck_accounts_provider` | `provider IN ('baidu','tencent')` | 不变（local 不建账号） |

downgrade：先 `UPDATE usage_events SET provider='auto' WHERE provider='local'`，再恢复旧约束；否则旧约束建立时必然失败。

迁移落地约束（`[spec-review-amendment R-07/R-21/R-35]`）：
- `backend/app/models.py` 的 `UsageEvent.__table_args__` MUST 同步改为四值——测试用 `Base.metadata.create_all` 建库，只改 Alembic 会让 local 事件在单测直接 IntegrityError。
- `account_id` 已是 `nullable=True`，本迁移**不加列**；`ck_accounts_provider` 不动。
- 迁移在启动时执行；上线前评估 `usage_events` 行数（超过 100 万行时在维护窗口执行），保留 `sqlite3 .backup` 与磁盘余量。
- 回滚命令用 `alembic downgrade -1`（或 revision `7c1f0d2a9b31`）；容器 entrypoint 启动即 `upgrade head`，演练时须用 `--entrypoint alembic` 覆盖。

## 失败模式与可观测性

| 场景 | 检测 | 系统行为 | 用户可见 | 恢复 |
| --- | --- | --- | --- | --- |
| 依赖未安装 | `find_spec` 失败 | `installed=false`、`state=unavailable`，开关视为不可用 | 显式 local → 403；auto 不兜底 | 重装镜像 |
| 模型加载失败 | warmup 异常 | `state=error`，`last_error`（脱敏） | 显式 local → 502；auto 回云错误 | 退避窗口后重试 |
| warmup 卡住 | warmup 超时（≤ ready 等待上限） | `state=error`，`next_retry_in_ms` | 显式 local → 502；auto 回云错误 | 退避后重试 |
| worker 崩溃 | `BrokenProcessPool` | 重建池，`error→starting` | 本次 502 | 下次请求自动恢复 |
| 单次超时 | `asyncio.wait_for` | terminate/kill 旧池并重建，generation++ | 504 `TIMEOUT` | 下次请求自动恢复 |
| 池重建取消兄弟请求 | generation 不匹配 | 映射 503/504 并写 `usage_event` | 503/504 | 下次请求 |
| 队列排满 | executor 排队 + deadline | 等到 deadline 即超时 | 504 | 降低并发/扩大 worker |
| 缓存命中但 local 已禁用 | provider gate 先于 `cache.get` | 开关变化清缓存 | 显式 local → 403；auto 不返回 local | 重新开启 |
| 云端失败且预算不足 | 剩余 < 1s | 不尝试本地，返回云错误 | 503/502/504（云错误） | 下次请求 |
| 开关在请求中变更 | 状态机 + generation | 新请求按新状态；旧池回调丢弃 | 可能一次 403/502 | 重试 |

可观测性：
- 结构化日志事件：`local_ocr.enabled` / `local_ocr.disabled` / `local_ocr.warmup`（含 model 与耗时）/ `local_ocr.fallback`（含 from_reason）/ `local_ocr.timeout` / `local_ocr.failed`。日志不含图片字节与识别原文。
- `usage_event`：`provider='local'`、`account_id=NULL`、`quota_used=0`、`latency_ms` 为整请求耗时；兜底成功与失败都记录。
- `GET /api/admin/local-ocr/status`：

```json
{
  "enabled": true,
  "installed": true,
  "state": "ready",
  "concurrency": 1,
  "timeout_ms": 30000,
  "effective_timeout_ms": 15000,
  "reserve_ms": 5000,
  "effective_reserve_ms": 5000,
  "model": {"engine": "onnxruntime", "family": "PP-OCRv6", "variant": "small", "bundled": true},
  "last_latency_ms": 812,
  "last_error": null,
  "next_retry_in_ms": null,
  "requests_total": 12,
  "fallback_total": 3
}
```

`[spec-review-amendment R-09/R-28/R-31]`：`effective_*` 是本请求预算下的实际值；`last_error` 只保留
错误码 + 脱敏短消息（去绝对路径、去堆栈、截断），不返回模型文件路径、凭证或识别原文。

- `GET /v1/providers` 增加：

```json
{"code": "local", "name": "本地 RapidOCR", "enabled": true}
```

- 设置更新示例：`PUT /api/admin/settings {"local_ocr_enabled": true}` → `{"settings": {...}, "cache_cleared": true}`（开关变化视为缓存参数变化，清空现有缓存）；非法类型返回 400 且 `error.fields[].field="local_ocr_enabled"`。

错误文案（`[spec-review-amendment R-20]`；problem / cause / fix 三段，与既有 `FIELD_RULES` 文案风格一致）：

| 错误 | message |
| --- | --- |
| 显式 local、开关关闭 | 本地 OCR 未启用。请在设置页开启「本地 OCR」开关后重试。 |
| 显式 local、依赖缺失 | 本地 OCR 依赖未安装。当前镜像未包含 `local` extra，请使用内置该依赖的 0.3.0 镜像。 |
| 本地识别失败 | 本地 OCR 运行失败。服务已记录该错误；请稍后重试，或显式指定云厂商。 |
| 本地识别超时 | 本地 OCR 超时。请缩小图片或稍后重试。 |
| 显式 local、模型加载中 | 本地 OCR 正在预热。请稍后重试。 |

`/v1/providers` 的 local `enabled` = `installed && enabled`（合并语义）；它不区分两种 false 的原因，客户端需要区分时应调用管理员状态接口。

## 非功能需求（数字化）

| 指标 | 目标 | 依据 |
| --- | --- | --- |
| 冷启动（建池→ready） | 目标 ≤5s；验收 ≤10s | 本机实测 2.4s；Linux/2 核 4G 待镜像冒烟补测 |
| 热调用 p95（最长边 ≤2000px 的截图） | ≤3s | 实测 900×220 为 0.49s；p95 用固定 N 次基准脚本计算，不用 `last_latency_ms` 单样本 |
| 本地单次超时上限 | 30s，且不超过剩余总预算；status 报 `effective_timeout_ms` | D4 |
| 本地预算预留 | 5s（auto 且本地可用时）；`reserve_eff` 按 R-01 不变量收敛 | D4 |
| ready 等待上限 | min(10s, `local_deadline - now`) | 冷启动 2.4s 的 4× 余量 |
| 镜像增量 | 下载约 110–130MB / 安装后约 350MB（**估算**，实施后按锁文件 wheel size 与 `du -sh` 回填） | 锁文件 wheel size 求和；外部数字未经本机核验 |
| worker 常驻内存 | 200–300MB（估算，实施后按容器 RSS 回填） | 模型 32MB + onnxruntime/opencv 运行时 |

## 安全与数据保护

- 图片在进入进程池前已完成 Pillow 校验、EXIF 旋转与像素上限检查；worker 只收 JPEG/PNG 字节。
- worker 不读环境凭证、不连数据库、不发网络请求；`spawn` 避免继承父进程**堆内存**，子进程仍会继承 `os.environ`，因此 worker initializer 清除 `MASTER_KEY`/`ADMIN_PASSWORD` 等敏感变量（`[spec-review-amendment R-26]`）。
- 识别原文与图片字节不落日志、不入状态接口；`usage_event` 只存 `image_hash` 前 16 位。
- 状态接口与设置接口沿用管理员会话 + CSRF；公共 `/v1/providers` 不泄露路径/版本细节。

## 切片与依赖

| 切片 | 交付行为 | 依赖 |
| --- | --- | --- |
| T1 引擎与进程池 | extra 可安装；worker 可 warmup/识别；父进程状态机与内部自检 | — |
| T2 公共路由与兜底 | `provider=local`、`auto` 兜底、预算预留、403/502/504 | T1 |
| T3 记账与迁移 | `usage_event` 接受 local；local 成功 quota_used=0 | T2（事件来源） |
| T4 管理端 | 设置项 + 状态接口 + 面板卡片 | T1 |
| T5 镜像与文档 | 镜像内置 extra、版本 0.3.0、README/.env.example | T1–T4 |

真实的 `Blocked-by` 以 `tickets.md` 为准，本表只表达语义依赖。

## Compliance

- **ADR-0001**：构建仍走 `uv export` + `uv pip install --index-url`，不读锁文件 URL；本 change 给 export 增加 `--extra local`。
- **ADR-0002**：锁文件用镜像重解析后把源 URL 规范化回 `pypi.org`/`files.pythonhosted.org`；`uv lock --check --offline` + `uv export` 做结构/内容校验，URL 可达性需在可达 PyPI 的环境用 `uv sync --frozen` 或 HEAD 抽查补验（`[spec-review-amendment R-24]`）；不把镜像写进锁。
- **D-6（架构边界）**：只改 `usage_event.provider` 的取值域，不改变任何跨模块数据模型的结构；`settings` 仍是 key/value。
- **R-DEP-06/08**：不改单 worker 与非 root 约束；进程池子进程沿用容器用户。
- **凭证约定**：文档/注释不出现本机私有凭证文档的具体路径或文件名。
- **许可证**：PaddleOCR 模型 Apache-2.0；README 增加归属说明。

## Risks / Trade-offs

- **OpenCV 5 行为回归** → 已实测识别正确；若线上复现，pin `opencv-python-headless<5` 并重跑锁更新流程。
- **进程池在 Windows（spawn）与 Linux 行为差异** → worker 模块保持无副作用、只收原始类型；单测用 fake engine，真实引擎测试标 `slow`。
- **超时后重建池导致连续两次冷启动** → 只在超时/崩溃时重建；正常路径不重建。
- **锁 URL 规范化产出 404** → 只做 host 替换且核对路径后缀；`uv lock --check --offline` + `uv export` 做结构校验；URL 可达性在可达 PyPI 环境用 `uv sync --frozen` 或 HEAD 抽查补验（ADR-0002 已记录该残留风险）。
- **镜像体积增长** → 记录在 README；默认开关关闭，未启用时不占 CPU/内存。
- **`usage_events` batch 重建期间短暂锁表** → 迁移只在启动时执行，单实例；先备份 DB（R-DEP-05）。

## Migration Plan

1. 构建并发布 `0.3.0` 镜像（`latest` 同步；`0.2.1` 不动）。
2. 部署前 `sqlite3 .backup`，并评估 `usage_events` 行数（超 100 万行在维护窗口执行）；启动时自动执行 `0003`（放宽 check 约束）。
3. 管理端开启 `local_ocr_enabled`；观察 `local-ocr/status` 到 `ready`，再用 `provider=local` 验一张图。
4. **回滚顺序**：先关闭本地开关（避免新 local 事件）→ 停新容器 → 用 0.3.0 镜像执行 `alembic -c /app/alembic.ini downgrade -1`（或 `7c1f0d2a9b31`；local 行映射为 `auto`）→ 启动 `0.2.1`。回滚时须覆盖 entrypoint（`--entrypoint alembic`），否则容器启动即 `upgrade head`。不可先启旧镜像再降级：旧镜像的 Alembic 脚本目录不认识 `0003`。

## Open Questions

- 目标部署机（Linux 容器、2 核 4G 下限）的本地识别 p95 未实测；本机 Windows 数据为参考。verify 阶段在服务器上补测，不改变设计与票拆。
- `python:3.12-slim` 上 onnxruntime/opencv 的系统库依赖（如 `libgomp1`）未在镜像内实测；以 task 5.1 的 `import rapidocr, onnxruntime` 与断网启动为准，缺库时在构建期安装。
- 镜像体积（约 110–130MB 下载 / 约 350MB 安装）与 worker 常驻内存（200–300MB）为估算；实施后按 `docker image`/`du -sh`/容器 RSS 回填。
- 是否把 `opencv-python-headless` pin 到 `<5`：当前实测通过，暂不 pin；若出现回归再按锁更新流程收紧。
