# Tasks

## 1. 依赖与本地引擎

- [x] 1.1 在 `backend/pyproject.toml` 增加 optional extra `local`（`rapidocr>=3.10,<4`、`onnxruntime>=1.20`），**先把项目版本升到 `0.3.0`**，再按 ADR-0002 用镜像重解析 `uv.lock` 并把源 URL 规范化回 PyPI；验证：`uv lock --check --offline` 退出 0、`uv export --frozen --no-dev --no-emit-project --extra local` 含 rapidocr/onnxruntime、`git diff backend/uv.lock` 只有新增包与源地址行 `[spec-review-amendment R-22]`
  - R-ID: R-LOC-01
- [x] 1.2 新增 `app/workers/local_ocr.py`（模块级引擎缓存 + `run_ocr`/`warmup`，输出归一化为 `text`/`lines[{text,confidence}]`，只收 bytes/语言，不导入 app.state/main；initializer 清除敏感 env）与 `app/core/local_engine.py`（状态机、**`multiprocessing.get_context("spawn").Pool` 可 terminate 池（不用 `ProcessPoolExecutor`）**、generation、幂等 `set_enabled`、warmup 含文字小图 + 超时、wait_for 超时、超时/崩溃重建、兄弟请求取消映射、warmup 失败退避、计数）；验证：单元测试覆盖状态迁移与 fake pool，超时不泄漏进程、兄弟请求不 500、重启恢复；真实引擎测试断言文本/置信度与空结果，标记 `slow`、未安装 extra 时 skip `[spec-review-amendment R-03/R-10/R-11/R-12/R-18/R-26/Q1-B]`
  - R-ID: R-LOC-02, R-LOC-03, R-LOC-04, R-LOC-05
- [x] 1.3 在 `app/config.py` 增加 `local_ocr_enabled=false`、`local_ocr_max_concurrency=1`、`local_ocr_timeout_ms=30000`、`local_ocr_reserve_ms=5000`、`local_ocr_min_budget_ms=1000`，并在 `state.py`/`main.py` 装配与关闭 `LocalEngine`：lifespan 按持久化 `local_ocr_enabled && installed` 调用 `set_enabled(true)`，关闭时 shutdown 上限 20s；本地专用 gate 接入公共路径；验证：重启后自动建池测试、启动/关闭 lifespan 无悬挂进程、配置默认值单测 `[spec-review-amendment R-05/R-19/R-29]`
  - R-ID: R-LOC-02, R-LOC-05

## 2. 公共路由与兜底

- [x] 2.1 `app/utils/images.py` 增加 local 分支（Pillow 校验 + EXIF 旋转 + 重编码 JPEG；上限作用于重编码后的 JPEG 字节 ≤ `MAX_UPLOAD_BYTES`、最长边 10000，不做 base64 膨胀检查）；验证：单测覆盖 9MB PNG 在 local 下通过、10000px 边界通过、超限仍 400 `[spec-review-amendment R-30]`
  - R-ID: R-API-03, R-LOC-01
- [x] 2.2 `Scheduler` 增加 local 分支与 `auto` 兜底：`reserve_eff = min(reserve, max(0, total − min_budget))`、云阶段截止 = deadline − reserve_eff、仅 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 触发、剩余不足 min_budget 放弃；`ScheduleResult.account_id` 改为可空；MODIFY R-SCH-03 的子 deadline 例外；验证：单测断言 1000/3000/5000/20000ms 边界、传给云适配器的 timeout 被扣减、InputError 不兜底、预算不足返回原错误 `[spec-review-amendment R-01/R-06]`
  - R-ID: R-SCH-03, R-SCH-05, R-SCH-07
- [x] 2.3 `app/api/public.py`：`VALID_PROVIDERS` 增 `local`、**provider 可用性门禁先于缓存读取**、显式 local 未启用的 403、local 失败 502/504 映射、`provider` 返回 local、**成功响应的 `quota.used` 与事件 `quota_used` 由实际 provider 派生（local→0）**、`/v1/providers` 增 local 条目；验证：API 测试覆盖 403/200/502/504、禁用后缓存不绕过、local 响应 quota=0、providers 不含账号字段 `[spec-review-amendment R-02/R-04]`
  - R-ID: R-API-01, R-API-05, R-API-06, R-CAC-01
- [x] 2.4 `local_ocr_enabled` 变化时清空缓存并在设置响应标记 `cache_cleared`；验证：开启/关闭开关后缓存归零，`GET /v1/providers` 的 local enabled 同步 `[spec-review-amendment R-02]`
  - R-ID: R-CAC-02, R-ADM-08

## 3. 记账与迁移

- [x] 3.1 新增 Alembic `0003` 迁移：batch 重建 `usage_events` 放宽 `ck_usage_provider` 至含 `local`，**同步修改 `app/models.py` 的 CheckConstraint**，downgrade 先用 `UPDATE ... SET provider='auto' WHERE provider='local'` 再恢复旧约束；迁移前评估行数（>100 万行走维护窗口）；验证：升级/降级往返测试（含一条 local 行）、`Base.metadata.create_all` 建库后插入 local 成功 `[spec-review-amendment R-07/R-35]`
  - R-ID: R-QTA-01
- [x] 3.2 本地成功路径写 `usage_event(provider='local', account_id=NULL, quota_used=0)`，不增加账号计数、Key 请求条数照记；**响应 `quota.used=0` 与事件同源**；验证：单测断言事件字段、账号计数不变、`/v1/me` 当日额度不增长、缓存命中的 local 事件为 0 `[spec-review-amendment R-04/R-15]`
  - R-ID: R-QTA-01, R-API-05
- [x] 3.3 用量聚合与日志查询的厂商标签增加「本地 RapidOCR」，前端 `PROVIDER_LABELS`、**日志与用量两处筛选下拉**同步；**账号域 `ProviderCode` 不扩 local，新增事件/展示用 provider 联合类型；`ProviderRow.code` 改用该展示联合（Q3 后 overview 含 local 行）**；验证：API 测试断言 group_by=provider 返回 local 行与 label、用量页 `provider=local` 过滤生效、前端 typecheck 通过 `[spec-review-amendment R-08/R-14]`
  - R-ID: R-ADM-06, R-API-06
- [x] 3.4 管理端 overview 的厂商行增加 `local`（`accounts=0`、`available_accounts=0`），今日请求总数与厂商行请求数之和对账；验证：含 local 事件的 overview API 测试断言行存在且总数=行和 `[spec-review-amendment R-13/Q3-A]`
  - R-ID: R-ADM-09

## 4. 管理端

- [x] 4.1 `runtime_settings.py` 增加 `local_ocr_enabled` 字段与 FIELD_RULES 文案（含 403/502/504 copy 表），`_apply_settings` 在 commit 后调用 `LocalEngine.set_enabled`（**幂等，仅值变化时执行**）并清缓存；验证：设置读写测试覆盖合法/非法/持久化/重复保存不重建池，开启后状态进入 starting `[spec-review-amendment R-10/R-20/R-33]`
  - R-ID: R-ADM-08, R-LOC-05
- [x] 4.2 新增 `GET /api/admin/local-ocr/status`（管理员鉴权、依赖缺失返回 `installed=false/state=unavailable`、`effective_timeout_ms`/`effective_reserve_ms`/`next_retry_in_ms`、`last_error` 脱敏）；验证：API 测试覆盖 200/401/依赖缺失/预热失败三态 `[spec-review-amendment R-09/R-28/R-31]`
  - R-ID: R-ADM-11
- [x] 4.3 设置页新增本地 OCR 卡片（开关 + 状态/模型/最近耗时/最近错误，依赖缺失禁用并说明）：**独立 useQuery + 同高骨架、三态、starting 轮询 ≤1s、只提交 dirty 字段、disabled 字段剔除、窄屏单列**，补 `types.ts`（账号/事件类型拆分）与轮询；验证：`pnpm typecheck` + `pnpm lint`，e2e 断言开关保存后状态从 starting 变 ready、状态接口慢时设置区仍可编辑 `[spec-review-amendment R-33]`
  - R-ID: R-PANEL-08, R-ADM-11

## 5. 镜像与文档

- [x] 5.1 Dockerfile 依赖层为 `uv export` 增加 `--extra local`；**版本源全部升 `0.3.0`**（`backend/pyproject.toml`、`backend/app/__init__.py`、`frontend/package.json`、`backend/uv.lock` project version、README 版本锚），compose tag 更新为 `0.3.0`/`latest`（`0.2.1` 不动）；**若基础镜像缺 `libgomp1` 等系统库，构建期安装**；验证：镜像构建成功、容器内 `python -c "import rapidocr, onnxruntime"` 通过、`/healthz` 为 ok、`readonly.version == 0.3.0` `[spec-review-amendment R-22/R-36]`
  - R-ID: R-DEP-11, R-DEP-10
- [x] 5.2 README 增加本地 OCR 说明、`LOCAL_OCR_*` 环境变量权威清单、模型 Apache-2.0 归属与镜像体积提示；**写明显式 `provider=local` 不计入日限额，仅受 Key RPM 与全局并发约束（M4 接受的边角）**；`.env.example` 补默认值；**逐处更新** README 的「不做本地 OCR」「provider 只接受 auto/baidu/tencent」「版本锚 0.2.1」「回滚到 0.1.0/0001」、`docs/tech-selection.md` 的按需下载/`/local-ocr/download`/`data/models/rapidocr`/`local_ocr_max_concurrency` 设置键；开发快速上手注明 `uv sync --project backend --extra local` 并补本地 OCR 上手的步骤数/耗时假设/TTHW 估算；验证：文档命令与默认值逐条对照 `.env.example` 与代码，`grep -rn "0.2.1\|不做本地 OCR\|local.*400\|/local-ocr/download"` 无残留 `[spec-review-amendment R-22/R-32/R-34/Q4-A]`
  - R-ID: R-DEP-11, R-LOC-01
- [x] 5.3 集成验收：停用全部云账号后 `provider=auto` 由本地返回 200；关闭开关后显式 local 返回 403；按 design 的回滚顺序演练 `alembic downgrade -1`（或 `7c1f0d2a9b31`，`--entrypoint` 覆盖）；**安装 extra 后跑 `pytest -m slow`**；**固定 N 次（≥30）基准脚本计算 p95**；**镜像冒烟脚本**：无外网启动 → 开启开关 → 轮询 status 到 ready；验证：验收记录含请求/响应、p95、状态接口快照与子进程数 `[spec-review-amendment R-16/R-17/R-21]`
  - R-ID: R-SCH-07, R-API-01, R-ADM-11, R-DEP-11

## 测试覆盖图

| 代码路径 | 测试类型 |
| --- | --- |
| `LocalEngine` 状态机 / generation / 超时重建 / 兄弟取消 | 单元（fake pool） |
| 池回收（超时后子进程数不增长） | 单元 + 集成（真实 spawn） |
| worker 真实识别 / 模型就绪 / 离线 | `slow` 集成（缺 extra 时 skip）+ 镜像冒烟 |
| 预算预留 / 兜底触发分支 / 1000–20000ms 边界 | 单元（fake clock/adapter） |
| `provider` 枚举 / 403 / 502 / 504 / providers 列表 | API（`httpx.ASGITransport`） |
| 缓存门禁 / 开关清缓存 / 禁用后不绕过 | API |
| 重启恢复 worker | lifespan 集成 |
| local 记账与迁移升降级 / `create_all` 插入 | 单元 + 迁移往返 |
| 设置读写 / 状态接口（unavailable/error/effective） | API |
| 面板三态 / 轮询 / 部分提交 / 窄屏 | 前端 typecheck/lint + e2e |
| 镜像内置 extra / 离线就绪 | 镜像冒烟脚本 |

## Workflow follow-up

- 项目评审要求满足后归档本 change 并复核归档结果。
