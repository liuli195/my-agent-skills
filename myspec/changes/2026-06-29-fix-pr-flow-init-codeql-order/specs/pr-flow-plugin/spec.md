## MODIFIED Requirements

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire separates CodeQL security from status checks
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** questionnaire（问答模板）MUST ask CodeQL security check（CodeQL 安全检查） before PR status checks（拉取请求状态检查）
- **THEN** if the user does not enable CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST NOT offer `Analyze Python` or `CodeQL` CodeQL-related checks（CodeQL 相关检查）
- **THEN** if the user enables CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST default to non-security-scan checks（非安全扫描检查） and only present `Analyze Python` as an optional advanced status check（高级状态检查） when its purpose is explained
- **THEN** questionnaire（问答模板）MUST treat `Require code scanning results`（要求代码扫描结果） as the primary CodeQL security gate（CodeQL 安全门禁）

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: CodeQL security check includes scan producer
- **WHEN** the user chooses to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST record a Rulesets（规则集）task to configure `Require code scanning results`（要求代码扫描结果）
- **THEN** GitHub setup guidance MUST record a task to create or enable a CodeQL scan producer（CodeQL 扫描结果来源）
- **THEN** it MUST select `CodeQL` as the code scanning tool（代码扫描工具）
- **THEN** it MUST use GitHub 默认阈值 for code scanning thresholds（代码扫描阈值）
