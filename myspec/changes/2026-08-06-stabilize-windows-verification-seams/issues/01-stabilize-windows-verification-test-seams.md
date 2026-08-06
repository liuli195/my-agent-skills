# 01 — 稳定 Windows 验证测试接缝

**What to build（建设内容）：** 让 Windows（视窗系统）下的 MySpec（自有规格）受控 Git（版本管理）测试和工作树 PowerShell（命令行程序）测试只依赖稳定行为，不再依赖 Git 安装目录布局、宿主颜色、宿主换行或 Git Bash（Git 命令行环境）附带命令；同时让 MySpec 检查覆盖测试实际读取的输入。

**Blocked by（阻塞项）：** None（无）— can start immediately（可立即开始）。

**Status（状态）：** `ready-for-agent`

- [x] 受控 Git 替身把系统解析出的精确命令路径原样转发，并在不同合法 Windows 路径形态下完成 MySpec 开发模式入口。
- [x] `powershell -File` 与 `pwsh -File` 的真实失败入口在 ANSI（终端控制码）和换行不同的情况下仍验证相同用户提示。
- [x] 提示断言失败不会遮蔽“不调用安装命令”和“不覆盖已有目录”等安全后置条件。
- [x] Windows 工作树测试不再依赖外部 `true` 命令且不会因此静默跳过。
- [x] MySpec 验证检查的触发路径与缓存输入包含测试实际读取的共享生命周期、仓库属性、忽略规则和正式规格。
- [x] 最小红灯能够分别复现错误 Git 转发和 PowerShell 原始子串断言失败，修复后同一检查转绿。

## Evidence（证据）

- Red（红灯）：Pi/PR Flow（拉取请求流程）环境稳定生成不存在的 `C:\Program Files\cmd\git.exe`，17 个打包 MySpec 测试报 `invalid_dev_source: git_root`；PowerShell 渲染把目标短语拆成多行后，原始子串断言失败。
- Green（绿灯）：包含空格路径的 `.cmd` Git 替身已通过候选 Tarball（压缩包）安装后的裸 `myspec` 开发模式入口（1 passed）；真实工作树脚本测试在 `powershell` 和 `pwsh` 下通过（7 passed）；MySpec 检查输入契约通过（1 passed）。
- User-entry smoke（用户入口冒烟）：候选 Tarball 安装后的裸 `myspec` 开发模式入口，以及两个真实 PowerShell `-File` 入口均已覆盖。
- Review（审查）：初审发现的路径重写、命令转发覆盖和过大占位文件均已修复；命令转发已并入现有打包用户入口，运行边界检查 11 passed；Windows PR 工作流项属于后续票据 2。
- Integration（集成）：固定基线快速验证检查全部 8 个非空检查项并返回 `status: passed`；无生产行为变化。
- Unresolved risk（未解决风险）：仅剩最终双轴审查与真实 PR CI（拉取请求持续集成）。
