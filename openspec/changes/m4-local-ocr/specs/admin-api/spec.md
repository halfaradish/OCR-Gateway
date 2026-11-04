# admin-api Specification

## MODIFIED Requirements

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

## ADDED Requirements

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
