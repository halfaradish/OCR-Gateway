---
ticket: 1
title: 本地引擎与进程池
head: ca748fac03c88660081d1e46bc504b3f77ed2904
status: DONE
suite_scope: {"domains":["backend"],"layers":["unit"],"base":"ca748fa","mode":"closeout"}
---

# Task 1 · 本地引擎与进程池

## 改动

- **依赖**：`backend/pyproject.toml` 增 optional extra `local`（`rapidocr>=3.10,<4`、`onnxruntime>=1.20`）并把项目版本升到 `0.3.0`；按 ADR-0002 用清华镜像重解析 `uv.lock`，把 1795 处源地址规范化回 `pypi.org` / `files.pythonhosted.org`；既有 53 个包版本 0 变化，新增 15 包；`uv lock --check --offline` 退出 0。
- **worker**（`backend/app/workers/local_ocr.py`，新）：模块级引擎懒加载；`worker_init` 清除 `MASTER_KEY`/`ADMIN_PASSWORD`；`warmup` 用含文字小图跑完整 pipeline 并断言非空；`run_ocr` 归一化为 `text` + `lines[{text,confidence}]`；不导入 `app.state`/`app.main`/`app.config`。
- **LocalEngine**（`backend/app/core/local_engine.py`，新）：`stopped/starting/ready/error/unavailable` 状态机；`multiprocessing.get_context("spawn").Pool` 可 terminate；warmup 超时、失败退避、generation 丢弃迟到回调、`set_enabled` 幂等、超时 terminate 整池并回 `starting`、崩溃/超时后重建、`is_available()`、`status()`（含 effective 值与脱敏 `last_error`）；错误类型 `LocalUnavailable(403)`/`LocalOcrError(502)`/`LocalTimeout(504)`/`LocalCancelled(503)`。
- **配置/装配**：`config.py` 增 5 个 `LOCAL_OCR_*` 默认值与范围校验；`state.py` 增 `local_engine` 字段；`main.py` lifespan 构造并 `start()`/`shutdown()`；`runtime_settings.py` 提前增 `local_ocr_enabled` 字段与 FIELD_RULES 文案（Task 4 再做热更新接线）。
- **测试**：新增 `backend/tests/test_m4_ticket1_local_engine.py`（fake pool 覆盖状态迁移/幂等/超时终止/兄弟取消/退避/重启恢复/worker 导入隔离/spawn context + 1 条 `slow` 真实引擎）；更新 `test_m3_ticket2_settings.py` 的 editable 期望加入 `local_ocr_enabled`。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 票级 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m4_ticket1_local_engine.py -q` | 0 | 10 | ca748fa |
| slow 真实引擎/真实池 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m4_ticket1_local_engine.py -q -m slow` | 0 | 4 | ca748fa |
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 224 | ca748fa |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests/test_m4_ticket1_local_engine.py` | 0 | 未知 | ca748fa |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | ca748fa |

## concerns

- 全量套件的 `2 skipped` 是既有 contract 测试（需本机私有凭证），`2 deselected` 是 `slow` 标记；本票已单独跑 `-m slow` 覆盖真实引擎。
- `multiprocessing.Pool` 的 worker 异常不会像 `ProcessPoolExecutor` 那样抛 `BrokenProcessPool`；异常路径按「结果永不 ready → 到 deadline 超时 → terminate 重建」处理，已在单测覆盖；真实池的超时终止与 2 并发已用 `slow` 测试覆盖（超时后子进程数不增长、两任务并行 <0.75s）。
- `LOCAL_OCR_ENABLED` 的运行时热更新尚未接线（`_apply_settings` 不调用 `set_enabled`），Task 4 补齐；本票只保证 lifespan 按启动值恢复。
- warmup 用 PIL 默认字体生成文字图；默认字体随 Pillow 分发，不依赖系统字体。
- `uv.lock` 的 URL 规范化只做 host 替换；ADR-0002 已记录「路径后缀需与 PyPI 一致」的残留风险，Task 5 在可达 PyPI 环境补 `uv sync --frozen` 或 HEAD 抽查。
