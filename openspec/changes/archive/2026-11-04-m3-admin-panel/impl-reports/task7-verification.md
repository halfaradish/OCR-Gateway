---
ticket: 7
title: 实现验证
head: 4df8684d1f3faa1c6c9e7b2060980994809c6f3e
status: DONE
suite_scope: {"hit_domains":["backend","docs","frontend"],"layers":["unit","quality"],"base":"bbeda41","mode":"closeout"}
---

# Task 7 · 实现验证

## 改动

本票不新增产品代码：运行本 change 命中域的全部层聚合套件并核对结果。

- 命中域（`suite_scope.py --base bbeda41 --head HEAD --mode closeout`）：`backend`、`frontend`、`docs`。
- 层集（照抄 `suite_scope.py --json`，MUST NOT 手抄）：`unit` → `uv run --project backend pytest
  backend/tests`；`quality` → `pnpm --dir frontend lint && pnpm --dir frontend typecheck &&
  pnpm --dir frontend build`。`docs` 域无层（只有 README/AGENTS 变更，不跑测试）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| unit | `uv run --project backend pytest backend/tests` | 0 | 214 passed, 2 skipped, 1 deselected | 4df8684 |
| quality | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build` | 0 | 未知 | 4df8684 |

聚合结果说明：

- 两个层均通过，且 SHA 一致（`4df8684`）。
- `unit` 的 1 条 deselected 是 `slow` 基准（`-m "not slow"` 默认排除），已在 Task 6 以
  `uv run --project backend pytest -m slow -q` 单独跑过（1 passed）。
- 本 change 声明的 e2e（浏览器冒烟）不属于 `suite_scope` 的自动层；Task 4/5/6 已分别执行
  smoke（14 checks）、admin（32 checks）、visual（6 checks），证据在 `review/e2e-task*/`。
- 交付前逐条核对：Tasks 1–6 的验收标准全部勾选并有对应报告；既有红测（README 缺 `sqlite3`）
  已在 Task 6 修复，`unit` 层现在全绿。

## concerns

- 聚合层不含 e2e：浏览器冒烟依赖真实 Chrome 与一个可登录实例，未纳入 `sdflow-lite.json` 的自动层，
  以票据报告与截图作为证据；这是有意的取舍（避免收尾门依赖 GUI 环境）。
- `quality` 层没有用例计数（lint/typecheck/build 只有通过/失败），报告写「未知」。
