# 01 — 统一 Codex 配置目录解析并隔离 Orca 临时目录

**What to build（构建内容）：** 两个生命周期命令行程序在 Orca（开发环境）会话、普通用户环境和自定义配置环境中，均能选择正确的 Codex 配置目录；用户可通过 `--codex-home` 精确指定目录，命令不会把 Orca 临时目录误当成用户目录。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）。

**Status（状态）：** ready-for-agent

- [ ] MySpec 和 Build and Verify 的 `doctor`、Codex 初始化和 `update` 支持统一的 `--codex-home` 选择。
- [ ] Orca 临时配置目录默认解析为用户 Codex 配置目录，非 Orca 自定义目录继续生效，显式参数优先。
- [ ] Codex 子进程和配置文件读写使用同一个解析目录，且不修改父进程环境。
- [ ] 诊断能报告实际目录和选择来源；不可用目录返回非零、可操作错误。
- [ ] 打包后的两个命令行程序入口及 Orca 环境最小冒烟通过。
