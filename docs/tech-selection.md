# OCR Gateway 技术选型

> 状态：已定稿（2026-11-02）
> 目标：聚合国内多家云 OCR 免费额度，对外提供统一 OCR API，小团队共享。
> 参考项目：`D:\Project\GitHub\Common-OCR`（仅借鉴适配器思路，不复制代码）

---

## 1. 决策总表

| 维度 | 决定 | 理由 |
| --- | --- | --- |
| 基座 | 全新重写 | 参考项目无 LICENSE、无鉴权、假加密、JSON 全量重写、多账号配额不成立 |
| 后端 | Python 3.12 + FastAPI + uvicorn | 本地 OCR 是 Python 生态；异步代理开销远小于云 OCR 延迟 |
| 前端 | React 18 + Vite + Tailwind + shadcn/ui | 管理面板组件成熟；构建后由 FastAPI 静态托管 |
| 存储 | SQLite（WAL）+ SQLAlchemy 2.0 async + Alembic | 小团队单实例足够；后续可迁 Postgres |
| HTTP | 手写适配器 + 全局共享 `httpx.AsyncClient` | 统一连接池、超时、重试、错误映射；热路径可控 |
| 首批厂商 | 百度、腾讯、阿里、华为 | 国内覆盖最广，四种签名方式能把适配器抽象打磨出来 |
| 账号模型 | 共享池 + 按人记账 | 成员贡献 key 进公共池，额度 × n；每个网关 API Key 记录各自用量 |
| 调度 | 优先级分层 + 同层 EWMA 延迟最低 | 行为可预测，主 key 优先，故障自动切备用 |
| 响应结构 | `text` + `lines[{text, confidence}]` | 不统一 bbox，避免四家坐标系归一化的坑 |
| 本地兜底 | RapidOCR + onnxruntime（CPU） | 模型十几 MB，中文效果好，按需下载，依赖轻 |
| 兜底触发 | 云账号全部不可用时自动 + `provider=local` 显式 | 默认不抢配额；云全挂时仍可用 |
| 配额 | 内置厂商模板 + 账号级覆盖 | 新账号开箱可用；模板数字标注「以官网为准」 |
| 缓存 | 内存 LRU + TTL（默认 1h） | 重复图片省额度、降延迟；不落盘，隐私风险低 |
| 成员流程 | 管理员全包 | v1 不做注册/审核；管理员建成员、建账号、发 API Key |
| 部署 | Docker Compose 优先，跨平台 | Windows/Linux 都能跑；模型和数据库挂 volume |
| 输入范围 | 图片（multipart / JSON base64 / URL）+ 批量 | PDF 放 v2 |
| 鉴权 | 网关 API Key + 管理员密码；API 鉴权可关闭 | 公网部署时默认开启；关闭时面板红色告警 |

---

## 2. 为什么不用 Common-OCR

代码审查结论（`AnotherJ1/Common-OCR`，v0.3.0，2 个 commit）：

1. **鉴权实际不存在**：`services/ocr-app/src/index.ts:208` 注释「已移除鉴权限制」，`/apikeys` 接口写了但从未校验，admin 路由裸奔。
2. **凭证加密是假的**：`packages/shared/src/crypto.ts` 把 JSON 转 Base64，`MASTER_KEY` 被忽略。
3. **热路径反向优化**：每次 OCR 写 1 条 `usageLog` + 3 个 `usageCounter`，每次 `save()` 都把整个 JSON（含全部历史日志）重写一遍，串行排队；日志越多越慢。
4. **多账号不成立**：credentials 挂在 platform 行上可以建多行，但 `checkQuota` 和 `incrementUsageCounter` 只按 `provider_code + capability` 聚合，没有账号级配额/冷却/并发/延迟状态。
5. **PDF 链路是坏的**：`jobLoop` 把 `pdfBase64` 塞进 `processImage` 当图片识别；适配器只有 `recognizeImageSync`。
6. **华为适配器 URL 拼错**：`/v2/{region}/ocr/general-text`，华为实际要求 `/v2/{project_id}/...`。
7. **无 LICENSE**：默认版权保留，严格说不能复制代码，只能参考思路。

可借鉴的部分：百度 OAuth token 缓存、腾讯 TC3 签名、阿里 RPC 签名、华为 AK/SK 签名的整体流程；统一结果字段的取舍。

---

## 3. 总体架构

```
                         ┌─────────────────────────────┐
  Client ──Bearer key──▶ │  FastAPI 公共 API            │
                         │  /v1/ocr/image, /batch       │
                         └──────────────┬──────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │  请求管线                              │
                    │  鉴权 → 限流 → 图片校验 → 缓存查询      │
                    └───────────────────┬───────────────────┘
                                        │ miss
                    ┌───────────────────▼───────────────────┐
                    │  调度器 Scheduler                      │
                    │  候选账号 → 优先级分层 → EWMA 延迟排序  │
                    │  配额/冷却/并发/QPS 过滤               │
                    └───────┬───────────────────────┬───────┘
                            │                       │ 全部不可用
              ┌─────────────▼─────────────┐   ┌─────▼──────────────┐
              │  云厂商适配器              │   │  Local OCR Worker  │
              │  百度 / 腾讯 / 阿里 / 华为 │   │  RapidOCR (进程池) │
              └─────────────┬─────────────┘   └─────┬──────────────┘
                            │                       │
                    ┌───────▼───────────────────────▼───────┐
                    │  结果归一化 text + lines               │
                    │  记 usage_event、更新配额与 EWMA       │
                    └───────────────────┬───────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │  SQLite (WAL)：配置/账号/日志/聚合     │
                    │  内存：配额计数器、EWMA、缓存、令牌桶   │
                    └───────────────────────────────────────┘

  Admin ──session──▶ /api/admin/*  ──▶ React SPA（静态托管）
```

---

## 4. 技术栈明细

### 后端依赖

| 用途 | 选型 |
| --- | --- |
| Web | `fastapi`, `uvicorn[standard]` |
| HTTP 客户端 | `httpx`（全局单例，keep-alive） |
| 序列化 | `orjson` |
| 配置 | `pydantic-settings` |
| ORM / 迁移 | `sqlalchemy[asyncio]`, `aiosqlite`, `alembic` |
| 加密 | `cryptography`（AES-GCM） |
| 密码哈希 | `argon2-cffi` |
| 会话 | `itsdangerous`（签名 cookie） |
| 缓存 | `cachetools`（TTLCache）+ 自定义 LRU 上限 |
| 图片 | `Pillow` |
| 上传 | `python-multipart` |
| 本地 OCR | `rapidocr`, `onnxruntime`（可选 extra `[local]`） |
| 测试 | `pytest`, `pytest-asyncio`, `respx`, `httpx.ASGITransport` |
| 质量 | `ruff`, `mypy` |

### 前端依赖

`react`, `react-router-dom`, `@tanstack/react-query`, `react-hook-form`, `zod`, `tailwindcss`, `shadcn/ui`, `recharts`。

### 运行方式

- Python 依赖用 `uv` 管理，`pyproject.toml` + `uv.lock`
- 前端 `pnpm`/`npm` 均可，构建产物复制到后端静态目录
- 本地 OCR 作为独立模块，默认不安装，`uv sync --extra local` 启用

---

## 5. 数据模型

### users

| 字段 | 说明 |
| --- | --- |
| `id` | INTEGER PK |
| `name` | 显示名 |
| `role` | `admin` / `member` |
| `password_hash` | 管理员才有；v1 成员不登录，可为空 |
| `enabled` | 是否启用 |
| `created_at` | |

> v1 面板仅管理员登录。成员是「配额与归属实体」，不提供登录。后续需要成员自助查看时再加只读角色。

### api_keys

| 字段 | 说明 |
| --- | --- |
| `id` | INTEGER PK |
| `user_id` | FK users |
| `name` | 备注 |
| `key_prefix` | 前 8 位，用于面板展示 |
| `key_hash` | SHA-256，唯一索引 |
| `enabled` | |
| `daily_limit` | 可空；该 key 每日最多消耗多少配额单位 |
| `rpm_limit` | 可空；每分钟请求数 |
| `last_used_at` | |

### accounts

| 字段 | 说明 |
| --- | --- |
| `id` | INTEGER PK |
| `provider` | `baidu` / `tencent` / `aliyun` / `huawei` |
| `name` | 展示名，如「百度-小明」 |
| `owner_id` | FK users，贡献者 |
| `credentials_enc` | AES-GCM 密文（nonce + ciphertext + tag，Base64） |
| `priority` | 越小越优先，默认 100 |
| `weight` | 同层排序的轻量权重，默认 1 |
| `enabled` | |
| `timeout_ms` | 该账号单次请求超时，默认 8000 |
| `max_concurrency` | 默认 2 |
| `qps_limit` | 可空；令牌桶速率 |
| `quota_daily` | 可空；单位见 `quota_unit` |
| `quota_monthly` | 可空 |
| `quota_total` | 可空 |
| `quota_unit` | `image` / `page` / `request`，默认 `image` |
| `reset_day` | 月度重置日，默认 1；日重置固定 Asia/Shanghai 00:00 |
| `state` | `active` / `cooling` / `invalid` / `quota_exhausted` / `disabled` |
| `cooldown_until` | |
| `last_error_code` | |
| `last_error_message` | |
| `ewma_latency_ms` | 启动时从最近成功记录恢复，否则用厂商种子值 |
| `last_used_at` | |
| `created_at` / `updated_at` | |

### usage_events

| 字段 | 说明 |
| --- | --- |
| `id` | INTEGER PK |
| `request_id` | UUID |
| `user_id` / `api_key_id` | 调用方 |
| `account_id` | 实际使用的账号；本地 OCR 为空 |
| `provider` | `baidu` / ... / `local` |
| `capability` | v1 固定 `general_text` |
| `success` | |
| `error_code` | |
| `latency_ms` | 端到端耗时 |
| `quota_used` | 通常 1 |
| `cached` | 是否命中缓存 |
| `image_hash` | 可选；默认只存前 16 位，便于排查重复请求 |
| `created_at` | |

> 默认不存 OCR 原文。需要排障时，管理员可临时开启 `debug_store_text`，带 TTL 清理。

### quota_counters

| 字段 | 说明 |
| --- | --- |
| `account_id` | |
| `period_type` | `daily` / `monthly` / `total` |
| `period_key` | `2026-11-02` / `2026-11` / `all` |
| `used` | |
| `updated_at` | |

热路径以内存计数器为准，每 2 秒批量 upsert 到该表；启动时加载当前周期数据。崩溃最多丢 2 秒计数。

### settings

键值表：`api_auth_enabled`、`local_ocr_enabled`、`local_ocr_max_concurrency`、`cache_enabled`、`cache_ttl_seconds`、`cache_max_entries`、`default_timeout_ms`、`request_deadline_ms`、`debug_store_text` 等。

---

## 6. API 设计

### 公共 API

所有接口使用 `Authorization: Bearer <gateway_key>`。`api_auth_enabled=false` 时允许匿名，但按 IP 限流并在面板告警。

#### POST /v1/ocr/image

三种输入二选一：

```http
# multipart
POST /v1/ocr/image
Content-Type: multipart/form-data

file=<binary>
language=zh
provider=baidu        # 可选；不传为 auto
```

```json
// JSON
{
  "image_base64": "...",
  "mime_type": "image/png",
  "language": "zh",
  "provider": "auto"
}
```

```json
// URL
{
  "image_url": "https://example.com/a.png",
  "language": "zh"
}
```

- `provider` 可选值：`auto`、`baidu`、`tencent`、`aliyun`、`huawei`、`local`
- `provider=local` 必须本地 OCR 已启用，否则 403
- 显式指定云厂商时**不跨厂商回退**；`auto` 才允许自动兜底到本地
- 图片默认上限 10MB；超过厂商限制时自动等比缩放/转 JPEG，仍超限则 400
- URL 拉取有 SSRF 防护：仅 http/https、禁止私网/回环/链路本地/云元数据地址、最多 3 次重定向、10s 超时、10MB 上限

成功响应：

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "baidu",
  "text": "第一行\n第二行",
  "lines": [
    { "text": "第一行", "confidence": null },
    { "text": "第二行", "confidence": null }
  ],
  "latency_ms": 412,
  "cached": false,
  "quota": { "unit": "image", "used": 1 },
  "warnings": []
}
```

- `confidence` 可能为 `null`（百度标准版等不返回）
- 不返回 `account_id`，避免暴露池内账号；管理员日志里可见

#### POST /v1/ocr/batch

`multipart/form-data`，多个 `files`，可选 `language`、`provider`。服务端按 4 并发处理，每张图独立计配额。

```json
{
  "results": [
    { "index": 0, "ok": true, "request_id": "...", "provider": "tencent", "text": "...", "lines": [], "latency_ms": 300, "quota": { "unit": "image", "used": 1 } },
    { "index": 1, "ok": false, "error": { "code": "PROVIDER_UNAVAILABLE", "message": "..." } }
  ]
}
```

#### GET /v1/providers

返回可用厂商与账号数量，不泄露凭证：

```json
{
  "providers": [
    { "code": "baidu", "name": "百度智能云", "available_accounts": 2, "enabled": true },
    { "code": "local", "name": "本地 RapidOCR", "enabled": false }
  ]
}
```

#### GET /v1/me

当前 API Key 的用量与限额（成员可以用 curl 自查，不需要登录面板）。

```json
{
  "user": "小明",
  "key_prefix": "ocr_ab12cd34",
  "today": { "requests": 42, "quota_used": 42 },
  "limits": { "daily_limit": 200, "rpm_limit": 30 }
}
```

#### 其他

- `GET /healthz`：进程与 DB 健康
- `GET /metrics`：Prometheus 指标（可选，默认关闭公网访问）

### 管理 API（`/api/admin/*`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/login` | 管理员登录，Set-Cookie |
| POST | `/logout` | |
| GET | `/me` | 当前管理员 |
| GET/POST | `/users` | 成员列表/创建 |
| PATCH/DELETE | `/users/{id}` | 改配额、禁用、删除 |
| GET/POST | `/api-keys` | Key 列表/创建（创建时只返回一次明文） |
| PATCH/DELETE | `/api-keys/{id}` | 启用/禁用/吊销 |
| GET/POST | `/accounts` | 账号列表/创建 |
| PATCH/DELETE | `/accounts/{id}` | 编辑/删除 |
| POST | `/accounts/{id}/test` | 用内置样图测活，返回文本+延迟 |
| POST | `/accounts/{id}/reset-state` | 手动清除冷却/失效 |
| GET | `/usage/summary` | 按用户/厂商/账号聚合 |
| GET | `/usage/series` | 时间序列，供图表 |
| GET | `/logs` | 请求日志（默认不含原文） |
| GET/PUT | `/settings` | 全局设置 |
| GET | `/quota-templates` | 厂商配额模板 |
| GET | `/local-ocr/status` | 模型是否下载、worker 是否就绪 |
| POST | `/local-ocr/download` | 触发模型下载 |
| POST | `/cache/clear` | 清空缓存 |

管理 API 使用 HttpOnly 签名 cookie + CSRF 双提交头；所有写操作校验 `X-CSRF-Token`。

### 错误码

| code | HTTP | 说明 |
| --- | --- | --- |
| `BAD_REQUEST` | 400 | 参数/图片无效 |
| `UNAUTHORIZED` | 401 | 缺少或无效 API Key |
| `FORBIDDEN` | 403 | 显式请求了未启用的 provider（如 local） |
| `RATE_LIMITED` | 429 | 网关限流 |
| `QUOTA_EXCEEDED` | 429 | 用户或账号配额耗尽 |
| `PROVIDER_UNAVAILABLE` | 503 | 所有候选账号不可用 |
| `TIMEOUT` | 504 | 总预算耗尽 |
| `PROVIDER_ERROR` | 502 | 厂商返回异常 |
| `INTERNAL_ERROR` | 500 | 未预期异常 |

---

## 7. 调度与失败语义

### 候选过滤

1. `enabled=true`
2. `state=active`（`cooling` 且 `cooldown_until` 已过则恢复）
3. 当前周期配额未耗尽
4. 并发信号量有空位
5. QPS 令牌桶有令牌

### 排序

1. `priority` 升序分层
2. 同层按 `ewma_latency_ms` 升序
3. 同延迟按 `last_used_at` 升序（LRU，摊平额度）
4. `weight` 作为同分的轻微偏移

### EWMA

```
ewma = 0.2 * latency_ms + 0.8 * ewma
```

初始种子按厂商给一个保守值（如 1000ms）。只统计成功请求；超时通过冷却惩罚，不污染延迟均值。

### 尝试循环

```
deadline = now + request_deadline_ms
for account in candidates:
    remaining = deadline - now
    if remaining <= 0: break
    timeout = min(account.timeout_ms, remaining)
    try:
        return await adapter.call(account, timeout)
    except Retryable as e:
        mark_account(e)
        continue
    except InputError:
        raise  # 不换账号，换也没用
if local_enabled and fallback_allowed:
    return await local_ocr(...)
raise PROVIDER_UNAVAILABLE
```

### 失败分类

| 情况 | 处理 |
| --- | --- |
| `AUTH_FAILED` | 账号 `state=invalid`，长冷却，面板告警贡献者；不自动恢复 |
| `QUOTA_EXCEEDED` | `state=quota_exhausted`，到重置时间自动恢复 |
| `RATE_LIMITED` | 按 `Retry-After` 或默认 30s 冷却，切下一个 |
| `TIMEOUT` / 网络错误 | 30s 冷却，切下一个 |
| 5xx / `PROVIDER_ERROR` | 10s 冷却，切下一个 |
| 输入错误（过大/格式） | 直接 400，不切 |
| 厂商返回空文本 | 视为成功，`text=""`，记 warning |

---

## 8. 配额与记账

- 单位统一为 `image`；PDF 的 `page` 留给 v2
- 日/月重置时区固定 `Asia/Shanghai`；日重置 00:00，月重置 `reset_day` 当天 00:00
- 账号级 `quota_daily/monthly/total` 任一为空表示不限制；全部为空时面板提示「未配置额度，可能超用」
- 内置模板（**数字上线前逐一核对官网，代码里标注“以官网为准”**）：

| 厂商 | 模板周期 | 参考额度 | 备注 |
| --- | --- | --- | --- |
| 百度 | 月 | 1000 次 | 通用文字识别标准版 |
| 腾讯 | 月 | 1000 次 | 通用印刷体识别 |
| 阿里 | 月 | 500 次 | 通用文字识别 |
| 华为 | 月 | 1000 次 | 通用文字识别 |

> 上表来自参考项目 README，未核对当期活动，**不作为事实使用**。实现时去各厂商控制台/定价页确认，并把模板做成可编辑的 JSON。

- 每次成功请求：`account.used += 1`，`user.used += 1`，`usage_event.quota_used=1`
- 缓存命中：`quota_used=0`，仍记录请求数和命中数
- 失败请求：不计配额，记 `error_code`
- 用户级 `daily_limit` 只限制其请求量，不影响账号池额度

---

## 9. 本地 OCR

- 引擎：RapidOCR（onnxruntime CPU backend）
- 安装：`uv sync --extra local`；Docker 镜像内置 onnxruntime，模型不打包进镜像
- 模型：首次启用或点击「下载模型」时下载到 `data/models/rapidocr/`；优先 ModelScope，失败回退 HuggingFace；显示下载进度和校验
- 运行：独立 `ProcessPoolExecutor(max_workers=local_ocr_max_concurrency)`，默认 1；避免 ONNX 阻塞事件循环
- 超时：本地任务默认 30s；若总 deadline 剩余不足，直接返回 `TIMEOUT`
- 输出：RapidOCR 的 `[box, text, score]` 归一化为 `lines[{text, confidence}]`，bbox 丢弃
- 触发：
  - `local_ocr_enabled=true` 且 `provider=auto`：云账号全部不可用时自动兜底
  - `provider=local`：显式调用（需已启用）
  - 显式云厂商：不兜底
- 状态：面板显示 worker 就绪、模型路径、最近一次耗时、CPU 占用（可选）

---

## 10. 缓存

- Key：`sha256(image_bytes) + language + (provider or "auto")`
- 存储：进程内 `TTLCache`，默认 1000 条 / 1 小时；单条结果超过 256KB 不缓存
- 命中：直接返回，`cached=true`，`quota_used=0`
- 只缓存成功且 `text` 非空的结果
- 管理端可清空；重启即失效
- 不缓存 URL 拉取的中间响应，只缓存最终 OCR 结果

---

## 11. 安全

| 项 | 方案 |
| --- | --- |
| 凭证加密 | AES-256-GCM，`MASTER_KEY` 环境变量（32 字节 Base64 或 hex）；启动时校验，缺失即拒绝启动 |
| 密码 | argon2id |
| 会话 | `itsdangerous` 签名 cookie，HttpOnly + SameSite=Lax + Secure（HTTPS 时） |
| CSRF | 双提交 token，写操作校验 `X-CSRF-Token` |
| API Key | `ocr_` + 32 字节随机；只存 SHA-256；面板只显示前缀 |
| 限流 | 每 Key 令牌桶（rpm）；匿名模式按 IP |
| SSRF | DNS 解析后校验 IP 段；禁止 127/8、10/8、172.16/12、192.168/16、169.254/16、::1、fc00::/7；禁止重定向到私网 |
| 上传 | 10MB 上限；Pillow 校验真实图片格式，不只信 Content-Type |
| 日志 | 默认不存 OCR 原文；错误信息截断；不记录凭证 |
| 面板 | CSP、`X-Content-Type-Options`、`Referrer-Policy`；管理 API 仅同源 |
| 公网 | API 鉴权默认开；关闭时面板红色告警并要求二次确认；建议反代加 HTTPS |

---

## 12. 前端页面

1. **登录**：管理员密码
2. **总览**：今日请求/成功率/缓存命中率、各厂商配额进度、平均延迟、最近错误
3. **账号**：表格（厂商/名称/贡献者/优先级/配额/状态/EWMA/最近错误）；新增/编辑弹窗按厂商渲染凭证字段；「测试连接」「重置状态」「禁用」
4. **成员与 Key**：创建成员、生成/吊销 API Key、设置日限额与 RPM；Key 明文只显示一次
5. **用量**：按用户/厂商/账号/时间筛选；折线图 + 表格；CSV 导出
6. **日志**：请求 ID、用户、厂商、账号、耗时、错误码；默认不显示原文
7. **设置**：API 鉴权开关（带警告）、本地 OCR 开关/模型下载、缓存 TTL/容量、超时、配额模板

UI 用 shadcn/ui 的 Table/Dialog/Form/Tabs/Card，图表用 recharts。所有请求走 `@tanstack/react-query`，错误统一 toast。

---

## 13. 目录结构

```
ocr-gateway/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口、lifespan、静态托管
│   │   ├── config.py               # pydantic-settings
│   │   ├── db.py                   # async engine/session
│   │   ├── models.py               # SQLAlchemy 模型
│   │   ├── schemas.py              # Pydantic 请求/响应
│   │   ├── security.py             # 密码、会话、API Key、加密
│   │   ├── api/
│   │   │   ├── public.py           # /v1/*
│   │   │   ├── admin.py            # /api/admin/*
│   │   │   └── deps.py             # 鉴权依赖、限流
│   │   ├── core/
│   │   │   ├── scheduler.py        # 候选过滤、排序、尝试循环
│   │   │   ├── registry.py         # 账号内存状态、EWMA、冷却
│   │   │   ├── quota.py            # 计数器、重置、刷盘
│   │   │   ├── cache.py            # LRU+TTL
│   │   │   ├── errors.py           # 统一错误类型
│   │   │   └── http.py             # 全局 httpx client
│   │   ├── providers/
│   │   │   ├── base.py             # ProviderAdapter 协议
│   │   │   ├── baidu.py
│   │   │   ├── tencent.py
│   │   │   ├── aliyun.py
│   │   │   ├── huawei.py
│   │   │   ├── local.py
│   │   │   └── templates.py        # 配额模板、凭证 schema
│   │   ├── workers/
│   │   │   └── local_ocr.py        # ProcessPool worker + 模型管理
│   │   └── utils/
│   │       ├── images.py           # 校验、缩放、EXIF 旋转
│   │       └── ssrf.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── api/
│   │   └── contract/               # 真实 key，默认 skip
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── lib/
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── data/                           # gitignore：sqlite、models、日志
├── docs/
│   └── tech-selection.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 14. 部署

### Docker Compose

```yaml
services:
  ocr-gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      MASTER_KEY: ${MASTER_KEY}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      DATA_DIR: /app/data
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

- 多阶段构建：Node 构建前端 → Python 运行时复制 `dist`
- 镜像内置 onnxruntime；RapidOCR 模型运行时下载到 volume
- 健康检查：`GET /healthz`
- 反向代理：Caddy/Nginx 负责 HTTPS；面板和 API 同域

### 裸机

```
uv sync --extra local
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows 同样可用；本地 OCR 需要至少 2 核 4G，首次模型下载需要外网。

---

## 15. 测试策略

| 层级 | 内容 |
| --- | --- |
| 单元 | 调度排序、配额重置、失败分类、EWMA、缓存 TTL/LRU、AES-GCM 往返、SSRF IP 校验 |
| 适配器 | `respx` 模拟厂商响应；签名用官方示例做黄金用例（腾讯 TC3、阿里 RPC、华为 AK/SK） |
| API | `httpx.ASGITransport` 测鉴权、限流、批量、错误码、缓存命中 |
| 契约 | `pytest -m contract`，需要 `BAIDU_*` 等环境变量；CI 默认跳过 |
| 前端 | 先保证类型检查 + 构建；关键流程后续补 Playwright |
| 性能 | 本地 mock 厂商延迟 0ms，测网关自身 p99；目标 < 20ms（不含厂商） |

### 上线前必须做的验证

1. 四家各用一个真实 key 跑通「测试连接」和一张中文截图
2. 核对四家当期免费额度，更新 `templates.py`
3. 腾讯 TC3 签名用官方示例校验，避免只有真 key 才能发现
4. 华为 `project_id` 从控制台「我的凭证」获取
5. 图片大小/格式边界：4MB/7MB/10MB 各厂商限制不同，确认自动缩放逻辑

---

## 16. 里程碑

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| M0 | 脚手架、配置、DB 迁移、管理员登录、面板壳 | 能登录，健康检查通过 |
| M1 | 百度适配器 + 调度器 + 配额 + 公共 API + 单元测试 | 单厂商端到端可用，失败能切备用 |
| M2 | 腾讯/阿里/华为适配器 + 签名黄金用例 | 四家都能测活并识别 |
| M3 | 账号/成员/Key/用量/日志/设置面板 | 管理员可完整管理 |
| M4 | 本地 OCR worker + 模型下载 + 兜底 | 云全挂时自动本地识别 |
| M5 | 缓存、批量、URL、Docker、性能测试、README | 一键起服务，压测达标 |

---

## 17. 风险与待办

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 四家签名手写易错 | 适配器不可用 | 黄金用例 + 真 key 契约测试 + 面板测活 |
| 免费额度模板过时 | 提前跳过或超用 | 上线前核对；账号级可改；面板提示未配置 |
| 多账号触发厂商风控 | 限流/封号 | 控制并发与 QPS；优先 BYOK 贡献；不对外转售 |
| 本地 OCR CPU 慢 | 兜底体验差 | 默认关闭；限制并发；大图先缩放；面板显示耗时 |
| SQLite 单写 | 多实例不可用 | v1 单实例；预留 Postgres 迁移 |
| URL 拉取 SSRF | 内网探测 | 严格 IP 校验 + 重定向复核 + 大小/超时限制 |
| 共享池滥用 | 额度被少数人烧完 | 每 Key 日限额 + RPM；用量面板可见 |
| 明文 Key 只在创建时显示 | 用户丢失 | 支持吊销重建；不支持找回 |

### 明确不在 v1 范围

- PDF OCR（v2：PyMuPDF 逐页渲染 + 异步任务）
- 成员自助注册/登录
- 多租户计费
- WebSocket 实时推送
- 表格/版面结构化识别
- Google/Azure/AWS 等海外厂商
