# Hand-off · docker-deploy-e2e

## ✅ 完成了什么

- **容器产物**：多阶段 `Dockerfile`（固定基础镜像 digest、uv 固定版本、依赖层缓存、运行期无 dev 依赖/测试）、
  `.dockerignore`、`docker/entrypoint.sh`（root→修属主→降权；迁移失败即退出）、`docker-compose.yml`
  （回环端口、healthcheck、数据卷、restart、优雅停止、日志轮转、构建期索引参数、双 tag）。锚点：
  `Dockerfile:1-67`、`docker/entrypoint.sh:1-19`、`docker-compose.yml:1-49`、`.dockerignore:1-19`。
- **启动契约**：空卷自动迁移 + `/healthz` 200；迁移失败非零退出且不监听；重复启动幂等；缺/非法
  `MASTER_KEY`/`ADMIN_PASSWORD` 启动期失败；多 worker 拒绝。证据：`impl-reports/task2-startup-contract.md`。
- **运行身份与自愈**：主进程 uid=10001、`/data` 属主 app；进程退出后编排自动重启（RestartCount 0→1）；
  数据卷 `down`/`up` 后成员仍在。证据：`impl-reports/task3-compose-run-identity.md`。
- **文档与配置面**：README 以 compose 一键起为主路径（含 TTHW 估算、反代片段、离线索引说明、uv 备选
  路径前置）、`.env.example` 补 `UV_DEFAULT_INDEX` 与容器 `DATA_DIR` 注释、文档静态测试同步。证据：
  `impl-reports/task4-docs-config.md`。
- **真机端到端**：冷启动 7s 到 healthy；三输入（multipart/base64/URL）均 200；缓存命中 `used=0`；
  配额与日志记账正确且不落原文；显式 `provider=baidu` 在无可用账号时 503 不回退；`auto` 由腾讯完成。
  证据：`e2e-acceptance.md`、`impl-reports/task5-e2e-acceptance.md`。
- **质量门**：聚合套件 152 passed / 2 skipped（合同测试按设计跳过）；ruff/mypy 无新增问题；代码审
  pass（自动修 1 项：compose 双 tag）；`verify: PASS`（closeout + retest，单 session 自证）。

## ⏳ 未完成延后

- `openspec/issues/open/T3.md`（OPEN，source_change=`docker-deploy-e2e`）——本地私有凭证文档名仍出现在
  已跟踪的 spec 期评审产物与更早 commit 历史中；文档本体已移出仓库。彻底消除需人工决定是否重写历史。
- 设计风险 A1 的**目标态部分**未覆盖：Windows Docker Desktop 下 bind mount 属主修复已实测可用；
  任意 Linux 宿主上的 bind mount 权限行为仍未实测（design 的 Risks 已记录，属后续部署环境验证）。
- `TRUST_PROXY_HEADERS=true` 的真实反代路径仍为 non-goal（仅 mock 测试覆盖）。

## ▶ 下一阶段建议

1. **Linux 宿主部署演练**：在目标 Linux 服务器上按 README 跑一遍（重点验证 bind mount 属主、基础镜像
   经 mirror 拉取、盘满/只读失败路径），把结果回写 design 的 A1。
2. **镜像交付/回滚流程**：把 `ocr-gateway:0.1.0` 的产出与备份恢复串成可重复脚本（当前为手工命令）；
   若要发布，再引入 registry 与 digest 固定。
3. **T3 收口**：决定是否接受历史暴露；后续 change 的已跟踪文档一律用「仓库外的本地私有凭证文档」代称。
4. 反代真机验收（若上线用到 `TRUST_PROXY_HEADERS`）单开 change。
