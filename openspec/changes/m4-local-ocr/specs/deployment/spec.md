# deployment Specification

## ADDED Requirements

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
