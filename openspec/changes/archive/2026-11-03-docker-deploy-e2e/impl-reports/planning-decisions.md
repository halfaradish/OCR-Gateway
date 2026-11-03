# 出票决策记录 · docker-deploy-e2e

> 由 `/sdflow-lite-ship` 相位一（出票）生成。本文件记录「承重约束 → 票」映射、切片采纳/偏离审计、
> 以及出票期的方案裁决。`tickets.md` 是唯一执行管线；本文件只作审计。

## 承重约束 → 票映射

来源：`decision-memo.md` 的 `## 承重约束`（C1–C8，全文已读）。

| 约束 | 内容要点 | 承载票 | 票内验收锚点 |
| --- | --- | --- | --- |
| C1 | 容器内可完成依赖安装（`uv.lock` 的 `files.pythonhosted.org` URL 不可直用） | Task 1 | 以可达索引为参数构建成功；安装版本与锁一致（38 个 `==`） |
| C2 | 迁移可用同一 `DATABASE_URL` 在任意 CWD 跑通且幂等 | Task 2 | 空卷建表；同卷二次启动无升级输出 |
| C3 | 应用导入期即要求凭证，缺则直接失败 | Task 2 | 缺/非法 `MASTER_KEY`、`ADMIN_PASSWORD` 时非零退出且日志含校验错误 |
| C4 | lifespan 不跑迁移，空数据卷首启必崩 | Task 2 | 空卷启动 `/healthz` 200 且五表存在；迁移失败不监听端口 |
| C5 | `DATA_DIR` 必须是绝对路径 | Task 3 | 编排解析出 `DATA_DIR=/data`、`DATABASE_URL` 为空 |
| C6 | 单 worker 约束在容器内成立 | Task 2 | `WEB_CONCURRENCY=2` 拒绝启动并报单实例约束 |
| C7 | 本机 Docker 可用且基础镜像可经 mirror 拉取 | Task 1 | 镜像构建成功、平台 `linux/amd64` |
| C8 | URL 输入验收需要公网可达图片 | Task 5 | 公网 `image_url` 输入 200 且 `text`/`lines` 非空 |

无「未映射的承重约束」。C1/C7 的可行性已在出票前实测（`python:3.12-slim` 本地 digest 与 design 固定值
一致；TUNA 索引 200；`uv export` 输出 38 个锁定项；容器内 `print` 可执行）。

## 切片采纳与偏离审计

`design.md`「切片与依赖」给出 S1–S5 五切片草图，本票集**默认采纳**：

| 票 | 对应切片 | 与草图关系 |
| --- | --- | --- |
| Task 1 | S1 镜像构建层 | 一致 |
| Task 2 | S2 启动契约 | 一致 |
| Task 3 | S3 编排与运行身份 | 一致 |
| Task 4 | S4 文档与配置面 | 一致 |
| Task 5 | S5 真机端到端验收 | 一致（依赖 S3、S4） |
| Task 6 | 实现验证收尾票 | 恒 1 张，覆盖全部功能票 |

- 切片偏离：无（未增/删/合并票、未改切片边界、未改阻塞边）。
- 阻塞边：1 → 2 → 3 → 4 → 5 → 6；与草图「S2←S1、S3←S2、S4←S3、S5←S3/S4」一致，收尾票覆盖 1–5。

## `T10-choice` 对抗复核

判定：**未触发**。三个必触发条件逐一排除：

1. `design.md` 含「切片与依赖」节（非合规缺席）⇒ 不触发；
2. 出票对草图无实质偏离（见上表）⇒ 不触发；
3. 切片草图与 `design.md` 正文无矛盾（S5 依赖 S3/S4，与正文「S5 真机端到端验收」的依赖声明一致）⇒ 不触发。

## 出票期技术核对（非方案裁决）

- `uv export --format requirements-txt` 与 `--format requirements.txt` 在 uv 0.13.6 下均可用（实测），
  票面接受 `tasks.md` 原写法；`--no-emit-project` / `--no-hashes` 均存在。
- `tasks.md` 的固定 digest `sha256:b18b261e...` 与本机 `python:3.12-slim` 镜像 digest 逐字一致，
  构建可用本地缓存。
- 包索引可达性实测：`https://pypi.tuna.tsinghua.edu.cn/simple/fastapi/` → HTTP 200。
