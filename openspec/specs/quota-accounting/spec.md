# quota-accounting Specification

## Purpose
定义账号配额与 Key 限额的计数、重置与用量事件，确保免费额度被准确追踪，且缓存命中与失败不误扣额度。

## Requirements

### Requirement: R-QTA-01 成功请求记账
每次成功调用厂商 SHALL 使账号计数 +1、Key 当日计数 +1、写入一条 `usage_event`（`quota_used=1`）；缓存命中记 `quota_used=0`；失败请求记 `quota_used=0` 且 MUST NOT 扣账号配额。本地识别成功 MUST 记 `quota_used=0`、`account_id=NULL`、`provider='local'`，MUST NOT 增加任何账号计数；Key 的请求条数与 RPM 仍按实际请求记录。本地事件（含显式 `provider=local` 与 auto 兜底）MUST NOT 计入用户日限额（`daily_limit` 按 `quota_used` 合计）。`[spec-review-amendment R-15]` `[m4-local-ocr]`

#### Scenario: 成功扣一次
- **WHEN** 一次未命中的请求经百度成功返回
- **THEN** 账号与 Key 计数各 +1，`usage_event.quota_used=1`

#### Scenario: 缓存命中不扣
- **WHEN** 相同图片、语言与 provider 再次请求并命中缓存
- **THEN** `usage_event.cached=1`、`quota_used=0`，账号与 Key 计数不变

#### Scenario: 失败不扣
- **WHEN** 所有候选均失败
- **THEN** 账号配额计数不变，`usage_event.success=0`、`quota_used=0`

#### Scenario: 本地成功不扣厂商额度
- **WHEN** 请求由本地引擎成功识别
- **THEN** 写入 `provider='local'`、`account_id=NULL`、`quota_used=0` 的事件，账号计数不变，Key 的当日请求条数 +1

#### Scenario: 显式本地不消耗日限额
- **WHEN** 同一 Key 连续以 `provider=local` 成功识别多张图片
- **THEN** `usage_event.quota_used` 均为 0，`/v1/me` 的当日已用额度不增长；仅 RPM 与全局并发约束生效

### Requirement: R-QTA-02 账号配额上限
账号 SHALL 支持日/月/总量三种上限，任一为 `NULL` 表示不限；达到上限的账号 MUST 被排除并置为 `quota_exhausted`。

#### Scenario: 日额度耗尽
- **WHEN** 账号当日用量达到 `quota_daily`
- **THEN** 账号状态为 `quota_exhausted` 且不再被选中

#### Scenario: 未配置额度
- **WHEN** 账号三项配额均为 `NULL`
- **THEN** 账号不受配额限制，管理端提示「未配置额度」

### Requirement: R-QTA-03 周期重置与刷盘
日周期 SHALL 以 `Asia/Shanghai` 00:00 为界，月周期按 `reset_day` 当天 00:00；内存计数 MUST 每 2 秒批量 upsert 到 `quota_counters`，启动时 MUST 加载当前周期值。

#### Scenario: 日重置
- **WHEN** 时间跨过 `Asia/Shanghai` 00:00
- **THEN** 日 `period_key` 变化，账号日用量从 0 重新计数

#### Scenario: 崩溃丢计数上限
- **WHEN** 进程在两次刷盘之间崩溃
- **THEN** 重启后最多丢失 2 秒内的计数

### Requirement: R-QTA-04 Key 日限额与 RPM
Key 的 `daily_limit` SHALL 限制该 Key 当日消耗的配额单位（`quota_used` 合计），`rpm_limit` SHALL 限制请求速率；两者不影响账号池额度；超限分别返回 429 `QUOTA_EXCEEDED` 与 `RATE_LIMITED`。`[spec-review-amendment Q2]`

#### Scenario: Key 日限额
- **WHEN** Key 当日 `quota_used` 合计达到 `daily_limit`
- **THEN** 后续请求返回 429 `QUOTA_EXCEEDED`

#### Scenario: 缓存命中不占日限额
- **WHEN** 该 Key 当日仅发生缓存命中（`quota_used=0`）
- **THEN** `daily_limit` 计数不变，请求不被限流

#### Scenario: RPM 恢复
- **WHEN** 距上次限流已超过 1 分钟
- **THEN** 令牌桶恢复，请求可再次通过

### Requirement: R-QTA-05 用量事件内容
`usage_event` SHALL 记录 `request_id`、`user_id`、`api_key_id`、`account_id`、`provider`、`success`、`error_code`、`latency_ms`、`quota_used`、`cached`、`image_hash` 前 16 位与 `created_at`；MUST NOT 记录 OCR 原文或图片字节。

#### Scenario: 不落原文
- **WHEN** 查询 `usage_events` 表
- **THEN** 不存在 OCR 文本或图片二进制字段或内容
