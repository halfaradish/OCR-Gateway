<!-- sdflow-lite:init:start —— 由 sdflow-lite-init 维护，勿手改本区块 -->
## sdflow-lite 规格驱动工作流（SDD）

本项目铺设了 sdflow-lite 工作流（OpenSpec spec-driven）。变更入口：

- 产 spec（澄清 → 拷问 → 四件套 + decision-memo）：`/sdflow-lite-spec`
- 设计审 + 人类拍板（两个人类门之一：设计拍板）：`/sdflow-lite-review`
- 代码审（可独立调用，或由 ship 按 gate 派发）：`/sdflow-lite-code-review`
- 驱动到 merge（gate 台账：出票 → 实现 → 代码审 → verify → 归档）：`/sdflow-lite-ship {change}`
- 铺设/重铺本工作流：`/sdflow-lite-init`

判官脚本：`ship_gate.py`（盘面即状态，只读零副作用；随 skill 安装，位于
`<skills 安装根>/sdflow-lite-ship/scripts/`）。
报告锚：`spec-review-report.md` / `code-review-report.md` / `verify-report.md` 头部
`ship-gate:` frontmatter（`design_approved` / `code_review` / `verify`），MUST 由
`anchor_writeback.py` 写入，MUST NOT 手写。
<!-- sdflow-lite:init:end -->

## 本地私有凭证文档约定

任何被跟踪文件（文档、报告、注释、提交说明）提及本机私有凭证文档时，一律使用
「仓库外的本地私有凭证文档」代称；MUST NOT 写出其具体路径或文件名。
历史提交中已存在的具体名称不作追溯处理（人 2026-11-03 拍板）。
