---
ticket: 5
title: 真机端到端验收（S5）
head: a93ae13e76fc691e9c650c09ba42aeab9bae49be
status: DONE
suite_scope: {"base": "2a549d1df780dfbaf675fdcfbe1ebab9d8d7d248", "head": "HEAD", "mode": "closeout", "domains_configured": true, "hit_domains": ["backend"], "layers": [{"name": "unit", "command": "uv run --project backend pytest backend/tests", "quick": "uv run --project backend pytest backend/tests -q", "full": "uv run --project backend pytest backend/tests", "count_regex": "(\\d+) passed", "timeout_sec": 1800}], "skipped_layers": []}
---

## 改动

- 无产品代码改动；本票为真机验证。新增 `openspec/changes/docker-deploy-e2e/e2e-acceptance.md`
  作为逐条验收证据（命令、时间戳、响应片段、镜像扫描、健康状态）。
- 执行面：本地 compose 栈（`ocr-gateway:0.1.0`）+ 真实百度/腾讯凭证。凭证从**仓库外**的本地
  私有文件读入 shell 环境后用于管理 API 调用，未写入任何文件、未注入容器环境、未进入证据。
- 验证后已重新启用百度账号并保持容器 `healthy`；`api-keys` 明文只保留前缀与长度，未落盘。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
| --- | --- | --- | --- | --- |
| 冷启动 | 清空 `data/` → `docker compose up -d` → 轮询健康：7s 到 `healthy`，`/healthz` 200（2026-11-03T14:49:59+08:00 → 14:50:06+08:00） | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 管理面配置 | `POST /api/admin/login` → `POST /users`（id=1）→ `POST /api-keys`（prefix `ocr_VIIIakyZ`）→ `POST /accounts`（baidu id=1、tencent id=2）→ `GET /accounts`（无明文凭证） | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 三输入识别 | multipart：200/provider=baidu/136 字/4 行/970ms；base64（清缓存冷调）：200/baidu/136 字/4 行/438ms；`image_url`（清缓存冷调）：200/baidu/136 字/4 行/2735ms | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 缓存命中 | 同图 + `language=zh` + `provider=auto` 第二次：`cached=true`、`quota.used=0`、`latency_ms=829` | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 配额记账 | `GET /api/admin/usage/summary` → baidu `requests=8,success=7,failure=1,cached=3,quota_used=4`、tencent `requests=1,success=1,quota_used=1`；`GET /api/admin/logs` 行内无 `text` 字段 | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 显式不回退 | 停用全部百度账号 → `provider=baidu` 请求返回 **HTTP 503**、`error.code=PROVIDER_UNAVAILABLE`、`message=no available account`（未由腾讯完成） | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| `auto` 切换 | 清缓存 → `provider=auto` → `provider=tencent`、`cached=false`、`quota.used=1`、`latency_ms=2156`、137 字/4 行 | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |
| 镜像/健康汇总 | 两个 tag、`linux/amd64`、225,191,517 B；凭证扫描 0 命中；主进程 uid=10001；`status=running, health=healthy` | 0 | 未知 | a93ae13e76fc691e9c650c09ba42aeab9bae49be |

上表「显式不回退」行的 HTTP 503 是**被验证行为**；shell 命令（curl）退出码为 0，响应码与错误体
已记录在 `e2e-acceptance.md`。

## concerns

- **凭证注入路径与票面字面口径的差异**：票面写「真实凭证经 `env_file` 注入」，实际做法是从仓库外
  的私有文件读入 **shell 环境**后调用管理 API——这比把厂商密钥注入容器环境更严格（`docker inspect`
  不会暴露它们）。用户明确指示凭证在该文档中，故按此执行；若要求严格字面口径，可改为 `.env`。
- **真实厂商调用次数**：本次共 9 次计费调用（baidu 8 次含 1 次失败、tencent 1 次），在 decision-memo
  已批准的真机验收额度口径内。
- **本轮留存的本地状态**：`./data` 内有 e2e 成员/Key/两家账号（真实凭证加密存储）；`.env` 仍是
  示例 MASTER_KEY/ADMIN_PASSWORD。若该数据目录用于后续使用，请替换 `.env` 前先备份或清理。
