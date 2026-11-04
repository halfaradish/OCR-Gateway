# Tasks

## 1. 依赖与本地引擎

- [ ] 1.1 在 `backend/pyproject.toml` 增加 optional extra `local`（`rapidocr>=3.10,<4`、`onnxruntime>=1.20`），按 ADR-0002 用镜像重解析 `uv.lock` 并把源 URL 规范化回 PyPI；验证：`uv lock --check --offline` 退出 0、`uv export --frozen --no-dev --no-emit-project --extra local` 含 rapidocr/onnxruntime、`git diff backend/uv.lock` 只有新增包与源地址行
  - R-ID: R-LOC-01
- [ ] 1.2 新增 `app/workers/local_ocr.py`（模块级引擎缓存 + `run_ocr`/`warmup`，输出归一化为 `text`/`lines[{text,confidence}]`，只收 bytes/语言，不导入 app.state/main）与 `app/core/local_engine.py`（状态机、spawn 进程池、warmup、wait_for 超时、超时/崩溃重建、计数）；验证：单元测试覆盖状态迁移与 fake executor，真实引擎测试断言文本/置信度与空结果，标记 `slow`、未安装 extra 时 skip
  - R-ID: R-LOC-02, R-LOC-03, R-LOC-04, R-LOC-05
- [ ] 1.3 在 `app/config.py` 增加 `local_ocr_enabled=false`、`local_ocr_max_concurrency=1`、`local_ocr_timeout_ms=30000`、`local_ocr_reserve_ms=5000`、`local_ocr_min_budget_ms=1000`，并在 `state.py`/`main.py` 装配与关闭 `LocalEngine`；验证：启动/关闭 lifespan 测试无悬挂进程，配置默认值有单测
  - R-ID: R-LOC-02, R-LOC-05

## 2. 公共路由与兜底

- [ ] 2.1 `app/utils/images.py` 增加 local 分支（原始 JPEG 字节上限 10MB、最长边 10000，不做 base64 膨胀检查）；验证：单测覆盖 9MB PNG 在 local 下通过、超限仍 400
  - R-ID: R-API-03, R-LOC-01
- [ ] 2.2 `Scheduler` 增加 local 分支与 `auto` 兜底：云阶段截止 = deadline − reserve、仅 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 触发、剩余不足 min_budget 放弃；`ScheduleResult.account_id` 改为可空；验证：单测断言传给云适配器的 timeout 被扣减、InputError 不兜底、预算不足返回原错误
  - R-ID: R-SCH-05, R-SCH-07
- [ ] 2.3 `app/api/public.py`：`VALID_PROVIDERS` 增 `local`、显式 local 未启用的 403、local 失败 502/504 映射、`provider` 返回 local、`/v1/providers` 增 local 条目；验证：API 测试覆盖 403/200/502/504 与 providers 不含账号字段
  - R-ID: R-API-01, R-API-05, R-API-06

## 3. 记账与迁移

- [ ] 3.1 新增 Alembic `0003` 迁移：batch 重建 `usage_events` 放宽 `ck_usage_provider` 至含 `local`，downgrade 先把 local 行映射为 auto 再恢复旧约束；验证：升级/降级往返测试（含一条 local 行）通过
  - R-ID: R-QTA-01
- [ ] 3.2 本地成功路径写 `usage_event(provider='local', account_id=NULL, quota_used=0)`，不增加账号计数、Key 请求条数照记；验证：单测断言事件字段与账号计数不变、缓存命中的 local 事件为 0
  - R-ID: R-QTA-01
- [ ] 3.3 用量聚合与日志查询的厂商标签增加「本地 RapidOCR」，前端 `PROVIDER_LABELS` 与日志筛选下拉同步；验证：API 测试断言 group_by=provider 返回 local 行与 label，前端类型检查通过
  - R-ID: R-ADM-06, R-API-06

## 4. 管理端

- [ ] 4.1 `runtime_settings.py` 增加 `local_ocr_enabled` 字段与 FIELD_RULES 文案，`_apply_settings` 在 commit 后调用 `LocalEngine.set_enabled`；验证：设置读写测试覆盖合法/非法/持久化，开启后状态进入 starting
  - R-ID: R-ADM-08, R-LOC-05
- [ ] 4.2 新增 `GET /api/admin/local-ocr/status`（管理员鉴权、依赖缺失返回 installed=false/state=unavailable）；验证：API 测试覆盖 200/401/依赖缺失三态
  - R-ID: R-ADM-11
- [ ] 4.3 设置页新增本地 OCR 卡片（开关 + 状态/模型/最近耗时/最近错误，依赖缺失禁用并说明），补 `types.ts` 与轮询；验证：`pnpm typecheck` + `pnpm lint`，e2e 断言开关保存后状态从 starting 变 ready
  - R-ID: R-PANEL-08, R-ADM-11

## 5. 镜像与文档

- [ ] 5.1 Dockerfile 依赖层为 `uv export` 增加 `--extra local`，版本升 `0.3.0`，compose tag 更新为 `0.3.0`/`latest`（`0.2.1` 不动）；验证：镜像构建成功且容器内 `python -c "import rapidocr, onnxruntime"` 通过，`/healthz` 为 ok
  - R-ID: R-DEP-11, R-DEP-10
- [ ] 5.2 README 增加本地 OCR 说明、`LOCAL_OCR_*` 环境变量、模型 Apache-2.0 归属与镜像体积提示；`.env.example` 补默认值；移除 README「不做本地 OCR」表述；更新 `docs/tech-selection.md` §9/§16 的本地 OCR 描述（模型随包内置、下载流程取消）；验证：文档中的命令与默认值逐条对照 `.env.example` 与代码
  - R-ID: R-DEP-11, R-LOC-01
- [ ] 5.3 集成验收：停用全部云账号后 `provider=auto` 由本地返回 200；关闭开关后显式 local 返回 403；按 design 的回滚顺序演练 `alembic downgrade 0002`；验证：验收记录含请求/响应与状态接口快照
  - R-ID: R-SCH-07, R-API-01, R-ADM-11

## 测试覆盖图

| 代码路径 | 测试类型 |
| --- | --- |
| `LocalEngine` 状态机 / 超时重建 | 单元（fake executor） |
| worker 真实识别 / 模型就绪 | `slow` 集成（缺 extra 时 skip） |
| 预算预留 / 兜底触发分支 | 单元（fake clock/adapter） |
| `provider` 枚举 / 403 / 502 / 504 / providers 列表 | API（`httpx.ASGITransport`） |
| local 记账与迁移升降级 | 单元 + 迁移往返 |
| 设置读写 / 状态接口 | API |
| 面板开关与状态展示 | 前端 typecheck/lint + e2e |
| 镜像内置 extra / 离线启动 | 镜像冒烟 |

## Workflow follow-up

- 项目评审要求满足后归档本 change 并复核归档结果。
