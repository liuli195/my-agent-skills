# 01 — 修复 Windows 热修复验证命令的命令行垫片解析

**What to build:** 让 Windows 上配置为 PATH 命令的 hotfix 验证命令正常启动，同时保持现有跨平台行为和安全的非 shell 执行方式。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] Windows 上 PATH 中的 `.cmd` 或 `.bat` 验证命令使用解析后的可启动路径执行。
- [x] 验证命令的其余参数、`shell=False` 和执行顺序保持不变。
- [x] 找不到命令时仍报告 `hotfix_verify_failed`，返回码为 `127`，且不进入推送流程。
- [x] Linux/macOS 现有命令解析测试继续通过。
- [x] 新增 `.cmd` 垫片解析和缺失命令回归测试。
- [x] Build and Verify（构建与验证）快速检查通过，并完成最小真实 hotfix 验证入口冒烟。

## Behavior Evidence（行为证据）

- 红灯：新增 Windows `.cmd` 解析测试在修复前失败，`shutil.which()` 未被调用。
- 绿灯：`python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k hotfix_verify_command` → `5 passed`。
- 受影响测试：PR Flow 相关测试 → `259 passed`。
- 真实冒烟：临时本地远端和 `.cmd` 垫片执行真实 `hotfix` 入口，输出 `status: hotfix_complete`，远端回读匹配。
- 快速验证：`build-and-verify verify --project .` → `status: passed`。
- 审查：规范审查无阻断发现；规格审查发现的相对路径风险已修复，针对性复核无阻断发现。
