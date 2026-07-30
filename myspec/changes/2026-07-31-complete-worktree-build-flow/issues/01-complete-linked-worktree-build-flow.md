# 01 — 完成关联工作树构建主流程

**What to build:** 让开发者在主工作区和关联工作树依次运行统一初始化入口后，从关联工作树激活其 `.venv`（虚拟环境）并通过唯一的 Build and Verify（构建与验证）`build`（构建检查）入口完成整个构建。移除本地插件包检查对 `claude plugin validate` 的外部依赖，同时保留仓库自有的插件清单、路径、市场登记和发布投影一致性检查。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 修改实现前，Windows 关联工作树完整流程检查稳定复现：TypeScript（类型脚本）编译成功后，Build and Verify 因缺少 `claude`、系统 Python 缺少 PyYAML（YAML 解析库）及其连带投影错误而失败。
- [ ] 主工作区和关联工作树继续使用同一个初始化入口；主工作区准备根级 Node.js（运行时）依赖，各关联工作树只链接兼容的共享依赖。
- [ ] 主工作区和关联工作树继续各自创建或复用 `.venv`，不新增跨工作树共享 Python 环境。
- [ ] Windows 关联工作树流程在运行构建前激活关联工作树的 `.venv`，配置中的子 Python 命令使用同一初始化环境。
- [ ] CI（持续集成）只从 Build and Verify 执行构建和验证，不新增直接 npm、TypeScript 或本地脚本检查入口。
- [ ] 本地插件包构建不再运行或要求 `claude plugin validate`，仓库依赖中不增加 Claude Code（代码代理）包。
- [ ] 本地插件包构建仍检查市场结构、Claude 与 Codex 插件清单名称、必需字段、引用路径、仓库目录边界、重复登记、Codex 开发市场和发布投影一致性。
- [ ] 更新与 `local-plugin-build-checks` 主规格的冲突：删除强制 Claude CLI 校验要求，以仓库自有结构检查作为有效契约。
- [ ] 公开行为回归证明没有安装 `claude` 时合法仓库仍可通过本地插件包构建，而已有损坏清单、越界路径、市场不一致和投影不一致案例仍失败。
- [ ] 现有初始化入口回归继续覆盖主工作区初始化、关联工作树链接、共享依赖缺失、依赖清单不一致、重复运行和失败退出码传播。
- [ ] Windows 关联工作树端到端回归从全新检出开始，依次完成主工作区初始化、关联工作树创建与初始化、环境激活和 Build and Verify 完整构建，并最终成功。
- [ ] 完整验证通过仓库 Build and Verify 入口运行；不以若干单元测试或直接 npm 构建替代端到端主流程。
