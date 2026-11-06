## MODIFIED Requirements

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire is fixed
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** agent（代理）MUST 先读取 `references/questionnaire.md`（问答模板）
- **THEN** questionnaire（问答模板）MUST 定义固定问题、固定选项、选择后果和跳转规则
- **THEN** agent（代理）MUST NOT 临场编造初始化问题或跳过最终写入确认
- **THEN** 用户沉默 MUST NOT 被视为确认
- **THEN** branch protection（分支保护）选择 GitHub Rulesets（GitHub 规则集）时，remote tasks（远端待办）MUST 默认启用 `Restrict deletions`（限制删除）
- **THEN** branch protection（分支保护）选择 GitHub Rulesets（GitHub 规则集）时，remote tasks（远端待办）MUST 默认启用 `Block force pushes`（阻止强制推送）
