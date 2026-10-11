# 0001 Agent Guard Architecture

状态：草案

替代说明：ADR [0002 Agent Guard Plugin Runtime 与会话焦点](0002-agent-guard-plugin-runtime-session-focus.md) 已替代本文中“项目级 Runtime code（运行时代码）独立复制并运行”、“Git Hook（Git 钩子）第一版兜底”和“通过 Subject Resolver（主体解析器）匹配 Guard Instance（守卫实例）”的旧决策。本文中“业务规则写入 Guard Profile（守卫画像）”、“Runtime（运行时）只执行通用机制”、“Hook（钩子）不推进状态”和“权限拒绝必须来自明确 Guard Instance（守卫实例）”继续有效。

## 决策

`agent-guard` 作为用户级 Skill 维护生成和升级能力。生成后的项目级 Guard Runtime 和 Guard Profile 必须可以独立运行，并且不得修改被守卫对象。

生成、更新或初始化 Guard Profile 前，必须先使用 `$grill-with-docs`（带文档拷问方法）完成被守卫对象调研，并形成 `grill_with_docs.status: confirmed` 的 `confirmed-notes.yaml`。没有已确认调研记录时，主 agent 不得直接生成画像、运行提取器或初始化。

Guard Profile 的 `GUARD-MANIFEST.yaml` 必须记录来源。业务画像使用 `source.kind: grill-with-docs-confirmed-notes`，并且 `source.status` 必须是 `confirmed`。`confirmed-notes.yaml` 模板默认状态是 `needs_confirmation`，避免把样板误当作已确认事实。

Agent Guard 采用 agent 驱动 Runtime、Hook 监督的架构：主 agent 主动调用 Guard Runtime 对齐状态、读取 Guard Brief，并在关键动作前请求判断；状态推进只能由主 agent 主动提交给 Runtime 的事件完成。Hook 和 Git hook 不驱动具体流程，也不推进状态，只做通用协议监督和最后兜底。

状态机的每个状态可以直接声明当前允许、询问或拒绝的工具调用范围。Hook 只提交工具名、参数、路径、命令和当前上下文给 Runtime，由 Runtime 按当前状态判断，不在 Hook 中写流程规则。

Agent Guard 不负责替用户生成或维护 Codex、Claude 的静态权限底座。静态权限可由用户按工具原生方式一次性配置；Agent Guard 只在状态机中表达动态流程权限，并可借鉴或兼容原生命令规则语法。

状态权限的权威格式是结构化 YAML，便于 Runtime 校验、审计和生成修复建议。Guard Profile 可以提供 Claude 风格的字符串清单作为简写，但校验或运行前必须规范化为结构化规则。

Guard Instance 必须由主 agent 或相关 Skill 在流程开始时显式 activate。Hook 不负责发现缺失实例，也不把缺失实例当成违规。

## 原因

守卫逻辑需要和目标 Skill、流程或任务说明解耦，避免目标对象更新时覆盖守卫能力。

只把“先调研”写在 Skill 提示里不够可靠。主 agent 可能跳过调研直接生成看似完整的画像，因此来源确认必须进入数据契约和校验脚本，让初始化入口继承同一层硬拦截。

## 后果

- 业务规则写入 Guard Profile。
- 新业务画像必须来自已确认的 `$grill-with-docs` 调研记录。
- `validate_guard_profile.py` 必须拒绝未确认来源的业务画像。
- 项目级和用户级初始化只发布已校验、已确认来源的画像草案。
- 主 agent 负责主动调用 Runtime。
- Hook 只捕获和标准化事件，并检查主 agent 是否遵守 Runtime 协议。
- Git hook 只在提交、推送等 Git 边界做通用兜底。
- Runtime 只执行通用机制，包括按当前状态评估工具权限。
- Codex、Claude 原生权限可作为规则语法或命令检查能力参考，但不是流程状态的权威来源。
- 权限拒绝必须来自明确 Guard Instance。
