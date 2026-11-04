# quota-accounting Specification

## MODIFIED Requirements

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
