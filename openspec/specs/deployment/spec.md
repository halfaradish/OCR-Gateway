# deployment Specification

## Purpose
定义 OCR Gateway 的容器化部署与启动契约：一键起、启动期自动迁移、配置与凭证注入、数据持久化、单实例约束、构建可复现、面板产物随镜像交付与运行身份，使「服务起得来、数据不丢、凭证不外泄」成为可观察、可验证的系统行为。

## Requirements

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

容器编排 SHALL 以既有 `GET /healthz`（端点契约由 `ocr-api` 的 R-API-06 拥有）作为健康探测入口；本要求只约束编排侧的消费行为，不重述端点状态码契约。`[spec-review-amendment]` 去重：原措辞与 R-API-06 形成两个真相源。

#### Scenario: 数据库可用

- **WHEN** 编排执行健康探测且数据库可访问
- **THEN** 探测请求得到 R-API-06 规定的成功响应，编排将容器标记为健康

#### Scenario: 数据库不可用

- **WHEN** 数据库不可访问
- **THEN** 探测请求得到 R-API-06 规定的失败响应，编排将该容器标记为不健康

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

- **WHEN** 服务运行并产生配额计数与用量事件（`usage_events`）
- **THEN** 这些持久化数据落在挂载卷内，不落在容器可写层；进程日志经 stdout 由容器日志驱动处理（含轮转），不写入卷

> `[spec-review-amendment]` 原措辞「请求日志落在挂载卷内」与 `backend/app/logging_setup.py:26`（stdout handler）不符，且 `usage_events` 与 stdout 日志是两类数据；此处按代码事实拆开表述。

### Requirement: R-DEP-06 单实例约束

容器化部署 MUST NOT 以多于一个 worker 运行；检测到多 worker 配置时系统 MUST 拒绝启动并给出明确原因。

#### Scenario: 多 worker 配置被拒

- **WHEN** 设置了 `WEB_CONCURRENCY` 或 `UVICORN_WORKERS` 大于 1，或传入 `--workers` 大于 1
- **THEN** 启动失败并报告单实例约束

#### Scenario: 默认单 worker

- **WHEN** 未设置任何 worker 相关变量
- **THEN** 服务以单 worker 正常启动

### Requirement: R-DEP-07 构建可复现且索引可参数化

镜像构建 SHALL 安装锁文件锁定的 Python 与前端依赖版本，并 SHALL 允许通过参数分别指定 PyPI 与 npm 包索引；构建 MUST NOT 依赖锁文件中记录的默认下载地址可达。

#### Scenario: 离线环境构建成功
- **WHEN** 默认 Python 包索引不可达，但参数指定的索引可达
- **THEN** 构建成功，且安装的依赖版本与锁文件一致

#### Scenario: npm 索引可参数化
- **WHEN** 默认 npm 源不可达，但参数指定的 npm 索引可达
- **THEN** 前端依赖安装与构建成功，且版本与前端锁文件一致

#### Scenario: 无可达索引
- **WHEN** 未指定索引且默认索引不可达
- **THEN** 构建失败，不产出可用镜像

### Requirement: R-DEP-08 运行身份与自愈

容器主进程 SHALL 以非 root 用户运行；entrypoint MAY 在降权前以 root 修复数据卷属主（Q1=A，人 2026-11-03 拍板）；进程异常退出后 SHALL 由编排自动重启；容器日志 SHALL 设有大小与份数上限。`[spec-review-amendment]` 明确「主进程非 root」而非「容器初始用户非 root」，与 Q1=A 的 root→chown→drop 一致。

#### Scenario: 非 root 运行

- **WHEN** 检查容器内主进程身份
- **THEN** 其 uid 不为 0

#### Scenario: 异常退出后自愈

- **WHEN** 容器主进程以非零码退出
- **THEN** 编排自动重启该容器

#### Scenario: 日志轮转

- **WHEN** 日志增长超过配置的大小上限
- **THEN** 日志轮转并只保留限定份数，磁盘不被写满

### Requirement: R-DEP-09 面板产物随镜像交付

运行镜像 SHALL 包含当前版本的前端构建产物，构建 MUST NOT 依赖宿主机预装 Node 或宿主机预先构建的产物；产物 MUST NOT 包含任何凭证或 Key 明文。`[spec-review-amendment R-01]`

#### Scenario: 镜像内构建
- **WHEN** 在干净检出上执行镜像构建
- **THEN** 构建阶段产出前端资源并复制进运行镜像，无需宿主机 Node

#### Scenario: 镜像托管面板
- **WHEN** 新镜像启动且请求 `/`
- **THEN** 返回面板入口 HTML，静态资源请求返回 200

#### Scenario: 产物不含敏感值
- **WHEN** 扫描前端构建产物
- **THEN** 不含 `MASTER_KEY`、`ADMIN_PASSWORD`、账号凭证或 API Key 的任何取值

#### Scenario: 回滚镜像
- **WHEN** 回滚到不含面板产物的旧镜像
- **THEN** 先把数据库恢复到与旧镜像匹配的 schema 版本（部署前备份或显式 `alembic downgrade`），旧镜像启动后公共与管理 API 仍正常，`/` 返回 404（旧镜像没有面板路由）

### Requirement: R-DEP-10 发布版本与回滚锚

发布镜像的版本 tag SHALL 不可变；新版本 MUST 使用新 tag，MUST NOT 覆盖既有发布 tag；回滚 MUST 同时恢复与目标镜像匹配的数据库 schema 版本（部署前备份或显式 downgrade）。`[spec-review-amendment R-01]`

#### Scenario: 新版本不覆盖旧 tag
- **WHEN** 发布 `0.2.0`
- **THEN** `0.1.0` tag 仍指向旧镜像

#### Scenario: 回滚到 0.1.0
- **WHEN** 数据库已升级到 `0002` 后回滚到 `0.1.0`
- **THEN** 先恢复部署前备份（或执行 `downgrade`）再启动旧镜像，`/healthz` 返回 200

### Requirement: R-DEP-11 运行镜像内置本地 OCR 依赖
运行镜像 SHALL 通过锁文件安装 optional extra `local`（rapidocr + onnxruntime 及其传递依赖），构建 MUST 继续支持通过参数指定 Python 索引；模型 MUST 随依赖包进入镜像，容器 MUST NOT 依赖运行期下载模型；本地 OCR 开关默认关闭。构建 MUST 验证镜像内可导入 rapidocr 与 onnxruntime；若基础镜像缺系统库（如 `libgomp1`），构建期 MUST 安装。版本升级 MUST 覆盖全部版本源：`backend/pyproject.toml`、`backend/app/__init__.py`、`frontend/package.json`、`backend/uv.lock` 的 project version、README 版本锚、compose tag。`[spec-review-amendment R-22/R-36]` `[m4-local-ocr]`

#### Scenario: 构建包含本地依赖
- **WHEN** 用参数指定的可达索引构建 0.3.0 镜像
- **THEN** 镜像内可导入 rapidocr 与 onnxruntime，安装版本与锁文件一致

#### Scenario: 系统库缺失
- **WHEN** 基础镜像导入 onnxruntime 时缺 `libgomp1` 等系统库
- **THEN** 构建期安装所需系统库并重新验证 import，不把问题留到运行期

#### Scenario: 无外网启动
- **WHEN** 容器在无外网环境启动且未开启本地 OCR
- **THEN** 服务正常启动、`/healthz` 为 ok，不产生任何模型下载请求

#### Scenario: 开启后离线就绪
- **WHEN** 在无外网的容器内开启本地 OCR
- **THEN** worker 使用镜像内置模型完成预热并进入 `ready`
