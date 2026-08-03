# 01 — 修复 Windows 热修复验证命令的命令行垫片解析

**What to build:** 让 Windows 上配置为 PATH 命令的 hotfix 验证命令正常启动，同时保持现有跨平台行为和安全的非 shell 执行方式。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Windows 上 PATH 中的 `.cmd` 或 `.bat` 验证命令使用解析后的可启动路径执行。
- [ ] 验证命令的其余参数、`shell=False` 和执行顺序保持不变。
- [ ] 找不到命令时仍报告 `hotfix_verify_failed`，返回码为 `127`，且不进入推送流程。
- [ ] Linux/macOS 现有命令解析测试继续通过。
- [ ] 新增 `.cmd` 垫片解析和缺失命令回归测试。
- [ ] Build and Verify（构建与验证）快速检查通过，并完成最小真实 hotfix 验证入口冒烟。
