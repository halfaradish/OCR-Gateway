# deployment Specification

## ADDED Requirements

### Requirement: R-DEP-11 运行镜像内置本地 OCR 依赖
运行镜像 SHALL 通过锁文件安装 optional extra `local`（rapidocr + onnxruntime 及其传递依赖），构建 MUST 继续支持通过参数指定 Python 索引；模型 MUST 随依赖包进入镜像，容器 MUST NOT 依赖运行期下载模型；本地 OCR 开关默认关闭。`[m4-local-ocr]`

#### Scenario: 构建包含本地依赖
- **WHEN** 用参数指定的可达索引构建 0.3.0 镜像
- **THEN** 镜像内可导入 rapidocr 与 onnxruntime，安装版本与锁文件一致

#### Scenario: 无外网启动
- **WHEN** 容器在无外网环境启动且未开启本地 OCR
- **THEN** 服务正常启动、`/healthz` 为 ok，不产生任何模型下载请求

#### Scenario: 开启后离线就绪
- **WHEN** 在无外网的容器内开启本地 OCR
- **THEN** worker 使用镜像内置模型完成预热并进入 `ready`
