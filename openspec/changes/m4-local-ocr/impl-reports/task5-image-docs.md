---
ticket: 5
title: 镜像、文档与集成验收
head: fcbdfab7fc5ad0b364619d45a06e0d1e53ee3adb
status: DONE
suite_scope: {"domains":["backend","docs","frontend"],"layers":["unit","quality"],"base":"fcbdfab","mode":"closeout"}
---

# Task 5 · 镜像、文档与集成验收

## 改动

- **镜像**：`Dockerfile` 依赖层改为 `uv export --extra local`（两个索引分支都带），并加
  `/app/.venv/bin/python -c "import rapidocr, onnxruntime"` 构建期校验；runtime 阶段安装
  `libgomp1`（onnxruntime 在 slim 上的常见依赖），新增 `ARG APT_MIRROR=` 以支持离线 Debian
  镜像（compose/`.env.example` 同步）。
- **版本**：`backend/app/__init__.py`、`frontend/package.json` 升 `0.3.0`（`pyproject.toml` /
  `uv.lock` 已在 Task 1 升）；compose image/build.tags 改 `ocr-gateway:0.3.0`；README 版本锚与回滚段
  更新为 0.3.0 → 0.2.1（含 `alembic downgrade -1` 与 `--entrypoint` 覆盖）。
- **文档**：README 移除「不做本地 OCR」，新增「本地 OCR」节（依赖/模型/开关/路由/配额/观测/镜像
  体积/回滚/冒烟），环境变量表补 5 个 `LOCAL_OCR_*` 与 `APT_MIRROR`，开发步骤补 `--extra local`，
  公共 API provider 说明改为含 local；`docs/tech-selection.md` 移除 `/local-ocr/download`、
  ModelScope/HuggingFace 下载、`data/models/`、`local_ocr_max_concurrency` 设置键等旧表述；
  `.env.example` 补默认值。
- **验收工具**：新增 `backend/tests/test_m4_ticket5_bench.py`（2000px 截图 30 次 p95）与
  `scripts/smoke_local_ocr.py`（起临时 0.3.0 容器：ready → 显式 local → auto 兜底 → 关闭 403）。
- **e2e script**：`frontend/package.json` 增 `e2e:local` 入口。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| 全量 pytest | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 0 | 252 | fcbdfab |
| slow 套件（真实引擎/p95 基准） | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q -m slow` | 0 | 6 | fcbdfab |
| 前端质量门 | `pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend build && echo "frontend quality gates passed: 3"` | 0 | 3 | fcbdfab |
| ruff | `backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests scripts/smoke_local_ocr.py` | 0 | 未知 | fcbdfab |
| mypy | `cd backend && .venv/Scripts/python.exe -m mypy app` | 0 | 未知 | fcbdfab |
| 镜像构建 | `docker build -t ocr-gateway:0.3.0 --build-arg UV_DEFAULT_INDEX=<清华> --build-arg NPM_REGISTRY=<npmmirror> --build-arg APT_MIRROR=<清华> .` | 0 | 未知 | fcbdfab |
| 镜像 import | `docker run --rm --entrypoint python ocr-gateway:0.3.0 -c "import rapidocr, onnxruntime"` | 0 | 1 | fcbdfab |
| 镜像冒烟 | `backend/.venv/Scripts/python.exe scripts/smoke_local_ocr.py --port 18080` | 0 | 4 | fcbdfab |
| 离线启动/就绪 | `docker run --network none ...` + `docker exec ...` 登录取 status 到 `ready` | 0 | 1 | fcbdfab |
| 回滚演练 | 0.3.0 镜像 `--entrypoint alembic ... downgrade -1`（含一条 local 行）→ 用 tag `0.2.1` 构建的镜像启动并读 `/healthz` | 0 | 2 | fcbdfab |

p95 实测：同一 2000×1000 截图 30 次，两次运行分别 **492ms / 563ms**（≤3s）。镜像冒烟输出：
`explicit local: local quota.used=0`、`auto fallback: local`、`disabled local: 403`。回滚演练后
`usage_events.provider` 由 `local` 变为 `auto`，`alembic_version=7c1f0d2a9b31`；用 tag `0.2.1`
构建的镜像在该库上 `/healthz` 返回 `{"status":"ok","db":"ok","version":"0.2.1"}`。

## concerns

- **镜像体积**：0.3.0 为 559MB，较 0.2.0（226MB）增加约 333MB；`/app/.venv` 432MB。design 的
  NFR 写的是「下载约 110–130MB / 安装后约 350MB（估算，实施后回填）」；本票在 README 回填了实测
  值，但**未改 design.md**——design 已过人类设计门并写锚，事后改会让锚失鲜，需走重审流程。若人认为
  需要把实测值写回 design，请在设计门/后续 change 处理。
- **libgomp1 与 APT_MIRROR**：slim 基础镜像不含 `libgomp1`，本环境直连 `deb.debian.org` 超时，
  构建需要 `APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn`。该参数默认空（走上游源），不改变
  普通环境的构建行为。
- **离线验证范围**：`--network none` 容器验证了「启动 + 开启 + 预热到 ready」，未在该容器内做
  图片识别（无网络但未 `docker cp` 图片）；带网络的镜像冒烟已经做了真实识别、auto 兜底与 403。
- **`rapidocr` 无 `__version__`**：构建期 import 校验只断言两个包可导入，不打印版本。
- **全量 `admin.mjs` e2e 仍依赖外部种子（「Ming」）**：本票未生成该种子；本地 OCR 的 e2e 在
  Task 4 用独立 `local-ocr.mjs` 覆盖（13 项）。两者不冲突，待有种子数据时可一并跑。
