## MODIFIED Requirements

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire is fixed
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** agent（代理）MUST 先读取 `references/questionnaire.md`（问答模板）
- **THEN** questionnaire（问答模板）MUST 定义固定问题、固定选项、选择后果和跳转规则
- **THEN** agent（代理）MUST NOT 临场编造初始化问题或跳过最终写入确认
- **THEN** 用户沉默 MUST NOT 被视为确认
- **THEN** 最终写入确认 MUST 提供 3 个固定选项：不写入放弃本次配置、只写入本地配置、按 remote tasks（远端待办）完成 GitHub（代码托管平台）配置后再写入本地配置
- **THEN** questionnaire（问答模板）MUST 明确 GitHub（代码托管平台）配置由 agent（代理）执行
- **THEN** questionnaire（问答模板）MUST 明确插件不提供 GitHub（代码托管平台）配置脚本能力
