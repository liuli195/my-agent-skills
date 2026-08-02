# 01 — 统一工具生命周期与身份

**What to build（构建内容）：** Build and Verify（构建与验证）成为独立 npm（软件包管理器）CLI（命令行程序），与 MySpec（自有规格）各自支持一致的发布版／源码版生命周期、三端 Agent（代理）初始化、诊断和更新；两者都能输出 PR Flow（拉取请求流程）所需的稳定工具身份。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）。

**Status（状态）：** ready-for-agent

- [ ] 两个包独立安装、独立版本演进，且都可从其 CLI（命令行程序）管理 Pi、Claude、Codex 的受管资源。
- [ ] 发布版和源码版身份均可由只读 `doctor`（诊断）机器读取；源码身份包含官方来源、完整提交和固定包目录。
- [ ] Build and Verify 的原有构建与验证语义保持不变，不合并到 MySpec（自有规格）或新增运行时依赖。
- [ ] 安装与更新具备现有 MySpec（自有规格）同等的锁、恢复和诊断边界。
- [ ] 候选 npm Tarball（npm 包文件）隔离安装后的 CLI（命令行程序）快速冒烟通过。
