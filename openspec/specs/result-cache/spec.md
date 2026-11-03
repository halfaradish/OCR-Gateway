# result-cache Specification

## Purpose
通过图片内容哈希复用成功结果，减少重复调用与免费额度消耗，同时保持公共 API 响应契约不变。

## Requirements

### Requirement: R-CAC-01 缓存键与命中
系统 SHALL 以 `sha256(image_bytes) + language + (provider 或 auto)` 为键缓存成功结果；命中时 MUST 返回 `cached=true`、`quota.used=0`，且不发起厂商调用。

#### Scenario: 重复图片命中
- **WHEN** 相同图片、语言与 provider 在 TTL 内再次请求
- **THEN** 返回 200、`cached=true`、`quota.used=0`，且无厂商出站请求

#### Scenario: provider 隔离
- **WHEN** 同一图片先以 `provider=baidu` 请求，再以 `provider=tencent` 请求
- **THEN** 两次缓存键不同，第二次不复用第一次结果

### Requirement: R-CAC-02 缓存边界

缓存 SHALL 仅保存成功且 `text` 非空、单条 ≤256KB 的结果；容量默认 1000 条、TTL 默认 3600 秒；容量与 TTL MUST 可经管理端运行时设置覆盖（容量 10–2000 条、TTL 60–86400 秒），参数变更 MUST 清空现有缓存；MUST 为进程内存储，重启即失效。`[spec-review-amendment R-50]`

#### Scenario: 空文本不缓存
- **WHEN** 厂商成功返回空文本
- **THEN** 结果不写入缓存

#### Scenario: 容量淘汰
- **WHEN** 已缓存 1000 条后再写入新结果
- **THEN** 按 LRU 淘汰最旧条目，容量不超过上限

#### Scenario: 运行时参数变更
- **WHEN** 管理员把 TTL 或容量改为新值并保存
- **THEN** 缓存被清空，后续请求使用新参数

### Requirement: R-CAC-03 管理端清空
管理员 SHALL 能清空缓存并返回清除条数；清空后相同请求 MUST 重新调用厂商。

#### Scenario: 清空后重新识别
- **WHEN** 管理员清空缓存后重复请求同一图片
- **THEN** 返回 `cached=false` 且发生厂商调用
