# Spec Delta

## MODIFIED Requirements

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
