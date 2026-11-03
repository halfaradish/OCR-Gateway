---
ship-gate:
  code_review: pass
  reviewed_sha: d66e89dceed1509ff74c6d89558e1f63cf9bc78688b2c77f4b044bb41b1b474c
  reviewed_manifest: MTAwNjQ0IGJsb2IgYjU3NWViMDEwYTVlYzYzOThhM2UxYTQ1ZmRkYmFhZDBmM2YxNTQ3MwkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIGY0YTliOWUzNjhlM2YwZGU3YjgwNDUxNGYwMTIzODJhM2UyZDBiY2YJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIDI4MzM3ZTViZDU3N2M1OWE3N2UwM2Q1MWY2ZmQyNjQxNGU1NzY1NmMJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiA0NjY2NzdmNDU3YTEyYjU4MWM0MTE0ODJkM2VkMTk0MzE0MjYyNTk5CUFHRU5UUy5tZAAxMDA2NDQgYmxvYiAwZmQ0ZmEyMjFmMzE2ZWQyNDM1YTdjZDMwMjhhYzNhYjU1YTA4Yzc1CURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgMTVkMjRjOWUyM2IzM2VmMGUxNDRmNDgzNTkyMDQ2YTRmMTllYjFhNglSRUFETUUubWQAMDQwMDAwIHRyZWUgNjE0MzEwMWI1MDhmY2MwMDZiODRlNjVhNzZkNzQ5YTI5NjQ5YWU4OQliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIDAzYjljNzU0MmI0MTk4ZjBlY2Y1MWJjNGFiNmQ1NGVjZGEyY2RjMzYJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDZhMDdhNTdjNTRiYmVhOGUxNGZhNzY0YjhmNzc2OGEwYzVlZjhhNmQJZG9jcw==
---
# 代码审报告 · docker-deploy-e2e

> ⚠️ 单 session 自查：实现者与审阅者为同一上下文；同模型、不同上下文，非独立评审。
> dispatch: single-session
完成度来源: tickets.md

## 结论

pass（自动修复 1 项 + defer 1 项；无阻塞交付的 Critical）

## scope 审计

diff base `2a549d1`（`base_resolve.py --field merge-base`），被审范围 `2a549d1..7e21293`。

| # | 类型 | 证据 | 严重度 |
|---|---|---|---|
| — | scope-drift | 未发现出圈改动：代码/配置改动 = `Dockerfile`、`.dockerignore`、`docker-compose.yml`、`docker/entrypoint.sh`、`README.md`、`.env.example`、`backend/tests/test_ticket5_api.py`，与 `proposal.md` 的 What Changes / Impact 一致；`backend/app/**` 业务逻辑、schema、公共 API 契约无改动；未实现 Non-Goals（反代/多实例/完整加固/管理面板） | — |
| — | 切片偏离 | `impl-reports/planning-decisions.md` 声明「无偏离」；实际 diff 与 S1–S5 划分、阻塞边一致，未发现静默偏离 | — |

| 票 | 五态 | 证据 |
|---|---|---|
| 1 镜像构建层 | DONE | checkpoint `6f763e2` + `impl-reports/task1-image-build.md` 验收表（构建/上下文/导入/无 dev/凭证扫描/tag） |
| 2 启动契约 | DONE | checkpoint `97fecb0` + `task2-startup-contract.md`（空卷迁移/失败/幂等/缺配置/多 worker/任意 CWD） |
| 3 编排与运行身份 | DONE | checkpoint `cb1484f` + `task3-compose-run-identity.md`（健康/非 root/权限/自愈/持久化） |
| 4 文档与配置面 | DONE | checkpoint `a93ae13` + `task4-docs-config.md`（README/.env.example/文档测试/全量回归） |
| 5 真机端到端 | DONE | checkpoint `2620307` + `task5-e2e-acceptance.md` + `e2e-acceptance.md`（冷启动/三输入/缓存/配额/不回退/auto） |
| 6 实现验证 | DONE | checkpoint `751f1e5` + `task6-implementation-verify.md`（聚合套件 152 passed） |

## Spec 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| 1 | compose 主路径 `docker compose build` 只产出 `ocr-gateway:0.1.0`，不产出 `latest`；design Q3=A 要求 `0.1.0` + `latest` 两个 tag | Minor | `docker-compose.yml:5-9`（修复前 build 段无 `tags:`）；实测 `docker images ocr-gateway` 曾出现 `latest` 指向旧镜像（`769d8a26` vs `985e2871`） | 采纳 → 自动修 |
| 2 | 本地私有凭证文档名出现在已跟踪的 spec 期产物（`proposal.md`、`spec-review-report.md`、`review/design-gate.html`）与更早 commit 历史中；用户明确要求不暴露该名称 | Important | `proposal.md:12`；`spec-review-report.md` 正文；`review/design-gate.html` 内嵌报告文本；`git log` 历史 | defer → T3（无法在不改写历史的前提下彻底消除，需人决定） |

## Standards 轴

无新增问题（base CR-01..12 + `domains/backend.md` CR-BE-01..03 逐条过）：

- 改动文件里唯一的 Python 改动是 `backend/tests/test_ticket5_api.py` 的断言追加（3 行），
  未删除/放宽既有断言，未加 skip/xfail（CR-12 通过）；新断言确定、无外部依赖（CR-09 通过）。
- `docker/entrypoint.sh`：`set -eu`；迁移失败即退出（CR-01/02）；变量全部加引号（CR-10）；
  日志不含密钥（CR-07）。
- `Dockerfile`：构建参数经引号插值，索引可参数化；`--frozen` + `--no-emit-project` 与 ADR-0001 一致；
  未发现密钥落层。
- `docker-compose.yml`：健康探测只用标准库；`restart`/`stop_grace_period`/`json-file` 轮转齐备；
  `DATABASE_URL` 置空语义已验证。

## 自动修

- [impl-review-fix] `docker-compose.yml` 的 build 段新增 `tags: [ocr-gateway:0.1.0, ocr-gateway:latest]`，
  使 compose 主路径也满足 design Q3=A 的双 tag 约定。实测：`docker compose config` 通过；
  `docker compose build` 后 `docker image inspect` 返回两个 tag 且指向同一 image。
  复审第 1 轮（限定该修复 diff）：YAML 合法、行为无副作用、无新增风险，干净。

## defer 台账

<!-- sdflow-lite:defer-ledger -->
| ID | 问题 | 去向 |
|---|---|---|
| T3 | 本地私有凭证文档名仍出现在已跟踪评审产物与 git 历史中（用户要求不暴露） | `openspec/issues/open/T3.md`（OPEN） |

## 既有问题

无（本 change 的改动未触发既有缺陷；`docs/` 下的私有凭证文档已移出仓库，文件内容未进仓）。

## 已裁掉（dismissed）

| # | 位置 | 理由 |
|---|---|---|
| 1 | `docker/entrypoint.sh:14` | 每次启动 `chown -R` 数据目录在数据量大时会变慢；当前规模（SQLite 数 MB）代价可忽略，且是 Q1=A 的必要步骤。 |
| 2 | `Dockerfile` 运行阶段 | venv 内保留 pip（约 10MB）；镜像仍远低于 400MB 预算，删除收益低、会破坏标准 venv 形态。 |
| 3 | `docker-compose.yml:17-20` | `.env` 中的 `UV_DEFAULT_INDEX` 会经 `env_file` 进入运行期环境；非密钥、无行为影响（构建参数已单独经 `build.args` 传入）。 |
| 4 | `.dockerignore` | `!.env.example` 反向包含示例文件；该文件不会进入镜像（无 COPY），保留便于将来 COPY 时排除真实 `.env`。 |
| 5 | `docker/entrypoint.sh:12` | 若有人直接 `docker run -e DATA_DIR=/` 会 `chown -R` 根文件系统；属误用路径，compose 的 `environment` 已固定 `/data`，不为低概率误用加守卫。 |

## 诚实边界

单 session 自查（实现与审阅同上下文）；引文与语义对应无机械核验。scope 审计、领域镜、2 面对抗镜
（运行期权限/信号路径、编排/构建边缘）与历史镜判据均在本 session 内完成；历史镜因「无 rename 且
无既有文件 ±≥200 行」按判据跳过。机械检查（ruff/mypy/pytest/构建）结果见各票 impl-report。
