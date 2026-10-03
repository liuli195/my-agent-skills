## MODIFIED Requirements

### Requirement: 画像拥有业务规则
系统 MUST 让 Guard Profile（守卫画像）拥有被守卫业务规则。Agent Guard（代理守卫）核心只执行通用匹配、读取、校验，以及由主代理显式请求且不包含业务判断的 guard-defined evidence（守卫定义证据）机械写入；核心 MUST NOT 自主作出业务通过结论。

#### Scenario: Comet review gate 不侵入 cross-agent-review
- **WHEN** Global Command Guard（全局命令守卫点）用于守卫 Comet build completion（构建完成）命令
- **THEN** Agent Guard（代理守卫）可以匹配命令、读取 `cross_agent_review_pass` artifact（跨代理审查通过产物）并校验 guard-defined evidence（守卫定义证据）`pass.json`
- **AND** Comet review gate（双星审查门禁）的 Guard Profile（守卫画像） MAY 配置指向生成 pass marker（通过标记）的 deny（拒绝）提示
- **AND** Agent Guard（代理守卫）不得准备 Cross Agent Review（跨代理审查）输入、检查其工作区前置条件、派发 reviewer agent（审查代理）、解析审查发现项或推进 Comet phase（阶段）

#### Scenario: 主代理显式记录守卫定义证据
- **WHEN** 主代理已经根据上游流程产物作出通过结论，并显式调用通用 `record-evidence`（记录证据）入口
- **THEN** Agent Guard（代理守卫） MAY 按 Guard Profile（守卫画像）的产物契约校验并机械写入 guard-defined evidence（守卫定义证据）
- **AND** 该写入 MUST NOT 推导、补充或改变主代理的业务结论

#### Scenario: 守卫不得自主生成通过证据
- **WHEN** 主代理没有显式调用 `record-evidence`（记录证据），或上游只存在报告但没有主代理通过结论
- **THEN** Agent Guard（代理守卫） MUST NOT 自主读取报告并生成 pass marker（通过标记）
