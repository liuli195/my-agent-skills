## MODIFIED Requirements

### Requirement: Agent Guard Skill 入口覆盖 Global Command Guard
系统 MUST 让 Agent Guard（代理守卫）Skill（技能）入口说明 Global Command Guard（全局命令守卫）边界，同时避免复写被守卫流程内部实现。

#### Scenario: 文档明确禁止项
- **WHEN** 文档说明 Comet review gate（审查门禁）或 Global Command Guard
- **THEN** 文档 MUST 明确禁止新增 reviewed wrapper（审查包装入口）、在 Agent Guard（代理守卫）中实现 cross-agent-review（跨代理审查）内部流程、把 `verify --apply` 作为主拦截点、以及复制真正的 external artifact（外部产物）来绕过原始产物路径
