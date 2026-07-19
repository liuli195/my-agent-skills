## MODIFIED Requirements

### Requirement: 画像拥有业务规则
系统 MUST 让 Guard Profile（守卫画像）拥有被守卫业务规则，Agent Guard（代理守卫）核心只执行通用匹配、读取和校验。

#### Scenario: Comet review gate 不侵入 cross-agent-review
- **WHEN** Global Command Guard（全局命令守卫点）用于守卫 Comet build completion（构建完成）命令
- **THEN** Agent Guard 可以匹配命令、读取 `cross_agent_review_pass` artifact（产物）并校验 guard-defined evidence（守卫定义证据）`pass.json`
- **AND** Comet review gate 的 Guard Profile MAY 配置指向生成 pass marker（通过标记）的 deny 提示
- **AND** Agent Guard 不得准备 cross-agent-review 输入、检查 cross-agent-review 的工作区前置条件、派发 reviewer agent（审查代理）或推进 Comet phase（阶段）
