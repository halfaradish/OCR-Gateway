# admin-api Specification

## Purpose
提供管理面 API：管理员通过 cookie + CSRF（浏览器面板）或 Bearer（脚本与 `/docs`）完成成员、Key、账号、用量、日志、设置与总览的全部运营动作。

## Requirements

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

### Requirement: R-ADM-02 成员管理
管理员 SHALL 能创建、列出、修改、删除成员；成员名 MUST 唯一；成员被禁用后其所有 Key MUST 立即失效。

#### Scenario: 创建重名成员
- **WHEN** 创建已存在的成员名
- **THEN** 返回 400 `BAD_REQUEST`，不创建

#### Scenario: 禁用成员
- **WHEN** 成员 `enabled=false`
- **THEN** 其 Key 调用公共 API 返回 401

### Requirement: R-ADM-03 API Key 管理
管理员 SHALL 能为成员创建、禁用、吊销 Key；创建响应 MUST 是唯一一次返回明文，之后只返回前缀；库中 MUST 只存 SHA-256。

#### Scenario: 明文只出现一次
- **WHEN** 创建 Key 后再次查询列表
- **THEN** 响应不含明文 key，只有 `key_prefix`

#### Scenario: 吊销 Key
- **WHEN** 删除或禁用 Key 后使用该 Key 调用
- **THEN** 返回 401

### Requirement: R-ADM-04 账号管理与凭证保护
管理员 SHALL 能创建、修改、删除百度与腾讯账号；凭证 MUST 按厂商 schema 校验后以 AES-GCM 加密存储；任何管理响应 MUST NOT 返回明文凭证。

#### Scenario: 创建账号
- **WHEN** 提交合法的百度凭证
- **THEN** 账号创建成功，响应只含脱敏字段

#### Scenario: 凭证缺失
- **WHEN** 提交缺少 `secret_key` 的腾讯凭证
- **THEN** 返回 400 `BAD_REQUEST`，不创建

### Requirement: R-ADM-05 账号测活与状态重置
管理员 SHALL 能对账号测活（内置样图或上传图片）与重置状态；测活 MUST NOT 扣配额、写用量事件或改变账号状态；`reset-state` MUST 清除 `invalid`/`cooling` 并恢复 `active`。

#### Scenario: 重置 invalid 账号
- **WHEN** 对 `invalid` 账号调用 reset-state
- **THEN** 状态为 `active` 并可参与调度

#### Scenario: 测活不产生副作用
- **WHEN** 管理员对账号测活
- **THEN** 不写 `usage_events`、不扣账号/Key 配额、不改变账号状态 `[spec-review-amendment D24]`

### Requirement: R-ADM-06 用量与日志查询
管理员 SHALL 能按时间与维度查询用量汇总、按本地日查询时间序列、分页查询请求日志；汇总、序列与日志 MUST 共用时间窗口并拒绝超过 90 天的跨度；汇总与序列 MUST 支持成员/厂商/账号过滤，汇总行 MUST 带显示名称并按 key 升序（`null` 最后），日志 MUST 带成员与账号名称、支持时间与错误码过滤并返回匹配总数；`provider='auto'` MUST 有显示名「自动路由」，`provider='local'` MUST 有显示名「本地 RapidOCR」；日志 MUST NOT 返回 OCR 原文与凭证。`[spec-review-amendment R-06/R-11/R-12/R-52/R-14]` `[m4-local-ocr]`

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

#### Scenario: 本地厂商标签
- **WHEN** 汇总或日志中出现 `provider='local'`
- **THEN** label 为「本地 RapidOCR」；用量与日志的厂商筛选均可传 `provider=local`

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

### Requirement: R-ADM-07 配额模板查询
管理员 SHALL 能查询内置配额模板（百度/腾讯参考额度与凭证字段），模板 MUST 标注「以官网为准」且 MUST NOT 被自动套用到账号。

#### Scenario: 查询模板
- **WHEN** 调用 `/api/admin/quota-templates`
- **THEN** 返回两家厂商的参考额度、凭证字段与免责说明

#### Scenario: 模板不自动套用
- **WHEN** 创建账号且未显式提供配额
- **THEN** 账号配额保持 `NULL`，不取模板数值

### Requirement: R-ADM-08 运行时设置读写
管理员 SHALL 能读取与部分更新运行时设置：缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时、本地 OCR 开关；更新 MUST 校验类型与范围，显式 `null` MUST 返回 400，校验错误 MUST 含字段名；提交成功后 MUST 对后续请求生效；缓存参数变化 MUST 清空现有缓存并在响应中标记；**本地 OCR 开关变化 MUST 同样清空缓存并在响应中标记 `cache_cleared`**；重启后 MUST 按持久化值恢复本地 worker（`enabled=true` 且依赖已安装时从 `starting` 开始建池）；只读项 MUST 包含鉴权状态、版本、上传限制、并发上限、会话时长与面板产物状态。`[spec-review-amendment R-05/R-15/R-02]` `[m4-local-ocr]`

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

#### Scenario: 本地开关生效
- **WHEN** 提交 `{"local_ocr_enabled": true}` 并保存
- **THEN** 响应成功且 `cache_cleared=true`，后续 `provider=local` 可用，状态接口从 `starting` 变为 `ready`

#### Scenario: 本地开关类型错误
- **WHEN** 提交 `{"local_ocr_enabled": "yes"}`
- **THEN** 返回 400 `BAD_REQUEST`，`error.fields[].field="local_ocr_enabled"`，开关不变

#### Scenario: 重启后恢复本地 worker
- **WHEN** 设置为 `local_ocr_enabled=true` 且依赖已安装，进程重启后读取设置
- **THEN** `readonly` 仍显示原值，本地 worker 自动从 `starting` 进入 `ready`，无需再次保存

### Requirement: R-ADM-09 总览聚合
管理员 SHALL 能获取总览数据：今日请求、成功、失败、缓存命中、配额用量、成功率、缓存命中率、平均延迟，近 7 个本地日的序列，各厂商账号数与可用账号数，账号配额用量，最近 10 条错误与缓存状态；今日 MUST 按 `Asia/Shanghai` 自然日计算；无请求时比率 MUST 为空值而不是 0；`available_accounts` MUST 表示瞬时可调度数；`provider='auto'` 的失败 MUST 单独计数；`provider='local'` MUST 在厂商行中返回一行（`accounts=0`、`available_accounts=0`），使今日总数与厂商行之和可对账。`[spec-review-amendment R-09/R-21/R-52/R-13]` `[m4-local-ocr]`

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

#### Scenario: 本地厂商行
- **WHEN** 今日存在 `provider='local'` 的事件
- **THEN** 厂商行包含 `local`（`accounts=0`、`available_accounts=0`），今日请求总数与各厂商行请求数之和一致

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

### Requirement: R-ADM-11 本地 OCR 状态查询
管理员 SHALL 能查询本地 OCR 状态：启用状态、依赖是否安装、运行状态（`stopped`/`starting`/`ready`/`error`/`unavailable`）、并发、超时与有效超时、预留预算与有效预留、下次重试等待、模型信息、最近耗时、最近错误、累计请求与兜底次数。接口 MUST 需要管理员会话，MUST NOT 返回模型文件绝对路径、凭证或识别原文；`last_error` MUST 为脱敏短消息（去路径/堆栈/截断）。`[spec-review-amendment R-28/R-31]` `[m4-local-ocr]`

#### Scenario: 状态可查
- **WHEN** 管理员请求 `GET /api/admin/local-ocr/status`
- **THEN** 返回上述字段；`state` 与当前 worker 生命周期一致

#### Scenario: 依赖缺失
- **WHEN** 运行环境未安装 rapidocr 或 onnxruntime
- **THEN** 返回 `installed=false`、`state="unavailable"`，不抛 500；`/v1/providers` 的 local `enabled` 为 false

#### Scenario: 预热失败
- **WHEN** warmup 因模型加载失败进入 `error`
- **THEN** 返回 `state="error"`、脱敏的 `last_error` 与 `next_retry_in_ms`，不含模型文件绝对路径

#### Scenario: 未授权
- **WHEN** 未携带管理员会话请求状态接口
- **THEN** 返回 401 `UNAUTHORIZED`
