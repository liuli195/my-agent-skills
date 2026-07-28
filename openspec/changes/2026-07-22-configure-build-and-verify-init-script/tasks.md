## 1. 初始化脚本契约

- [x] 1.1 在 `tests/test_setup_worktree_script.py` 添加失败测试，覆盖脚本定位仓库根目录、创建或复用 `.venv`（本地虚拟环境）、使用 Python（Python 语言）3.12 和仅安装 `requirements-dev.txt`（开发依赖清单）的契约。
- [x] 1.2 运行该定向测试，确认因初始化脚本尚不存在而失败。

## 2. 工作树环境入口

- [x] 2.1 新增 `scripts/setup-worktree.ps1`，复用量化研究实验室的最小控制流，并适配本仓库仅有的 `requirements-dev.txt`（开发依赖清单）。
- [x] 2.2 运行定向测试，确认脚本契约通过且失败退出码可传播。

## 3. 用户入口验证

- [x] 3.1 在用户明确授权安装依赖后，从工作树外运行 `scripts/setup-worktree.ps1`，确认创建或复用 `.venv`（本地虚拟环境）并完成开发依赖安装。
- [x] 3.2 运行本仓库构建检查和快速验证，确认初始化脚本纳入发布形态后不破坏既有流程。
- [x] 3.3 运行 OpenSpec（开放规格）严格校验并复核规格场景与任务完成状态。

## 验证记录

- 从 `D:\`（磁盘根目录）调用 `scripts/setup-worktree.ps1`：复用本工作树 `.venv`（本地虚拟环境），开发依赖均可用。
- `.venv\Scripts\python.exe -m pytest -q tests/test_setup_worktree_script.py`：2 passed。
- `openspec validate configure-build-and-verify-init-script --strict`（严格规格校验）：通过。
- Build and Verify（构建与验证）的 build（构建检查）和默认 verify（快速验证）：通过。
- 升级判定：用户选择继续 Tweak（小改流程）；15 个变更文件主要为 OpenSpec（开放规格）和 Comet（彗星流程）元数据，未涉及跨模块架构变更。
