# 01 — 稳定 Windows 验证测试接缝

**What to build:** 让 Windows（视窗系统）下的 MySpec（自有规格）受控 Git（版本管理）测试和工作树 PowerShell（命令行程序）测试只依赖稳定行为，不再依赖 Git 安装目录布局、宿主颜色、宿主换行或 Git Bash（Git 命令行环境）附带命令；同时让 MySpec 检查覆盖测试实际读取的输入。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 受控 Git 替身把系统解析出的精确命令路径原样转发，并在不同合法 Windows 路径形态下完成 MySpec 开发模式入口。
- [ ] `powershell -File` 与 `pwsh -File` 的真实失败入口在 ANSI（终端控制码）和换行不同的情况下仍验证相同用户提示。
- [ ] 提示断言失败不会遮蔽“不调用安装命令”和“不覆盖已有目录”等安全后置条件。
- [ ] Windows 工作树测试不再依赖外部 `true` 命令且不会因此静默跳过。
- [ ] MySpec 验证检查的触发路径与缓存输入包含测试实际读取的共享生命周期、仓库属性、忽略规则和正式规格。
- [ ] 最小红灯能够分别复现错误 Git 转发和 PowerShell 原始子串断言失败，修复后同一检查转绿。
