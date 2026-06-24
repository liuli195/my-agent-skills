## MODIFIED Requirements

### Requirement: Global command guard points

系统 MUST 支持 Global Command Guard（全局命令守卫点）在命令匹配后按声明式 skip condition（跳过条件）放行特定上下文，并且不得把具体业务 workflow（工作流）判断硬编码进 Runtime（运行时）。

#### Scenario: 声明式 YAML 条件命中时跳过守卫

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** 该守卫声明 `skip_when`（跳过条件）读取相对 YAML（配置文件）路径、字段和允许值
- **AND** 该 YAML（配置文件）字段值命中允许值
- **THEN** Runtime（运行时）跳过该守卫的 evidence（证据）检查
- **AND** 该守卫不应造成 deny（拒绝）
- **AND** Runtime（运行时）在 audit（审计）中记录被跳过的守卫编号和跳过原因

#### Scenario: 跳过条件未命中时继续原有检查

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** `skip_when`（跳过条件）缺失、目标文件缺失、字段缺失、字段值未命中、YAML（配置文件）不可读或路径模板不安全
- **THEN** Runtime（运行时）继续执行该守卫原有 evidence（证据）检查
