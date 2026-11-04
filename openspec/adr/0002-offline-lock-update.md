# ADR-0002: 离线环境更新 `uv.lock` —— 镜像解析后把源 URL 规范化回 PyPI

- Status: accepted
- Date: 2026-11-04

## Context

本项目跟踪 `backend/uv.lock`，并由 ADR-0001 规定：镜像构建用 `uv export` + `uv pip install --index-url <mirror>`，
**MUST NOT 把区域镜像写进被 git 跟踪的锁文件**（否则任何 clone 到其他地区的副本都会莫名走国内镜像）。

M4 需要新增可选依赖 `rapidocr` / `onnxruntime`（`[project.optional-dependencies].local`）。
`uv export --frozen` 要求锁文件与 `pyproject.toml` 一致，因此必须重新解析锁文件。但本机
`pypi.org` / `files.pythonhosted.org` 不可达，唯一可用的是国内镜像，于是直接 `uv lock` 会把
**全部** 既有依赖的 `source.registry` 与 wheel 下载地址改写成镜像地址：

```
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv lock
grep -c "pypi.tuna.tsinghua.edu.cn" uv.lock  → 1795
grep -c "files.pythonhosted.org\|pypi.org/simple" uv.lock → 0
```

这正好落在 ADR-0001 否决过的「对镜像重新生成 uv.lock」分支上，不能用「反正 Dockerfile 不读 URL」
糊弄过去——`uv sync` 的读者会直接踩到。

## Decision

更新锁文件分三步，且**只允许新增依赖带来的版本变化**：

1. 在 `backend/pyproject.toml` 声明 extra（本次为 `local = ["rapidocr>=3.10,<4", "onnxruntime>=1.20"]`）；
2. 用镜像解析：`UV_DEFAULT_INDEX=<mirror> uv lock`；
3. **把源地址规范化回 PyPI 规范形态**（纯 host 替换，路径/哈希/尺寸不变）：

   ```
   https://pypi.tuna.tsinghua.edu.cn/simple    → https://pypi.org/simple
   https://pypi.tuna.tsinghua.edu.cn/packages/ → https://files.pythonhosted.org/packages/
   ```

4. 校验：`uv lock --check --offline` 必须退出 0；`uv export --frozen --no-dev --extra local …`
   必须列出新增包；`git diff backend/uv.lock` 必须只含新增包与源地址行，**既有包版本 MUST NOT 变化**。

本次实测结果：既有 53 个包版本 0 变化，新增 15 个包；normalize 后 `tuna` 计数为 0，
`pypi.org/simple` 76 处、`files.pythonhosted.org` 1719 处，`uv lock --check --offline` 通过。

## Alternatives

- **把镜像 URL 留在锁文件里（已否决）** —— 违反 ADR-0001；锁文件是跨地区共享的仓库资产。
- **不更新 `uv.lock`，另写 `requirements-local.txt`（已否决）** —— 依赖出现双真相源，
  `uv sync --extra local` 失效，升级时两处都要改，长期必然漂移。
- **把 local 依赖并入主依赖（已否决）** —— 仍需重解析锁文件（同样要规范化），还会让默认开发/测试
  环境强制安装约 200MB 依赖，违背「默认不安装、extra 启用」的既有选型。
- **手写锁文件条目（已否决）** —— 哈希、平台矩阵、marker 都靠手算，错误无法被 `--frozen` 提前发现。

## Consequences

- **正面**：锁文件保持区域中立；`uv export --extra local` 与既有构建链兼容；离线机器也能升级依赖。
- **负面**：锁的更新流程多一步 host 替换，读者不看本 ADR 会以为锁被动过手脚。
- **负面**：规范化依赖「镜像路径与 PyPI 路径逐字一致」这一事实；本次已对既有包抽样核对
  （fastapi / sqlalchemy 的 `/packages/...` 后缀完全一致）。若某镜像改写了路径布局，规范化会产出
  404 地址，`uv sync` 才会暴露——因此**只允许在核对后缀一致后替换**。
- **失效条件**：若本机/CI 能直连 PyPI，直接 `uv lock` 即可，无需本流程。
