---
ship-gate:
  verify: PASS
  reviewed_sha: d66e89dceed1509ff74c6d89558e1f63cf9bc78688b2c77f4b044bb41b1b474c
  reviewed_manifest: MTAwNjQ0IGJsb2IgYjU3NWViMDEwYTVlYzYzOThhM2UxYTQ1ZmRkYmFhZDBmM2YxNTQ3MwkuZG9ja2VyaWdub3JlADEwMDY0NCBibG9iIGY0YTliOWUzNjhlM2YwZGU3YjgwNDUxNGYwMTIzODJhM2UyZDBiY2YJLmVudi5leGFtcGxlADEwMDY0NCBibG9iIDI4MzM3ZTViZDU3N2M1OWE3N2UwM2Q1MWY2ZmQyNjQxNGU1NzY1NmMJLmdpdGlnbm9yZQAxMDA2NDQgYmxvYiA0NjY2NzdmNDU3YTEyYjU4MWM0MTE0ODJkM2VkMTk0MzE0MjYyNTk5CUFHRU5UUy5tZAAxMDA2NDQgYmxvYiAwZmQ0ZmEyMjFmMzE2ZWQyNDM1YTdjZDMwMjhhYzNhYjU1YTA4Yzc1CURvY2tlcmZpbGUAMTAwNjQ0IGJsb2IgMTVkMjRjOWUyM2IzM2VmMGUxNDRmNDgzNTkyMDQ2YTRmMTllYjFhNglSRUFETUUubWQAMDQwMDAwIHRyZWUgNjE0MzEwMWI1MDhmY2MwMDZiODRlNjVhNzZkNzQ5YTI5NjQ5YWU4OQliYWNrZW5kADA0MDAwMCB0cmVlIGE2YjJmYTlhNTFjZmNjNDU5OWI2NDI5ODVjNTM5MDQ5NmU2Y2ExZGYJZG9ja2VyADEwMDY0NCBibG9iIDAzYjljNzU0MmI0MTk4ZjBlY2Y1MWJjNGFiNmQ1NGVjZGEyY2RjMzYJZG9ja2VyLWNvbXBvc2UueW1sADA0MDAwMCB0cmVlIDZhMDdhNTdjNTRiYmVhOGUxNGZhNzY0YjhmNzc2OGEwYzVlZjhhNmQJZG9jcw==
---
# 需求核对 · docker-deploy-e2e

> ⚠️ 单 session 自证：测试由主 session 触发；同模型、不同上下文，非独立验证。
> 证据: verify-evidence-closeout.json @ base=2620307 head=4ee0da1（归档提交，含代码审修复）；
> verify-evidence-retest.json @ base=2620307 head=87eac81（归档前、代码审修复后的重跑）

核对口径：不信任复选框与既有报告措辞，逐条对照 `tasks.md`、`specs/deployment/spec.md`（R-DEP-01..08）
与 delta 引用的既有能力需求（R-ADM/R-API/R-CAC/R-QTA/R-SCH）；每条 ✅ 附可机验锚点。

## 变更要求（deployment delta）

| 需求 | 判定 | 锚点 | 证据 |
| --- | --- | --- | --- |
| R-DEP-01 启动期自动迁移 | ✅ | `docker/entrypoint.sh:15-19`；`Dockerfile:64-67` | entrypoint 先 `alembic -c /app/alembic.ini upgrade head` 再 `exec uvicorn … --workers 1`；`test-e2e` 空卷启动日志含 `Running upgrade -> 01b12c86bd76`；只读空卷启动 exit=1 且无监听行（task2 报告） |
| R-DEP-02 健康状态可被编排消费 | ✅ | `docker-compose.yml:28-43` | healthcheck 用镜像内 Python 标准库请求 `/healthz`（10s/3s/5/30s）；`docker inspect` → `healthy`（task3、e2e 记录） |
| R-DEP-03 配置与凭证只经环境注入 | ✅ | `backend/app/config.py:66-67,84-92`；`docker-compose.yml:15-21` | 缺/非法 `MASTER_KEY`、短 `ADMIN_PASSWORD` 均非零退出并抛 `ValidationError`（task2 报告）；compose 经 `env_file` 注入，镜像层无 `ENV MASTER_KEY` |
| R-DEP-04 镜像与上下文不含凭证 | ✅ | `.dockerignore:2-19`；`Dockerfile:60-65` | 上下文探针：`backend/.venv`/`tests`/`docs`/`openspec`/`.git` 均不可 COPY；镜像层扫描 `change-me-please` 0 次、历史无 `ENV MASTER_KEY/ADMIN_PASSWORD`；仓库内真实凭证值 0 命中（task1 报告 + 本次 diff 扫描） |
| R-DEP-05 数据持久化 | ✅ | `docker-compose.yml:20-25`；`backend/app/config.py:89-92` | `DATA_DIR=/data`（绝对路径）+ `./data:/data` 卷；建成员后 `down`/`up -d` 仍可查到（task3 报告）；`DATABASE_URL` 置空强制推导 |
| R-DEP-06 单实例约束 | ✅ | `backend/app/config.py:108-130`；`docker/entrypoint.sh:19` | `WEB_CONCURRENCY=2` 启动 exit=3、日志含「单实例约束」（task2 报告）；uvicorn 显式 `--workers 1` |
| R-DEP-07 构建可复现且索引可参数化 | ✅ | `Dockerfile:3,17-33,40-42`；`openspec/adr/0001-…md` | `uv export --frozen --no-emit-project` → 38 个锁定版本与镜像内 `pip list` 逐项一致；可达索引构建成功、无索引构建失败；`backend/uv.lock` 在 `2a549d1..HEAD` 无改动 |
| R-DEP-08 运行身份与自愈 | ✅ | `Dockerfile:55-58`；`docker/entrypoint.sh:9-13`；`docker-compose.yml:26-27,45-48` | 主进程 uid=10001（`docker top`），`/data` 文件属主 10001；`RestartCount` 0→1 后重新 healthy；`json-file` + `max-size/max-file`、`stop_grace_period: 25s` |

## 引用需求（由既有能力拥有，本 change 真机验证）

| 需求 | 判定 | 锚点 | 证据 |
| --- | --- | --- | --- |
| R-ADM-02 成员管理 / R-ADM-03 Key 管理 / R-ADM-04 账号管理 | ✅ | `backend/app/api/admin.py:161-345` | e2e 5.2：登录→建成员→建 Key（明文仅一次，prefix `ocr_VIIIakyZ`）→建百度/腾讯账号→`GET /accounts` 无明文（`e2e-acceptance.md`） |
| R-API-01 单张图片识别 / R-API-02 三种输入 | ✅ | `backend/app/api/public.py:59-140,192+` | e2e 5.3：multipart/base64/`image_url` 三次均 200，`text` 非空、`lines` 4 项，provider=baidu（含清缓存冷调） |
| R-CAC-01 缓存键与命中 | ✅ | `backend/app/api/public.py:216-241` | e2e 5.4：同图同参第二次 `cached=true`、`quota.used=0`、`latency_ms=829` |
| R-QTA-01 成功请求记账 / R-QTA-05 日志不落原文 | ✅ | `backend/app/api/public.py` 记账段；`backend/app/api/admin.py:495,536` | e2e 5.5：usage summary `baidu requests=8 success=7 …`、`tencent requests=1`；logs 行内无 `text` 字段 |
| R-SCH-03 故障切换 / R-SCH-05 显式不回退 | ✅ | `backend/app/scheduler.py`（既有，本 change 未改） | e2e 5.6：`provider=baidu` 无账号 → HTTP 503 `PROVIDER_UNAVAILABLE`；5.7：`provider=auto` → `provider=tencent` |

## 收尾票证据核对

- `impl-reports/task6-implementation-verify.md`：`check_impl_report.py` 通过；`## 验证` 表头逐字合规；
  层集来自 `suite_scope.py --mode closeout`（`unit`）。
- 通过行用例数 152（非 0，无 ZERO-RUN）；收尾票仅一条通过行 ⇒ SHA 一致性平凡成立（`2620307`）。
- `verify_runner` closeout：exit 0、`ok=true`、`clean_tree=true`、`unit 152 passed @ f447a77`。
- 代码审自动修后 `git diff 2620307..HEAD` 含非 `openspec/` 路径（`docker-compose.yml`）⇒ 已跑
  retest：exit 0、`ok=true`、`unit 152 passed @ 87eac81`。

## Minor / 豁免

- 无 Minor 缺口。
- 归档前 delta 核对：`delta-sync.json`（pre-archive）`ok=false`，原因是 `deployment` 为**新能力**、
  `openspec/specs/deployment/spec.md` 尚未存在——主 spec 由随后 `openspec archive` 同步生成；
  归档后已重跑核对并置 `ok=true`（见归档提交）。
- 证据重生成：首次 closeout 以 `--head HEAD` 运行，证据 `head` 字段记录了字面量 `HEAD`，被 gate 判
  非法；遂在归档提交（`4ee0da1`）上重跑 closeout 并把 `head` 写为实际 SHA；retest 证据保留其运行
  SHA（`87eac81`）并同步修正 `head` 字段。两次运行均为真实执行（unit 152 passed）。

## 结论

`verify: PASS`（closeout 与 retest 均通过；tasks.md 28/28 已对账）。
