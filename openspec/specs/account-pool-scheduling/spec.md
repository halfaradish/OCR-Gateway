# account-pool-scheduling Specification

## Purpose
定义账号池的候选过滤、排序、尝试循环与状态转移，保证同厂商多账号在故障时自动切换且行为可预测。

## Requirements

### Requirement: R-SCH-01 候选过滤
调度器 SHALL 只纳入满足全部条件的账号：provider 匹配、enabled、状态 active（冷却到期与配额周期变化惰性恢复）、周期配额未耗尽、并发未满、QPS 令牌可用。

#### Scenario: 排除冷却账号
- **WHEN** 某账号处于 `cooling` 且 `cooldown_until` 未到
- **THEN** 该账号不出现在候选中

#### Scenario: 并发已满
- **WHEN** 账号 `in_flight` 已达到 `max_concurrency`
- **THEN** 该账号被跳过，请求使用下一个候选

### Requirement: R-SCH-02 候选排序
候选 SHALL 按 `priority` 升序，同优先级按 EWMA 延迟升序，再按 `last_used_at` 升序，最后按 `weight` 降序；成功请求 MUST 更新 EWMA（0.2×本次 + 0.8×旧值）与 `last_used_at`。

#### Scenario: 优先级分层
- **WHEN** 账号 A `priority=10`、账号 B `priority=100`
- **THEN** A 始终排在 B 之前

#### Scenario: 同层低延迟优先
- **WHEN** 两个账号同 `priority`，EWMA 分别为 300ms 与 900ms
- **THEN** 300ms 的账号先被使用

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

### Requirement: R-SCH-04 状态与冷却
失败 SHALL 按分类转移状态：`AUTH_FAILED` → `invalid`（仅管理员重置）、`QUOTA_EXCEEDED` → `quota_exhausted`（周期重置恢复）、`RATE_LIMITED`/`TIMEOUT`/网络 → `cooling` 30s、5xx → `cooling` 10s；到期 MUST 在下次选择时惰性恢复。腾讯 `AuthFailure.SignatureExpire` MUST 归 `PROVIDER_ERROR`（冷却 30s + 告警），MUST NOT 置 `invalid`。`[spec-review-amendment Q4]`

#### Scenario: 鉴权失败长禁用
- **WHEN** 适配器返回 `AUTH_FAILED`
- **THEN** 账号状态为 `invalid`，直到管理员执行 reset-state

#### Scenario: 冷却自动恢复
- **WHEN** `cooling` 账号的 `cooldown_until` 已过
- **THEN** 下次选择时恢复 `active` 并可被选中

#### Scenario: 时钟偏移不永久禁用
- **WHEN** 腾讯返回 `AuthFailure.SignatureExpire`
- **THEN** 账号进入 `cooling` 30s，不进入 `invalid`，冷却后可再次被选中

### Requirement: R-SCH-05 显式厂商不回退
当请求指定 `provider` 时，调度器 MUST 只使用该厂商账号，禁止跨厂商切换；只有 `auto` 可在全部厂商账号间切换。

#### Scenario: 显式百度无可用
- **WHEN** `provider=baidu` 且所有百度账号不可用
- **THEN** 返回 503 `PROVIDER_UNAVAILABLE`，不调用腾讯

#### Scenario: auto 跨厂商
- **WHEN** `provider=auto` 且百度账号全部不可用而腾讯可用
- **THEN** 请求成功并返回 `provider="tencent"`

### Requirement: R-SCH-06 单进程运行时状态
调度器 SHALL 在单进程内维护账号运行时状态；启动时 MUST 从账号表加载 EWMA 初始值与状态，MUST NOT 依赖多 worker 共享状态。

#### Scenario: 重启恢复 EWMA
- **WHEN** 进程重启
- **THEN** 账号 EWMA 使用数据库中的值；无记录时使用厂商种子 1000ms
