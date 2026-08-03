# 02 — 阻止 update 静默跳过旧来源迁移

**What to build（构建内容）：** 当任一受支持客户端仍使用 Legacy MySpec Source（旧 MySpec 来源）时，`update`（更新）在任何写入前停止，并给出实际受影响客户端的精确迁移命令；完成迁移后，重新运行 `update` 能正常刷新稳定来源。

**Blocked by（前置项）：** 01 — 统一 Codex 配置目录解析并隔离 Orca 临时目录。

**Status（状态）：** completed

- [x] 更新前置检查能区分稳定来源、旧来源和无关来源，不把旧来源当作未安装。
- [x] 发现旧来源时，`update` 以非零结果停止，不安装软件包、不创建待处理状态、不修改客户端配置。
- [x] 错误输出列出实际受影响客户端和精确的 `init` 迁移命令，不触碰未受影响客户端。
- [x] 迁移失败可安全重试，并继续遵守既有项目级来源和无关客户端保护规则。
- [x] 完成迁移后重新执行 `update` 能刷新稳定来源并通过最终诊断。
- [x] MySpec 和 Build and Verify 的打包命令行入口、失败路径、迁移路径和重试路径验证通过。

## Verification（验证）

- 打包入口目标测试：MySpec 和 Build and Verify 的旧来源阻断、无写入、迁移失败重试和迁移后 `update` 均通过。
- Build and Verify 快速验证：`verify.build-and-verify` 214/214、`verify.runtime-boundaries` 11/11 通过；`verify.my-spec` 82 项通过，12 项为既有受控开发源 `npm link` 换行导致的 `invalid_dev_source: dirty_worktree` 失败。
- 项目级保护：启用中的项目级旧来源会先阻断；`init --pi` 按既有契约禁用后，`update` 放行且保留项目文件。
- 最终针对性审查：无阻断发现。
