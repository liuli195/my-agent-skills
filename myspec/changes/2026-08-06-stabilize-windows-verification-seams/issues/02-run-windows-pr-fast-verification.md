# 02 — 接入 Windows PR 固定基线快速验证

**What to build:** 让现有 Windows（视窗系统）PR（拉取请求）任务在保留真实工作树构建冒烟的同时，通过 Build and Verify（构建与验证）以当前 PR 的固定基线运行受影响检查；手动触发时仍可运行完整验证，最终跨平台汇总门禁保持不变。

**Blocked by:** 01 — 稳定 Windows 验证测试接缝。

**Status:** ready-for-agent

- [x] PR 工作流检出足够的 Git（版本管理）历史，并将不可移动的目标提交作为验证基线。
- [x] Windows PR 任务通过已安装的 Build and Verify 入口运行快速验证，不直接调用测试运行器或仓库内部脚本。
- [x] 相关 PR 的验证结果只有在 `checked` 非空且状态通过时成功，无效基线或检查失败会阻断任务。
- [x] 手动触发工作流时可以通过当前检出中的 Build and Verify 入口运行 Windows 完整验证。
- [x] 现有 Windows 工作树初始化、环境激活和构建主路径保持执行。
- [x] Linux（操作系统）完整验证、`Full Verify`（完整验证）汇总名称及其跨平台依赖保持不变。
- [x] 工作流契约测试锁定固定基线快速验证和手动完整验证，不修改远端 Ruleset（规则集）。

## Evidence

- Red：原 Windows 任务没有固定基线验证步骤；首次集成验证又暴露了手动完整验证入口与当前候选包契约冲突，以及虚拟环境中的 Python Launcher（Python 启动器）定位错误。
- Green：工作流契约 3 passed，发布工作流契约 1 passed，虚拟环境启动器与打包 MySpec 入口 2 passed，运行边界 11 passed。
- Integration：`build-and-verify verify --project . --base 727a58484b5a5b3bfde1d80378691567b2497532` 返回 `status: passed`、`full-not-run: true`，并检查全部 8 个非空 `checked` 项。
- User-entry smoke：Windows 虚拟环境中已通过同一固定基线命令；真实 GitHub PR 任务留待交付阶段确认。
- Unresolved risk：仅剩 GitHub 托管环境表达式和任务编排需要真实 PR CI（拉取请求持续集成）确认。
