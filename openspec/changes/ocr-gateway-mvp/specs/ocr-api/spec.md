# Spec Delta

## Purpose

为团队成员提供统一、强制鉴权的单张图片 OCR HTTP 契约，屏蔽百度/腾讯差异，返回稳定的 text + lines 结构。

## ADDED Requirements

### Requirement: R-API-01 单张图片识别
系统 SHALL 接受 multipart 文件或 JSON base64 二选一，将图片交给调度器识别并返回归一化结果；同一请求同时提供两种输入 MUST 返回 400。`language` 只接受 `zh`（默认）/`en`/`auto`，其它值 MUST 返回 400，并按厂商映射表传给适配器。`[spec-review-amendment D4]`

#### Scenario: multipart 识别成功
- **WHEN** 客户端携带 Bearer Key 上传 `file` 且未指定 provider
- **THEN** 系统返回 200，`text` 与 `lines` 存在，`provider` 为实际使用的厂商

#### Scenario: base64 识别成功
- **WHEN** 客户端发送 `{"image_base64":"..."}` 且未指定 provider
- **THEN** 系统返回 200，响应含 `request_id`、`latency_ms`、`quota.used`

#### Scenario: 两种输入同时提供
- **WHEN** 请求同时提供 `file` 与 `image_base64`（或 `image_base64` 与 `image_url`）
- **THEN** 系统返回 400 `BAD_REQUEST`

#### Scenario: 不支持的 provider
- **WHEN** 请求的 `provider` 不在 `auto`、`baidu`、`tencent` 之内（如 `local`）
- **THEN** 系统返回 400 `BAD_REQUEST`，不调用任何厂商

#### Scenario: 不支持的语言
- **WHEN** 请求的 `language` 不在 `zh`、`en`、`auto` 之内
- **THEN** 系统返回 400 `BAD_REQUEST`，不调用任何厂商

### Requirement: R-API-02 URL 图片输入
系统 SHALL 支持 `image_url` 输入，并 MUST 在拉取前与每次重定向后校验目标地址：仅 http/https，拒绝私网/回环/链路本地/云元数据地址，最多 3 次重定向，10s 超时、10MB 上限。

#### Scenario: 合法公网 URL
- **WHEN** 客户端提交公网可访问的 https 图片 URL
- **THEN** 系统拉取并识别，返回 200

#### Scenario: 私网地址被拒
- **WHEN** `image_url` 解析到 127.0.0.1、10.0.0.0/8 或 169.254.169.254 等受限地址
- **THEN** 系统返回 400 `BAD_REQUEST`，且不发起出站请求

#### Scenario: 超限或重定向过多
- **WHEN** 拉取超过 10s、内容超过 10MB 或重定向超过 3 次
- **THEN** 系统返回 400 `BAD_REQUEST`

### Requirement: R-API-03 图片规范化
系统 SHALL 用 Pillow 校验真实图片内容并只接受 JPEG/PNG/BMP；入口上限 10MB（按解码后的图片字节数）；MUST 在解码前拒绝 >40M 像素或最长边 >10000 的图片；MUST 按 EXIF 方向旋转，并按厂商限制（百度：base64+urlencode 后 ≤8MB、最短边 ≥15px、最长边 ≤4096px）等比缩放/转 JPEG，仍超限返回 400。`[spec-review-amendment D8/D10/D11]`

#### Scenario: 超限自动缩放
- **WHEN** 上传 9MB 的 PNG 且 `provider=auto`
- **THEN** 系统缩放到百度限制（base64+urlencode 后 ≤8MB、最短边 ≥15px、最长边 ≤4096px）后提交厂商并返回 200

#### Scenario: 伪造图片
- **WHEN** 上传内容无法被 Pillow 解码（即使扩展名为 .png）
- **THEN** 系统返回 400 `BAD_REQUEST`

#### Scenario: 像素炸弹
- **WHEN** 上传的图片声明像素数超过 40M（如 12000×12000）
- **THEN** 系统在解码前返回 400 `BAD_REQUEST`，不分配完整位图

#### Scenario: 超过入口上限
- **WHEN** 请求体超过 10MB
- **THEN** 系统返回 400 `BAD_REQUEST`，不调用厂商

### Requirement: R-API-04 API Key 鉴权与限额
公共 API SHALL 强制 `Authorization: Bearer <gateway key>`；缺失、无效、Key 被禁用或所属成员被禁用 MUST 返回 401；Key 日限额与 RPM 超限分别返回 429 `QUOTA_EXCEEDED` 与 `RATE_LIMITED`。

#### Scenario: 缺少 Key
- **WHEN** 请求未携带 Authorization
- **THEN** 返回 401 `UNAUTHORIZED`

#### Scenario: 日限额耗尽
- **WHEN** 该 Key 当日成功消耗达到 `daily_limit`
- **THEN** 返回 429 `QUOTA_EXCEEDED`

#### Scenario: RPM 超限
- **WHEN** 该 Key 在 1 分钟内请求数超过 `rpm_limit`
- **THEN** 返回 429 `RATE_LIMITED`

### Requirement: R-API-05 统一响应与错误码
成功响应 SHALL 含 `request_id`、`provider`、`text`、`lines[{text, confidence}]`、`latency_ms`、`cached`、`quota{unit,used}`、`warnings`；失败响应 SHALL 为 `{"request_id","error":{"code","message"}}` 并遵守约定 HTTP 状态。网关全局并发饱和且等待超过剩余预算时 SHALL 返回 503 `PROVIDER_UNAVAILABLE`（message 标注 gateway at capacity）。`[spec-review-amendment Q5]`

#### Scenario: confidence 可空
- **WHEN** 实际厂商为百度标准版
- **THEN** `lines[].confidence` 为 `null`，响应仍为 200

#### Scenario: 全部候选不可用
- **WHEN** `auto` 请求没有任何可用账号
- **THEN** 返回 503 `PROVIDER_UNAVAILABLE`

#### Scenario: 厂商持续异常
- **WHEN** 所有候选都返回 5xx/协议错误，且预算未耗尽
- **THEN** 返回 502 `PROVIDER_ERROR` `[spec-review-amendment D5]`

#### Scenario: 总预算耗尽
- **WHEN** 尝试所有候选后超过 `REQUEST_DEADLINE_MS`
- **THEN** 返回 504 `TIMEOUT`

#### Scenario: 网关并发饱和
- **WHEN** 全局并发达到 `MAX_CONCURRENT_REQUESTS` 且等待超过剩余预算
- **THEN** 返回 503 `PROVIDER_UNAVAILABLE`，message 标注 gateway at capacity

### Requirement: R-API-06 服务元数据与健康检查
系统 SHALL 提供 `GET /v1/providers`（厂商与可用账号数，不含凭证）、`GET /v1/me`（当前 Key 的今日用量与限额）、`GET /healthz`（数据库健康）。

#### Scenario: providers 不泄露凭证
- **WHEN** 已配置 2 个百度账号与 1 个腾讯账号
- **THEN** `/v1/providers` 返回 `available_accounts` 计数，响应中无凭证字段

#### Scenario: 数据库不可用
- **WHEN** `/healthz` 的数据库检查在 1s 内失败
- **THEN** 返回 503，`db` 字段为 `error`
