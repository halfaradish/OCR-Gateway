# admin-panel Specification

## MODIFIED Requirements

### Requirement: R-PANEL-08 设置界面
设置页 SHALL 分可编辑区与只读区：可编辑缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时、本地 OCR 开关；只读展示鉴权状态、版本、上传限制、并发上限与会话时长；页面 MUST 展示配额模板与「以官网为准」免责声明。本地 OCR 区 MUST 展示运行状态、模型信息、最近耗时与最近错误；依赖缺失时 MUST 禁用开关并说明原因。`[m4-local-ocr]`

#### Scenario: 保存合法设置
- **WHEN** 管理员把缓存 TTL 改为合法值并保存
- **THEN** 保存成功，刷新页面后显示新值

#### Scenario: 非法值
- **WHEN** 管理员提交超出范围的值
- **THEN** 字段显示错误，保存被阻止，原设置不变

#### Scenario: 缓存参数变更提示
- **WHEN** 管理员修改缓存开关、TTL 或容量并保存
- **THEN** 成功提示说明现有缓存已清空

#### Scenario: 清空缓存
- **WHEN** 管理员点击清空缓存并确认
- **THEN** 页面提示已清除的条数，缓存条目归零

#### Scenario: 只读区
- **WHEN** 管理员查看设置页
- **THEN** 鉴权状态显示为强制开启，版本、上传限制、并发与会话时长可见

#### Scenario: 本地 OCR 开关与状态
- **WHEN** 管理员开启本地 OCR 并保存
- **THEN** 卡片显示状态从 `starting` 变为 `ready`，并展示模型、最近耗时与错误为空

#### Scenario: 本地依赖缺失
- **WHEN** 本地依赖未安装
- **THEN** 开关禁用并显示不可用原因，保存请求不提交该字段
