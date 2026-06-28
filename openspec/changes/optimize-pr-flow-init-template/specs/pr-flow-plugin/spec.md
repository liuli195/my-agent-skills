## ADDED Requirements

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: Remote guidance shows current state before recommendations
- **WHEN** agent（代理）prepares the confirmation summary for `pr-flow-init`
- **THEN** it MUST show the current GitHub（代码托管平台）state for Rulesets（规则集）, branch protection（分支保护）, merge methods（合并方式）, auto-delete head branch（自动删除源分支）, and PR status checks（拉取请求状态检查） when that state has been inspected
- **THEN** it MUST show recommended GitHub setup separately from local files that will be written
- **THEN** it MUST NOT imply that GitHub setup has been applied

#### Scenario: Remote tasks use GitHub official rule names
- **WHEN** GitHub setup guidance includes branch protection（分支保护）
- **THEN** it MUST describe the task as creating or updating a branch ruleset（分支规则集） for the selected target branches
- **THEN** it MUST name `Require a pull request before merging`（合并前要求拉取请求） as the rule that requires protected branches to change through PR（拉取请求）
- **THEN** it MUST set `required_approving_review_count: 0` unless the user explicitly chooses an approving review（批准审查） requirement

#### Scenario: PR status checks are concrete or explicit future work
- **WHEN** the user chooses to require PR status checks（拉取请求状态检查）
- **AND** no concrete PR check names are available from inspected workflows
- **THEN** the GitHub setup guidance MUST record a task to add or identify PR status checks before enabling `Require status checks to pass before merging`（合并前要求状态检查通过）
- **THEN** it MUST NOT invent check names

#### Scenario: CodeQL security check is an explicit ruleset task
- **WHEN** the user chooses to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST record a Rulesets（规则集）task to configure `Require code scanning results`（要求代码扫描结果）
- **THEN** it MUST select `CodeQL` as the code scanning tool（代码扫描工具）
- **THEN** it MUST use GitHub 默认阈值 for code scanning thresholds（代码扫描阈值）
- **WHEN** the user chooses not to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST NOT include a CodeQL（代码扫描工具）remote task（远端待办）

#### Scenario: Confirmation summary is user-readable first
- **WHEN** agent（代理）shows the init draft before final confirmation
- **THEN** it MUST first show user-readable tables for local writes, GitHub current state, GitHub recommendations, and validation results
- **THEN** YAML（配置格式）MAY be shown only as supporting detail after the user-readable summary

## MODIFIED Requirements

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Skill entrypoint delegates detail to references
- **WHEN** agent（代理）加载 `pr-flow-init` Skill（初始化技能）
- **THEN** Skill（技能）入口 MUST 声明 hard boundaries（硬边界）、closed loop（闭环）、required flow（必需流程）和 output（输出）
- **THEN** Skill（技能）入口 MUST 指向 `references/questionnaire.md`（问答模板）、`references/config-draft.md`（配置草案规则）和 `references/validation.md`（校验规则）
- **THEN** Skill（技能）入口 MUST NOT 内联完整问答细节
- **THEN** Skill（技能）入口 MUST state that existing `.pr-flow/config.yaml`（配置文件）, branch state（分支状态）, or history can only be used as reference and cannot replace user answers or final confirmation

#### Scenario: Questionnaire starts with read-only inspection
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** agent（代理）MUST 先读取 `references/questionnaire.md`（问答模板）
- **THEN** questionnaire（问答模板）MUST require read-only inspection before asking configuration questions
- **THEN** read-only inspection MUST cover default branch（默认分支）, remote branches（远端分支）, GitHub Rulesets（GitHub 规则集）, branch protection（分支保护）, merge methods（合并方式）, auto-delete head branch（自动删除源分支）, and available PR status checks（拉取请求状态检查） when GitHub access is available
- **THEN** read-only inspection MUST NOT write local config or GitHub settings

#### Scenario: Questionnaire uses the fixed latest template
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** questionnaire（问答模板）MUST define fixed questions, fixed options, selection consequences, and jump rules
- **THEN** questionnaire（问答模板）MUST ask for default PR target branch（拉取请求目标分支）
- **THEN** questionnaire（问答模板）MUST ask which branches need branch protection（分支保护） through GitHub Rulesets（GitHub 规则集）
- **THEN** questionnaire（问答模板）MUST ask whether PR status checks（拉取请求状态检查） are required
- **THEN** questionnaire（问答模板）MUST ask whether to enable CodeQL security check（CodeQL 安全检查） after PR status checks（拉取请求状态检查）
- **THEN** questionnaire（问答模板）MUST ask whether hotfix（热修复） direct push（直接推送） is allowed, and only then ask whether to reuse or create authorization phrase（授权短语）
- **THEN** questionnaire（问答模板）MUST ask which merge methods（合并方式） are allowed
- **THEN** questionnaire（问答模板）MUST NOT ask separate required review（必需审查） or required checks（必需检查） questions after those decisions have already been captured by branch protection（分支保护） and PR status checks（拉取请求状态检查）
- **THEN** agent（代理）MUST NOT 临场编造初始化问题或跳过最终写入确认
- **THEN** 用户沉默 MUST NOT 被视为确认

#### Scenario: Plugin and Skill content are organized by user scenario
- **WHEN** 维护 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容
- **THEN** Skill（技能）入口和 `references/`（参考文件）MUST 按用户场景组织，而不是按 YAML（配置格式）字段或 script（脚本）函数平铺
- **THEN** 用户场景 MUST 覆盖 automatic inspection（自动检查）、default PR target branch（默认拉取请求目标分支）、branch protection（分支保护）、PR status checks（拉取请求状态检查）、CodeQL security check（CodeQL 安全检查）、hotfix（热修复）、merge methods（合并方式）、GitHub（代码托管平台）远端配置建议和最终写入确认
- **THEN** questionnaire（问答模板）MUST 作为固定执行模板服务这些场景，但场景组织要求不只限于 questionnaire（问答模板）
- **THEN** Plugin（插件）级 init（初始化）路由验收 MUST remain covered for `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）
- **THEN** agent（代理）MUST NOT treat those plugin entrypoints（插件入口） as planned source edits unless their init（初始化） route wording conflicts with the new contract
- **THEN** unrelated complete、cleanup、hotfix 和 tweak（收尾、清理、热修复、小改）Skill（技能）内容 MUST NOT be reorganized unless it directly describes init（初始化）

#### Scenario: Draft and validation rules are fixed references
- **WHEN** agent（代理）生成配置草案
- **THEN** agent（代理）MUST 读取 `references/config-draft.md`（配置草案规则）
- **WHEN** agent（代理）执行写入前校验或展示校验摘要
- **THEN** agent（代理）MUST 读取 `references/validation.md`（校验规则）
- **THEN** agent（代理）MUST 按这些固定参考文件展示草案、问题、影响、GitHub current state（GitHub 当前状态）和 executable setup tasks（可执行配置待办）
- **THEN** if GitHub access（GitHub 访问权限）, `gh` CLI（GitHub 命令行工具） or network（网络） is unavailable, agent（代理）MUST show the GitHub current state（GitHub 当前状态） as `not inspected`（未检查） or `no access`（无权限） and MUST NOT present recommendations as confirmed current state
