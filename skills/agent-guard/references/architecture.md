# Architecture（架构）

本文件只用于快速定向。执行流程放在 5 个场景入口自己的 `references/` 中。

职责边界：

- `agent-guard`：薄路由入口，只识别场景并转到对应入口。
- `agent-guard-install`：调研被守卫对象，生成或更新未初始化的 Guard Profile（守卫画像）草案。
- `agent-guard-init`：第一次创建项目级或用户级运行位置。
- `agent-guard-update`：维护已初始化守卫，升级 Runtime（运行时）或同步已校验画像。
- `agent-guard-run`：激活实例、读取 Guard Brief（守卫简报）、提交标准事件。
- `agent-guard-hooks`：dry-run、安装或验证 Codex Hook（Codex 钩子）和 Git Hook（Git 钩子）。
- Guard Profile（守卫画像）：存放具体守卫规则。
- Guard Runtime（守卫运行时）：执行通用机制，不写业务规则。
- Hook（钩子）：捕获事件、标准化事件并调用 Runtime（运行时）；不创建实例，不推进状态。
- 被守卫对象：保持原样，不成为守卫配置的一部分。

共享资源：

- 通用概念只保留在 `skills/agent-guard/references/`。
- 文件骨架和默认字段以 `skills/agent-guard/assets/templates/` 为权威。
- 可重复执行的确定性操作以 `skills/agent-guard/scripts/` 为权威。

项目级生成物应能脱离用户级 `agent-guard` 独立运行。用户级 Skill（技能）不能成为项目运行时依赖。
