# Proposal

> 本 change 为已完成视觉改版的补记（2026-11-04），不改变任何 API 或运行时行为。

## Why

M3 面板落地后暴露出五个视觉问题：所有模块重量相同、顶部指标区不构成首屏看板、模块内信息分组边界模糊、留白缺少疏密对比、次要文字噪声干扰主线。同时 D-A6「蓝色只给操作、焦点与图表」在近白纸面 `#F7F9FB` 上几乎不可见，淡蓝主题无法成立。管理员于 2026-11-04 选择「淡蓝纸面 + 深蓝导航轨」方向，本 change 补记这次改版并修订对应规格。

## What Changes

- 主题：纸面改为雾蓝 `#EDF2F7`，左侧导航改为深藏青 `#10334F`，总览新增雾蓝指标带；修订 D-A6 的蓝色使用规则——蓝色承担结构（导航、指标带、选中与焦点），数据本身仍用 ink/navy。
- 层级：每页至多一个白色主面板承载主要操作；其余模块回到纸面，以字号和间距分层，不再用同规格卡片切割。
- 总览：新增首屏指标带（44px 主数字加三项读数），账号配额成为唯一主面板，厂商区改为紧凑账本表。
- 分组：账号与日志的筛选并入表格面板工具栏；用量筛选改为纸面上的上下细线工具带；成员选择表收紧，Key 面板独立成主面板。
- 降噪：删除顶栏常驻提示、概览页脚中点串、重复计数与重复厂商副标题；移动端指标带改为 2×2，抽屉补回登出入口。
- 登录页：桌面改为深藏青分屏，移动端保留深藏青品牌带。
- 组件：新增 `section`、`watch-band`、`segmented`、`filter-bar`，移除 `metric-strip`；`index.css` 更新调色板与字号阶。

## Success Metrics

- 视觉层级 — 基准：区块标题与间距同质 → 目标：总览首屏主数字 44px、页面标题 30px、每页主面板唯一 → 观察方式：桌面与移动截图。
- 主题可见性 — 基准：纸面近白、蓝色仅出现在按钮与折线 → 目标：雾蓝纸面、深藏青导轨与雾蓝指标带贯穿所有路由 → 观察方式：截图与 CSS token。
- 交互回归 — 基准：既有 e2e 断言 → 目标：`smoke.mjs` 14 项与 `admin.mjs` 33 项全绿 → 观察方式：临时数据库副本上运行 e2e。
- 质量门 — 目标：`pnpm lint`、`pnpm typecheck`、`pnpm build` 全绿 → 观察方式：`sdflow-lite.json` 的 `frontend.quality` 层。

## Non-Goals

- 不改变任何 API、数据模型、配额与调度逻辑。
- 不引入深色主题、图表库替换或新的 UI 依赖。
- 不做组件级视觉回归测试；继续用 lint/typecheck/build 加浏览器 e2e 覆盖。
- 不调整路由与字段，只调整页面内模块层级与呈现方式。

## Compliance

- 修订并遵守 `openspec/specs/admin-panel/spec.md` 的 R-PANEL-10（视觉与响应式），delta 见本 change。
- 遵守 D-A6 的其余规则：无渐变、无投影、状态点加文字、配额刻度标尺、对比度不低于 4.5:1、尊重 `prefers-reduced-motion`。
- 遵守 `AGENTS.md`：任何被跟踪文件提及本机私有凭证文档时，只使用「仓库外的本地私有凭证文档」代称。
- 前端质量门沿用 `openspec/sdflow-lite.json` 的 `frontend.quality`（lint + typecheck + build）。

## Capabilities

### Modified Capabilities

- `admin-panel`: 更新 R-PANEL-10，把「浅色单主题」细化为雾蓝纸面、深藏青导航轨与每页单一主面板，并明确首屏指标带与移动端抽屉登出。

## Impact

- 代码：`frontend/src/index.css`、`frontend/src/components/*`、`frontend/src/pages/*`。
- 无后端、依赖、构建配置或运行时行为变化。
