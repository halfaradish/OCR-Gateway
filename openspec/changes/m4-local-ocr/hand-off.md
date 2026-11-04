# Hand-off · m4-local-ocr

## ✅ 完成了什么

- **本地 OCR 能力**：可选 extra `local`（rapidocr 3.10 + onnxruntime 1.31.1，模型随 wheel 内置）、
  spawn 进程池 worker、状态机（stopped/starting/ready/error/unavailable）、warmup/超时终止/重建/
  退避/generation，均经单测与 slow 真实引擎测试。
- **公共路由**：`provider=local`（403/502/503/504 语义）、`auto` 按 `reserve_eff` 兜底、缓存门禁
  先于命中、local 成功 `quota.used=0`、`/v1/providers` local 条目。
- **记账与迁移**：0003 放宽 `usage_event.provider` 至含 local（downgrade 映射回 auto）、`models.py`
  同步、local 事件 `account_id=NULL`、用量/日志/总览标签与对账。
- **管理端**：settings 开关（热更新、清缓存、重启恢复）、`/api/admin/local-ocr/status`、设置页
  状态卡（三态/轮询/dirty 提交/窄屏）。
- **交付**：0.3.0 镜像（内置 extra + libgomp1）、README/.env.example/tech-selection 文档、
  镜像冒烟脚本、p95 基准、回滚演练（0.3.0 → 0.2.1）。
- 代码审 7 项自动修复（超时恢复、竞态、关闭上限、fallback 日志、错误展示），复审后全绿。

验证锚：`verify-report.md`（PASS）；`verify-evidence-closeout.json @ 6f71ca8`；代码审
`code-review-report.md @ 7064fae`。

## ⏳ 未完成延后

- `openspec/issues/open/` 中无 `source_change: m4-local-ocr` 的条目；本 change 无 defer 台账项。
- 三项 **Minor 观测**（未建台账，记录在 `verify-report.md` 缺口区）：
  1. design.md 的镜像体积估算未回填实测值（README 已回填；改 design 会触发设计锚失鲜）。
  2. 全量 `frontend/e2e/admin.mjs` 依赖外部种子「Ming」（既有测试基建缺口）。
  3. 镜像冒烟未显式记录 worker 子进程数（状态只报 `concurrency`）。

## ▶ 下一阶段建议

- **本地独立配额/限流**（memo 接受边角 A2/Q4）：显式 `provider=local` 目前只受 Key RPM 与全局
  并发约束；若观测到 CPU 被持续打满，另开 change 增加本地日计数/限额。
- **e2e 种子治理**：把 `admin.mjs` 依赖的「Ming」种子写成脚本（或改为测试内自建），让全量
  e2e 可在干净库运行；本 change 的 `local-ocr.mjs` 已独立可跑。
- **性能回填**：把 0.3.0 实测体积（559MB / venv 432MB）与服务器 2 核 4G 的 p95 写回 design
  的下一个修订版（随下一次设计门）。
- **模型质量抽样**：用真实业务截图抽样对比本地与云厂商；若准确率不足，按 Non-Goals 的可证伪
  假设另开 change 引入更大/语言模型（保持离线分发）。
