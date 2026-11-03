# Spec Delta

## MODIFIED Requirements

### Requirement: R-ADM-01 管理员登录与令牌

系统 SHALL 用 `ADMIN_PASSWORD` 校验登录，返回签名 Bearer token 并设置 HttpOnly 会话 cookie 与 CSRF cookie（默认 12h）；除 `/api/admin/login` 外的所有 `/api/admin/*` MUST 接受 Bearer 或有效会话 cookie，缺失/无效/过期返回 401；cookie 会话的写方法 MUST 校验 `X-CSRF-Token`；登录失败 MUST 限速（5 次/分钟，按 IP + 全局双层，全局层只延迟不永久阻断）；登出 MUST 清空会话与 CSRF cookie。`[spec-review-amendment D16/D20；m3 恢复 cookie+CSRF 双轨；R-49]`

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

#### Scenario: Bearer 无效且存在 cookie
- **WHEN** 请求同时携带无效 Bearer 与有效会话 cookie
- **THEN** 返回 401，不回退 cookie

#### Scenario: Swagger Authorize
- **WHEN** 打开 `/docs`
- **THEN** OpenAPI 声明 Bearer security scheme，Authorize 可用

#### Scenario: HTTPS 反代 Cookie
- **WHEN** 反代终结 TLS，转发 `X-Forwarded-Proto` 且 `TRUST_PROXY_HEADERS=true`
- **THEN** 登录响应的会话 cookie 与 CSRF cookie 都带 `Secure`

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

管理员 SHALL 能按时间与维度查询用量汇总、按本地日查询时间序列、分页查询请求日志；汇总、序列与日志 MUST 共用时间窗口并拒绝超过 90 天的跨度；汇总与序列 MUST 支持成员/厂商/账号过滤，汇总行 MUST 带显示名称并按 key 升序（`null` 最后），日志 MUST 带成员与账号名称、支持时间与错误码过滤并返回匹配总数；`provider='auto'` MUST 有显示名「自动路由」；日志 MUST NOT 返回 OCR 原文与凭证。`[spec-review-amendment R-06/R-11/R-12/R-52]`

#### Scenario: 按厂商汇总
- **WHEN** 调用 `/usage/summary?group_by=provider`
- **THEN** 返回每个厂商的成功、失败、缓存命中计数与平均延迟

#### Scenario: 平均延迟口径
- **WHEN** 汇总或序列范围内同时存在成功与失败事件
- **THEN** 平均延迟为该范围内全部事件 `latency_ms` 的整数均值（含失败事件），无事件时为 `null`

#### Scenario: 汇总显示名称
- **WHEN** 汇总按成员或账号分组
- **THEN** 每行包含可显示的名称；对应实体已删除时为 `null`

#### Scenario: 已删除实体分组
- **WHEN** 汇总范围内同时存在有效成员与已删除成员
- **THEN** 已删除成员合并为 `key=null` 的单行，排序在有效 key 之后，label 为 `null`

#### Scenario: 自动路由失败
- **WHEN** `provider=auto` 的请求因无候选失败
- **THEN** 汇总中 `auto` 行 label 为「自动路由」，总览 `today.auto_failures` 加一

#### Scenario: 汇总跨度上限
- **WHEN** 汇总请求的时间跨度超过 90 天
- **THEN** 返回 400 `BAD_REQUEST`

#### Scenario: 默认窗口
- **WHEN** 未传 `from/to` 请求序列
- **THEN** 返回 7 个本地日桶（含今日）

#### Scenario: 日序列
- **WHEN** 调用 `/usage/series?from=2026-10-29&to=2026-11-04`
- **THEN** 返回按 `Asia/Shanghai` 日分桶的序列，缺失日期补零，且包含 `2026-11-04` 当日

#### Scenario: 仅日期结束值含当日
- **WHEN** `to` 只给 `YYYY-MM-DD` 形式
- **THEN** 该参数被解释为该本地日的结束，筛选结果包含当日事件

#### Scenario: 日期边界
- **WHEN** 事件时间恰好是 `to` 次日的本地 00:00:00
- **THEN** 该事件不计入本次筛选（半开区间）

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

管理员 SHALL 能读取与部分更新运行时设置：缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时；更新 MUST 校验类型与范围，显式 `null` MUST 返回 400，校验错误 MUST 含字段名；提交成功后 MUST 对后续请求生效；缓存参数变化 MUST 清空现有缓存并在响应中标记；只读项 MUST 包含鉴权状态、版本、上传限制、并发上限、会话时长与面板产物状态。`[spec-review-amendment R-05/R-15]`

#### Scenario: 读取设置
- **WHEN** 调用 `GET /api/admin/settings`
- **THEN** 返回可编辑项与只读项，值为当前生效值

#### Scenario: 部分更新
- **WHEN** 只提交 `cache_ttl_seconds`
- **THEN** 其余设置保持不变，重启后新值仍生效

#### Scenario: 非法值
- **WHEN** 提交超出范围的缓存 TTL 或非整数
- **THEN** 返回 400 `BAD_REQUEST`，`error.fields` 含字段名，设置与运行时均不变

#### Scenario: 显式 null
- **WHEN** 提交 `{"cache_ttl_seconds": null}`
- **THEN** 返回 400 `BAD_REQUEST`，不把 null 当作未提供

#### Scenario: 容量与预算上限
- **WHEN** 提交 `cache_max_entries=2001` 或 `request_deadline_ms=20001`
- **THEN** 返回 400 `BAD_REQUEST`

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

管理员 SHALL 能获取总览数据：今日请求、成功、失败、缓存命中、配额用量、成功率、缓存命中率、平均延迟，近 7 个本地日的序列，各厂商账号数与可用账号数，账号配额用量，最近 10 条错误与缓存状态；今日 MUST 按 `Asia/Shanghai` 自然日计算；无请求时比率 MUST 为空值而不是 0；`available_accounts` MUST 表示瞬时可调度数；`provider='auto'` 的失败 MUST 单独计数。`[spec-review-amendment R-09/R-21/R-52]`

#### Scenario: 有数据的总览
- **WHEN** 今日存在成功与失败请求
- **THEN** 各计数、成功率、缓存命中率与平均延迟为非空值

#### Scenario: 无请求的总览
- **WHEN** 今日没有请求
- **THEN** 计数为 0，成功率、缓存命中率与平均延迟为 `null`

#### Scenario: 可用账号数
- **WHEN** 某厂商账号被禁用、冷却或配额耗尽
- **THEN** 该厂商的可用账号数不包含这些账号

#### Scenario: 可用账号数的瞬时口径
- **WHEN** 账号并发已满或令牌桶暂时为空
- **THEN** 该账号也暂不计入 `available_accounts`；GET 不改变账号状态

#### Scenario: 近 7 日序列
- **WHEN** 请求总览
- **THEN** 响应包含 7 个本地日桶的序列

#### Scenario: 自动路由失败计数
- **WHEN** 今日存在 `provider=auto` 的失败事件
- **THEN** `today.auto_failures` 计入这些事件，厂商行不重复计入

#### Scenario: 最近错误
- **WHEN** 存在超过 10 条失败记录
- **THEN** 只返回最近 10 条，包含账号名称，且不含 OCR 原文与凭证

### Requirement: R-ADM-10 账号列表用量与归属

账号列表 SHALL 返回每个账号的贡献者名称、当前日/月/总量周期的已用配额、限额与周期键；已用值 MUST 与调度使用的配额计数一致，限额为空时 MUST 返回 `null`。`[spec-review-amendment R-07]`

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

#### Scenario: 删除账号清理配额
- **WHEN** 删除一个有已用配额的账号，再等待两个 flush 周期并创建新账号
- **THEN** 不出现外键错误，新账号的已用值为 0
