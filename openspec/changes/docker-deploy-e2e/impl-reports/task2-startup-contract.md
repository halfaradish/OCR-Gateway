---
ticket: 2
title: 启动契约（S2）
head: 5190a7d7c194fe3545181c33718112532def2b1d
status: DONE
suite_scope: {"base": "2a549d1df780dfbaf675fdcfbe1ebab9d8d7d248", "head": "HEAD", "mode": "closeout", "domains_configured": true, "hit_domains": ["backend"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

## 改动

- 新增 `docker/entrypoint.sh`：`set -eu` → `alembic -c /app/alembic.ini upgrade head` →
  `exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`。迁移失败即退出（不启动服务）；
  `exec` 使 uvicorn 成为主进程（后续权限模型可在此前置属主修复）。
- `Dockerfile` 运行阶段复制 entrypoint 并设为 `ENTRYPOINT`；入口点使用 venv 内的 console scripts
  （镜像 `PATH` 已指向 `/app/.venv/bin`），不依赖 PATH 中是否存在系统级 alembic/uvicorn。
- 迁移命令以 `-c /app/alembic.ini` 绝对路径执行，`%(here)s/alembic` 与 `env.py` 的
  `DATABASE_URL` → `DATA_DIR` 解析顺序保证任意 CWD 可用。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 构建 | `docker build --build-arg UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple -t ocr-gateway:0.1.0 -t ocr-gateway:latest .` | 0 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 空卷启动 | `docker run -d -p 127.0.0.1:18000:8000 -e MASTER_KEY=<32B> -e ADMIN_PASSWORD=<≥8> -v ocrgw_data_1:/data ocr-gateway:0.1.0` → `curl /healthz` 200；`docker exec ... python -c "sqlite3 … sqlite_master"` | 0 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 重复启动幂等 | `docker restart ocrgw-t2` → 日志无 `Running upgrade`，`/healthz` 200 | 0 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 迁移失败 fail-fast | 空卷只读挂载 `-v ocrgw_ro:/data:ro` 启动 → 容器退出、日志 `unable to open database file`、无 uvicorn 监听行 | 1 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 必填配置缺失/非法 | 分别不传 `MASTER_KEY`、传 `MASTER_KEY=short`、传 `ADMIN_PASSWORD=abc` → 三种均以非零码退出且含 `ValidationError` | 1 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 多 worker 拒绝 | `-e WEB_CONCURRENCY=2` 启动 → 退出码 3，日志 `单实例约束：检测到 WEB_CONCURRENCY=2` | 3 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |
| 任意 CWD + 幂等 | `--entrypoint sh -c "cd /tmp && DATABASE_URL=sqlite+aiosqlite:////tmp/probe.db alembic -c /app/alembic.ini upgrade head"` → 五表；二次执行无升级输出 | 0 | 未知 | 5190a7d7c194fe3545181c33718112532def2b1d |

上表的非零退出码是**被验证行为本身**（迁移失败 / 缺配置 / 多 worker 拒绝），不是验证失败；对应日志
已核对含预期错误信息。

## concerns

- `docker restart` 复用同一容器，迁移为无操作；`Running upgrade` 不再出现即幂等证据（alembic 对
  head 已是最新时只打印 context 行）。
- 迁移失败测试使用**空卷 + 只读挂载**：已迁移卷上的只读启动不会失败（alembic 只读版本表），这是
  预期语义，验证只针对「迁移必须写入而写入被拒」的真实失败路径。
- entrypoint 当前以 root 运行迁移（权限模型在 Task 3 落地：root → 修属主 → 降权）。
