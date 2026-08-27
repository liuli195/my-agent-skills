# 01 — 修复 Windows 长路径工作树清理

**What to build（交付结果）：** 让 Windows（视窗系统）上包含深层 `.local/spec-work` 生成物的已完成 PR（拉取请求）关联工作树，通过现有 PR Flow（拉取请求流程）清理入口完成非强制删除，不再因路径过长留下实体目录。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** completed

- [x] Windows（视窗系统）真实 Git 仓库中生成超过系统路径限制的被忽略 `.local/spec-work` 文件后，带删除工作树参数的清理命令成功完成。
- [x] 清理成功后，目标实体目录和 Git 工作树登记均消失，主工作树保持原有安全和目标分支同步行为。
- [x] 长路径支持只作用于当前删除命令，不写入仓库或用户 Git 配置。
- [x] 短路径、非 Windows（视窗系统）环境、非强制删除和现有 Orca（工作区管理器）分支行为保持兼容。

## Behavior evidence（行为证据）

- Red（红灯）：`python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k windows_long_paths` 首次运行复现 `git_worktree_remove_failed` 和 `Filename too long`。
- Green（绿灯）：公开清理入口回归通过；相关 PR Flow（拉取请求流程）测试 11 项通过，目标目录和登记均消失。
- Fast Verification（快速验证）：`build-and-verify verify --project .` 通过，`verify.pr-flow` 和 `verify.runtime-boundaries` 实际执行，完整验证未运行。
- User-entry Smoke（用户入口冒烟）：临时真实 Windows（视窗系统）Git 仓库执行 `cleanup --remove-worktree` 成功，目标目录不存在、登记消失、主工作树保持预期状态，`core.longpaths` 未持久写入。
- Review（审查）：规范与规格首次审查发现测试未覆盖公开入口，已修复；后续审查及主工作树验收修正复审均通过，无阻塞项。
- Unresolved risk（未解决风险）：一般文件锁、Orca（工作区管理器）删除器长路径行为和历史残留目录恢复不在本票据范围内。
