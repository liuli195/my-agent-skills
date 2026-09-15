# 02 — 构建前置并保留软件包元数据完整性

## Parent

- GitHub Issue（GitHub 问题）#234：https://github.com/liuli195/my-agent-skills/issues/234

## What to build

让维护者通过 Build and Verify（构建与验证）的统一构建入口提前运行共享发布仓库元数据门禁，并让发布工作流在不写死仓库名称的前提下继续证明 Tarball（npm 软件包）保留了已校验的源码元数据。

## Acceptance criteria

- [x] 仓库构建配置新增发布元数据检查，并通过 Release Flow（发布流程）的现有项目校验入口检查所有已登记 npm 包。
- [x] 快速验证在 npm 包清单、Release Flow（发布流程）或发布工作流变化时选择相关检查，且成功证据包含非空 `checked`（已检查项）。
- [x] 发布工作流和生成模板删除仓库地址及包目录硬编码。
- [x] 打包后继续比较源码清单和 Tarball 清单的仓库元数据，并保留包名、公开访问、隔离安装、诊断和完整性检查。
- [x] MySpec（自有规格）和 Build and Verify（构建与验证）的构建、快速验证、完整验证及真实命令冒烟通过。

## Behavior evidence

- Red（红灯）：新增公开契约断言后，快速验证分别因缺少构建检查和工作流仍含仓库硬编码失败。
- Green（绿灯）：快速验证检查 8 项且状态为 `passed`；`verify.release-flow` 102 项、`verify.build-and-verify` 223 项、`verify.runtime-boundaries` 11 项通过。
- User-entry smoke（用户入口冒烟）：`build-and-verify build --project .` 实际执行 `build.release-metadata`，`checked`（已检查项）非空且状态通过。
- Tarball（npm 软件包）证据：测试从源码工作流和生成模板提取真实 Node（运行环境）比较命令；相同元数据通过，URL（网址）或目录改变均失败。
- Review（审查）：Standards（规范）与 Spec（规格）提出的快速选择和实际比较测试缺口已补齐；定向复审无阻塞。
- Final verification（最终验证）：完整验证检查 8 项且状态为 `passed`；总时长超过 60 秒预算并产生性能警告，但不影响功能验证结论。
- Unresolved risk（未解决风险）：无。

## Blocked by

- 01 — 共享发布仓库元数据门禁

**Status:** ready-for-agent
