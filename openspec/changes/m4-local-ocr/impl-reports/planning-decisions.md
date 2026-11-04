# Planning Decisions · m4-local-ocr

> 出票依据：`design.md` 的 `## 切片与依赖`（T1–T5）+ `decision-memo.md` 的 `## 承重约束`（C1–C9）。
> 出票预算：5 张功能票 + 1 张收尾票（Task 6）。

## 承重约束 → 票

| 约束 | 内容摘要 | 对应票 | 验收锚 |
| --- | --- | --- | --- |
| C1 | 引擎可离线运行、模型随包分发 | Task 1 / Task 5 | Task 1 断网识别 + 不联网断言；Task 5 镜像无外网 ready |
| C2 | 依赖可进 `python:3.12-slim` | Task 1 / Task 5 | Task 1 extra 可安装；Task 5 镜像 import + 系统库验证 |
| C3 | 冷启动/热调用耗时 | Task 1 / Task 5 | Task 1 warmup 超时与状态；Task 5 p95 基准与 ready 阈值 |
| C4 | 调度器没有 local 通路 | Task 2 | Task 2 `VALID_PROVIDERS`/Scheduler local 分支/403 测试 |
| C5 | 记账口径（quota_used 合计、RPM 独立） | Task 2 / Task 3 | Task 2 local 事件字段与响应 quota=0；Task 3 标签/总览对账 |
| C6 | provider 枚举权威源全集 | Task 2 / Task 3 / Task 4 | Task 2 公共枚举；Task 3 类型拆分/标签；Task 4 状态与面板 |
| C7 | 构建链（`uv export --extra local`） | Task 1 / Task 5 | Task 1 锁校验；Task 5 镜像构建 |
| C8 | 设置热更新是单进程语义 | Task 4 | Task 4 幂等 set_enabled/重启恢复/清缓存 |
| C9 | 镜像体积 | Task 5 | Task 5 体积估算回填与 README |

无「承重约束未映射」项。

## 切片采用与偏离审计

默认采纳 design 的 T1–T5 划分与阻塞边；**一处实质偏离**：

- **切片偏离**：把「Alembic 0003 + `models.py` 约束同步」从 T3（记账与迁移）前移到 T2（公共路由与兜底）；T3 收缩为记账标签、用量/日志筛选与总览对账。| 理由：design 的边是 T3 `Blocked-by: T2`（事件来源），但 T2 的 local 成功路径要写 `provider='local'` 事件，而旧 `ck_usage_provider` 会拒绝——迁移是 T2 的**前置**而非后继。系统镜：避免 T2 的 API 测试在旧 schema 上假绿/跳过；用户镜：无行为变化；开发循环镜：T2 自带 schema 前置、可独立 demo，T3 只做标签与对账，票更内聚。主次判定：**开发循环镜优先**（否则 T2 的验收无法在真实 DB 上通过）。

`T10-choice` 复核（因对草图有实质偏离，必触发）：

- `T10-choice`复核: 将 0003/models.py 前移到 T2、T3 收缩为标签与对账 | 结论 **通过** | 反方：违背 design 的 T3 票边界、T2 变大。反驳：若把迁移留在 T3，T2 的 local 事件写入在 `Base.metadata.create_all` 建库上必然 IntegrityError（`tests/conftest.py:45`），只能假勾或跳过，违反「零用例/未验证不算通过」；迁移 + ORM 一行增量仍在一个工作段内，T2 的边界仍是「local 请求端到端可用」这一行为。证伪条件：若实施中发现 T2 需要同时改聚合/面板，则拆票。

## 其他出票决策

- **T4 与 T2/T3 并行性**：T4 只依赖 T1（LocalEngine），可与 T2/T3 串行执行；本仓实现串行，不引入并行风险。T4 的开关清缓存与 T2 的缓存门禁分属不同票，验收互不重叠。
- **收尾票**：Task 6，`Blocked-by: 1,2,3,4,5`，`R-ID: all`，唯一收尾节点。
- **e2e 标注**：Task 4（设置页 starting→ready、三态/轮询）与 Task 5（镜像离线冒烟、云全挂兜底、回滚演练）标注 `[e2e]`；其余票无 e2e，只跑单元 + 依赖链集成。
- **预算**：功能票 5 张（≤6），收尾票 1 张（不计预算）；无 expand–contract 迁移批次。
