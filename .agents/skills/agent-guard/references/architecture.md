# Architecture（架构）

本文件只用于快速定向。执行细节按场景读取其他 reference（参考文档）。

职责边界：

- `agent-guard`：用户级 Skill（技能），负责调研、生成、升级和校验。
- Guard Profile（守卫画像）：存放具体守卫规则。
- Guard Runtime（守卫运行时）：执行通用机制。
- 主 agent（主代理）：主动调用 Runtime（运行时）对齐状态、读取 Guard Brief（守卫简报），并在关键动作前请求判断。
- Hook（钩子）：捕获外部事件、标准化事件并调用 Runtime（运行时）；只做通用协议监督，不写具体流程规则。
- Git hook（Git 钩子）：在提交、推送等 Git 边界做通用兜底，不写具体流程规则。
- 被守卫对象：保持原样，不成为守卫配置的一部分。

项目级生成物应能脱离用户级 `agent-guard` 独立运行。用户级 Skill（技能）不能成为项目运行时依赖。

细节路由：

- 画像结构：`guard-profile.md`
- 运行时行为：`runtime-contract.md`
- Hook（钩子）接入：`hook-contract.md`
- Guard Brief（守卫简报）注入：`guard-injection.md`
