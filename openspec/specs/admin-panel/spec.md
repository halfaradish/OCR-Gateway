# admin-panel Specification

## Purpose
管理面板的浏览器行为与交付边界：管理员通过同源 SPA 登录并完成日常运营操作，静态资源由网关托管并受安全响应头保护。

## Requirements

### Requirement: R-PANEL-01 登录与会话

面板 SHALL 提供管理员密码登录；登录成功后进入总览并保持会话，刷新页面不丢失登录态；未认证访问受保护路由 MUST 跳转登录；登出 MUST 清除会话并回到登录页。

#### Scenario: 登录成功
- **WHEN** 管理员在登录页提交正确密码
- **THEN** 进入总览页，顶栏显示管理员身份

#### Scenario: 刷新保持登录
- **WHEN** 已登录管理员的页面刷新
- **THEN** 仍停留在原页面，不跳转登录

#### Scenario: 未认证访问
- **WHEN** 未登录时直接访问 `/accounts`
- **THEN** 跳转到登录页

#### Scenario: 登出
- **WHEN** 管理员点击登出
- **THEN** 回到登录页，浏览器后退不能恢复已登录页面

### Requirement: R-PANEL-02 路由与导航

面板 SHALL 提供登录、总览、账号、成员与 Key、用量、日志、设置七个路由；受保护路由共享侧栏与顶栏导航；未知路径 MUST 显示 404 页面并可返回总览。

#### Scenario: 七个路由可达
- **WHEN** 管理员依次访问七个路由
- **THEN** 每个路由渲染对应页面且无控制台错误

#### Scenario: 未知路径
- **WHEN** 访问不存在的面板路径
- **THEN** 显示 404 页面，提供返回总览的入口

#### Scenario: 窄屏导航
- **WHEN** 视口宽度小于 768px
- **THEN** 侧栏收起为顶部抽屉，当前页面仍可到达全部导航项

### Requirement: R-PANEL-03 总览

总览 SHALL 显示今日请求数、成功率、缓存命中率、平均延迟、各厂商可用账号、账号配额进度与最近错误；无数据时 MUST 显示空态而不是空白区域。

#### Scenario: 有数据的今日指标
- **WHEN** 今日存在请求记录
- **THEN** 四项今日指标显示非空数值

#### Scenario: 无数据的空态
- **WHEN** 今日没有请求记录
- **THEN** 指标显示 0 或「—」，并提供去用量页查看历史的入口

#### Scenario: 最近错误
- **WHEN** 存在失败请求
- **THEN** 最近错误列表显示时间、厂商、账号、错误码与耗时，不含 OCR 原文

### Requirement: R-PANEL-04 账号管理界面

账号页 SHALL 列表展示厂商、名称、贡献者、优先级、配额、状态、EWMA 延迟与最近错误，并支持新建、编辑、测活、重置状态、启用/禁用与删除；凭证字段 MUST 按厂商渲染，编辑时 MUST NOT 回填明文；编辑时超时留空 MUST 省略字段而不是提交 `null`。`[spec-review-amendment R-14]`

#### Scenario: 新建账号
- **WHEN** 管理员选择厂商并填写该厂商全部必填凭证
- **THEN** 账号创建成功并出现在列表中，列表只显示脱敏凭证

#### Scenario: 编辑时保留凭证
- **WHEN** 管理员编辑账号但凭证字段留空
- **THEN** 保存后原凭证仍可用，测活成功

#### Scenario: 编辑时超时留空
- **WHEN** 管理员编辑账号且超时字段留空
- **THEN** 提交省略该字段，原超时保持不变，不发送 `null`

#### Scenario: 测活结果
- **WHEN** 管理员点击测活
- **THEN** 显示识别文本与耗时；失败时显示错误码与消息，且不产生用量记录

#### Scenario: 未配置额度提示
- **WHEN** 账号的日/月/总量限额全部为空
- **THEN** 配额列显示「未配置额度，可能超用」提示，不显示为额度已满

#### Scenario: 重置状态确认
- **WHEN** 管理员点击重置状态
- **THEN** 确认框说明会同时清零该账号的配额计数；确认后状态恢复为 `active` 且用量从 0 开始

#### Scenario: 删除确认
- **WHEN** 管理员删除账号
- **THEN** 先出现确认对话框，确认后账号从列表移除

### Requirement: R-PANEL-05 成员与 Key 界面

成员与 Key 页 SHALL 支持创建、启用/禁用、删除成员，以及为成员创建 Key、设置日限额与 RPM、启用/吊销 Key；创建 Key 的明文 MUST 只在创建成功时显示一次，之后列表只显示前缀。

#### Scenario: 创建成员
- **WHEN** 管理员提交新的成员名称
- **THEN** 成员出现在列表，并可为其创建 Key

#### Scenario: Key 明文只显示一次
- **WHEN** 管理员创建 Key 后关闭成功对话框并刷新列表
- **THEN** 列表不显示明文，只显示前缀

#### Scenario: 删除成员提示级联
- **WHEN** 管理员删除仍有 Key 的成员
- **THEN** 确认对话框说明其 Key 会一并吊销

#### Scenario: 吊销 Key
- **WHEN** 管理员吊销某个 Key
- **THEN** 该 Key 立即从「启用」变为不可用状态展示

### Requirement: R-PANEL-06 用量界面

用量页 SHALL 支持按时间范围、成员、厂商、账号筛选，切换请求数、成功率、平均延迟三种视图，显示折线图与汇总表，汇总表 MUST 支持按成员/厂商/账号分组切换，并支持把当前筛选结果导出为 CSV；筛选条件 MUST 反映在 URL 中。

#### Scenario: 筛选与 URL
- **WHEN** 管理员修改时间范围或厂商筛选
- **THEN** 图表与表格更新，URL query 同步变化，刷新后筛选保持

#### Scenario: 空范围
- **WHEN** 所选范围内没有请求
- **THEN** 图表区显示「所选时间内没有请求」的空态

#### Scenario: CSV 导出
- **WHEN** 管理员点击导出
- **THEN** 下载的 CSV 行与当前汇总表一致，包含表头与筛选后的数据

### Requirement: R-PANEL-07 日志界面

日志页 SHALL 支持按时间、成功/失败、厂商、错误码筛选并分页；列表显示时间、request_id、成员、厂商、账号、耗时、状态与错误码；详情 MUST NOT 展示 OCR 原文或凭证。

#### Scenario: 筛选与分页
- **WHEN** 管理员选择失败状态并翻到第二页
- **THEN** 列表只显示失败记录，分页位置与 URL 同步

#### Scenario: 详情不含原文
- **WHEN** 管理员打开一条日志详情
- **THEN** 只显示元数据与错误码，不显示 OCR 原文或凭证

#### Scenario: 空结果
- **WHEN** 筛选条件没有匹配记录
- **THEN** 显示空态与清除筛选的入口

#### Scenario: 时间按本地时区显示
- **WHEN** 管理员查看日志或账号的最近使用时间
- **THEN** 时间按 `Asia/Shanghai` 展示，服务端的 UTC naive 时间不被当作浏览器本地时间

### Requirement: R-PANEL-08 设置界面

设置页 SHALL 分可编辑区与只读区：可编辑缓存开关、缓存 TTL、缓存容量、请求总预算、账号默认超时；只读展示鉴权状态、版本、上传限制、并发上限与会话时长；页面 MUST 展示配额模板与「以官网为准」免责声明。

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

### Requirement: R-PANEL-09 三态与重复提交

每个数据视图 SHALL 具备加载、空、错误三种状态；写操作提交期间 MUST 禁用按钮并防止重复触发；请求超时或网络失败 MUST 给出可恢复的错误提示。

#### Scenario: 加载态
- **WHEN** 页面数据尚未返回
- **THEN** 显示与最终内容同高的骨架，不出现布局跳动

#### Scenario: 请求失败
- **WHEN** 数据请求返回错误
- **THEN** 显示错误说明与重试按钮，点击重试重新请求

#### Scenario: 双击提交
- **WHEN** 管理员快速双击保存按钮
- **THEN** 只发出一次写请求，按钮在请求期间禁用

### Requirement: R-PANEL-10 视觉与响应式

面板 SHALL 使用浅色单主题与深墨蓝主色，采用发丝线分隔、留白与少量圆角，MUST NOT 使用渐变、卡片投影或装饰性背景；状态 MUST 以圆点加文字表达；配额进度 MUST 以带刻度标尺呈现；窄屏 MUST 保持可用。

#### Scenario: 桌面布局
- **WHEN** 视口宽度不小于 1280px
- **THEN** 显示左侧导航、顶栏与内容区，表格数字右对齐

#### Scenario: 窄屏表格
- **WHEN** 视口宽度小于 768px
- **THEN** 表格横向滚动且关键列仍可读，页面不出现横向溢出

#### Scenario: 减少动效
- **WHEN** 系统启用 `prefers-reduced-motion`
- **THEN** 页面过渡与动效被关闭

#### Scenario: 可读性
- **WHEN** 检查正文、次要文字与状态
- **THEN** 文字对比度不低于 4.5:1，状态不单独依赖颜色表达

### Requirement: R-PANEL-11 同源托管与回退

网关 SHALL 在面板构建产物存在时同源托管 SPA 与静态资源；对非 API 且无文件扩展名的未知路径 MUST 回退到入口 HTML；对 `/api/*`、`/v1/*`、`/healthz` 的未知路径 MUST 返回 JSON 404，不得被回退吞掉；非 API 但带扩展名且文件不存在的请求 MUST 返回 404 JSON，不得回退成 HTML；产物缺失时 MUST 明确提示且不影响公共与管理 API。`[spec-review-amendment R-13]`

#### Scenario: 根路径
- **WHEN** 构建产物存在且访问 `/`
- **THEN** 返回面板入口 HTML

#### Scenario: 深链接刷新
- **WHEN** 管理员直接访问 `/accounts` 并刷新
- **THEN** 返回入口 HTML，面板路由渲染账号页

#### Scenario: API 404 不被吞
- **WHEN** 访问不存在的 `/api/admin/not-exist`
- **THEN** 返回 JSON 404，而不是入口 HTML

#### Scenario: 缺失静态资源
- **WHEN** 访问不存在的 `/assets/not-exist.js`
- **THEN** 返回 404 JSON，不返回入口 HTML

#### Scenario: 深链接入口
- **WHEN** 访问 `/accounts` 且构建产物存在
- **THEN** 返回入口 HTML

#### Scenario: 产物缺失
- **WHEN** 构建产物不存在且访问 `/`
- **THEN** 返回明确的未构建提示，`/healthz` 与 `/v1/ocr/image` 仍正常

### Requirement: R-PANEL-12 前端安全与数据最小化

面板 MUST NOT 把管理员 token、账号凭证或 API Key 明文写入 localStorage、sessionStorage 或 URL；登录后的写请求 MUST 携带 CSRF 头；面板入口、静态资源与所有返回入口 HTML 的深链接响应 MUST 带 CSP，所有响应 MUST 带 `X-Content-Type-Options`、`Referrer-Policy` 与 frame 限制头；CSP MUST NOT 允许内联脚本，且 MUST NOT 阻断既有 `/docs`。`[spec-review-amendment R-36]`

#### Scenario: 不持久化敏感值
- **WHEN** 管理员登录并创建 Key
- **THEN** 浏览器持久化存储中不存在管理员 token、凭证或 Key 明文

#### Scenario: 写请求带 CSRF
- **WHEN** 面板发起创建、修改或删除请求
- **THEN** 请求包含与 CSRF cookie 一致的 `X-CSRF-Token`

#### Scenario: 安全响应头
- **WHEN** 请求面板入口或任意返回入口 HTML 的深链接
- **THEN** 响应包含 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy` 与 frame 限制头

#### Scenario: API 安全头
- **WHEN** 请求管理 API
- **THEN** 响应包含 `X-Content-Type-Options: nosniff`、`Referrer-Policy` 与 frame 限制头

#### Scenario: 文档页不被阻断
- **WHEN** 浏览器打开 `/docs`
- **THEN** Swagger UI 正常加载，不被 CSP 拦截

#### Scenario: 内联脚本被禁
- **WHEN** 检查面板 CSP 的 `script-src`
- **THEN** 不包含 `'unsafe-inline'`
