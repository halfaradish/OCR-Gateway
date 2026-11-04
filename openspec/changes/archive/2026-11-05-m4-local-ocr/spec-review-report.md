---
ship-gate:
  design_approved: true
  reviewed_sha: d9830926d98700477e470f50dba510449508bb51fed81ecb5511a170371dc7e7
  reviewed_manifest: MTAwNjQ0IGJsb2IgNzA0MWViNzBmNDAyNzRhNDdhOGE3NzFlMGRiNzk5MWVhMGFjYTU4ZQlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9kZWNpc2lvbi1tZW1vLm1kADEwMDY0NCBibG9iIGFhZDJiMTNlMTk5YTNhZDM1MWE3MDkxYjU0M2Q4ZmFmNmQ1NGZlYTAJb3BlbnNwZWMvY2hhbmdlcy9tNC1sb2NhbC1vY3IvZGVzaWduLm1kADEwMDY0NCBibG9iIDIxYzVlNmQzMGYyMDAyMjgwMDcxYTBkNjBkNjViZjc4OGY0ZjNiNDAJb3BlbnNwZWMvY2hhbmdlcy9tNC1sb2NhbC1vY3IvcHJvcG9zYWwubWQAMTAwNjQ0IGJsb2IgN2E3OGU3ZThkNDE3YTFlYjUzMDQzZTk0ZTk0NDE3MWE5NDllZTRiZAlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9zcGVjcy9hY2NvdW50LXBvb2wtc2NoZWR1bGluZy9zcGVjLm1kADEwMDY0NCBibG9iIGQ3MmMwMjJkMjhkNTY2NTU2YTdiZTJlNjI4Zjg3NGExMmQwM2IwMjAJb3BlbnNwZWMvY2hhbmdlcy9tNC1sb2NhbC1vY3Ivc3BlY3MvYWRtaW4tYXBpL3NwZWMubWQAMTAwNjQ0IGJsb2IgNzc2YzM4Mjk5M2Q2NzgwNzQ0MWQyZmM5OGU3N2U3NGQ1ZWRlNDA1NwlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9zcGVjcy9hZG1pbi1wYW5lbC9zcGVjLm1kADEwMDY0NCBibG9iIDI5MTE3NWQ4ODA2MDcwYmNhNzZkNGY5NmFlMzM0MWI4ZTY3NzNmNzEJb3BlbnNwZWMvY2hhbmdlcy9tNC1sb2NhbC1vY3Ivc3BlY3MvZGVwbG95bWVudC9zcGVjLm1kADEwMDY0NCBibG9iIDhhMWMyOTY3NzM0ZGU0NjJhYmY1NGE1NjQ2YTk4MTBjYzA3YTU1NTkJb3BlbnNwZWMvY2hhbmdlcy9tNC1sb2NhbC1vY3Ivc3BlY3MvbG9jYWwtb2NyL3NwZWMubWQAMTAwNjQ0IGJsb2IgYTBhOTYzOTc0ZDc3ZTE5ZTdjZjNkMGM5ODRmNjEwNTVkNjMxODFiYwlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9zcGVjcy9vY3ItYXBpL3NwZWMubWQAMTAwNjQ0IGJsb2IgNDRlODIyYWIxZmViYzMzNTczMTQ3MDE1ZjUzNWM0MjdkYjI4MDNiOQlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9zcGVjcy9xdW90YS1hY2NvdW50aW5nL3NwZWMubWQAMTAwNjQ0IGJsb2IgZmU1ZjQ5ZjhjZDcwZmE3YzZmZDlkMDhhYzJmNTM2OTc3MzkzYWQ0NAlvcGVuc3BlYy9jaGFuZ2VzL200LWxvY2FsLW9jci9zcGVjcy9yZXN1bHQtY2FjaGUvc3BlYy5tZA==
title: m4-local-ocr 设计审报告
change: m4-local-ocr
reviewed_at: 2026-11-04T22:40:00+08:00
reviewed_commit: 228b79d
dispatch: fresh-subagent(6 镜)
memo: ok
---

# Spec Review Report · m4-local-ocr

> ⚠️ **同模型 fresh-context**：隔离的是上下文，不是模型盲点。
>
> 派发镜：对抗镜 ×3（隐藏假设 / 失败模式与并发 / 乐观估计与边界）+ 领域镜 ×3（backend / frontend-react / devex）= 6 个 fresh-context 只读子代理（`Explore`），全部成功、无回退、无截断。广审双镜（strategy / plan-eng）与接地镜由主 session 完成——三者带生成历史，存在自查偏置，结论按「主 session 自审」降级对待。
>
> 评审对象：`228b79d` 的四件套 + `decision-memo.md`（`check_decision_memo.py` 退出 0；`openspec validate m4-local-ocr --strict` 通过）。
>
> 合并后 37 条：高 12 · 中 11 · 低 14。所有 finding 的引文均来自本会话亲验或子代理 `file:line:quote`；外部事实（wheel 体积、RapidOCR 懒加载细节）标「未经接地」。

---

## 拍板三问

**Q-scope 范围划界认不认？**
自答：锚 `proposal.md` `## Non-Goals`（不做模型下载/本地独立配额/多并发调优/GPU/多实例广播/批量 PDF）与 `design.md` `## Goals / Non-Goals`（不改云账号候选/排序/冷却；不做跨实例协调）。评审认为边界总体成立，但 **Non-Goals「不做本地独立配额」的假设 A2「本地只在云全挂时承接」与显式 `provider=local` 冲突**——显式 local 何时都可调用，见 R-15。请一并确认这一划界。
[x] 认 [ ] 不认

**Q-deps 依赖/顺序认不认？**
自答：锚 `design.md` `## 切片与依赖`（T1 引擎与进程池 → T2 公共路由/T4 管理端 → T3 记账 → T5 镜像文档；T3 依赖 T2 的事件来源）。依赖链本身成立；但 T1 需补「可 kill 的进程池 / generation」、T3 需补「`models.py` 同步」，否则任务顺序对而实现会返工（R-03/R-07/R-10）。
[x] 认 [ ] 不认

**Q-risk 风险赌注与对策认不认？**
自答：锚 `design.md` `## Risks / Trade-offs` 6 条 + `decision-memo.md` `## 接受的边角` 6 条。评审认为还缺 3 项风险：运行中任务不可取消（R-03）、兄弟请求被池重建取消（R-12）、`python:3.12-slim` 系统库未显式验证（R-36）。接受这些风险的话，需把「可 kill 池」的成本计入 T1。
[x] 认 [ ] 不认

---

## 决策登记区

> `[需拍板]` 在主 session 无法单方面定；`[自动决策]` 已按通则自行裁决并落入 amendment，可覆盖。

## 拍板结果（人 2026-11-04）

人已批准进入设计 HARD-GATE，并按推荐拍板：

- **Q1 → B**：`multiprocessing.get_context("spawn").Pool`（可 `terminate()`）；已落入 design 组件职责与 tasks 1.2。
- **Q2 → A**：`reserve_eff` clamp；已落入 design 预算不变量、R-SCH-07 与 tasks 2.2。
- **Q3 → A**：overview 增加 `local` 行（`accounts=0`）；已落入 R-ADM-09 delta、design 可观测性、tasks 3.4。
- **Q4 → A**：保持 D3，修正理由并写明仅受 Key RPM/并发；已落入 proposal Non-Goals、R-QTA-01、tasks 5.2。
- 拍板三问：范围 **认** / 依赖 **认** / 风险 **认**。
- 窄复核（增量）：Q1/Q3/Q4 的二次修订只触及上述段落与 R-ADM-09 delta；`openspec validate --strict` 通过，R-ADM-09 的 7 条既有 scenario 全部保留并新增「本地厂商行」。

### [需拍板]

**Q1 进程池的「超时即回收」机制（对应 R-03，高）**

现状设计用 `ProcessPoolExecutor` + `shutdown(wait=False, cancel_futures=True)` 重建池。该 API 只能取消**尚未开始**的任务，**不能终止正在推理的进程**；卡死任务会作为孤儿进程继续占用 200–300MB 与 CPU，每次超时累积一个。

- 选项 A：自管 `Process + Queue`（每个 worker 一个进程，可 `terminate()/kill()`）——控制力最强，代码量最大。
- 选项 B：改用 `multiprocessing.get_context("spawn").Pool`（自带 `terminate()`/`kill()`，超时后整池回收）——代码量最小，语义最直接；代价是放弃 `ProcessPoolExecutor` 的 future API，需自行包一层。**推荐**。
- 选项 C：保留 `ProcessPoolExecutor`，在 spec 写明「运行中任务不可取消」并接受孤儿进程——与 `R-LOC-04「避免一个卡死任务永久占住唯一 worker」` 直接冲突，不推荐。

推荐 B。系统镜：多一个自管类，但回收语义可测试；用户镜：超时可恢复；开发循环镜：不引入新依赖，fake pool 可注入。主次判定：**正确性优先于 API 便利**。

**Q2 预算预留策略（对应 R-01，高）**

`request_deadline_ms` 允许 1000–20000ms，而 reserve 固定 5000ms；`deadline < reserve` 时云阶段截止落在过去，auto 连健康云账号都不试。

- 选项 A：`reserve_eff = min(LOCAL_OCR_RESERVE_MS, max(0, total - LOCAL_OCR_MIN_BUDGET_MS))`，且仅在 `total ≥ reserve_eff + min_budget` 时启用本地兜底。**推荐**。
- 选项 B：启用 local 时校验 `request_deadline_ms ≥ reserve + min_budget`，把 ≤6s 的设置拒掉；需同步改 R-ADM-08 的 1000ms 下限断言。
- 选项 C：按比例预留（如 total 的 25%，上限 5s）——行为更难解释，不推荐。

推荐 A：不改既有设置范围，预算过小时退化为「本地不兜底」，与本地禁用等价；status 暴露 `effective_reserve_ms`。代价：管理员把小预算 + 开本地时，auto 仍只走云，需要在状态/日志里说明。

**Q3 总览是否给 `local` 加一行（对应 R-13，中）**

`today.requests` 已包含 `provider=local` 事件，但 provider 行硬编码 `("baidu","tencent")`；D10 又明确「overview 的 provider 列表不加 local」。结果是 R-ADM-09 的「今日总数与厂商行对账」被打破（现有代码注释 `admin.py:720` 正说明这是刻意维持的契约）。

- 选项 A：加 `local` 行（`accounts=0`、`available_accounts=0`），同步 MODIFY R-ADM-09 与 D10。**推荐**。
- 选项 B：`today.requests` 剔除 local 事件——本地用量从总览消失，不推荐。
- 选项 C：维持 D10，接受对账差——需要在 R-ADM-09 写明例外，且面板会出现「总数 > 行和」。

推荐 A。系统镜：一行数据、无新查询；用户镜：本地用量可见且对账成立；开发循环镜：改两处硬编码 + 一个测试。主次判定：**对账正确性优先于「local 无账号不进行」的洁癖**。

**Q4 显式 `provider=local` 是否受用户日限额（对应 R-15，中）**

D3 定 `quota_used=0`，memo 的接受理由写「概率低（仅云全挂时触发）」——但显式 `provider=local` 在任何时候都可用，该理由不成立。当前实际约束只剩 Key RPM + 全局并发。

- 选项 A：保持 D3，修正接受理由，明确「显式 local 是仅受 RPM/并发约束的免额度通道」，README/安全说明写明，记 todo。**推荐**（M4 范围外）。
- 选项 B：本地事件计入日限额（`quota_used=1`）——破坏「配额=厂商额度」语义，面板多处口径要改。
- 选项 C：新增本地专用日计数与限额——新字段/迁移/面板，超出 M4。

推荐 A。代价：存在被单 Key 持续占用 CPU 的滥用面（全局并发 8、本地 1 worker 会排队并超时，影响可控）。若人不接受，需另开 change，不要在本 change 塞入。

### [自动决策]

| ID | 对应 | 决策 | 理由 |
| --- | --- | --- | --- |
| D1 | R-02 | 缓存读取前做 provider 可用性门禁；`local_ocr_enabled` 变化视为缓存参数变化（清空缓存并在响应标记 `cache_cleared`） | 403 契约必须优先于缓存命中；清缓存成本低且与既有配置变更语义一致 |
| D2 | R-04 | 成功响应的 `quota.used` 与 `usage_event.quota_used` 都由 `result.provider` 派生（local→0） | 消除 `public.py` 两处硬编码 1；R-API-05 已要求 local=0 |
| D3 | R-05 | lifespan 在 `local_ocr_enabled && installed` 时调用 `set_enabled(true)` | R-ADM-08「重启后新值仍生效」与 R-LOC-05「启用后建池预热」的必然推论 |
| D4 | R-06 | MODIFY R-SCH-03：总 deadline 不变，auto 云阶段用 `deadline − reserve_eff` 子 deadline，本地阶段用总 deadline | 消除两条权威需求的冲突；保留既有「同一绝对 deadline」的意图 |
| D5 | R-07 | task 3.1 同时修改 `models.py` 的 `ck_usage_provider`，并加 `create_all` 插入 local 的测试 | 测试建库走 `Base.metadata.create_all`，ORM 不同步会让 local 事件在单测里直接 IntegrityError |
| D6 | R-08 | 账号域保留 `ProviderCode = baidu\|tencent`；新增 `EventProvider = ProviderCode \| auto \| local` 供日志/用量/标签/`ProviderRow.code`（Q3 后 overview 也返回 local 行）；账号/凭证映射仍用 `ProviderCode` | 防止账号创建 UI 被 local 污染；memo C6「改 types.ts:1」按此修正 |
| D7 | R-09 | 依赖缺失 → `unavailable`（不建池，显式 local 仍 403）；模型加载失败 → `error`；同步状态图/JSON/spec | 两份 spec 已写 unavailable，只有 design 状态机漏了 |
| D8 | R-10 | `set_enabled` 幂等且仅在状态变化时执行；enable/disable/rebuild 分配自增 generation，回调先比对 generation；disable 清 ready event | 防止迟到 warmup 覆盖新状态、重复建池 |
| D9 | R-11 | warmup 用含文字的小图并断言返回非空；warmup 加超时（≤ ready 等待上限），超时置 `error` | 1×1 白图在检测阶段即返回，不能证明 rec/cls 已加载；warmup 卡住会让 starting 永久停留 |
| D10 | R-12 | 用 generation 区分「本轮超时」与「被重建取消」；后者映射 503/504 并写 usage_event；只允许超时 owner 单飞重建 | 否则兄弟请求收到 `CancelledError` → 500 且无事件 |
| D11 | R-14 | tasks 3.3 增 usage-page 下拉与 `provider=local` URL 断言；admin-api delta 增 MODIFIED R-ADM-06（local 标签「本地 RapidOCR」） | task 引用了 R-ADM-06，但 change 的 delta 里没有该需求 |
| D12 | R-16 | Success Metric 改为「成功=200 且 provider=local；504 单独计失败并给阈值」；p95 用固定 N 次基准脚本（或 status 增 histogram） | `last_latency_ms` 是单样本，算不出 p95；「200 或 504」把失败计入成功 |
| D13 | R-17 | tasks 增独立验收步骤：装 extra 后 `pytest -m slow`、镜像内断网启动并轮询 status 到 ready；把「镜像冒烟脚本」列为交付物 | 默认 `addopts = -m 'not slow'`，P0 的真实引擎/离线就绪在默认流程里永不执行 |
| D14 | R-18 | warmup 失败加最小重试间隔（30s）+ 指数退避；请求路径不同步等待重试；status 暴露 `next_retry_in_ms` | 确定性加载失败会被每个云故障请求反复触发 |
| D15 | R-19 | 显式 local 先取 local gate（= max_workers）再取全局信号量；auto 兜底阶段在全局槽内取 local gate | 排队本地请求不再占满全局并发槽 |
| D16 | R-20 | design 增 copy 表：403（开关关闭 vs 依赖缺失两种 cause/fix）、502、504 的 problem/cause/fix 原文；写明 `/v1/providers.enabled` 的合并语义 | DX-02 判定 UNVERIFIABLE（只有错误码没有文案） |
| D17 | R-21/R-22 | 回滚命令改 `alembic downgrade -1`（或 `7c1f0d2a9b31`）+ `--entrypoint` 覆盖；tasks 5.1/5.2 列全部版本源与文档落点 | 0002 的 revision 不是 `0002`；entrypoint 启动即 `upgrade head` |
| D18 | R-25 | design 增 auto 兜底 + 超时重建的 ASCII 序列图 | TG-10（跨 3+ 组件）与 TG-26（并发）双重命中，design-diagrams 要求序列图 |
| D19 | R-26～R-37 | 低项批量修订：worker initializer 清理敏感 env、`mp_context` 写法、last_error 脱敏、shutdown 上限、local 规范化表述、status effective timeout、`LOCAL_OCR_*` 权威表、面板三态/轮询/部分提交、README `--extra local`、迁移行数评估、slim 系统库验证、ready 阈值统一 | 均为低成本修正，不改变架构 |

### [已裁掉]

| ID | 原始发现 | 裁掉理由 |
| --- | --- | --- |
| X1 | 「兜底失败要写两条 usage_event（云+本地）」 | 不成立：`request_id` 唯一（`models.py:115`），设计原意是 local 分支成功/失败各记一条，不是同一请求两条 |
| X2 | 「auto 兜底的 local 结果不应进入 auto 缓存」 | 部分不成立：R-CAC-01 允许缓存实际服务成功的结果；开关切换清缓存后，云恢复前返回缓存 local 属正常缓存语义。只保留「清理」要求，不另设回退标记 |
| X3 | 「`ProcessPoolExecutor(spawn, ...)` 是硬错误」 | 降级为低：design 是图形简写，不构成 API 契约；已在 R-27 要求改为 `mp_context` |
| X4 | 「local 要保留原始字节才能满足 10MB，与 EXIF 旋转冲突」 | 不成立：设计意图是「旋转/重编码后按 JPEG 字节计上限」，不是保留原字节；已在 R-30 纠正表述 |
| X5 | 「BE-11 要求 SLA/RTO/RPO」 | N/A：单实例自托管工具，proposal 未承诺 SLA；不新增 |
| X6 | 「BE-09 要求 zero-downtime」 | N/A：单实例部署，维护窗口可接受；不新增 |

---

## 合并发现与裁决

> 每条给出：命中镜 / 证据（亲验或子代理引文）/ 裁决。/ 严重度：高=阻断，中=实现期返工，低=记录即可。

### 高

#### R-01 预算预留与 `request_deadline_ms` 下限冲突
- **命中**：ADV-A / ADV-B / ADV-C / ENG
- **证据**：`design.md:69`「`auto` 且本地可用 → 云阶段截止 `deadline - reserve`」；`design.md:72`「本地单次超时 = `min(LOCAL_OCR_TIMEOUT_MS, deadline - now)`；剩余 < `LOCAL_OCR_MIN_BUDGET_MS`（默认 1000）时不再尝试本地」；`backend/app/runtime_settings.py:81-87`「`request_deadline_ms` … minimum=1000 / maximum=20000」；`backend/app/config.py:71`「request_deadline_ms: int = 20000」；`decision-memo.md:20`「auto+本地启用时云阶段为本地预留 5s」
- **裁决**：成立。预算 1–5s 时云阶段 deadline 已过，auto 连健康云账号都不尝试；预算 1–4s 时本地也因剩余 <1s 放弃 → 直接 504。需引入 `reserve_eff` 并写入 R-SCH-07；见 Q2。

#### R-02 缓存命中先于 local 可用性门禁；开关切换不清缓存
- **命中**：ADV-A / ADV-B / ADV-C / BE
- **证据**：`backend/app/api/public.py:218-219`「cache_key = … / cached = state.cache.get(cache_key)」位于 `Scheduler` 与 `provider` 校验之前；`backend/app/api/public.py:312`「state.cache.set(cache_key, payload)」；`backend/app/core/cache.py:35`「return f"{digest}:{language}:{provider}"」；`backend/app/api/admin.py:1094`「cache_cleared = state.cache.reconfigure(...)」；`specs/ocr-api/spec.md:6`「显式 `local` 在本地 OCR 未启用或依赖不可用时 MUST 返回 403」；`openspec/specs/result-cache/spec.md:9`「命中时 MUST 返回 cached=true、quota.used=0，且不发起厂商调用」
- **裁决**：成立。关闭开关后，显式 local 仍可能命中旧缓存返回 200；auto 缓存键下也可能返回 `provider=local`。修：门禁前置 + 开关变化清缓存。新增 `result-cache` delta。

#### R-03 超时不能终止运行中的 worker；重建池不回收旧进程
- **命中**：ADV-A / ADV-B / ADV-C / BE
- **证据**：`design.md:112`「单次超时：取消 future、`shutdown(wait=False, cancel_futures=True)` 重建池并回到 `starting`……避免一个卡死任务永久占住唯一 worker」；`specs/local-ocr/spec.md:42`「超时 MUST 返回 504 `TIMEOUT`，MUST 取消排队任务并重建进程池」
- **裁决**：成立（Python 语义：`cancel_futures` 只取消 pending，`shutdown(wait=False)` 不终止运行中进程）。设计目标与机制矛盾。见 Q1。

#### R-04 本地成功仍会写 `quota_used=1` / 响应 `quota.used=1`
- **命中**：ADV-B / ENG
- **证据**：`backend/app/api/public.py:323`「quota_used=1,」；同文件成功响应 `_response_payload(..., False, 1)`（约 334-335 行）；`specs/ocr-api/spec.md` R-API-05「`quota.used` … 对本地识别成功 MUST 为 0」；`specs/quota-accounting/spec.md` R-QTA-01「本地识别成功 MUST 记 `quota_used=0`」
- **裁决**：成立。事件侧 task 3.2 已覆盖，但响应侧与既有硬编码未进任务；两处都必须由 `result.provider` 派生。

#### R-05 持久化的 `local_ocr_enabled` 重启后不恢复
- **命中**：ADV-A / ADV-B / ADV-C / BE
- **证据**：`backend/app/main.py:65`「runtime = await load_runtime_settings(session, resolved)」；`backend/app/main.py:83`「state = AppState(」——lifespan 无 `set_enabled`；`design.md:97`「stopped --> starting: set_enabled(true)」是唯一启动路径；`tasks.md:9` 只要求「装配与关闭」；`specs/admin-api/spec.md:13`「其余设置保持不变，重启后新值仍生效」
- **裁决**：成立。重启后 `enabled=true` 但 `state=stopped`，显式 local 既不满足 403 条件也不可用。

#### R-06 R-SCH-03 与 R-SCH-07 的 deadline 语义冲突
- **命中**：ADV-A / STR
- **证据**：`openspec/specs/account-pool-scheduling/spec.md:32`「`public.py` 的外层等待与 `Scheduler` MUST 使用同一个绝对 deadline」；`specs/account-pool-scheduling/spec.md:22-24` R-SCH-07「云阶段截止 MUST 为总 deadline 减去本地预留预算」；change 只 MODIFY R-SCH-05，未改 R-SCH-03
- **裁决**：成立。两条权威需求可互相违反；需 MODIFY R-SCH-03 明确「总 deadline 不变 + 云阶段子 deadline」的例外。

#### R-07 `models.py` 的 `ck_usage_provider` 未列入 task 3.1
- **命中**：ADV-B / BE
- **证据**：`backend/app/models.py:137`「provider IN ('baidu', 'tencent', 'auto'), name="ck_usage_provider"」；`backend/tests/conftest.py:45`「await connection.run_sync(Base.metadata.create_all)」；`tasks.md:23` 只写「新增 Alembic `0003` 迁移」
- **裁决**：成立。测试建库走 `create_all`，ORM 不同步会让 local 事件在单测直接 IntegrityError。

#### R-08 `ProviderCode` 复用于账号/事件/总览导致类型与语义冲突
- **命中**：ADV-A / BE / FE / DX
- **证据**：`frontend/src/types.ts:1`「export type ProviderCode = "baidu" | "tencent";」；同文件 `ProviderRow.code: ProviderCode`；`frontend/src/pages/accounts-page.tsx:49`「const CREDENTIAL_FIELDS: Record<ProviderCode, …> = {」；同文件 `provider: z.enum(["baidu", "tencent"])`；`decision-memo.md:41`「frontend/src/types.ts:1」列为需改
- **裁决**：成立。直接扩 union 会逼账号 UI 为 local 配凭证，且与 D10「总览不加 local」冲突。拆类型。Q3 拍板让 overview 也返回 local 行后，`ProviderRow.code` 必须使用展示联合（含 local）；账号/凭证映射仍只接受 baidu/tencent。

#### R-09 `unavailable` 状态在 design 状态机缺失，与两份 spec 冲突
- **命中**：ADV-A / ADV-B / BE / DX
- **证据**：`design.md:99`「starting --> error: 依赖缺失/模型加载失败」；`specs/local-ocr/spec.md:53`「状态按 `stopped`/`starting`/`ready`/`error`/`unavailable` 报告」；`specs/admin-api/spec.md:63`「返回 `installed=false`、`state="unavailable"`」
- **裁决**：成立。按 spec 统一：依赖缺失=unavailable（不建池）；模型加载失败=error。

#### R-10 状态机缺少 generation / 幂等；迟到 warmup 覆盖、重复建池
- **命中**：ADV-B
- **证据**：`design.md:109`「`set_enabled(true)` 只负责建池并提交 warmup」；`design.md:112`「重建池并回到 starting」；`design.md:151`「开关在请求中变更…在跑任务跑完」；`tasks.md:32`「`_apply_settings` 在 commit 后调用 `LocalEngine.set_enabled`」
- **裁决**：成立。若每次保存都无条件 `set_enabled(true)`，ready 状态可能再建一个池；disable 后迟到的 warmup 也可把状态改回 ready。需 generation + 幂等 + disable 清 event。

#### R-11 warmup 用 1×1 白图可能未加载 rec/cls；warmup 无超时
- **命中**：ADV-A / BE
- **证据**：`design.md:7`「`RapidOCR()` 构造不加载模型，首次调用才加载」；`design.md:110`「warmup 用 1×1 白图跑一次完整 pipeline，成功才算 `ready`（覆盖模型加载）」；`design.md:111`「`starting` 期间的本地请求等待就绪事件，最多等 min(10s, 剩余预算)」
- **裁决**：成立（中高）。1×1 白图在检测阶段通常无候选框，rec/cls 不会执行，「覆盖模型加载」的结论未经验证；warmup 卡住时状态永久 `starting`。修：含文字小图 + warmup 超时。

#### R-12 池重建取消兄弟请求的排队 future → `CancelledError` → 500
- **命中**：ADV-B / BE
- **证据**：`design.md:112`「取消 future、shutdown(...cancel_futures=True) 重建池」；`design.md:148`「取消排队任务」；`backend/app/api/public.py:264`「except SchedulerError as exc:」；`public.py:281`「except InputError as exc:」——未捕获 `CancelledError`
- **裁决**：成立（中高）。云全挂时多个 auto 同时兜底是主场景；被牵连取消的请求会 500 且不写 usage_event。需 generation 区分并映射 503/504。

### 中

#### R-13 总览的今日总数与厂商行不再对账（R-ADM-09）
- **命中**：ADV-A
- **证据**：`backend/app/api/admin.py:720`「auto failures are counted separately so today's totals reconcile with the two provider rows (D-A3 / R-ADM-09)」；`admin.py:782`「for code in ("baidu", "tencent")」；`design.md:26`（D10）「管理端 overview 的 provider 列表不加 local」；`openspec/specs/admin-api/spec.md:225` R-ADM-09
- **裁决**：成立。local 事件进入 `today.requests` 但不进 provider 行 → 对账差。见 Q3（推荐加 local 行）。

#### R-14 用量页筛选/标签与 R-ADM-06 的 delta 缺失
- **命中**：FE / BE / DX
- **证据**：`tasks.md:27` 只点名「日志筛选下拉」；`frontend/src/pages/usage-page.tsx:196-199` 只有 baidu/tencent/auto 三个选项；`frontend/src/pages/logs-page.tsx:161-164` 同样；`openspec/specs/admin-api/spec.md:106` R-ADM-06 未在 change delta 中修改
- **裁决**：成立。用量页无法按 local 筛选；task 引用的 R-ADM-06 没有对应需求增量。

#### R-15 显式 `provider=local` 不受日限额，memo 的「概率低」理由不成立
- **命中**：ADV-A
- **证据**：`decision-memo.md:50`「本地请求不受用户日限额（quota_used=0）— 概率低（仅云全挂时触发）」；`proposal.md:12`「显式 `provider=local` 在已启用时直接走本地，不经过云账号/配额」；`openspec/specs/quota-accounting/spec.md:46`「daily_limit SHALL 限制该 Key 当日消耗的配额单位（quota_used 合计）」
- **裁决**：成立。显式 local 随时可用，memo 的触发条件不成立。见 Q4（推荐保持 D3 + 修正理由 + README 写明）。

#### R-16 Success Metrics 不可证伪
- **命中**：ADV-C / BE
- **证据**：`proposal.md:22`「本地已启用且 worker 就绪时，≤2000px 的截图 100% 返回 200 或明确 504」；`proposal.md:23`「度量：状态接口 `last_latency_ms`、单元/基准测试与镜像冒烟」；`design.md:167`「"last_latency_ms": 812」；`design.md:187`「热调用 p95（≤2000px 截图）≤3s」
- **裁决**：成立。504 被计入成功；`last_latency_ms` 是单样本，无法算 p95；2000px 未定义长边/面积。

#### R-17 slow/真实引擎/镜像验收无落点
- **命中**：ADV-C
- **证据**：`backend/pyproject.toml:42`「addopts = "-m 'not slow'"」；`tasks.md:7`「标记 `slow`、未安装 extra 时 skip」；`tasks.md:41` 只验 import；`proposal.md:24`「度量：镜像冒烟脚本读 `/api/admin/local-ocr/status`」（无任务交付该脚本）
- **裁决**：成立。默认测试环境不装 extra，真实引擎测试被 skip；离线就绪与 Success Metric #3 不会被任何任务执行。

#### R-18 warmup 失败无退避 → 每个请求重复 spawn/import/加载
- **命中**：ADV-B
- **证据**：`design.md:104`「error --> starting: 下次请求或重新启用重试」；`specs/account-pool-scheduling/spec.md:23`「云端无候选或全部候选以可重试错误失败时尝试本地识别」
- **裁决**：成立。确定性加载失败时，每个云故障请求都会重建池并重复失败，占用 5s reserve。需最小重试间隔 + 退避。

#### R-19 本地排队请求占用全局信号量
- **命中**：BE
- **证据**：`design.md:119`「多请求在 executor 队列等待并各自受 deadline 约束」；`design.md:120`「全局 `MAX_CONCURRENT_REQUESTS` 信号量仍在最外层，本地请求也计入」；`backend/app/api/public.py:253`「await asyncio.wait_for(state.semaphore.acquire(), timeout=remaining)」
- **裁决**：成立。8 个长本地请求可占满全局槽，云端请求等到预算耗尽后 503，而本地只有 1 个 worker。加 local gate。

#### R-20 403/502/504 文案三件套缺失，403 无法区分两种 cause
- **命中**：DX（DX-02 UNVERIFIABLE）
- **证据**：`specs/ocr-api/spec.md:6`、`design.md:145`、`design.md:168` 只有错误码；`specs/ocr-api/spec.md:87`「`enabled` 反映本地 OCR 是否启用且安装可用」；`backend/app/runtime_settings.py:58`「The user-visible texts below are the ones from the design's copy table (single source)」——本 change 无对应文案
- **裁决**：成立。同一 403 覆盖「开关关闭」与「依赖缺失」，fix 完全不同；需 copy 表。

#### R-21 `alembic downgrade 0002` 命令与 entrypoint 冲突
- **命中**：ADV-C / BE
- **证据**：`design.md:236`「用 0.3.0 镜像执行 `alembic downgrade 0002`」；`tasks.md:45` 同；`backend/alembic/versions/0002_settings.py:16`「revision: str = "7c1f0d2a9b31"」；`docker/entrypoint.sh:17`「alembic -c /app/alembic.ini upgrade head」；`docker-compose.yml:29`「stop_grace_period: 25s」
- **裁决**：成立。`0002` 不是 revision id；且容器启动即 `upgrade head`，无法直接 `run` 降级。改 `-1`/`7c1f0d2a9b31` + `--entrypoint` 覆盖。

#### R-22 文档/版本落点不完整
- **命中**：ADV-C / BE / DX
- **证据**：`README.md:260`「公共 API 的 `provider` 只接受 `auto`/`baidu`/`tencent`；`local` 等取值返回 400」；`README.md:193`「版本锚 … `ocr-gateway:0.2.1`」；`README.md:196-198` 回滚仍写 0.1.0/0001；`docs/tech-selection.md:22/212/346/453/589/600` 仍写按需下载/`/local-ocr/download`/`data/models/rapidocr`/`local_ocr_max_concurrency` 为设置键；`backend/app/__init__.py:1`、`backend/pyproject.toml:3`、`frontend/package.json:4`、`backend/uv.lock:914` 均为 0.2.1
- **裁决**：成立。tasks 5.2 只点名 §9/§16 与「不做本地 OCR」，照文档走会得到错误行为/版本。

#### R-25 缺少请求序列图（TG-10 / TG-26 必画）
- **命中**：STR / ENG
- **证据**：`references/design-diagrams.md` 触发条件表「跨 3+ 组件协作 → 序列图」「并发 / 共享可变状态 → 序列图（竞态交互时序）」；`design.md` 只有架构 ASCII、决策流程图、状态机图，无序列图
- **裁决**：成立。补 auto 兜底 + 超时重建的 ASCII 序列图。

### 低（一行带过，均在 amendment 中处理）

- **R-23** 镜像体积/RSS 数字未实测：`decision-memo.md:44` 的 opencv 34.8MB 与子代理外部查询（56.5MB）冲突，本机无外网无法核验 → 标「未经接地」，改为估算 + 测量命令，实施后回填。`design.md:191-192`、`proposal.md:76` 同步。
- **R-24** ADR-0002 的「双验证」过强：`design.md:216/227`；ADR 已自述 URL 可达性需 `uv sync` 才能暴露（`adr/0002:57-59`），design 改为「结构/内容校验；可达性在可达 PyPI 环境补验」。
- **R-26** spawn 只避免继承堆内存，不阻止 env 继承：`design.md:121/197`；worker initializer 清理 `MASTER_KEY`/`ADMIN_PASSWORD`。
- **R-27** `ProcessPoolExecutor(spawn, ...)` 非有效 API：`design.md:45`；改为 `mp_context=multiprocessing.get_context("spawn")`（若 Q1 选 B 则同步为 Pool context）。
- **R-28** `last_error` 可能泄露模型绝对路径：`specs/admin-api/spec.md:55`、`design.md:113/168`；只保留错误码 + 脱敏短消息。
- **R-29** shutdown 无时限：`design.md:114`；上限 ≤20s（compose grace 25s）。
- **R-30** local 规范化表述含糊：`specs/ocr-api/spec.md:37`、`tasks.md:14`；写明「Pillow 校验 + EXIF 旋转 + 重编码 JPEG；上限作用于重编码后的 JPEG 字节；最长边 10000；不做 base64 膨胀」。
- **R-31** 30s 本地超时在当前 20s 上限下不可达：`design.md:72/164`、`config.py:71`；status 增 `effective_timeout_ms`。
- **R-32** `LOCAL_OCR_*` 权威清单不一致：`decision-memo.md:25`（3 个）vs `tasks.md:9`（5 个）；design 增「键/类型/默认/来源/范围/理由」表。
- **R-33** 面板状态卡三态/单一数据源/轮询/部分提交未定义：`specs/admin-panel/spec.md:6/30/34`、`frontend/src/pages/settings-page.tsx:81/98/142`、baseline R-PANEL-09；按 D19 批量补场景。
- **R-34** 本地 onboarding 无 TTHW / `uv sync` 不含 extra：`README.md:65`、`README.md:22`；补 `--extra local` 与步骤数/耗时假设。
- **R-35** SQLite batch 重建的行数/磁盘余量未评估：`design.md:229`、`models.py:141`；迁移计划补行数评估与维护窗口。
- **R-36** `python:3.12-slim` 系统库（如 libgomp1）未显式验证：`Dockerfile:67` 之后无 apt-get；`specs/deployment/spec.md:10` 只要求 import；task 5.1 的 import 检查可捕获，但应写成显式验证并允许按需安装。
- **R-37** ready 阈值数字口径不一：`proposal.md:24`「30s 内 ready」vs `design.md:186/190`「冷启动 ≤5s / ready 等待 min(10s, 剩余)」；统一为「验收 ≤10s，目标 ≤5s」。

---

## 分镜列示

### 广审 · strategy（主 session）

- 范围/完整性：Non-Goals、假设 A1–A4、优先级 P0–P2、五切片均在；`openspec validate --strict` 通过。新增发现：R-06（R-SCH-03 未改）、R-25（缺序列图）、R-37（ready 阈值口径）。
- 外部一致性：R-02（result-cache 未进 capabilities）、R-06、R-13（R-ADM-09）、R-14（R-ADM-06）。
- 清晰度：R-09（unavailable）、R-30（local 规范化）、R-31（30s 上限）、R-32（配置清单）。
- 范围/YAGNI：未发现扩大范围的实现；`app/core/local_engine.py` + `app/workers/local_ocr.py` 两个新模块属于单一能力，不判范围蔓延。
- ADR 三镜：`decision-memo.md`「三镜代价」有主次判定，D1–D16 有候选与否决理由 → 通过。
- 正文即最终态：design 无修订播报/旧方案残留 → 通过。

### 广审 · plan-eng（主 session）

- 可行性：R-03（不可取消）、R-12（兄弟取消）、R-19（信号量）、R-36（slim 系统库）。
- 错误处理：R-04、R-11、R-18、R-20、R-28；失败模式表缺「池重建取消」「warmup 卡住」「缓存命中绕过门禁」三行。
- NFR：R-16、R-23、R-31、R-37。
- 可追踪性：R-05（无任务）、R-07（models.py）、R-14（R-ADM-06 无 delta）、R-17（无 slow 验收）；其余 R-ID 双向覆盖成立。
- 图表/组件/安全：R-25；组件职责表齐全；R-26/R-28 安全表述。

### 对抗镜 A · 隐藏假设（子代理，12 条 → 合并 R-01/02/03/05/06/08/09/11/13/15/26/36）

攻击面：C1–C9 证据锚、RapidOCR 懒加载、spawn 语义、既有契约不变、openapi/specs 对读。全部 12 条均带锚；R-11 的「1×1 不触发 rec」与 R-36 的「slim 系统库」依赖外部/运行期事实，已在正文标为中高/低。

### 对抗镜 B · 失败模式与并发（子代理，12 条 → 合并 R-01/02/03/04/05/07/09/10/12/18/27/31）

攻击面：状态机竞态、预算算术、缓存/semaphore/usage_event、403/502/504、迁移。全部带锚；R-04/R-10/R-12 为本轮最高价值的组合发现。

### 对抗镜 C · 乐观估计与边界（子代理，12 条 → 合并 R-01/02/03/05/16/17/21/22/23/24/30/31）

攻击面：数字自洽、边界值、外部事实、验收口径、文档一致性。R-23 的外部体积数字本机无法核验，已标「未经接地」；R-30 的「保留原始字节」前提被主 session 纠正（X4）。

### 领域镜 · backend（子代理，15 条 → 合并 R-02/03/04/05/07/08/09/11/12/16/19/21/22/28/29/35）

BE-01 迁移（R-07/R-35）、BE-02 API（R-02/R-08/R-09/R-22）、BE-03 Auth（R-28）、BE-04 错误（R-03/R-11/R-12）、BE-05 一致性（R-05）、BE-06 性能（R-19）、BE-07 可观测（R-16）、BE-09 退出（R-29）、BE-11 回滚（R-21）。BE-08（退避）由 R-18 覆盖；BE-10（分发）通过；BE-11 SLA/RTO/RPO 判 N/A（X5）。

### 领域镜 · frontend-react（子代理，9 条 → 合并 R-08/R-14/R-33）

FE-01/02/07/09/10/13 与 REACT-01/02；REACT-03 判 N/A（Vite + React SPA，无 RSC，`frontend/package.json:48`、`frontend/src/App.tsx:28`）。视觉类 FE-04/05/06/08/12 判 N/A（管理面板既有视觉方向，无新落地页/第三方脚本/多语言）。

### 领域镜 · devex（子代理，10 条 → 合并 R-08/R-09/R-20/R-22/R-31/R-32/R-34）

DX-01 UNVERIFIABLE（无 TTHW 估算）、DX-02 UNVERIFIABLE（无错误文案）、DX-03 FAIL（配置清单/30s 默认）、DX-04 FAIL（unavailable 语义/版本与回滚文档/模型下载残留/混版本说明）、DX-05 N/A（不新增 SKILL）。全部带锚。

### 接地镜（主 session）

亲验 28 处代码事实，**0 条假引文**：

| 事实 | 结果 |
| --- | --- |
| `public.py:28` VALID_PROVIDERS 只有 auto/baidu/tencent | ✅ |
| `public.py:218-219` 缓存读取在 scheduler/门禁前 | ✅ |
| `public.py:323` 成功事件硬编码 `quota_used=1` | ✅ |
| `public.py:253` 全局 semaphore 在最外层 | ✅ |
| `runtime_settings.py:81-87` deadline 1000–20000 | ✅ |
| `main.py:65/83` lifespan 无 local 装配 | ✅ |
| `models.py:137` 三值 check；`account_id` 已 nullable | ✅（迁移表无需加列） |
| `conftest.py:45` create_all 建库 | ✅ |
| `alembic 0002 revision = 7c1f0d2a9b31` | ✅ |
| `entrypoint.sh:17` 启动即 upgrade head | ✅ |
| `docker-compose.yml:29` grace 25s；`image: 0.2.1` | ✅ |
| `pyproject.toml:42` addopts 排除 slow | ✅ |
| `admin.py:720/782` overview 对账注释 + 硬编码两厂 | ✅ |
| `admin.py:1094` 只 reconfigure 缓存参数 | ✅ |
| `registry.py:153` candidates；`base.py:111` PROVIDER_NAMES | ✅ |
| `deps.py:202` 日限额按 `sum(quota_used)` | ✅ |
| `types.ts:1/28`、`accounts-page.tsx:49/76` | ✅ |
| `usage-page.tsx:196-199`、`logs-page.tsx:161-164` | ✅ |
| `settings-page.tsx:81/98/142` | ✅ |
| `README.md:17/22/65/193/196-198/260` | ✅ |
| `tech-selection.md:22/212/346/453/589/600` | ✅ |
| `ADR-0002:38/57-59` | ✅ |
| `.github/workflows` 不存在（无 CI） | ✅ |

**未经接地（外部/运行期事实）**：opencv wheel 体积（子代理给 56.5MB，memo 给 34.8MB，本机无外网/锁文件无该包）、rapidocr 首次调用是否加载全部三模型、Linux/2 核 4G 的冷/热延迟、PP-OCRv6 许可证文本。均已在正文标注，不作为裁决依据。

---

## T/S 残差

- `openspec validate m4-local-ocr --strict` → **valid**（exit 0）；`check_decision_memo.py` → ok（exit 0）。
- 模版槽：proposal 的 Why/Success Metrics/Non-Goals/Compliance/假设/优先级齐；design 的 Goals/Non-Goals/决策/数据模型/NFR/安全/切片/Risks/Migration/Open Questions 齐；specs 的 ADDED/MODIFIED + 稳定 ID + Scenario 齐；tasks 的 R-ID 追溯基本齐。
- 缺口（已在正文列为 finding）：**序列图**（BASE-19/T，R-25）；**错误文案槽**（DX-02，R-20）；**配置键权威表**（R-32）。
- 位置偏差（不阻塞）：Open Questions 在 `design.md` 而非 `proposal.md`——内容存在，模板建议位置不同。
- `TG-25`（版本化多文件契约套件）未命中，BASE-29 scope-check 表 N/A；`TG-24` 外部计费 N/A（本地不产生厂商费用，云厂商计费不变）。

---

## 诚实边界

- 6 个派发镜均为**同模型 fresh-context**：隔离的是上下文，不是模型盲点；对抗镜的「refuted=true」默认没有跨模型第二意见兜底。
- 广审双镜与接地镜由主 session 亲做，带生成历史，存在自查偏置；本报告把「主 session 独有发现」与「子代理发现」分列，便于人复核。
- 子代理 findings 一律先视为「待接地」；主 session 抽查了合并池中 ≥1/3（实际亲验 28 处，覆盖全部高项与大部分中项），未逐条复核所有低项引文。
- 无机械引用核验脚本（lite 无此门），抽查是指令层纪律，**不声称机械保证**。
- 外部事实（wheel 体积、RapidOCR 行为、Linux 性能、许可证）本机无法核验，已标「未经接地」；不在裁决中当作已证实。
- `decision-memo.md` 是机械哈希件（`decision_hash` = 正文 sha256），本轮**未改写**；memo 中被评审修正的表述（C6 `types.ts:1`、C9 体积、D10 overview、接受边角「概率低」）以本报告的 R-08/R-23/R-13/R-15 与四件套的 `[spec-review-amendment]` 为准。
