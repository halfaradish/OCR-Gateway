# result-cache Specification

## MODIFIED Requirements

### Requirement: R-CAC-01 缓存键与命中
系统 SHALL 以 `sha256(image_bytes) + language + (provider 或 auto)` 为键缓存成功结果；命中时 MUST 返回 `cached=true`、`quota.used=0`，且不发起厂商调用。公共入口 MUST 先执行 provider 可用性门禁，再做缓存读取：显式 `provider=local` 在本地 OCR 未启用或依赖不可用时 MUST 返回 403，MUST NOT 因缓存命中返回 200。`[spec-review-amendment R-02]` `[m4-local-ocr]`

#### Scenario: 重复图片命中
- **WHEN** 相同图片、语言与 provider 在 TTL 内再次请求
- **THEN** 返回 200、`cached=true`、`quota.used=0`，且无厂商出站请求

#### Scenario: provider 隔离
- **WHEN** 同一图片先以 `provider=baidu` 请求，再以 `provider=tencent` 请求
- **THEN** 两次缓存键不同，第二次不复用第一次结果

#### Scenario: 禁用 local 后不命中
- **WHEN** 先在启用状态缓存一张 `provider=local` 结果，再关闭本地开关并请求同一图片
- **THEN** 返回 403 `FORBIDDEN`（不是缓存 200）；`provider=auto` 不返回 `provider="local"` 的缓存结果

### Requirement: R-CAC-02 缓存边界
缓存 SHALL 仅保存成功且 `text` 非空、单条 ≤256KB 的结果；容量默认 1000 条、TTL 默认 3600 秒；容量与 TTL MUST 可经管理端运行时设置覆盖（容量 10–2000 条、TTL 60–86400 秒），参数变更 MUST 清空现有缓存；`local_ocr_enabled` 变化 MUST 同样清空现有缓存（含 `auto` 键下可能存在的 local 结果）；MUST 为进程内存储，重启即失效。`[spec-review-amendment R-02]` `[m4-local-ocr]`

#### Scenario: 空文本不缓存
- **WHEN** 厂商成功返回空文本
- **THEN** 结果不写入缓存

#### Scenario: 容量淘汰
- **WHEN** 已缓存 1000 条后再写入新结果
- **THEN** 按 LRU 淘汰最旧条目，容量不超过上限

#### Scenario: 运行时参数变更
- **WHEN** 管理员把 TTL 或容量改为新值并保存
- **THEN** 缓存被清空，后续请求使用新参数

#### Scenario: 本地开关变更
- **WHEN** 管理员开启或关闭本地 OCR 并保存
- **THEN** 缓存被清空，响应标记 `cache_cleared=true`

### Requirement: R-CAC-03 管理端清空
管理员 SHALL 能清空缓存并返回清除条数；清空后相同请求 MUST 重新调用厂商。`[m4-local-ocr]`

#### Scenario: 清空后重新识别
- **WHEN** 管理员清空缓存后重复请求同一图片
- **THEN** 返回 `cached=false` 且发生厂商调用
