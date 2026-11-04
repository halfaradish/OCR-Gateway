# local-ocr Specification

## Purpose
定义本地 OCR 引擎的可用性、进程隔离、识别输出与启停状态，使网关在云厂商不可用时仍能提供降级识别能力。

## ADDED Requirements

### Requirement: R-LOC-01 引擎与模型来源
系统 SHALL 通过可选依赖 extra `local` 提供 RapidOCR（onnxruntime CPU）引擎；模型 MUST 随安装包分发并在本地校验，识别路径 MUST NOT 发起网络请求。`language` 取值 `zh`/`en`/`auto` SHALL 全部使用内置模型。

#### Scenario: 离线识别
- **WHEN** 主机无外网且已安装 extra、模型随包存在
- **THEN** 本地识别成功返回文本，且不产生任何下载请求

#### Scenario: 依赖缺失
- **WHEN** 运行环境未安装 rapidocr 或 onnxruntime
- **THEN** 系统报告本地能力不可用，进程不因导入失败而崩溃，云端识别不受影响

### Requirement: R-LOC-02 进程隔离与并发
本地识别 SHALL 在独立进程池中执行，MUST NOT 阻塞事件循环；并发上限 SHALL 由环境变量控制，默认 1。子进程 MUST 以 `multiprocessing.get_context("spawn")` 创建，MUST NOT 继承父进程堆内存中的凭证；worker initializer MUST 清除 `MASTER_KEY`/`ADMIN_PASSWORD` 等敏感环境变量，worker MUST NOT 读取任何凭证。显式 local 请求 SHOULD 先获取本地并发门（大小 = 并发上限）再进入全局并发槽，使排队中的本地请求不占用全局槽。`[spec-review-amendment R-19/R-26/R-27]`

#### Scenario: 不阻塞事件循环
- **WHEN** 一个本地识别任务持续运行 2 秒
- **THEN** 同期健康检查与其他 OCR 请求仍能及时响应

#### Scenario: 并发生效
- **WHEN** `LOCAL_OCR_MAX_CONCURRENCY=2` 且两个本地请求同时到达
- **THEN** 两个任务并行执行，不互相排队等待

#### Scenario: 本地排队不挤占全局并发
- **WHEN** 8 个显式 local 请求同时到达而本地并发为 1，同时有云请求到达
- **THEN** 云请求仍能取得全局并发槽，不因本地排队被饿死

### Requirement: R-LOC-03 识别与输出归一化
本地引擎 SHALL 把结果归一化为 `text`（行以换行连接）与 `lines[{text, confidence}]`，置信度取 0–1；成功但无文本 MUST 视为成功，返回空 `text` 与 `EMPTY_TEXT` 警告。

#### Scenario: 中文截图
- **WHEN** 上传含中文与数字的清晰截图
- **THEN** 返回 200、`provider="local"`，`lines` 顺序与图片自上而下一致

#### Scenario: 无文本
- **WHEN** 图片不含可识别文字
- **THEN** 返回 200、`text=""`，`warnings` 含 `EMPTY_TEXT`

### Requirement: R-LOC-04 超时、取消与恢复
单次本地识别 SHALL 受剩余请求预算约束，上限由 `LOCAL_OCR_TIMEOUT_MS` 控制；超时 MUST 返回 504 `TIMEOUT`，MUST **终止（terminate/kill）旧池的 worker 进程**并重建（仅取消排队任务不够）；同一池中因重建被取消的其他请求 MUST 映射为 503/504 并写入 `usage_event`，MUST NOT 冒泡为 500；worker 崩溃 MUST 在下次请求时重建，MUST NOT 使后续本地请求永久失败。应用关闭时 shutdown 上限 20s，超时后 kill 残留 worker。`[spec-review-amendment R-03/R-12/R-29]`

#### Scenario: 单次超时
- **WHEN** 本地识别超过剩余预算
- **THEN** 返回 504 `TIMEOUT`，旧 worker 被终止、本地状态回到可重试态

#### Scenario: 超时不泄漏进程
- **WHEN** 连续 N 次本地识别超时
- **THEN** 子进程数不超过并发上限，不随超时次数增长

#### Scenario: 兄弟请求被重建取消
- **WHEN** 一个请求超时触发池重建，同一池中另有排队请求
- **THEN** 被取消的请求返回 503/504 并写入 `usage_event`，不返回 500

#### Scenario: worker 崩溃后恢复
- **WHEN** worker 进程异常退出
- **THEN** 下一次本地请求重建进程池并成功识别

### Requirement: R-LOC-05 开关与就绪状态
系统 SHALL 提供本地 OCR 开关，默认关闭；启用后 SHALL 建池并预热模型，状态按 `stopped`/`starting`/`ready`/`error`/`unavailable` 报告；关闭 MUST 停止进程池且不再执行本地识别。开关为持久化运行时设置：进程重启后 MUST 按持久化值恢复建池（`enabled=true` 时从 `starting` 开始）。依赖缺失 MUST 记为 `unavailable` 且不建池；模型加载失败 MUST 记为 `error`。`set_enabled` MUST 幂等（仅状态变化时执行）；warmup MUST 使用含文字的小图并断言返回非空，MUST 有超时；`error` 后的重试 MUST 有最小间隔与退避。状态快照 SHALL 含启用状态、依赖是否安装、运行状态、并发、超时与有效值、预留预算与有效值、模型信息、最近耗时、最近错误（脱敏）、下次重试等待与累计请求/兜底次数。`[spec-review-amendment R-05/R-09/R-10/R-11/R-18/R-28/R-31]`

#### Scenario: 启用并预热
- **WHEN** 管理员开启本地 OCR
- **THEN** 状态先为 `starting`，预热完成后变为 `ready` 并报告模型信息

#### Scenario: 重启后恢复
- **WHEN** 持久化设置为 `local_ocr_enabled=true` 且依赖已安装，进程重启
- **THEN** worker 自动建池并预热，状态从 `starting` 进入 `ready`，无需管理员再次保存

#### Scenario: 依赖缺失
- **WHEN** 运行环境未安装 rapidocr 或 onnxruntime
- **THEN** 状态为 `unavailable`，不建池；开启开关也不创建 worker；显式 local 仍返回 403

#### Scenario: 重复启用不重复建池
- **WHEN** 在 `ready` 或 `starting` 状态下再次保存设置（值仍为 true）
- **THEN** 不创建第二个进程池，状态不变

#### Scenario: 关闭后拒绝
- **WHEN** 管理员关闭本地 OCR 后请求 `provider=local`
- **THEN** 返回 403 `FORBIDDEN`，且不再创建 worker 进程

#### Scenario: 预热失败后退避
- **WHEN** warmup 因模型加载持续失败进入 `error`
- **THEN** 在最小重试间隔内不重复 spawn/加载，状态接口报告 `next_retry_in_ms`
