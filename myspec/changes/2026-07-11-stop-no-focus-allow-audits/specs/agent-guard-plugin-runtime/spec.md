## MODIFIED Requirements

### Requirement: Runtime Router 焦点处理
系统 MUST 保持现有 Session Focus permission（会话焦点权限）语义不变；Global Command Guard（全局命令守卫点）只在 PreToolUse（工具调用前）入口增加独立的前置检查，并且无活动会话焦点的放行结果 MUST NOT 写入 `no_session_focus_instance` 审计文件。

#### Scenario: 全局命令守卫点先于会话焦点权限执行
- **WHEN** 一个命令同时匹配 Global Command Guard（全局命令守卫点）和 Session Focus permission rule（会话焦点权限规则）
- **THEN** Runtime（运行时）先评估 Global Command Guard（全局命令守卫点）
- **AND** 任一检查返回 deny（拒绝）时命令不得执行

#### Scenario: 全局命令守卫点允许后继续检查会话焦点
- **WHEN** Global Command Guard（全局命令守卫点）允许一个命令
- **AND** 当前存在 Session Focus permission rule（会话焦点权限规则）
- **THEN** Runtime（运行时）继续执行现有 Session Focus permission（会话焦点权限）检查

#### Scenario: 会话焦点不被全局命令守卫点修改
- **WHEN** Global Command Guard（全局命令守卫点）允许或拒绝一个命令
- **THEN** Runtime（运行时）不得写入、替换或删除 Session Focus Binding（会话焦点绑定）

#### Scenario: 没有活动会话焦点时放行
- **WHEN** PreToolUse（工具调用前）入口没有活动 Session Focus Instance（会话焦点实例）并继续执行
- **THEN** Runtime（运行时）返回 `status=allow` 和 `reason=no_session_focus_instance`
- **AND** Runtime（运行时）不写 `no_session_focus_instance` 审计，也不返回该已停止生成审计的路径
- **AND** Runtime（运行时）保留并返回独立生成的 Global Command Guard（全局命令守卫点）审计

#### Scenario: 没有活动会话焦点时阻断
- **WHEN** 必须具有活动 Session Focus Instance（会话焦点实例）的入口没有活动焦点
- **THEN** Runtime（运行时）中止当前操作并保留 `no_session_focus_instance` 审计
