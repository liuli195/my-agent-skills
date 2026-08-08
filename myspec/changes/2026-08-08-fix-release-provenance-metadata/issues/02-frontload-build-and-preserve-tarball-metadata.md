# 02 — 构建前置并保留软件包元数据完整性

## Parent

- GitHub Issue（GitHub 问题）#234：https://github.com/liuli195/my-agent-skills/issues/234

## What to build

让维护者通过 Build and Verify（构建与验证）的统一构建入口提前运行共享发布仓库元数据门禁，并让发布工作流在不写死仓库名称的前提下继续证明 Tarball（npm 软件包）保留了已校验的源码元数据。

## Acceptance criteria

- [ ] 仓库构建配置新增发布元数据检查，并通过 Release Flow（发布流程）的现有项目校验入口检查所有已登记 npm 包。
- [ ] 快速验证在 npm 包清单、Release Flow（发布流程）或发布工作流变化时选择相关检查，且成功证据包含非空 `checked`（已检查项）。
- [ ] 发布工作流和生成模板删除仓库地址及包目录硬编码。
- [ ] 打包后继续比较源码清单和 Tarball 清单的仓库元数据，并保留包名、公开访问、隔离安装、诊断和完整性检查。
- [ ] MySpec（自有规格）和 Build and Verify（构建与验证）的构建、快速验证、完整验证及真实命令冒烟通过。

## Blocked by

- 01 — 共享发布仓库元数据门禁

**Status:** ready-for-agent
