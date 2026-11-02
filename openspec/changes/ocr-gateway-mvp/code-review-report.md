---
ship-gate:
  code_review: pass
  reviewed_sha: d5d1e8793651b5ef8a32dd5262e85dc38353368e3a93b02e6aa1bd74f1c1e676
  reviewed_manifest: MTAwNjQ0IGJsb2IgYmUzMGQyNjU5NWIzODM1M2EwYmJmZjBiMGRlNTE4MGFjZWM1YTFiNAkuZW52LmV4YW1wbGUAMTAwNjQ0IGJsb2IgMjgzMzdlNWJkNTc3YzU5YTc3ZTAzZDUxZjZmZDI2NDE0ZTU3NjU2YwkuZ2l0aWdub3JlADEwMDY0NCBibG9iIDQ2NjY3N2Y0NTdhMTJiNTgxYzQxMTQ4MmQzZWQxOTQzMTQyNjI1OTkJQUdFTlRTLm1kADEwMDY0NCBibG9iIDcxNjM5MGVmMDNkNTNlMTI3ODFhNzVhZTU1YWQ4ZmE3YmQ5MGNkOTEJUkVBRE1FLm1kADA0MDAwMCB0cmVlIDVkYzIxNGM5MzJhOTkwMGU3ZjdhZGMwYWY4NDFiYmFiYzc2Nzg3OWUJYmFja2VuZAAwNDAwMDAgdHJlZSA2YTA3YTU3YzU0YmJlYThlMTRmYTc2NGI4Zjc3NjhhMGM1ZWY4YTZkCWRvY3M=
---
# 代码审报告 · ocr-gateway-mvp

> ⚠️ 单 session 自查：实现者与审阅者为同一上下文；同模型、不同上下文，非独立评审。
完成度来源: tickets.md

## 结论

**pass**。首轮 code review 发现 4 项 Important（登录限流反代失效、`MASTER_KEY` 示例不可用、
Alembic 配置漂移、SSRF IPv4-mapped IPv6 绕过）与 6 项 Minor，均已修复或按简化原则 defer；
复审限定在修复 diff，未再发现 Critical/Important。聚合套件 148 passed / 2 skipped（真实账号契约
测试默认 skip）。

## scope 审计

| # | 类型 | 证据 | 严重度 |
|---|---|---|---|
| S1 | DONE | Task 1：`backend/app/{config,db,models,main}.py`、`alembic/versions/0001_initial.py`；`test_ticket1_bootstrap.py` 14 passed；checkpoint `4f6128f` | — |
| S2 | DONE | Task 2：`backend/app/api/{admin,deps}.py`、`security.py`、`schemas.py`；`test_ticket2_admin.py` 23 passed；checkpoint `997018c` | — |
| S3 | DONE | Task 3：`core/{registry,scheduler,quota,cache}.py`、`providers/baidu.py`、`utils/images.py`、`api/public.py`；ticket3 套件 59 passed；checkpoint `c4d4266` | — |
| S4 | DONE | Task 4：`providers/tencent.py`、账号测活/`reset-state`；ticket4 套件 22 passed；checkpoint `3099f3e` | — |
| S5 | DONE | Task 5：`utils/ssrf.py`、缓存边界、用量/日志、`README.md`；ticket5 套件 27 passed；checkpoint `06a3231` | — |
| S6 | DONE / 真实账号识别 UNVERIFIABLE | Task 6：契约测试文件 + 聚合套件 139 passed（修复后 148 passed）、2 skipped；checkpoint `df1ddea`/`e6be815`；真实百度/腾讯识别因本地凭证未配置未执行 | Minor |
| S7 | 无 SCOPE-CREEP | `git diff --stat 567491a..9f45631` 仅 `backend/`、`.env.example`、`README.md`、`openspec/`；未实现 Non-Goals（SPA/批量/本地 OCR/阿里/华为/Docker/settings/匿名/cookie） | — |

完成度五态：Task 1–5 全部 `DONE`；Task 6 的工单验收（聚合套件）`DONE`，其真实厂商识别子项
`UNVERIFIABLE`（凭证仅本地、契约测试默认 skip，符合 C9/D12）。`tasks.md` 与 `tickets.md` 无冲突：
tasks 6.1/6.2 的契约测试已存在并按设计 skip；6.3 的切换演练由 Task 3/4 的 API e2e 覆盖。

切片偏离对账：`impl-reports/planning-decisions.md` 申报「无切片偏离」；实际 diff 的 S1–S5 边界、
阻塞边与票数与申报一致。出票期把 `tasks.md` 2.5 的全局信号量验收归入 Task 3 已在该文件说明，
不属于切片边界变化。无 silent creep。

## Spec 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| F1 | 反向代理后所有请求的 peer 都是代理 IP，per-IP 登录限流退化为全局封锁；攻击者 5 次错误即可把管理员锁在门外（违背设计 D16「全局层不阻断」的意图） | Important | `backend/app/api/admin.py:52`（`_client_ip`）；`backend/tests/test_ticket2_admin.py:244`、`:265` | 采纳/已修：新增 `TRUST_PROXY_HEADERS`（默认 false），仅在显式启用时取 `X-Forwarded-For`/`X-Real-IP` 首跳并校验 IP；README 明示只在可信反代后启用 |
| F2 | `.env.example` 的 `MASTER_KEY=base64:...` 会被 `decode_master_key` 拒绝，按 quickstart 复制后进程无法启动 | Important | `backend/app/config.py:13`；`backend/tests/test_ticket1_bootstrap.py:223`、`:229` | 采纳/已修：支持 `base64:`/`b64:`/`hex:` 前缀；示例值可解码 |
| F3 | Alembic 不读 `.env`/`DATA_DIR`，迁移可能建在应用不使用的库；`./data` 不存在时迁移直接失败 | Important | `backend/alembic/env.py:14`、`:56`；`backend/tests/test_ticket1_bootstrap.py:239` | 采纳/已修：`load_dotenv` 仓库根 `.env`、`DATA_DIR` 回退、SQLite 父目录自动创建；URL 优先级 `-x` > `DATABASE_URL` > 显式 config > `DATA_DIR` > 默认 |
| F4 | SSRF 对 `::ffff:127.0.0.1` 等 IPv4-mapped IPv6 地址不判私网，可绕过；非法端口在 `parsed.port` 抛 `ValueError` 返回 500 而非 400 | Important | `backend/app/utils/ssrf.py:16`、`:44`；`backend/tests/test_ticket5_ssrf_cache.py:161`、`:166`、`:173` | 采纳/已修：mapped 地址下沉到 IPv4 校验；端口/解析异常归一为 `UrlFetchError`（400） |
| F5 | `api_keys.last_used_at` 管理端可见但永不更新 | Minor | `backend/app/api/public.py:186`；`backend/tests/test_ticket3_ocr_api.py:88` | 采纳/已修：记录 usage 时同步更新 |
| F6 | `usage_events.provider` CHECK 比设计表多允许 `auto` | Minor | `backend/app/models.py:136`；task1/task3 报告 | 已知偏差：`provider=auto` 无候选失败事件必须有请求级值；已在 Task 1/3 报告声明，不阻塞 |
| F7 | `reset-state` 清零日/月/总量三类配额计数（设计只显式要求总量经 reset-state 恢复） | Minor | `backend/app/api/admin.py:389`；task4 报告 | 已知偏差：让「quota_exhausted 账号恢复 active 并可参与调度」在验收上成立；已在 Task 4 报告声明，不阻塞 |

## Standards 轴

| # | 问题 | 严重度 | 证据锚 | 裁决 |
|---|---|---|---|---|
| F8 | `logger.exception("unhandled error", exc_info=exc)` 传异常对象而非 `True`/元组，依赖 `sys.exc_info()` 的隐式行为 | Minor | `backend/app/main.py:157` | 采纳/已修：改为 `logger.exception("unhandled error")` |
| F9 | 请求体在 `request.json()/form()` 前没有应用侧上限；新增 `Content-Length` 守卫只覆盖带声明长度的请求，chunked 仍有残差 | Minor | `backend/app/api/public.py:62` | 部分修复 + defer T1（反代仍应作为第一道限制） |
| F10 | `LoginLimiter._per_ip` 对唯一 IP 无上限；启用可信代理头后可被伪造 IP 喷洒撑大内存 | Minor | `backend/app/state.py:42`、`:66` | 采纳/已修：>10000 条时按窗口清理；`record_failure` 用 `setdefault` 防 KeyError |
| F11 | `record_failure` 在未先调 `blocked` 时对 `_per_ip[ip]` 抛 `KeyError` | Minor | `backend/app/state.py:66` | 采纳/已修（与 F10 同一路径） |
| F12 | 百度 OAuth token 无 per-account 并发刷新合并，首并发可能重复打 token 端点 | Minor | `backend/app/providers/baidu.py:122` | defer T2：低概率/小影响；30 天有效期 |
| F13 | 新增 `TRUST_PROXY_HEADERS`、契约 marker、README 段落没有同步到测试/文档 | Minor | `backend/tests/test_ticket2_admin.py`、`README.md` | 采纳/已修：补测试与文档 |

## 自动修

- [impl-review-fix] F1：`_client_ip` 可信代理头 + `TRUST_PROXY_HEADERS` 配置 + README。
- [impl-review-fix] F2：`decode_master_key` 支持 `base64:`/`b64:`/`hex:` 前缀。
- [impl-review-fix] F3：Alembic `load_dotenv`、`DATA_DIR` 回退、SQLite 父目录创建。
- [impl-review-fix] F4：IPv4-mapped IPv6 校验、非法端口归一为 400。
- [impl-review-fix] F5：`api_keys.last_used_at` 同步。
- [impl-review-fix] F8：`logger.exception` 调用修正。
- [impl-review-fix] F9：`Content-Length` 上限守卫（chunked 残差 defer T1）。
- [impl-review-fix] F10/F11：`LoginLimiter` 内存上限 + `setdefault`。
- [impl-review-fix] F13：测试与文档同步。

修复后复审：范围限定为 `checkpoint(impl-review)` 的 diff（`9f45631`），逐文件复核；未再发现
Critical/Important；聚合套件 148 passed / 2 skipped，ruff/mypy 绿。

## defer 台账

<!-- sdflow-lite:defer-ledger -->
| ID | 问题 | 去向 |
|---|---|---|
| T1 | chunked/无 `Content-Length` 请求的流式 body 上限 | `openspec/issues/open/T1.md` |
| T2 | 百度 OAuth token 并发刷新合并 | `openspec/issues/open/T2.md` |

## 既有问题

| # | 问题 | 证据锚 |
|---|---|---|
| — | 无（本次 diff 未发现既有代码缺陷） | — |

## 已知偏差（不阻塞）

- `usage_events.provider` 允许 `auto`：无候选的 `auto` 失败事件需要请求级 provider；Task 1/3
  报告已声明。
- `reset-state` 清零三类配额计数：管理员显式覆盖，满足「quota_exhausted 恢复可调度」验收；
  Task 4 报告已声明。
- 新增 `TRUST_PROXY_HEADERS`（默认 false）不在设计环境变量表中：这是本次 review 为反代部署
  下 per-IP 登录限流恢复可用性而增加的显式可选配置；默认值保持设计「不信任 X-Forwarded-*」的
  行为，README 已说明仅在可信反代后开启。

## 已裁掉

| # | 位置 | 理由 |
|---|---|---|
| D1 | 缓存命中在全局并发信号量之前返回 | 有意的廉价路径：不调用厂商、不占 OCR 并发；Task 5 报告已记录 |
| D2 | DNS rebinding 残余风险 | 设计已接受（解析后校验 + 逐跳复核；IP 固定/出口代理不在 MVP） |
| D3 | `orjson` 在 proposal 依赖清单中出现但未使用 | 无行为要求；D14 规模下 stdlib json 足够，不构成缺陷 |
| D4 | 账号测活的内置样图可能不被真实厂商识别 | 测活端点如实返回 `ok=false` + 分类；这是探活语义，不是代码缺陷 |
| D5 | base64 输入不接受换行/空白 | API 契约要求标准 base64；客户端可自行去空白，影响低 |

## 诚实边界

单 session 自查：实现者与审阅者为同一上下文，同模型、不同上下文，非独立评审。findings 的引文
均重新打开文件核对，但「引文与语义对应」及非局部 finding 的分类无机械核验。真实百度/腾讯账号
契约测试因未配置本地凭证而 skip，本报告未把 skip 当通过。`ship_gate.py` 只保证锚与报告格式，
不保证本报告结论的质量。
