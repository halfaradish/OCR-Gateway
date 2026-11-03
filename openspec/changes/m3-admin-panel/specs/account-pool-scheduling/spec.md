# Spec Delta

## MODIFIED Requirements

### Requirement: R-SCH-03 故障切换与总预算

对可重试失败，调度器 SHALL 标记账号并继续下一个候选，直到成功或请求总预算耗尽；输入错误 MUST NOT 切换；无候选可用返回 503，候选全部失败且最后一次失败为 `PROVIDER_ERROR` 返回 502，预算耗尽返回 504。请求总预算默认取 `REQUEST_DEADLINE_MS`，MUST 可被管理端运行时设置覆盖并即时生效，且 `public.py` 的外层等待与 `Scheduler` MUST 使用同一个绝对 deadline。`[spec-review-amendment R-50]`

#### Scenario: 主账号 5xx 切换备用
- **WHEN** 首选账号返回 5xx
- **THEN** 同一请求由同厂商备用账号成功返回

#### Scenario: 输入错误不回退
- **WHEN** 首选账号返回图片格式错误
- **THEN** 直接返回 400，不调用备用账号

#### Scenario: 厂商持续 5xx
- **WHEN** 候选账号都返回 5xx 且总预算未耗尽
- **THEN** 返回 502 `PROVIDER_ERROR`，不返回 503

#### Scenario: 运行时预算生效
- **WHEN** 管理员把请求总预算改为 10000ms 并保存
- **THEN** 后续请求按新的 10000ms 总预算执行，不再被旧的外层 deadline 截断
