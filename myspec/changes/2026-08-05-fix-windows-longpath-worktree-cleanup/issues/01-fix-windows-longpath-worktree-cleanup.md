# 01 — 修复 Windows 长路径工作树清理

**What to build（交付结果）：** 让 Windows（视窗系统）上包含深层 `.local/spec-work` 生成物的已完成 PR（拉取请求）关联工作树，通过现有 PR Flow（拉取请求流程）清理入口完成非强制删除，不再因路径过长留下实体目录。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [ ] Windows（视窗系统）真实 Git 仓库中生成超过系统路径限制的被忽略 `.local/spec-work` 文件后，带删除工作树参数的清理命令成功完成。
- [ ] 清理成功后，目标实体目录和 Git 工作树登记均消失，主工作树保持不变。
- [ ] 长路径支持只作用于当前删除命令，不写入仓库或用户 Git 配置。
- [ ] 短路径、非 Windows（视窗系统）环境、非强制删除和现有 Orca（工作区管理器）分支行为保持兼容。

## Behavior evidence（行为证据）

- Red（红灯）：当前 Git 删除命令在深层 `.local/spec-work` 文件路径下返回 `Filename too long`，并留下目标目录。
- Green（绿灯）：实施后同一真实 Windows 入口删除成功，目标目录和登记均消失。
- Smoke（冒烟）：Build and Verify（构建与验证）快速验证通过，并完成真实 Windows 清理入口冒烟。
- Review（审查）：完成标准与规格审查，无未解决阻断项。
- Unresolved risk（未解决风险）：一般文件锁、Orca（工作区管理器）删除器长路径行为和历史残留目录恢复不在本票据范围内。
