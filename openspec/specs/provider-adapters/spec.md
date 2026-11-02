# provider-adapters Specification

## Purpose
定义百度与腾讯两家云 OCR 的调用、签名、结果归一化与错误分类，使调度器与公共 API 不感知厂商差异。

## Requirements

### Requirement: R-ADP-01 百度通用文字识别适配
系统 SHALL 使用百度 `general_basic`：以 `client_credentials` 获取 access_token 并在过期前 5 分钟刷新缓存；调用时以 form-urlencoded 提交 base64 图片；把 `words_result[].words` 归一化为文本行。

#### Scenario: token 缓存复用
- **WHEN** 连续两次调用同一百度账号且 token 未临近过期
- **THEN** 只请求一次 token 端点，第二次复用缓存值

#### Scenario: 标准版无置信度
- **WHEN** 百度返回 `words_result` 且未包含概率
- **THEN** 适配器输出的 `lines[].confidence` 为 `null`

#### Scenario: token 鉴权失败
- **WHEN** 百度返回 access_token 无效或过期错误（110/111）
- **THEN** 适配器刷新 token 并重试一次；仍失败才抛出 `AUTH_FAILED` 分类 `[spec-review-amendment D7]`

### Requirement: R-ADP-02 腾讯通用印刷体识别适配
系统 SHALL 调用 `GeneralBasicOCR`（Version `2018-11-19`、域名 `ocr.tencentcloudapi.com`），使用 TC3-HMAC-SHA256 签名，并把 `TextDetections[]` 映射为文本行且保留 Confidence。

#### Scenario: 签名黄金用例
- **WHEN** 用官方示例的固定密钥与时间戳计算签名
- **THEN** 生成的 Authorization 与官方期望值一致

#### Scenario: 返回置信度
- **WHEN** 腾讯返回 `TextDetections` 且含 `Confidence`
- **THEN** `lines[].confidence` 为 0–100 的数值

### Requirement: R-ADP-03 结果归一化
系统 SHALL 把厂商结果统一为 `text`（各行以换行连接）与 `lines[{text, confidence}]`；厂商成功但无文本时 MUST 视为成功，返回空 `text` 与警告 `EMPTY_TEXT`。

#### Scenario: 多行结果
- **WHEN** 厂商返回 3 行识别结果
- **THEN** `text` 为 3 行以换行连接，`lines` 长度 3 且顺序一致

#### Scenario: 空结果
- **WHEN** 厂商成功但没有任何文本行
- **THEN** 返回 200，`text=""`，`warnings` 含 `EMPTY_TEXT`

### Requirement: R-ADP-04 厂商错误分类
适配器 SHALL 把厂商响应分类为 `AUTH_FAILED`、`QUOTA_EXCEEDED`、`RATE_LIMITED`、`TIMEOUT`、`PROVIDER_ERROR` 或 `InputError`；分类 MUST 依据厂商文档错误码与 HTTP 状态，并由黄金用例覆盖；码值映射表见 `design.md` 附录（含官方 URL 与核对日期）。`[spec-review-amendment D31]`

#### Scenario: 配额耗尽
- **WHEN** 厂商返回配额或余额不足错误码
- **THEN** 适配器抛出 `QUOTA_EXCEEDED`，调度器把账号置为 `quota_exhausted`

#### Scenario: 输入错误不切换
- **WHEN** 厂商返回图片格式或参数错误
- **THEN** 适配器抛出 `InputError`，公共 API 返回 400 且不尝试其他账号

#### Scenario: 签名过期不归鉴权失败
- **WHEN** 腾讯返回 `AuthFailure.SignatureExpire`
- **THEN** 适配器抛出 `PROVIDER_ERROR`，不抛出 `AUTH_FAILED` `[spec-review-amendment Q4]`

### Requirement: R-ADP-05 单账号测活
系统 SHALL 支持管理员对指定账号测活：用内置样图或上传图片调用适配器，返回文本、延迟与分类结果；测活 MUST NOT 写入用量事件、扣配额或改变账号状态。

#### Scenario: 测活成功
- **WHEN** 管理员对可用百度账号发起测活
- **THEN** 返回 `ok=true`、识别文本与延迟

#### Scenario: 测活失败不改状态
- **WHEN** 管理员对超时账号测活
- **THEN** 返回 `ok=false` 与错误分类，账号状态与配额计数不变
