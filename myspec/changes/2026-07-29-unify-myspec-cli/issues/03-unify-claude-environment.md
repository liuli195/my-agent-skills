# 03 — 让 Claude 使用统一软件包自带市场

**What to build:** Claude（代码代理）用户能够通过统一初始化入口注册 npm 包自带的单插件市场，并让该市场随机器级开发／发布模式切换到同一份 MySpec（自有规格）内容。

**Blocked by:** 02 — 让 Pi 使用统一软件包.

**Status:** ready-for-agent

- [ ] `myspec init --claude` 在 Claude（代码代理）存在时注册、安装并启用 npm 包自带市场，在客户端不存在时明确失败。
- [ ] `myspec init --all` 在 Claude 不存在时跳过并报告，且不尝试安装 Claude（代码代理）。
- [ ] 开发／发布切换后，Claude 插件被刷新或重装并使用全局 npm 包稳定目录对应的内容。
- [ ] 旧 `my-agent-skills-marketplace` 中的 MySpec（自有规格）插件只被禁用，市场和插件缓存不被删除。
- [ ] `myspec doctor --claude` 只读查询 Claude 的真实市场、插件、版本、启用状态和重新加载要求。
- [ ] 端到端测试证明切换前后 Claude 只启用一套四个 Skill（技能），并能观察到开发源码变化。
