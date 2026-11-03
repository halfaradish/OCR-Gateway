# Spec Delta

## MODIFIED Requirements

### Requirement: R-ADM-01 管理员登录与令牌

系统 SHALL 用 `ADMIN_PASSWORD` 校验登录，返回签名 Bearer token 并设置 HttpOnly 会话 cookie 与 CSRF cookie（默认 12h）；除 `/api/admin/login` 外的所有 `/api/admin/*` MUST 接受 Bearer 或有效会话 cookie，缺失/无效/过期返回 401；cookie 会话的写方法 MUST 校验 `X-CSRF-Token`；登录失败 MUST 限速（5 次/分钟，按 IP + 全局双层，全局层只延迟不永久阻断）；登出 MUST 清空会话与 CSRF cookie。`[spec-review-amendment D16/D20；m3 恢复 cookie+CSRF 双轨]`

#### Scenario: 登录成功
- **WHEN** 提交正确密码
- **THEN** 返回 token、`expires_in` 与 `csrf_token`，并设置会话 cookie 与 CSRF cookie

#### Scenario: Cookie 属性
- **WHEN** 在 HTTPS 请求上登录
- **THEN** 会话 cookie 为 HttpOnly 且带 `Secure`，CSRF cookie 可被脚本读取且与响应中的 `csrf_token` 一致

#### Scenario: 未带令牌访问管理 API
- **WHEN** 请求 `/api/admin/accounts` 且无 Authorization、无会话 cookie
- **THEN** 返回 401

#### Scenario: Bearer 访问
- **WHEN** 请求携带有效 Bearer token
- **THEN** 请求成功，且不要求 CSRF 头

#### Scenario: Cookie 写请求缺 CSRF
- **WHEN** 仅凭会话 cookie 发起 `PUT /api/admin/settings` 且缺少或不匹配 `X-CSRF-Token`
- **THEN** 返回 403 `FORBIDDEN`，不执行写操作

#### Scenario: Cookie 写请求带 CSRF
- **WHEN** 仅凭会话 cookie 发起写请求且 `X-CSRF-Token` 与 CSRF cookie 一致
- **THEN** 写操作成功

#### Scenario: 当前管理员
- **WHEN** 已登录管理员请求 `/api/admin/me`
- **THEN** 返回 `username` 与 `csrf_token`；cookie 会话缺 CSRF cookie 时补发

#### Scenario: 登出
- **WHEN** 管理员调用 `/api/admin/logout`
- **THEN** 两个 cookie 被清空，随后仅凭 cookie 的请求返回 401

#### Scenario: 暴力尝试
- **WHEN** 1 分钟内连续 5 次密码错误
- **THEN** 第 6 次返回 429

### Requirement: R-ADM-06 用量与日志查询

管理员 SHALL 能按时间与维度查询用量汇总、按本地日查询时间序列、分页查询请求日志；汇总与序列 MUST 支持成员/厂商/账号过滤，汇总行 MUST 带显示名称，日志 MUST 带成员与账号名称、支持时间与错误码过滤并返回匹配总数；日志 MUST NOT 返回 OCR 原文与凭证。

#### Scenario: 按厂商汇总
- **WHEN** 调用 `/usage/summary?group_by=provider`
- **THEN** 返回每个厂商的成功、失败、缓存命中计数与平均延迟

#### Scenario: 平均延迟口径
- **WHEN** 汇总或序列范围内同时存在成功与失败事件
- **THEN** 平均延迟为该范围内全部事件 `latency_ms` 的整数均值（含失败事件），无事件时为 `null`

#### Scenario: 汇总显示名称
- **WHEN** 汇总按成员或账号分组
- **THEN** 每行包含可显示的名称；对应实体已删除时为 `null`

#### Scenario: 日序列
- **WHEN** 调用 `/usage/series?from=2026-10-29&to=2026-11-04`
- **THEN** 返回按 `Asia/Shanghai` 日分桶的序列，缺失日期补零，且包含 `2026-11-04` 当日

#### Scenario: 仅日期结束值含当日
- **WHEN** `to` 只给 `YYYY-MM-DD` 形式
- **THEN** 该参数被解释为该本地日的结束，筛选结果包含当日事件

#### Scenario: 时间范围倒置
- **WHEN** `from` 晚于 `to`
- **THEN** 返回 400 `BAD_REQUEST`

#### Scenario: 序列跨度上限
- **WHEN** 序列请求的时间跨度超过 90 天
- **THEN** 返回 400 `BAD_REQUEST`

#### Scenario: 日志分页
- **WHEN** 调用 `/logs?limit=50&offset=50`
- **THEN** 返回第二页、不超过 50 条，并返回匹配总数

#### Scenario: 日志过滤
- **WHEN** 调用 `/logs?success=false&provider=tencent&error_code=TIMEOUT`
- **THEN** 只返回同时满足三个条件的记录

#### Scenario: 日志显示名称
- **WHEN** 日志行对应的成员或账号存在
- **THEN** 返回 `user_name` 与 `account_name`；实体已删除时为 `null`

#### Scenario: 非法时间
- **WHEN** 传入无法解析的 `from` 或 `to`
- **THEN** 返回 400 `BAD_REQUEST`

## ADDED Requirements

### Requirement: R-ADM-08 运行时设置读写

管理员 SHALL 能读取与部分更新运行时设置：缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时；更新 MUST 校验类型与范围，提交成功后 MUST 对后续请求生效；缓存参数变化 MUST 清空现有缓存并在响应中标记；只读项 MUST 包含鉴权状态、版本、上传限制、并发上限、会话时长与面板产物状态。

#### Scenario: 读取设置
- **WHEN** 调用 `GET /api/admin/settings`
- **THEN** 返回可编辑项与只读项，值为当前生效值

#### Scenario: 部分更新
- **WHEN** 只提交 `cache_ttl_seconds`
- **THEN** 其余设置保持不变，重启后新值仍生效

#### Scenario: 非法值
- **WHEN** 提交超出范围的缓存 TTL 或非整数
- **THEN** 返回 400 `BAD_REQUEST`，设置与运行时均不变

#### Scenario: 未知键
- **WHEN** 提交未被定义的设置键
- **THEN** 返回 400 `BAD_REQUEST`，不静默忽略

#### Scenario: 缓存参数变更
- **WHEN** 修改缓存开关、TTL 或容量并保存
- **THEN** 响应标记缓存已清空，缓存条目归零

#### Scenario: 请求预算生效
- **WHEN** 把请求总预算改为更小值并保存
- **THEN** 后续 OCR 请求使用新的总预算

#### Scenario: 账号默认超时生效
- **WHEN** 修改账号默认超时后创建未显式指定超时的账号
- **THEN** 新账号使用新的默认超时

### Requirement: R-ADM-09 总览聚合

管理员 SHALL 能获取总览数据：今日请求、成功、失败、缓存命中、配额用量、成功率、缓存命中率、平均延迟，各厂商账号数与可用账号数，账号配额用量，最近 10 条错误与缓存状态；今日 MUST 按 `Asia/Shanghai` 自然日计算；无请求时比率 MUST 为空值而不是 0。

#### Scenario: 有数据的总览
- **WHEN** 今日存在成功与失败请求
- **THEN** 各计数、成功率、缓存命中率与平均延迟为非空值

#### Scenario: 无请求的总览
- **WHEN** 今日没有请求
- **THEN** 计数为 0，成功率、缓存命中率与平均延迟为 `null`

#### Scenario: 可用账号数
- **WHEN** 某厂商账号被禁用、冷却或配额耗尽
- **THEN** 该厂商的可用账号数不包含这些账号

#### Scenario: 最近错误
- **WHEN** 存在超过 10 条失败记录
- **THEN** 只返回最近 10 条，包含账号名称，且不含 OCR 原文与凭证

### Requirement: R-ADM-10 账号列表用量与归属

账号列表 SHALL 返回每个账号的贡献者名称、当前日/月/总量周期的已用配额、限额与周期键；已用值 MUST 与调度使用的配额计数一致，限额为空时 MUST 返回 `null`。

#### Scenario: 成功请求后用量增加
- **WHEN** 账号成功完成一次 OCR 请求
- **THEN** 该账号的日/月/总量已用值各增加 1

#### Scenario: 贡献者名称
- **WHEN** 账号有贡献者成员
- **THEN** 列表返回 `owner_name`；贡献者已删除时为 `null`

#### Scenario: 未配置限额
- **WHEN** 账号未配置日/月/总量限额
- **THEN** 对应 `limit` 为 `null`，已用值仍返回

#### Scenario: 周期切换
- **WHEN** 跨过 `Asia/Shanghai` 的日重置点
- **THEN** 日已用值从 0 开始，月与总量保持不变
