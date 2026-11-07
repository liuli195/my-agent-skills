# 01 — 阻断同工作树工具链同步

**What to build（构建内容）：** 当 PR Flow（拉取请求流程）的目标工作树同时是开发工具源码工作树时，公开命令在任何受管工具链文件或 PR 操作前安全停止，并给出隔离恢复路径；隔离工作树和发布模式继续保持原有行为。

**Blocked by（前置项）：** None — can start immediately

**Status（状态）：** completed

- [x] `init`、`complete` 和 `tweak` 使用目标项目目录读取工具诊断，并能识别工具链工作树冲突。
- [x] 冲突返回稳定的 `toolchain_same_worktree_unsupported` 停止原因，包含源码工作树、目标工作树和隔离恢复提示。
- [x] 冲突停止发生在文件写入、暂存、提交、PR 创建或 PR 同步前；工作区、暂存区、提交历史和远端调用均保持不变。
- [x] 隔离开发源码工作树、发布版工具和未迁移旧仓库继续通过现有行为测试。
- [x] 公开命令回归测试覆盖 `--project` 与调用目录不同、未发布源码提交和工具诊断身份字段不完整的场景。
- [x] `pr-flow-complete`、`pr-flow-tweak` 和相关入口文档说明冲突及恢复方式。
- [x] 通过针对 PR Flow 的快速回归、Build and Verify（构建与验证）快速验证，以及同工作树停止和隔离工作树继续的真实入口冒烟。

## Behavior Evidence（行为证据）

- Red（红灯）：新增公开入口回归首次运行失败，旧实现返回 `toolchain_identity_invalid` 或使用错误的诊断目录。
- Green（绿灯）：`pytest tests/test_pr_flow_cli.py -q` 通过（279 项）；PR Flow 插件测试通过（13 项）。
- Fast Verification（快速验证）：`build-and-verify verify --project .` 通过，4 个检查均实际执行，完整验证未运行。
- User-entry Smoke（用户入口冒烟）：同工作树真实 `init` 返回 `toolchain_same_worktree_unsupported`，提交和两个受管文件哈希保持不变；隔离工作树真实 `init` 返回 `initialized`，生成工作流固定到当前源码提交。
- Review（审查）：Standards（规范）和 Spec（规格）双轴审查均通过，无阻塞项。
- Unresolved Risk（未解决风险）：无；同一工作树继续运行仍是明确不支持的边界，恢复方式为隔离目标工作树或发布版工具。
