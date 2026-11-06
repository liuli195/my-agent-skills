# 02 — 让 Pi 使用统一软件包

**What to build:** Pi（编码代理）用户能够通过 `myspec init --pi` 初始化统一来源，并通过显式开发／发布模式切换让 Pi 和 CLI（命令行程序）始终使用同一个全局 npm 包稳定目录。

**Blocked by:** 01 — 发布可安装的统一 MySpec CLI.

**Status:** ready-for-agent

- [ ] `myspec init --pi` 在 Pi（编码代理）存在时登记并启用全局 npm 包稳定目录，在 Pi 不存在时明确失败。
- [ ] `myspec init --all` 在 Pi 不存在时跳过并报告，且不尝试安装 Pi（编码代理）。
- [ ] `myspec init --dev` 校验当前目录或显式源码目录，保存当前发布版本，通过 npm Link（npm 本地链接）切入源码并刷新 Pi。
- [ ] `myspec init --release` 恢复保存的固定发布版本，不隐式升级；缺少恢复版本时停止。
- [ ] Pi 中旧远端或旧源码 MySpec（自有规格）来源只被禁用，不被删除。
- [ ] `myspec doctor --pi` 只读报告真实 CLI（命令行程序）、包来源、模式、版本、重复来源和重新加载要求。
- [ ] 端到端测试证明发布模式、开发模式和恢复后的 Pi 均只启用一套四个 Skill（技能）。
