# 真机端到端验收记录 · docker-deploy-e2e

> 执行时间：2026-11-03 14:49–14:57（+08:00）。环境：Windows 11 + Docker Desktop，
> Docker server 29.4.3（linux/amd64）。镜像：`ocr-gateway:0.1.0` / `ocr-gateway:latest`
> （225,191,517 B；基础镜像 digest `sha256:b18b261e…`）。
>
> 凭证处理：真实百度/腾讯凭证从**仓库外**的本地私有文件读取到 shell 环境后仅用于管理 API 调用；
> 本记录、镜像与容器环境均不含任何密钥明文。网关 API Key 的明文只在创建响应中出现一次，
> 本记录仅保留前缀与长度。

## 5.1 冷启动（≤90s）

| 项 | 值 |
| --- | --- |
| 前置 | 镜像已构建（Q2=A 口径）；`data/` 清空 |
| 命令 | `docker compose up -d` |
| 起止时间戳 | `2026-11-03T14:49:59+08:00` → `2026-11-03T14:50:06+08:00` |
| 耗时 | **7s**（阈值 90s） |
| 健康状态 | `docker inspect` → `healthy`；`GET /healthz` → `200` |

## 5.2 管理 API 配置

| 动作 | 结果 |
| --- | --- |
| `POST /api/admin/login` | 200，返回 token（不记录值） |
| `POST /api/admin/users` `{"name":"e2e-member"}` | 200，`id=1`，`enabled=true` |
| `POST /api/admin/api-keys` `{"user_id":1,"name":"e2e-key"}` | 200，`key_prefix=ocr_VIIIakyZ`，长度 47（明文仅此一次，未落盘） |
| `POST /api/admin/accounts`（baidu，credentials 经环境传入） | 200，`id=1`，`state=active` |
| `POST /api/admin/accounts`（tencent，credentials 经环境传入） | 200，`id=2`，`state=active` |
| `GET /api/admin/accounts` | 返回两家；响应不含 `credentials` 明文（脱敏/省略） |

## 5.3 真机三输入识别

三种输入均使用真 Key 调用 `POST /v1/ocr/image`（`language=zh`）。base64 与 URL 两行均为**清缓存后
冷调用**（排除缓存干扰）。

| 输入 | provider | cached | quota.used | latency_ms | text_len | lines | text 片段 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| multipart 文件（`file=@general.png`） | baidu | false | 1 | 970 | 136 | 4 | `http://www.baidu.com` … |
| JSON base64（冷） | baidu | false | 1 | 438 | 136 | 4 | `http://www.baidu.com` … |
| JSON `image_url`（公网图，冷） | baidu | false | 1 | 2735 | 136 | 4 | `http://www.baidu.com` … |

## 5.4 缓存命中

同一图片、`language=zh`、`provider=auto` 连续请求第二次：
`cached=true`、`quota.used=0`、`latency_ms=829`，`text`/`lines` 正常返回。

## 5.5 配额记账

`GET /api/admin/usage/summary`（调用结束后）：

```json
{"from":"2026-10-27T06:56:43Z","to":"2026-11-03T06:56:43Z","group_by":"provider","rows":[
  {"key":"baidu","requests":8,"success":7,"failure":1,"cached":3,"quota_used":4},
  {"key":"tencent","requests":1,"success":1,"failure":0,"cached":0,"quota_used":1}]}
```

`GET /api/admin/logs?limit=3`：行内字段 `provider/success/error_code/cached/quota_used/latency_ms`
与调用一致；响应中**不存在 `text` 字段**（日志不落 OCR 原文）。

## 5.6 显式厂商不回退

1. `PATCH /api/admin/accounts/1` `{"enabled":false}` → `state=disabled`（唯一百度账号停用）。
2. `POST /v1/ocr/image` `{"provider":"baidu","image_url":"https://baidu-ai.bj.bcebos.com/ocr/general.png"}`
   → **HTTP 503**，body：
   `{"error":{"code":"PROVIDER_UNAVAILABLE","message":"no available account"}}`
   ⇒ 未回退到腾讯。

## 5.7 `auto` 跨厂商切换

清空缓存后同一请求改 `provider=auto`：
`provider=tencent`、`cached=false`、`quota.used=1`、`latency_ms=2156`、`text_len=137`、`lines=4` ⇒ 自动切换成立。

## 镜像与容器健康（汇总）

| 检查 | 结果 |
| --- | --- |
| 镜像规格 | `docker image inspect` → `RepoTags=["ocr-gateway:0.1.0","ocr-gateway:latest"]`，`linux/amd64`，225,191,517 B |
| 凭证扫描（停止态镜像层） | `change-me-please` 出现 0 次；镜像历史无 `ENV MASTER_KEY` / `ENV ADMIN_PASSWORD` |
| 运行身份 | 主进程 uid=10001（`docker top`）；`/data` 内文件属主 10001 |
| 容器健康 | `docker inspect` → `status=running, health=healthy` |

> 备注：验证后已重新启用百度账号（`enabled=true`），容器保持 healthy。
