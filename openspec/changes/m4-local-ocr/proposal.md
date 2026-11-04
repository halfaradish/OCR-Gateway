# Proposal: m4-local-ocr

## Why

当前网关的可用性完全依赖百度/腾讯云：两家同时故障、额度耗尽或全部账号进入冷却时，`provider=auto` 只能返回 503。M4 用随镜像分发的本地 RapidOCR 引擎提供降级路径，让「云全挂」从不可用变为「可识别但质量低于云」。

## What Changes

- 新增本地 OCR 能力：RapidOCR（onnxruntime CPU）运行在独立进程池 worker 中，模型随 wheel 内置，不联网下载；可选依赖 extra `local`。
- 新增运行时设置 `local_ocr_enabled`（默认 `false`，热更新）：关闭时 worker 不启动、显式 `provider=local` 返回 403。
- `provider=auto` 在云端无可用账号或全部尝试失败时自动兜底本地；云阶段为本地预留 5s 预算；显式云厂商仍不回退。
- 显式 `provider=local` 在已启用时直接走本地，不经过云账号/配额。
- 记账口径：本地成功 `quota_used=0`、`account_id=NULL`、`provider='local'`；Key 的 RPM 仍生效。
- 新增 Alembic 迁移放宽 `usage_event.provider` 检查约束以接受 `local`（downgrade 把 local 行映射回 `auto`）。
- 管理端：`GET /api/admin/local-ocr/status` 返回 worker 状态/模型/最近耗时；设置页新增本地 OCR 卡片。
- `/v1/providers` 增加 `local` 条目；用量与日志的厂商标签增加「本地 RapidOCR」。
- 发布镜像内置 local extra（构建仍支持索引参数化）；版本升至 `0.3.0`，`0.2.1` 保留为回滚锚点。
- 锁文件更新遵循新增的 ADR-0002（镜像解析后把源 URL 规范化回 PyPI）。

## Success Metrics

- **云全挂兜底成功率** — 基准 0%（当前返回 503）→ 目标：本地已启用且 worker 就绪时，最长边 ≤2000px 的截图 ≥95% 返回 200 且 `provider="local"`；504/5xx 单独计失败并留样（`[spec-review-amendment R-16]`）→ 度量：集成测试（停用/移除全部云账号）+ 手工验收。
- **本地识别延迟** — 基准 无（未实现）→ 目标：热调用 p95 ≤3s（本机 900×220 实测 0.49s）→ 度量：固定 N 次（≥30）基准脚本计算 p95 + 镜像冒烟；不使用 `last_latency_ms` 单样本。
- **镜像启动不回归** — 目标：0.3.0 镜像在无外网环境启动，开启开关后 worker ≤10s 进入 `ready`（目标 ≤5s）→ 度量：镜像冒烟脚本读 `/api/admin/local-ocr/status`。

## Non-Goals

- **不做模型下载/自定义模型目录/多语言模型** — 可证伪假设：rapidocr 3.10 内置 PP-OCRv6 small 对中文截图与中英混排足够好（本机实测 score 0.975）；若真实业务截图准确率明显不足，再另开 change 引入语言模型下载。
- **不做本地独立配额/限流** — 可证伪假设：自动兜底只在云全挂时触发，显式 `provider=local` 仅受 Key RPM 与全局并发约束（默认本地并发 1）；若观测到本地 CPU 被持续打满，再引入本地限额（`[spec-review-amendment R-15]`）。
- **不做本地账号管理/多并发调优/GPU** — 可证伪假设：兜底场景不需要与云同等吞吐；并发保留 env 旋钮即可。
- **不做多实例开关广播** — 可证伪假设：v1 强制单 worker（R-DEP-06），不存在多进程读到不同开关的情况。
- **不做批量接口/PDF/结构化识别** — 既有 Non-Goals，不在 M4 扩大。

## Compliance

- **ADR-0001**：镜像构建不读锁文件里的下载地址，仍用 `uv export` + `pip install --index-url`；**ADR-0002**：离线更新锁文件后必须把源 URL 规范化回 PyPI。
- **R-DEP-06** 单实例约束、**R-DEP-08** 非 root：本地 worker 与进程池不改运行身份。
- **凭证约定**：任何文档/注释不写本机私有凭证文档的具体路径或文件名。
- **模型许可证**：PaddleOCR 模型为 Apache-2.0，镜像与 README 保留归属说明。
- **安全**：本地 worker 不访问网络；输入图片沿用既有 Pillow 校验与像素上限。

## 需求优先级

- **P0（M4 验收必需）**：引擎与 worker 可用（R-LOC-01/02/04）、`auto` 兜底与预算预留（R-SCH-07）、`provider=local` 与 403（R-API-01）、本地记账与 `usage_event` 迁移（R-QTA-01）、开关热更新（R-ADM-08）。
- **P1（可观测与面板）**：状态接口（R-ADM-11）、`/v1/providers` local 条目（R-API-06）、设置页卡片（R-PANEL-08）、用量/日志标签（R-ADM-06）。
- **P2（交付面）**：镜像内置 extra 与版本锚（R-DEP-11/R-DEP-10）、README/环境变量/许可证说明。P2 未完成不阻塞兜底能力本身，但阻塞发布。

## 假设

- **A1** 内置 PP-OCRv6 small 对业务截图够用（可证伪：抽样准确率显著低于云厂商）→ 触发另开 change 引入语言/更大模型。
- **A2** 兜底流量不会持续打满 CPU（本地只在云全挂时承接，默认并发 1）→ 触发时再引入本地限额。
- **A3** 目标部署机（2 核 4G 下限）热调用可满足 5s 预留（本机实测 0.49s）→ verify 在服务器补测。
- **A4** 可达镜像提供 rapidocr/onnxruntime 的 cp312 manylinux wheel（已用 `uv lock` 解析验证）。

## Capabilities

### New Capabilities

- `local-ocr`: 本地识别引擎、worker 进程池生命周期、模型来源与就绪状态、输出归一化与失败语义。

### Modified Capabilities

- `ocr-api`: `provider` 枚举与 local 语义、local 成功/失败响应与 `quota.used`、`/v1/providers` 条目。
- `account-pool-scheduling`: `auto` 兜底本地的触发条件与云阶段预算预留。
- `quota-accounting`: 本地事件的记账口径（quota_used=0、account_id 为空）。
- `result-cache`: provider 可用性门禁先于缓存命中；本地开关切换时清缓存（`[spec-review-amendment R-02]`）。
- `admin-api`: 运行时设置新增 `local_ocr_enabled`；新增 local OCR 状态端点。
- `admin-panel`: 设置页本地 OCR 开关与状态展示。
- `deployment`: 运行镜像内置 local extra；新版本 tag 与回滚锚点。

## Impact

- **代码**：`backend/app/workers/local_ocr.py`（新）、`core/local_engine.py`（新）、`core/scheduler.py`、`core/cache.py`（门禁/清理）、`api/public.py`、`api/admin.py`、`utils/images.py`、`runtime_settings.py`、`config.py`、`main.py`、`state.py`、`models.py`、`providers/base.py`；前端 `settings-page.tsx`、`usage-page.tsx`、`logs-page.tsx`、`types.ts`、`lib/providers.ts`。
- **API**：`/v1/ocr/image`（provider 语义）、`/v1/providers`、`/api/admin/settings`、`/api/admin/local-ocr/status`。
- **DB**：新增迁移 `0003`（放宽 `ck_usage_provider`）。
- **依赖**：`rapidocr>=3.10,<4`、`onnxruntime>=1.20`（optional extra `local`）；`uv.lock` 重新解析。
- **部署**：镜像增加约 110MB 下载/约 350MB 安装体积；新增 `LOCAL_OCR_*` 环境变量；`.env.example`、README 更新。
