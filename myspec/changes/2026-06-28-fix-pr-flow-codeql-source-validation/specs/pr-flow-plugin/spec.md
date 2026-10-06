## MODIFIED Requirements

### Requirement: PR Flow init validates confirmed configuration
系统 MUST 提供只读配置校验能力，用于校验 `pr-flow-init` Skill（初始化技能）生成的配置草案。

#### Scenario: Validate reports missing CodeQL scan producer
- **WHEN** validate（校验） reads a config（配置） that declares CodeQL code scanning（代码扫描） guidance
- **AND** the project（项目） has no local CodeQL workflow（代码扫描工作流）
- **THEN** validate（校验） MUST output a remote task（远端待办） to create or enable a CodeQL scan producer（CodeQL 扫描结果来源）
- **WHEN** the project（项目） has a local workflow（工作流） using `codeql-action`
- **THEN** validate（校验） MUST NOT output the missing scan producer（扫描结果来源） remote task（远端待办）
