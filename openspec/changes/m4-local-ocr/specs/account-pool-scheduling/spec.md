# account-pool-scheduling Specification

## MODIFIED Requirements

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
当 `provider=auto`、本地 OCR 已启用且依赖可用时，调度器 SHALL 在云端无候选或全部候选以可重试错误失败时尝试本地识别；云阶段截止 MUST 为总 deadline 减去本地预留预算；本地尝试 MUST 使用剩余预算，剩余不足最小预算时 MUST 放弃兜底并返回云阶段原错误；`InputError`、显式云厂商或本地不可用时 MUST NOT 触发本地兜底。`[m4-local-ocr]`

#### Scenario: 云全挂自动兜底
- **WHEN** `provider=auto`、本地已启用且就绪，所有云账号不可用或均失败
- **THEN** 请求由本地引擎完成并返回 200、`provider="local"`

#### Scenario: 输入错误不兜底
- **WHEN** 首选云账号返回图片格式错误（`InputError`）
- **THEN** 直接返回 400，不尝试本地引擎

#### Scenario: 本地不可用不预留
- **WHEN** `provider=auto` 但本地未启用或依赖缺失
- **THEN** 云阶段使用完整总预算，不扣减本地预留

#### Scenario: 云端失败但预算不足
- **WHEN** 云阶段失败后剩余预算低于本地最小预算
- **THEN** 不启动本地识别，返回云阶段原错误（503/502/504）
