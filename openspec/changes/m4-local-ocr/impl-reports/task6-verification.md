---
ticket: 6
title: 实现验证
head: 249fd4977552230523f83a726e0f713d2caec89b
status: DONE
suite_scope: {"domains":["backend","docs","frontend"],"layers":["unit","quality"],"base":"ca748fa","mode":"closeout"}
---

# Task 6 · 实现验证

## 改动

- 无源码改动；本票只运行本 change 命中域（backend / docs / frontend）的聚合套件并汇总前五票的证据。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| unit（backend） | `uv run --project backend pytest backend/tests` | 0 | 252 | 249fd49 |
| quality（frontend） | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build && echo "frontend quality gates passed: 3"` | 0 | 3 | 249fd49 |

层集来自 `suite_scope.py --mode closeout`（base `ca748fa` → HEAD）；`docs` 域无自动化层。

## 附加证据（非 suite_scope 层，来自各票报告）

- **slow/真实引擎**：`pytest backend/tests -q -m slow` → 6 passed；p95 492ms / 563ms（30 次，2000×1000）。
- **前端 e2e**：`node frontend/e2e/local-ocr.mjs` → 13 项通过（含状态慢时设置可编辑、骨架、错误+重试、starting→ready、刷新保持、480px）。
- **镜像冒烟**：`scripts/smoke_local_ocr.py` → ready / 显式 local quota=0 / auto 兜底 local / 关闭后 403。
- **离线容器**：`--network none` 启动 → 开启开关 → `ready`（PP-OCRv6，installed=true）。
- **回滚演练**：0.3.0 镜像 `downgrade -1` → local 行变 auto、revision `7c1f0d2a9b31`；tag `0.2.1` 镜像在该库上 `/healthz` = ok/0.2.1。

## 既有红测

无。全量 unit 为 252 passed、2 skipped（既有 contract 测试，需本机私有凭证）、6 deselected（slow）。

## concerns

- **defer 台账**：`openspec/issues/open/` 中没有 `source_change: m4-local-ocr` 的条目（现有 T1–T5 均属于更早的 change），本 change 无待关单项。
- **全量 `admin.mjs` e2e**仍依赖外部种子（「Ming」）；本票用 `local-ocr.mjs` 覆盖本 change 的 e2e 场景，未伪造种子。
- **镜像构建/冒烟是本地 Docker 证据**（0.3.0 559MB、0.2.1 从 tag 重建），未 push 镜像；发布步骤仍需按 README 的版本锚执行。
