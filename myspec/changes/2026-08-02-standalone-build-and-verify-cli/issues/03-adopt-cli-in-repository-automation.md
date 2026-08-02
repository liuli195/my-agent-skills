# 03 — 将仓库自动化改用 Build and Verify CLI

**What to build（构建内容）：** 本仓库自身的构建、验证、发布前检查、Skill（技能）说明和正式 MySpec（自有规格）契约使用 Build and Verify（构建与验证）CLI（命令行程序），不再依赖仓库复制的运行时快照或 MySpec 专用 npm（软件包管理器）发布假设。

**Blocked by（前置项）：** 01 — 统一工具生命周期与身份；02 — 迁移 Build and Verify 旧运行时。

**Status:** ready-for-agent

- [ ] 本仓库受管自动化和用户入口改用新 CLI（命令行程序）；调用方转换不改变既有构建、快速验证或完整验证选择语义。
- [ ] Build and Verify、Plugin Sync（插件同步）和 Release Flow（发布流程）的运行时快照契约被最小替换，没有并行旧入口。
- [ ] 与本次发布候选相关的验证保持快速冒烟，不新增 Tarball（npm 包文件）端到端回归。
- [ ] 现有正式规格中与新行为冲突的要求同步更新。
- [ ] 仓库的既有快速构建与验证入口通过。
