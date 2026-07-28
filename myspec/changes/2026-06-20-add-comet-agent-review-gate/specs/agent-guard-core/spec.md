## MODIFIED Requirements

### Requirement: 画像拥有业务规则
系统 MUST 把具体业务守卫规则保存在 Guard Profile（守卫画像）配置中，同时保持 Runtime（运行时）和 Agent Guard Skill（代理守卫技能）入口逻辑通用。Agent Guard MUST NOT contain business workflow orchestration（业务流程编排） or hard-coded business logic（硬编码业务逻辑） for any guarded target.

#### Scenario: Runtime 处理守卫事件
- **WHEN** Runtime（运行时）收到标准化守卫事件
- **THEN** Runtime 加载当前 Guard Profile（守卫画像），并评估画像定义的 state machine（状态机）、permissions（权限）、guard checks（守卫检查）、artifacts（产物）和 brief（简报）语义

#### Scenario: Runtime 保持通用
- **WHEN** 新增一个被守卫的业务流程
- **THEN** Runtime（运行时）不为该具体流程新增硬编码规则
- **AND** Runtime 只执行通用机制，例如命令匹配、上下文提取、artifact（产物）解析、JSON predicate（JSON 谓词）校验、allow/deny（允许/拒绝）结果和 audit（审计）记录

#### Scenario: Skill 入口不承载业务编排
- **WHEN** Agent Guard Skill（代理守卫技能）文档说明某个 Global Command Guard（全局命令守卫点）的 deny（拒绝）结果
- **THEN** 文档可以解释通用返回字段，例如 reason、next、suggestion、captures、failing guards 和 artifact/evidence 信息
- **AND** 这些字段的场景化内容 MAY 来自 Guard Profile（守卫画像）中的 deny 配置
- **AND** Runtime（运行时）只负责按通用机制透传或渲染这些配置字段
- **AND** 文档不得实现或复写被守卫业务流程的下一步执行顺序

#### Scenario: 外部 Skill 拥有自身流程
- **WHEN** 守卫点依赖另一个 Skill（技能）或 workflow（工作流）生成外部 evidence（证据）
- **THEN** Agent Guard 只能校验该 evidence 是否满足 Guard Profile 声明
- **AND** Guard Profile MAY 配置 deny reason、next 和 suggestion 来提示调用方后续处理方向
- **AND** Agent Guard 不得把这些提示升级为内置流程，也不得实现、派发或复制该外部 Skill 的内部流程
- **AND** 该外部流程的输入准备、执行步骤、工作区约束、测试约束和结果生成规则 MUST 保留在对应 Skill 或调用方契约中

#### Scenario: Comet review gate 不侵入 cross-agent-review
- **WHEN** Global Command Guard（全局命令守卫点）用于守卫 Comet build completion（构建完成）命令
- **THEN** Agent Guard 可以匹配命令、读取 `cross_agent_review_pass` artifact（产物）并校验 `review-pass.json`
- **AND** Comet review gate 的 Guard Profile MAY 配置指向生成 pass marker（通过标记）的 deny 提示
- **AND** Agent Guard 不得准备 cross-agent-review 输入、检查 cross-agent-review 的工作区前置条件、派发 reviewer agent（审查代理）或推进 Comet phase（阶段）
