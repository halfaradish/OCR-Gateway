---
ticket: 6
title: 实现验证收尾（聚合套件）
head: df1ddead840eff2e555dffc62949daedbde05114
status: DONE
suite_scope: {"base": "8b634bb", "head": "df1ddead840eff2e555dffc62949daedbde05114", "mode": "closeout", "hit_domains": ["backend", "docs"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

# Task 6 实现报告 · 实现验证收尾（聚合套件）

## 改动

- 新增真实账号契约测试 `backend/tests/test_contract_real_accounts.py`（百度/腾讯各一条）：凭证只从本地环境变量读取，未配置时默认 skip；配置后走真实厂商并断言文本非空、记录延迟。
- `backend/pyproject.toml` 注册 `contract` marker，供 `pytest -m contract` 单独运行。
- 按 `suite_scope.py --mode closeout` 的命中域（backend + docs）与层集（unit）运行聚合套件；docs 域无自动测试层，README/`.env.example` 的运营段落由测试静态核对。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 聚合（单元+集成+e2e） | `uv run --project backend pytest backend/tests` | 0 | 139 | df1ddead840eff2e555dffc62949daedbde05114 |
| 静态检查 | `uv run --project backend ruff check backend` | 0 | 未知 | df1ddead840eff2e555dffc62949daedbde05114 |
| 类型检查 | `uv run --project backend mypy backend/app` | 0 | 未知 | df1ddead840eff2e555dffc62949daedbde05114 |

聚合套件结果：139 passed, 2 skipped（两条真实账号契约测试因未配置本地凭证而 skip）；0 failed；退出码 0。层集来自 `suite_scope.py --mode closeout`：`backend` 域 `unit` 层，命令 `uv run --project backend pytest backend/tests`；`docs` 域无测试层，未覆盖层不参与本表核验。

## 既有红测

无。

## concerns

- 真实百度/腾讯账号契约测试默认 skip（凭证仅本地，C9/D12）；本次未配置凭证，故 2 条 skip 如实记录，未把 skip 当通过。
- `docs` 域没有自动测试层；README 的关键命令/段落由 `test_run_docs_cover_quickstart_and_operations` 静态核对，未在真实反代/备份环境执行。
- 0ms mock 基准 p99 <20ms 已包含在聚合套件内（`test_gateway_overhead_p99_under_20ms`）。

## 票外发现

无。
