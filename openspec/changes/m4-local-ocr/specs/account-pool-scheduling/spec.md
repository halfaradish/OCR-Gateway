# account-pool-scheduling Specification

## MODIFIED Requirements

### Requirement: R-SCH-03 故障切换与总预算
对可重试失败，调度器 SHALL 标记账号并继续下一个候选，直到成功或请求总预算耗尽；输入错误 MUST NOT 切换；无候选可用返回 503，候选全部失败且最后一次失败为 `PROVIDER_ERROR` 返回 502，预算耗尽返回 504。请求总预算默认取 `REQUEST_DEADLINE_MS`，MUST 可被管理端运行时设置覆盖并即时生效，且 `public.py` 的外层等待与 `Scheduler` MUST 使用同一个绝对 deadline。当 `provider=auto` 且本地 OCR 可用时，云阶段 MAY 使用 `deadline − reserve_eff` 作为子 deadline；本地阶段 MUST 使用原始总 deadline，整个请求 MUST NOT 超过总 deadline。`[spec-review-amendment R-50/R-06]` `[m4-local-ocr]`

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

#### Scenario: 本地兜底不突破总预算
- **WHEN** `provider=auto`、本地可用、云阶段用尽 `deadline − reserve_eff`
- **THEN** 本地阶段仍受原始总 deadline 约束，整个请求不超过总预算；预算不足时返回云阶段原错误

### Requirement: R-SCH-05 显式厂商不回退
当请求指定 `provider` 时，调度器 MUST 只使用该厂商账号，禁止跨厂商切换；只有 `auto` 可在全部厂商账号间切换。`provider=local` MUST 只使用本地引擎，MUST NOT 回退到任何云厂商。`[m4-local-ocr]`

#### Scenario: 显式百度无可用
- **WHEN** `provider=baidu` 且所有百度账号不可用
- **THEN** 返回 503 `PROVIDER_UNAVAILABLE`，不调用腾讯

#### Scenario: auto 跨厂商
- **WHEN** `provider=auto` 且百度账号全部不可用而腾讯可用
- **THEN** 请求成功并返回 `provider="tencent"`

#### Scenario: 显式本地不回云
- **WHEN** `provider=local` 且本地引擎失败
- **THEN** 返回本地错误（502/504），不调用任何云厂商

## ADDED Requirements

### Requirement: R-SCH-07 auto 兜底本地与预算预留
当 `provider=auto`、本地 OCR 已启用且依赖可用时，调度器 SHALL 在云端无候选或全部候选以可重试错误失败时尝试本地识别；云阶段截止 MUST 为总 deadline 减去本地预留预算；本地尝试 MUST 使用剩余预算，剩余不足最小预算时 MUST 放弃兜底并返回云阶段原错误；`InputError`、显式云厂商或本地不可用时 MUST NOT 触发本地兜底。`reserve_eff` MUST 按 `min(LOCAL_OCR_RESERVE_MS, max(0, total_budget − LOCAL_OCR_MIN_BUDGET_MS))` 收敛；`total_budget ≤ LOCAL_OCR_MIN_BUDGET_MS` 时 MUST NOT 预留（等价于不兜底）。`[spec-review-amendment R-01]` `[m4-local-ocr]`

#### Scenario: 云全挂自动兜底
- **WHEN** `provider=auto`、本地已启用且就绪，所有云账号不可用或均失败
- **THEN** 请求由本地引擎完成并返回 200、`provider="local"`

#### Scenario: 输入错误不兜底
- **WHEN** 首选云账号返回图片格式错误（`InputError`）
- **THEN** 直接返回 400，不尝试本地引擎

#### Scenario: 本地不可用不预留
- **WHEN** `provider=auto` 但本地未启用或依赖缺失
- **THEN** 云阶段使用完整总预算，不扣减本地预留

#### Scenario: 小预算不预留
- **WHEN** `request_deadline_ms` 为 1000–5000ms 且本地启用
- **THEN** `reserve_eff=0`，云阶段使用完整预算，不因预留导致云阶段截止落在过去

#### Scenario: 云端失败但预算不足
- **WHEN** 云阶段失败后剩余预算低于本地最小预算
- **THEN** 不启动本地识别，返回云阶段原错误（503/502/504）
