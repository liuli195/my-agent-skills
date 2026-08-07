# 01 — 保护隔离 MySpec 发布形态验证

**What to build（构建内容）：** 当贡献者验证当前检出的 MySpec（自有规格）时，验证从隔离 PATH（可执行文件搜索路径）调用当前 Tarball（压缩包）安装出的裸 `myspec` CLI（命令行程序），完成完整规格流程，并在 Windows 与 Linux 安装布局及存在宿主同名命令时保持确定性。

**Blocked by（前置票据）：** None — can start immediately（无，可立即开始）。

**Status（状态）：** ready-for-agent

- [ ] 当前检出生成的 Tarball（压缩包）在空安装前缀中完成隔离安装。
- [ ] 隔离 PATH 中的裸 `myspec` 解析到该测试安装，不使用机器预装版本。
- [ ] 宿主 PATH 中存在假 `myspec`、`pi`、`claude` 和 `codex` 时，隔离运行不受污染。
- [ ] Windows 与 Linux npm 安装布局的前缀推导均有确定性覆盖。
- [ ] 至少一条裸 `myspec` 路径完成校验、预览、差异和正式应用。
- [ ] 以固定 Verification Baseline（验证基线）运行 Build and Verify（构建与验证）时，`checked`（已检查）非空、包含 `verify.my-spec` 且最终状态通过。
