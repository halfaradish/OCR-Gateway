# Planning Decisions · ocr-gateway-mvp

> 相位一（出票）决策台账。来源：`design.md`「切片与依赖」、`tasks.md` 1.x–6.x、
> `decision-memo.md` 承重约束 C1–C9。

## 切片方案

默认采纳 `design.md` 的 S1–S5 五张垂直切片，与 `tickets.md` 的 Task 1–5 一一对应；
Task 6 为 ship 规则强制的「实现验证」收尾票（`R-ID: all`，不计预算）。

| 切片 | 票 | 阻塞边 |
| --- | --- | --- |
| S1 脚手架与存储 | Task 1 | none |
| S2 管理端鉴权与实体 | Task 2 | Task 1 |
| S3 百度链路与调度 | Task 3 | Task 1, 2 |
| S4 腾讯链路与切换 | Task 4 | Task 3 |
| S5 输入补全与可运营性 | Task 5 | Task 3, 4 |
| 收尾 | Task 6 | Task 1–5 |

## 承重约束 → 票

| 承重约束 | 落点票 | 验收锚（票内条目） |
| --- | --- | --- |
| C1 免费额度按厂商账号计、可池化 | Task 3, Task 4 | 账号配额上限/周期计数/候选池切换；`auto` 跨厂商切换 |
| C2 百度通用文字识别标准版接口形态 | Task 3 | 百度适配器（OAuth token、form、`general_basic`、`words_result`、8MB/4096px 归一化） |
| C3 腾讯 GeneralBasicOCR 接口形态 | Task 4 | TC3 签名黄金用例、`GeneralBasicOCR`、`TextDetections[].Confidence` |
| C4 单实例 SQLite 足够 | Task 1, Task 6 | WAL + 单 worker 守卫；聚合套件通过 |
| C5 无 SPA 的管理端可行 | Task 2 | 登录/token + 成员/Key/账号/模板全部 JSON CRUD，Bearer 可用 |
| C6 URL 输入的 SSRF 防护可用标准库实现 | Task 5 | `getaddrinfo` + IP 段校验 + 逐跳复核 |
| C7 默认不落 OCR 原文 | Task 3, Task 5 | `usage_event` 不含原文/图片字节；日志查询不含原文 |
| C8 显式 provider 不跨厂商回退 | Task 4 | `provider=baidu` 无可用时 503 且不调腾讯 |
| C9 真实凭证仅本地保管、不进仓 | Task 1, Task 2 | 配置只读环境变量、示例仅占位值；凭证加密落库、响应脱敏 |

## 切片偏离审计

无切片偏离：未增票、未删票、未合并票、未改阻塞边、未改切片边界（S1–S5 原样采纳）。

两处票内归属说明（不构成切片偏离）：

1. `tasks.md` 2.5 把「全局并发信号量」放在管理端鉴权任务组；`design.md` 的 S2 可观察行为
   （登录、成员/Key/账号 CRUD、凭证加密、Key 明文仅一次）不含并发限流，S3 的可观察行为
   （`/v1/ocr/image` 经百度返回结果）才承载该行为。故其验收归入 Task 3 的 OCR 端点条目。
   三镜：系统镜（行为归属清晰、避免无端点的悬空验收）优先；开发循环镜（可独立验证）受益；
   用户镜无感知。主次判定：系统镜优先。
2. `tasks.md` 6.1–6.3 的真实账号识别与故障切换演练：真实账号契约测试以默认 skip 形式落在
   Task 3/Task 4 的适配器测试内；同厂商/跨厂商切换演练落在 Task 3/Task 4 的 `[e2e]` 条目；
   Task 6 以聚合套件复跑并如实记录 skip 状态。理由：凭证仅本地（C9）、默认 skip 是设计
   既定行为（D12），不另立人工票。

## `T10-choice` 复核

不触发。三个必触发条件逐条判定：

1. `design.md` 含「切片建议」节（「切片与依赖」）且直接采纳——不触发；
2. 出票对草图无实质偏离（无增删/合并/改阻塞边/改切片边界）——不触发；
3. 切片草图与 `design.md` 正文无矛盾——不触发。

诚实边界：以上为出票方自报判定，无确定性捕获路径。

## 票外发现

无（出票阶段未发现需要 fold/defer 的票外问题）。
