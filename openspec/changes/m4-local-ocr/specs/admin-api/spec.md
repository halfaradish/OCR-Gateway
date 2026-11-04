# admin-api Specification

## MODIFIED Requirements

### Requirement: R-ADM-08 运行时设置读写
管理员 SHALL 能读取与部分更新运行时设置：缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时、本地 OCR 开关；更新 MUST 校验类型与范围，显式 `null` MUST 返回 400，校验错误 MUST 含字段名；提交成功后 MUST 对后续请求生效；缓存参数变化 MUST 清空现有缓存并在响应中标记；只读项 MUST 包含鉴权状态、版本、上传限制、并发上限、会话时长与面板产物状态。`[spec-review-amendment R-05/R-15]` `[m4-local-ocr]`

#### Scenario: 读取设置
- **WHEN** 调用 `GET /api/admin/settings`
- **THEN** 返回可编辑项与只读项，值为当前生效值

#### Scenario: 部分更新
- **WHEN** 只提交 `cache_ttl_seconds`
- **THEN** 其余设置保持不变，重启后新值仍生效

#### Scenario: 非法值
- **WHEN** 提交超出范围的缓存 TTL 或非整数
- **THEN** 返回 400 `BAD_REQUEST`，`error.fields` 含字段名，设置与运行时均不变

#### Scenario: 显式 null
- **WHEN** 提交 `{"cache_ttl_seconds": null}`
- **THEN** 返回 400 `BAD_REQUEST`，不把 null 当作未提供

#### Scenario: 容量与预算上限
- **WHEN** 提交 `cache_max_entries=2001` 或 `request_deadline_ms=20001`
- **THEN** 返回 400 `BAD_REQUEST`

#### Scenario: 未知键
- **WHEN** 提交未被定义的设置键
- **THEN** 返回 400 `BAD_REQUEST`，不静默忽略

#### Scenario: 缓存参数变更
- **WHEN** 修改缓存开关、TTL 或容量并保存
- **THEN** 响应标记缓存已清空，缓存条目归零

#### Scenario: 请求预算生效
- **WHEN** 把请求总预算改为更小值并保存
- **THEN** 后续 OCR 请求使用新的总预算

#### Scenario: 账号默认超时生效
- **WHEN** 修改账号默认超时后创建未显式指定超时的账号
- **THEN** 新账号使用新的默认超时

#### Scenario: 本地开关生效
- **WHEN** 提交 `{"local_ocr_enabled": true}` 并保存
- **THEN** 响应成功，后续 `provider=local` 可用，状态接口从 `starting` 变为 `ready`

#### Scenario: 本地开关类型错误
- **WHEN** 提交 `{"local_ocr_enabled": "yes"}`
- **THEN** 返回 400 `BAD_REQUEST`，`error.fields[].field="local_ocr_enabled"`，开关不变

## ADDED Requirements

### Requirement: R-ADM-11 本地 OCR 状态查询
管理员 SHALL 能查询本地 OCR 状态：启用状态、依赖是否安装、运行状态（`stopped`/`starting`/`ready`/`error`/`unavailable`）、并发、超时、预留预算、模型信息、最近耗时、最近错误、累计请求与兜底次数。接口 MUST 需要管理员会话，MUST NOT 返回模型文件绝对路径、凭证或识别原文。`[m4-local-ocr]`

#### Scenario: 状态可查
- **WHEN** 管理员请求 `GET /api/admin/local-ocr/status`
- **THEN** 返回上述字段；`state` 与当前 worker 生命周期一致

#### Scenario: 依赖缺失
- **WHEN** 运行环境未安装 rapidocr 或 onnxruntime
- **THEN** 返回 `installed=false`、`state="unavailable"`，不抛 500；`/v1/providers` 的 local `enabled` 为 false

#### Scenario: 未授权
- **WHEN** 未携带管理员会话请求状态接口
- **THEN** 返回 401 `UNAUTHORIZED`
