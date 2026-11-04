# admin-panel Specification

## MODIFIED Requirements

### Requirement: R-PANEL-08 设置界面
设置页 SHALL 分可编辑区与只读区：可编辑缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时、本地 OCR 开关；只读展示鉴权状态、版本、上传限制、并发上限与会话时长；页面 MUST 展示配额模板与「以官网为准」免责声明。本地 OCR 区 MUST 展示运行状态、模型信息、最近耗时与最近错误；依赖缺失时 MUST 禁用开关并说明原因。开关草稿 MUST 以设置表单为唯一来源，状态卡只读展示；状态卡 MUST 具备加载/空/错误三态，使用独立查询与同高骨架，MUST NOT 阻塞可编辑区；`starting` 期间 MUST 轮询（≤1s）至 `ready`/`error`，`ready`/`stopped` 停止或降频；保存 MUST 只提交 dirty 字段，disabled 字段 MUST 从 payload 剔除；窄屏 MUST 单列可用，`last_error` MUST 截断并可展开。`[spec-review-amendment R-33]` `[m4-local-ocr]`

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

#### Scenario: 状态卡三态
- **WHEN** 状态接口请求中/返回空/请求失败
- **THEN** 分别显示同高骨架、空态说明与错误说明+重试按钮；可编辑设置在三种情况下仍可操作

#### Scenario: 状态查询不阻塞设置
- **WHEN** 状态接口慢于设置接口返回
- **THEN** 设置表单先渲染并可编辑，状态卡在局部骨架中等待，不出现整页 loading

#### Scenario: 只提交改动字段
- **WHEN** 管理员只修改本地 OCR 开关后保存
- **THEN** 请求体只包含该字段（或 dirty 字段），不因其他字段未变而产生覆盖

#### Scenario: 本地依赖缺失
- **WHEN** 本地依赖未安装
- **THEN** 开关禁用并显示不可用原因，保存请求不提交该字段

#### Scenario: 窄屏展示
- **WHEN** 视口宽度小于断点
- **THEN** 本地 OCR 卡片单列展示，`last_error` 截断且可展开，不破坏其他设置区
