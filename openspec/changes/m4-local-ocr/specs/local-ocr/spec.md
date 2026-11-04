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
本地识别 SHALL 在独立进程池中执行，MUST NOT 阻塞事件循环；并发上限 SHALL 由环境变量控制，默认 1。子进程 MUST 以 spawn 方式创建，MUST NOT 继承父进程内存中的凭证。

#### Scenario: 不阻塞事件循环
- **WHEN** 一个本地识别任务持续运行 2 秒
- **THEN** 同期健康检查与其他 OCR 请求仍能及时响应

#### Scenario: 并发生效
- **WHEN** `LOCAL_OCR_MAX_CONCURRENCY=2` 且两个本地请求同时到达
- **THEN** 两个任务并行执行，不互相排队等待

### Requirement: R-LOC-03 识别与输出归一化
本地引擎 SHALL 把结果归一化为 `text`（行以换行连接）与 `lines[{text, confidence}]`，置信度取 0–1；成功但无文本 MUST 视为成功，返回空 `text` 与 `EMPTY_TEXT` 警告。

#### Scenario: 中文截图
- **WHEN** 上传含中文与数字的清晰截图
- **THEN** 返回 200、`provider="local"`，`lines` 顺序与图片自上而下一致

#### Scenario: 无文本
- **WHEN** 图片不含可识别文字
- **THEN** 返回 200、`text=""`，`warnings` 含 `EMPTY_TEXT`

### Requirement: R-LOC-04 超时、取消与恢复
单次本地识别 SHALL 受剩余请求预算约束，上限由 `LOCAL_OCR_TIMEOUT_MS` 控制；超时 MUST 返回 504 `TIMEOUT`，MUST 取消排队任务并重建进程池；worker 崩溃 MUST 在下次请求时重建，MUST NOT 使后续本地请求永久失败。

#### Scenario: 单次超时
- **WHEN** 本地识别超过剩余预算
- **THEN** 返回 504 `TIMEOUT`，本地状态回到可重试态

#### Scenario: worker 崩溃后恢复
- **WHEN** worker 进程异常退出
- **THEN** 下一次本地请求重建进程池并成功识别

### Requirement: R-LOC-05 开关与就绪状态
系统 SHALL 提供本地 OCR 开关，默认关闭；启用后 SHALL 建池并预热模型，状态按 `stopped`/`starting`/`ready`/`error`/`unavailable` 报告；关闭 MUST 停止进程池且不再执行本地识别。状态快照 SHALL 含启用状态、依赖是否安装、运行状态、并发、超时、模型信息、最近耗时、最近错误与累计请求/兜底次数。

#### Scenario: 启用并预热
- **WHEN** 管理员开启本地 OCR
- **THEN** 状态先为 `starting`，预热完成后变为 `ready` 并报告模型信息

#### Scenario: 关闭后拒绝
- **WHEN** 管理员关闭本地 OCR 后请求 `provider=local`
- **THEN** 返回 403 `FORBIDDEN`，且不再创建 worker 进程
