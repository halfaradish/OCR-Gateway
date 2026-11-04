---
schema_version: 1
change: m4-local-ocr
branch: feat/m4-local-ocr
generated_at: 2026-11-04T21:40:31+08:00
decision_hash: a140abd5fb4c
---

# 决策纪要 · m4-local-ocr

## 目标态

本地 OCR 成为可启用的兜底厂商：`provider=auto` 时云端不可用自动切本地，显式 `provider=local` 可用，管理端可开关并看到 worker 状态。

## 拍板决策

- **D1 范围：worker + 开关 + auto 兜底 + 显式 local + 状态；不做模型下载** — 依据：rapidocr 3.10.0 wheel 内置 det/rec/cls 三个 onnx 模型（实测解包），离线可用；**砍掉的候选**：下载/修复端点（几乎不会走的联网路径）、自定义模型目录（本机镜像源未必可达 ModelScope/HF，验收风险最高）、独立 local 镜像（运维矩阵翻倍）。
- **D2 镜像：发布镜像内置 local extra，开关默认关** — 依据：技术选型 §9「镜像内置 onnxruntime」；启用无需重构建。**砍掉的候选**：默认 slim 构建参数（启用要先重构建，易踩坑）、独立 local tag。
- **D3 记账：local 成功 `quota_used=0`、`account_id=NULL`、`provider='local'`** — 依据：本地不消耗厂商额度；用户日限额按 `quota_used` 合计，故不拦本地；RPM 仍由 KeyRateLimiter 生效。**砍掉的候选**：`quota_used=1`（与「配额=厂商额度」语义冲突，面板口径要改多处）、独立本地限额（M4 范围外）。
- **D4 预算：总预算上限保持 20s；auto+本地启用时云阶段为本地预留 5s；本地 timeout=`min(30s, 剩余)`；剩余 <1s 不再试本地** — 依据：实测冷启动约 2.4s、热调用 0.49s，5s 可覆盖冷池；不改 R-ADM-08 的 20001→400 断言。**砍掉的候选**：上限提到 60s（spec 面变大）、本地独立预算（违反 R-SCH-03 整请求 deadline）。
- **D5 兜底触发：仅 `auto` 且本地可用，云端 `NoCandidate`/`UpstreamFailed`/`DeadlineExceeded` 时** — 依据：技术选型 §9「云账号全部不可用时自动兜底」；`InputError` 表示请求本身被拒，不兜底；显式云厂不回退（既有语义）。
- **D6 模型与语言：只用 wheel 内置 PP-OCRv6 small，`zh`/`en`/`auto` 统一走内置模型，不联网下载其他语言** — 依据：内置模型实测中文+数字识别正确（score 0.975）；下载路径在本机镜像环境不可保证。
- **D7 隔离：`ProcessPoolExecutor`（spawn）+ 模块级 worker 函数，默认 1 并发（env 可调），启用时起池并预热，禁用时关闭** — 依据：RapidOCR/ONNX 会在 Python 侧做检测后处理，不能占事件循环；实测 `RapidOCR()` 构造不加载模型、首次调用才加载，故必须预热才能让「就绪」状态有意义。
- **D8 图片规范化：local 分支用原始 JPEG 字节上限（10MB）与最长边 10000，不做 base64 膨胀检查** — 依据：base64 膨胀是厂商传输开销，本地不需要；否则 9MB PNG 会被误判超限。
- **D9 配置面：runtime setting 仅 `local_ocr_enabled`；并发/超时/预留为 env（`LOCAL_OCR_MAX_CONCURRENCY` / `LOCAL_OCR_TIMEOUT_MS` / `LOCAL_OCR_RESERVE_MS`）** — 依据：并发变更要重建进程池，进设置页会引入热重建复杂度；M3 hand-off 只要求补真实开关与状态。
- **D10 可观测：新增 `/api/admin/local-ocr/status`；`/v1/providers` 增 `local` 条目；用量/日志标签增 `local`；管理端 overview 的 provider 列表不加 local** — 依据：local 无账号语义（`accounts`/`available_accounts` 无意义），总览按事件聚合的请求数已包含 local。
- **D11 失败语义：显式 `local` 未启用或依赖缺失 → 403 `FORBIDDEN`；运行失败 → 502 `PROVIDER_ERROR`；超时 → 504 `TIMEOUT`** — 依据：技术选型 §API「必须已启用，否则 403」。
- **D12 DB：新增迁移放宽 `ck_usage_provider` 至 `('baidu','tencent','auto','local')`；downgrade 先把 `provider='local'` 行映射为 `auto` 再恢复旧约束** — 依据：`models.py:137` 的 check 会拒绝 local 事件；`ck_accounts_provider` 不变（local 不建账号）。
- **D13 依赖与锁：`backend/pyproject.toml` 增 optional extra `local`；`uv.lock` 用镜像重解析后把源 URL 规范化回 `pypi.org` / `files.pythonhosted.org`** — 依据：ADR-0001 禁止把区域镜像写进跟踪的锁文件；实测重解析保持全部 53 个既有包版本不变、仅新增 15 包，且路径后缀与 PyPI 逐字一致。**砍掉的候选**：`backend/requirements-local.txt` 旁路（双真相源、`uv sync --extra local` 失效）。
- **D14 测试：默认单测注入 fake engine，不依赖 rapidocr；真实引擎测试标 `slow` 且缺依赖 skip；既有 provider 枚举断言同步更新** — 依据：`uv sync` 默认不装 extra，默认测试必须在无 rapidocr 环境通过。
- **D15 版本：升至 0.3.0，镜像 tag `0.3.0` + `latest`，`0.2.1` 保留为回滚锚点** — 依据：功能里程碑（M3 为 0.2.0，0.2.1 为补丁）。
- **D16 新增 ADR-0002，记录离线环境更新 `uv.lock` 的流程与边界** — 依据：人 2026-11-04 明确拍板；该步骤（镜像解析 + URL 规范化回 PyPI）不看文档无法猜到，且与 ADR-0001「镜像不写入锁文件」互补。

## 承重约束

- **C1 引擎可离线运行且模型随包分发** — 验证方式：清华镜像可见 `rapidocr 3.10.0`；解包 wheel 见 `rapidocr/models/PP-OCRv6_det_small.onnx`(9.9MB)、`PP-OCRv6_rec_small.onnx`(21MB)、`ch_ppocr_mobile_v2.0_cls_mobile.onnx`(0.6MB)；临时 venv 实测输出 `('OCR 网关本地兜底测试 12345',)`、score 0.975，日志 `File exists and is valid` 未联网。**证据锚**：`python -m pip index versions rapidocr --index-url <清华镜像>` 输出；wheel 内 `dist-info/METADATA` 与 `rapidocr/models/`。
- **C2 依赖可进 `python:3.12-slim`** — 验证方式：`uv lock` 解析出 `onnxruntime 1.31.1 cp312 manylinux_2_28_x86_64`；bookworm glibc 2.36 ≥ 2.28；实测 cv2 5.0.0 + numpy 2.5.4 + ort 1.31.1 组合可跑中文 OCR。**证据锚**：临时 `uv.lock` 的 wheel 列表；临时 venv 版本输出。
- **C3 冷启动/热调用耗时** — 验证方式：本机实测 import 1.23s + init 0.01s + 首次调用 1.12s（加载模型）+ 二次调用 0.49s（900×220 图）。**证据锚**：`run_ocr.py` 输出 `import_s=1.23 init_s=0.01 cold_call_s=1.12 warm_call_s=0.49`。
- **C4 调度器没有 local 通路** — 验证方式：`VALID_PROVIDERS` 仅 auto/baidu/tencent；`registry.candidates` 按账号过滤，local 无账号；`ScheduleResult.account_id` 为 `int`。**证据锚**：`backend/app/api/public.py:28`、`backend/app/core/registry.py:153-186`、`backend/app/core/scheduler.py:52-57`、`backend/app/api/public.py:299-302`。
- **C5 记账口径** — 验证方式：用户日限额按 `sum(UsageEvent.quota_used)` 判定；RPM 由独立令牌桶。**证据锚**：`backend/app/api/deps.py:199-208`、`backend/app/state.py:20-40`、`openspec/specs/quota-accounting/spec.md` R-QTA-01。
- **C6 provider 枚举权威源全集（口径一致性）** — 验证方式：全仓 grep `baidu`（不带 `--include`）+ 逐个消费面判「改/不改」。**证据锚**：`grep -rln baidu --exclude-dir=.git --exclude-dir=node_modules ...` 命中文件列表。判定：**改** = `api/public.py`（VALID_PROVIDERS、providers 列表）、`api/admin.py:967`（用量标签）、`providers/base.py:111`（PROVIDER_NAMES 增 local）、`utils/images.py`（local 限额分支）、`frontend/src/types.ts:1`、`lib/providers.ts`、`logs-page.tsx:162-163`、`usage-page` 筛选、`README.md:17`（移除「不做本地 OCR」）；**不改** = `schemas.py:35`（账号创建仅云厂）、`models.py:86` 的 `ck_accounts_provider`、`REQUIRED_CREDENTIALS`、`providers/templates.py`（配额模板）、`api/admin.py:781` overview 硬编码列表。
- **C7 构建链** — 验证方式：Dockerfile 用 `uv export --frozen --no-dev`，加 extra 必须 `--extra local`；`uv lock` 在本机（`UV_DEFAULT_INDEX`=清华）会把 1795 处源改写成镜像、pypi.org 归零；重解析后既有 53 包版本 0 变化、新增 15 包、URL 路径后缀逐字一致；规范化后 `uv lock --check --offline` 退出 0；`uv export --extra local` 含 rapidocr/onnxruntime。**证据锚**：`Dockerfile` 依赖层命令；临时目录 `m4-uvcheck` 的 diff 与 `uv lock --check --offline` 输出；`openspec/adr/0001-*.md`。
- **C8 设置热更新是单进程语义** — 验证方式：`_apply_settings` 在 commit 后替换 `state.runtime`；启动时 `load_runtime_settings` 合并 env 与 DB。**证据锚**：`backend/app/api/admin.py:1075-1093`、`backend/app/main.py:78-96`、`backend/app/runtime_settings.py:19-46`。
- **C9 镜像体积** — 验证方式：锁文件 Linux x86_64 wheel 求和 109.4MB 下载（onnxruntime 23.8 + opencv-python-headless 34.8 + numpy 16.7 + rapidocr 27.3 + 其余 6.8）。**证据锚**：临时 `uv.lock` 的 `size` 字段求和。

## 接受的边角

- **大图/弱 CPU 的本地识别可能超过 5s 预留而 TIMEOUT** — 概率中、影响可感知、完美成本高（异步任务或拉长预算）；**为何接受**：兜底路径允许失败，云端恢复即回到正常路径，且 TIMEOUT 有明确错误码。
- **启用后常驻一个 worker 进程**（模型 32MB + 运行时，内存估算 200–300MB）— 概率 100%（仅启用时）；影响内存；完美成本：懒加载会牺牲首请求延迟与「就绪」状态可见性；**为何接受**：默认关闭，启用是管理员显式动作。
- **本地请求不受用户日限额**（quota_used=0）— 概率低（仅云全挂时触发）、影响 CPU 占用、完美成本中（新增本地限额字段与口径）；**为何接受**：M4 范围外，记 todo。
- **OpenCV 5 是刚发布的大版本** — 已实测兼容；**为何接受**：不为低概率问题提前 pin，若线上复现再 pin `<5`。
- **模型许可证为 Apache-2.0，镜像再分发需保留归属说明** — **为何接受**：在 README 增加一段归属与许可证说明即可。
- **local 开关只在单进程生效** — 概率 0（v1 强制单 worker）；**为何接受**：既有单实例约束已覆盖。

## 三镜代价

命中 TG-23（模型来源、镜像形态、锁更新策略均有 ≥2 合理方案）。

- **系统镜**：新增 15 个传递依赖、约 +350MB 安装体积、一个常驻进程池；退化路径明确（关开关即回到纯云路径）。
- **用户镜**：云全挂时从 503 变为「可识别但质量低于云」；大图可能超时。
- **开发循环镜**：多一套可选依赖与进程池生命周期，测试需 fake 注入；默认开发环境不装 extra，日常负担小。
- **主次判定**：以「云全挂仍可用」的可用性为主，体积/内存为次。
