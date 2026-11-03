# Spec Delta

## Purpose

定义 OCR Gateway 的容器化部署与启动契约：一键起、启动期自动迁移、配置与凭证注入、数据持久化、单实例约束、构建可复现与运行身份，使「服务起得来、数据不丢、凭证不外泄」成为可观察、可验证的系统行为。

## ADDED Requirements

### Requirement: R-DEP-01 启动期自动迁移

容器启动时系统 SHALL 先完成数据库迁移再启动 HTTP 服务；迁移失败时 MUST 以非零退出码终止，且 MUST NOT 进入对外服务状态。

#### Scenario: 空数据卷首次启动

- **WHEN** 容器以空数据卷启动且配置有效
- **THEN** 系统自动完成迁移，启动完成后 `GET /healthz` 返回 200

#### Scenario: 迁移失败

- **WHEN** 迁移因数据库不可写而失败
- **THEN** 容器以非零退出码终止，且不监听 HTTP 端口

#### Scenario: 重复启动幂等

- **WHEN** 容器在已完成迁移的数据卷上再次启动
- **THEN** 迁移为无操作，服务正常启动

### Requirement: R-DEP-02 健康状态可被编排消费

系统 SHALL 提供可被容器编排消费的健康状态：`GET /healthz` 在数据库可用时返回 200，不可用时返回 503。

#### Scenario: 数据库可用

- **WHEN** 编排执行健康探测且数据库可访问
- **THEN** 返回 200，响应体含 `status=ok` 与 `db=ok`

#### Scenario: 数据库不可用

- **WHEN** 数据库不可访问
- **THEN** 返回 503，编排将该容器标记为不健康

### Requirement: R-DEP-03 配置与凭证只经环境注入

系统 SHALL 只从环境变量（含 `env_file`）读取 `MASTER_KEY`、`ADMIN_PASSWORD` 与运行期配置；必填项缺失时 MUST 在启动阶段失败。

#### Scenario: 缺必填配置

- **WHEN** 未提供 `MASTER_KEY` 或 `ADMIN_PASSWORD`
- **THEN** 容器在启动阶段以非零退出码终止，不进入服务态

#### Scenario: 配置完整

- **WHEN** 必填项齐备且格式合法
- **THEN** 服务正常启动并通过健康检查

### Requirement: R-DEP-04 镜像与构建上下文不含凭证

镜像 MUST NOT 包含任何真实凭证或本地运行数据；构建上下文 MUST 排除 `.env`、`data/` 与本地凭证文档。

#### Scenario: 镜像内容扫描

- **WHEN** 对构建产物执行内容扫描
- **THEN** 镜像内不含 `MASTER_KEY`、`ADMIN_PASSWORD`、百度或腾讯密钥的任何取值

#### Scenario: 构建上下文排除

- **WHEN** 执行镜像构建
- **THEN** `.env`、`data/` 与本地凭证文档不进入构建上下文

### Requirement: R-DEP-05 数据持久化

容器化部署 SHALL 将 `DATA_DIR` 设为绝对路径并挂载为卷；容器销毁重建后 MUST 保留既有业务数据。

#### Scenario: 容器重建保留数据

- **WHEN** 容器被销毁并以同一卷重建
- **THEN** 先前创建的成员、API Key 与账号仍然存在

#### Scenario: 数据写入卷内

- **WHEN** 服务运行并产生配额计数与请求日志
- **THEN** 数据落在挂载卷内，不落在容器可写层

### Requirement: R-DEP-06 单实例约束

容器化部署 MUST NOT 以多于一个 worker 运行；检测到多 worker 配置时系统 MUST 拒绝启动并给出明确原因。

#### Scenario: 多 worker 配置被拒

- **WHEN** 设置了 `WEB_CONCURRENCY` 或 `UVICORN_WORKERS` 大于 1，或传入 `--workers` 大于 1
- **THEN** 启动失败并报告单实例约束

#### Scenario: 默认单 worker

- **WHEN** 未设置任何 worker 相关变量
- **THEN** 服务以单 worker 正常启动

### Requirement: R-DEP-07 构建可复现且索引可参数化

镜像构建 SHALL 安装锁文件锁定的依赖版本，并 SHALL 允许通过参数指定包索引；构建 MUST NOT 依赖锁文件中记录的默认下载地址可达。

#### Scenario: 离线环境构建成功

- **WHEN** 默认包索引不可达，但参数指定的索引可达
- **THEN** 构建成功，且安装的依赖版本与锁文件一致

#### Scenario: 无可达索引

- **WHEN** 未指定索引且默认索引不可达
- **THEN** 构建失败，不产出可用镜像

### Requirement: R-DEP-08 运行身份与自愈

容器 SHALL 以非 root 用户运行；进程异常退出后 SHALL 由编排自动重启；容器日志 SHALL 设有大小与份数上限。

#### Scenario: 非 root 运行

- **WHEN** 检查容器内主进程身份
- **THEN** 其 uid 不为 0

#### Scenario: 异常退出后自愈

- **WHEN** 容器主进程以非零码退出
- **THEN** 编排自动重启该容器

#### Scenario: 日志轮转

- **WHEN** 日志增长超过配置的大小上限
- **THEN** 日志轮转并只保留限定份数，磁盘不被写满
