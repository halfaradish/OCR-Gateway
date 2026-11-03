---
ticket: 3
title: 编排与运行身份（S3）
head: 97fecb0b6f52b579a0501aa1b68aa571e92139c8
status: DONE_WITH_CONCERNS
suite_scope: {"base": "2a549d1df780dfbaf675fdcfbe1ebab9d8d7d248", "head": "HEAD", "mode": "closeout", "domains_configured": true, "hit_domains": ["backend"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

## 改动

- 新增 `docker-compose.yml`：单服务、`127.0.0.1:8000` 回环映射、`env_file: .env`、
  `build.args.UV_DEFAULT_INDEX: "${UV_DEFAULT_INDEX:-}"`（构建期参数不经 env_file 注入）、
  `environment: DATA_DIR=/data` 与 `DATABASE_URL: ""`、`./data:/data` 卷、`restart: unless-stopped`、
  `stop_grace_period: 25s`、显式 `json-file` 日志驱动的 `max-size: 10m` / `max-file: "3"`；
  healthcheck 用镜像内 Python 标准库 `urllib.request` 请求 `/healthz`（`interval=10s`、`timeout=3s`、
  `retries=5`、`start_period=30s`）。
- `Dockerfile` 运行阶段创建 `app` 用户（uid/gid 10001）与 `/data` 目录。
- `docker/entrypoint.sh`：以 root 启动时 `mkdir -p "$DATA_DIR"` + `chown -R app:app`，随后
  `exec setpriv --reuid=app --regid=app --init-groups "$0"` 重新执行自身；降权后再迁移并启动 uvicorn。
  ⇒ 迁移与服务均以非 root 身份运行，`/data` 内产物属主为 app（避免 root 建库导致运行期写失败）。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 编排解析 | `docker compose config`（过滤敏感字段）→ `DATA_DIR=/data`、`DATABASE_URL=""`、build args、回环端口、卷、restart、stop_grace_period、json-file + max-size/max-file、健康探测四参数齐备 | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |
| 拉起与健康 | `docker compose up -d --build` → `docker compose ps` 显示 `Up … (healthy)`；`curl /healthz` 200 | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |
| 运行身份（主进程） | `docker top ocr-gateway -eo pid,user,uid,args` → `10001 10001 /app/.venv/bin/python … uvicorn … --workers 1`；`/data` 内 db/shm/wal 属主均 `10001 10001` | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |
| 权限错误检查 | `docker compose logs` 全量过滤 `permission/denied/traceback/error` → 无匹配；迁移与配额刷盘均无权限错误 | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |
| 持久化 | 经 `POST /api/admin/users` 建成员 `t3-persist` → `docker compose down` → `up -d` → `GET /api/admin/users` 仍返回该成员 | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |
| 自愈重启 | 容器内 `kill -TERM 1`（主进程退出）→ `StartedAt` 变更、`RestartCount=1`、状态 `running/healthy`、`/healthz` 200 | 0 | 未知 | 97fecb0b6f52b579a0501aa1b68aa571e92139c8 |

## concerns

- **`docker kill` 不触发重启（Docker 语义，非本应用问题）**：用 `alpine sleep` 对照实测，`docker kill`
  同样不重启（`RestartCount=0`）——Docker 把 CLI 主动 kill 视同人工停止；因此自愈验证改用容器内
  `kill -TERM 1` 使主进程自然退出，`RestartCount` 从 0→1、服务重新 healthy，证明 `unless-stopped`
  生效。人工 `docker stop`/`docker kill` 不重启是预期行为（避免与手动运维对抗）。
- **`docker compose exec … id -u` 显示 0**：容器配置的 USER 仍是 root（Q1=A 需要 root 起点完成属主
  修复与降权），`exec` 会话默认继承容器配置身份；R-DEP-08 的权威判据是「主进程身份」，已用
  `docker top` 验证为 10001。未在 compose 设 `user:`（会切断 root→chown→drop 的路径）。
- **Windows Docker Desktop 的 bind mount 属主修复可用**（design 的 A1 风险在本机未触发）：
  entrypoint 的 `chown -R app:app /data` 成功，db 文件属主 10001；Linux 宿主的 bind mount 权限仍未
  实测（目标态风险保留在 design 的 Risks）。
- 本地 `.env` 为验证用占位值（gitignored），Task 5 前需替换为真实厂商凭证。
