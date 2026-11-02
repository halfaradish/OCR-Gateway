# Spec Delta

## Purpose

提供无前端 SPA 的管理面：管理员通过 Bearer token 完成成员、Key、账号、用量、日志与配额模板的全部运营动作。

## ADDED Requirements

### Requirement: R-ADM-01 管理员登录与令牌
系统 SHALL 用 `ADMIN_PASSWORD` 校验登录并返回签名 Bearer token（默认 12h）；所有 `/api/admin/*` MUST 校验 token，缺失/无效/过期返回 401；登录失败 MUST 限速（5 次/分钟）。

#### Scenario: 登录成功
- **WHEN** 提交正确密码
- **THEN** 返回 token 与 `expires_in`

#### Scenario: 未带令牌访问管理 API
- **WHEN** 请求 `/api/admin/accounts` 且无 Authorization
- **THEN** 返回 401

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

### Requirement: R-ADM-06 用量与日志查询
管理员 SHALL 能按时间与维度查询用量汇总、分页查询请求日志；日志 MUST NOT 返回 OCR 原文与凭证。

#### Scenario: 按厂商汇总
- **WHEN** 调用 `/usage/summary?group_by=provider`
- **THEN** 返回每个厂商的成功、失败与缓存命中计数

#### Scenario: 日志分页
- **WHEN** 调用 `/logs?limit=50&offset=50`
- **THEN** 返回第二页且不超过 50 条

### Requirement: R-ADM-07 配额模板查询
管理员 SHALL 能查询内置配额模板（百度/腾讯参考额度与凭证字段），模板 MUST 标注「以官网为准」且 MUST NOT 被自动套用到账号。

#### Scenario: 查询模板
- **WHEN** 调用 `/api/admin/quota-templates`
- **THEN** 返回两家厂商的参考额度、凭证字段与免责说明

#### Scenario: 模板不自动套用
- **WHEN** 创建账号且未显式提供配额
- **THEN** 账号配额保持 `NULL`，不取模板数值
