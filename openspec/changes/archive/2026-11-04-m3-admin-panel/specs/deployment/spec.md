# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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

## ADDED Requirements

### Requirement: R-DEP-10 发布版本与回滚锚

发布镜像的版本 tag SHALL 不可变；新版本 MUST 使用新 tag，MUST NOT 覆盖既有发布 tag；回滚 MUST 同时恢复与目标镜像匹配的数据库 schema 版本（部署前备份或显式 downgrade）。`[spec-review-amendment R-01]`

#### Scenario: 新版本不覆盖旧 tag
- **WHEN** 发布 `0.2.0`
- **THEN** `0.1.0` tag 仍指向旧镜像

#### Scenario: 回滚到 0.1.0
- **WHEN** 数据库已升级到 `0002` 后回滚到 `0.1.0`
- **THEN** 先恢复部署前备份（或执行 `downgrade`）再启动旧镜像，`/healthz` 返回 200
