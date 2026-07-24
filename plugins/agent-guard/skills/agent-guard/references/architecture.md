# Architecture（架构）

本文件只用于快速定向。执行流程放在 4 个场景入口自己的 `references/` 中。

职责边界：

- `agent-guard`：薄路由入口，只识别场景并转到对应入口。
- `agent-guard-install`：调研被守卫对象，生成或更新未初始化的 Guard Profile（守卫画像）草案。
- `agent-guard-init`：第一次创建项目级或用户级运行位置。
- `agent-guard-update`：维护已初始化守卫，更新 Agent Guard Plugin（代理守卫插件）或同步已校验画像。
- `agent-guard-run`：激活 Session Focus Instance（会话焦点实例）、切换焦点、关闭实例、提交标准事件。
- Guard Profile（守卫画像）：存放具体守卫规则。
- Guard Runtime（守卫运行时）：由 Plugin（插件）发布，执行通用机制，不写业务规则。
- Hook（钩子）：由 Plugin（插件）发布，捕获事件、标准化事件并调用 Runtime（运行时）；不创建实例，不推进状态。Hook（钩子）安装和验证通过 Plugin Installer（插件安装器）或 `agent-guard-update` 执行，不保留独立场景入口。
- 被守卫对象：保持原样，不成为守卫配置的一部分。

共享资源：

- 通用概念只保留在插件包内的 `skills/agent-guard/references/`。
- Guard Profile（守卫画像）文件骨架和默认字段以插件包内的 `skills/agent-guard/assets/templates/` 为权威。
- 可重复执行的确定性操作以插件包内的 `skills/agent-guard/scripts/` 为权威。

项目级生成物只保存 Guard Profile（守卫画像）和运行态数据；通用 Runtime code（运行时代码）随 Plugin（插件）安装。
