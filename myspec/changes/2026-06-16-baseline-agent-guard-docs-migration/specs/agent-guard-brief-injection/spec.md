## ADDED Requirements

### Requirement: 最新简报生命周期
系统 MUST 在 activation（激活）、state transitions（状态转换）、guard failures（守卫失败）、permission denials（权限拒绝）、permission asks（权限询问）以及简报文件缺失或过期后，为当前 Guard Instance（守卫实例）维护 latest Guard Brief（最新守卫简报）。

#### Scenario: 激活后刷新
- **WHEN** activation（激活）为 Guard Instance（守卫实例）写入 Session Focus Binding（会话焦点绑定）
- **THEN** Runtime（运行时）立即为该实例写入 latest `brief.json` 和 `brief.md`

#### Scenario: 状态结果后刷新
- **WHEN** state completion（状态完成）成功，或因必需 artifacts（产物）或 guard points（守卫点）缺失而失败
- **THEN** Runtime（运行时）用当前状态、失败信息或下一步信息刷新 latest brief（最新简报）内容

### Requirement: 读取触发注入
系统 MUST 在第一版基线中使用 pull-to-inject（读取触发注入）行为，即 agent（代理）显式读取当前 latest brief（最新简报），Runtime（运行时）记录 injection state（注入状态）。

#### Scenario: 第一次读取简报
- **WHEN** agent（代理）为已有焦点的会话读取当前 brief（简报），且该 session（会话）和 instance（实例）尚未注入当前 `brief_hash`
- **THEN** Runtime（运行时）返回 `injectable`，并记录已注入的 `brief_hash`

#### Scenario: 重复读取简报
- **WHEN** agent（代理）为同一个 `source + session_id + profile_id + instance_id` 再次读取同一份 brief（简报）
- **THEN** Runtime（运行时）返回 `already_injected`，不重复写入 injection record（注入记录）

### Requirement: 基于焦点的简报身份
系统 MUST 使用 Session Focus Instance（会话焦点实例）识别 latest brief（最新简报）和 injection records（注入记录），使用 `profile_id + instance_id`，不使用 `subject_key_hash`。

#### Scenario: 最新简报路径
- **WHEN** 写入 latest brief（最新简报）文件
- **THEN** 它们保存在 `.local/guard/latest/<profile_id>/<instance_id>/brief.json` 和 `.local/guard/latest/<profile_id>/<instance_id>/brief.md`

#### Scenario: 注入记录路径
- **WHEN** 写入 injection record（注入记录）
- **THEN** 它保存在 `.local/guard/injections/<source>/<session_id-hash>/<profile_id>/<instance_id>.json`

### Requirement: 简报载荷内容
系统 MUST 在 latest brief payload（最新简报载荷）中包含足够结构化数据，让 agent（代理）理解当前状态、允许动作、禁止动作、缺失产物、最近拒绝原因、权限、转换条件、状态完成指令、审计位置和 brief hash（简报哈希）。

#### Scenario: 活跃状态载荷
- **WHEN** 当前 instance（实例）处于 active（活跃）状态
- **THEN** latest brief payload（最新简报载荷）包含 state（状态）、state version（状态版本）、allowed next steps（允许下一步）、forbidden next steps（禁止下一步）、missing artifacts（缺失产物）、next step（下一步）、permissions（权限）、transition conditions（转换条件）、audit path（审计路径）、`brief_hash` 和渲染后的 brief text（简报文本）

#### Scenario: 终止状态载荷
- **WHEN** 当前 instance（实例）处于 terminal state（终止状态）
- **THEN** brief（简报）提示流程已完成和审计位置，不提示 agent（代理）再次提交 `state_completed` 事件

### Requirement: 简报哈希稳定性
系统 MUST 根据影响业务含义的 brief（简报）字段计算 `brief_hash`，并且必须排除只和时间戳有关的变化。

#### Scenario: 业务状态变化
- **WHEN** state（状态）、state version（状态版本）、allowed next steps（允许下一步）、forbidden next steps（禁止下一步）、missing artifacts（缺失产物）、recent denial reasons（最近拒绝原因）或 transition conditions（转换条件）变化
- **THEN** 生成的 `brief_hash` 发生变化

#### Scenario: 生成时间变化
- **WHEN** 只有 `generated_at` 变化，业务字段没有变化
- **THEN** 生成的 `brief_hash` 保持不变

### Requirement: 状态完成简报门禁
系统 MUST 要求当前 `brief_hash` 已经通过 brief entrypoint（简报入口）读取后，才接受 `state_completed` transition（状态完成转换）。

#### Scenario: 未读取简报
- **WHEN** agent（代理）在读取当前 latest brief（最新简报）前提交 `state_completed`
- **THEN** Runtime（运行时）返回 `brief_required`，包含当前 brief（简报）数据，并且不推进状态

#### Scenario: 完成前已读取简报
- **WHEN** 当前 `brief_hash` 已经为当前 session（会话）和 instance（实例）读取并记录
- **THEN** Runtime（运行时）可以评估 state completion transition（状态完成转换）

### Requirement: 简报失败处理
系统 MUST 在不存在有效且唯一的 Session Focus Instance（会话焦点实例）时清晰地让 brief read（简报读取）失败，并且不得为无效焦点状态写 injection records（注入记录）。

#### Scenario: 没有焦点
- **WHEN** brief reading（简报读取）找不到当前 Session Focus Instance（会话焦点实例）
- **THEN** Runtime（运行时）返回 `no_session_focus_instance`，提示先 activation（激活），并且不写 injection record（注入记录）

#### Scenario: 多焦点或无效焦点
- **WHEN** brief reading（简报读取）发现多个 focus bindings（焦点绑定）或一个无效 focus binding（焦点绑定）
- **THEN** Runtime（运行时）返回 error（错误），审计焦点问题，并且不写 injection record（注入记录）

### Requirement: Runtime 拥有简报内容
系统 MUST 确保 injectable brief content（可注入简报内容）来自 Runtime-generated latest brief files（运行时生成的最新简报文件），而不是手写文本或调用方提供的状态文本。

#### Scenario: 调用方请求简报
- **WHEN** 调用方调用 brief entrypoint（简报入口）
- **THEN** Runtime（运行时）解析当前焦点，加载或刷新 Runtime-generated latest brief（运行时生成的最新简报），并返回该内容

#### Scenario: 调用方尝试绕过焦点
- **WHEN** 调用方尝试传入 `profile_id`、`instance_id`、`subject` 或 `subject_key_hash` 直接选择 brief（简报）
- **THEN** brief entrypoint（简报入口）拒绝该绕过方式，并改用 Session Focus Binding（会话焦点绑定）
