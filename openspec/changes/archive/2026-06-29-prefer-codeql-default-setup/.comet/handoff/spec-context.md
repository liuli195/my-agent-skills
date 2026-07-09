# Comet Spec Context

- Change: prefer-codeql-default-setup
- Phase: design
- Mode: beta
- Context hash: dffa350f6b0ebc9cd1af386e990084e85796717c05c81d67a09ba466495b0605

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/prefer-codeql-default-setup/proposal.md
- SHA256: d0912357a88a602b02fab9ac91c4612d7912ffd3cced35336ace3c606340f241
- Source: openspec/changes/prefer-codeql-default-setup/design.md
- SHA256: 15063fc641b94b3b27b8ce89c2a1f3970ff46b6ca77f6620a9c9fae00a7b6da3
- Source: openspec/changes/prefer-codeql-default-setup/tasks.md
- SHA256: 7c19cf3157ec410c3b054ec6475c5448f452d5fcb39f0acc988faf3fa139a472
- Source: openspec/changes/prefer-codeql-default-setup/specs/pr-flow-plugin/spec.md
- SHA256: 294f1335a3f01e327aad11e8b1a00204a7b4aeb69ad51ff57254c21882b22ca7

## Acceptance Projection

## openspec/changes/prefer-codeql-default-setup/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/prefer-codeql-default-setup/specs/pr-flow-plugin/spec.md
- Lines: 1-34
- SHA256: 294f1335a3f01e327aad11e8b1a00204a7b4aeb69ad51ff57254c21882b22ca7

```md
## MODIFIED Requirements

### Requirement: PR Flow init validates confirmed configuration
系统 MUST 提供只读配置校验能力，用于校验 `pr-flow-init` Skill（初始化技能）生成的配置草案。

#### Scenario: Validate reports CodeQL default setup task
- **WHEN** validate（校验） reads a config（配置） that declares CodeQL code scanning（代码扫描） guidance
- **THEN** validate（校验） MUST output a remote task（远端待办） to enable CodeQL Default setup（CodeQL 默认配置）
- **THEN** validate（校验） MUST output a remote task（远端待办） to configure GitHub Rulesets（GitHub 规则集） CodeQL code scanning（CodeQL 代码扫描）
- **THEN** validate（校验） MUST NOT call GitHub API（GitHub 接口） or `gh` CLI（GitHub 命令行工具） to inspect remote CodeQL Default setup（CodeQL 默认配置）
- **THEN** validate（校验） MUST NOT report remote CodeQL Default setup（CodeQL 默认配置） as confirmed
- **WHEN** the project（项目） has a local workflow（工作流） using `codeql-action`
- **THEN** validate（校验） MUST still output the CodeQL Default setup（CodeQL 默认配置） remote task（远端待办）

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire separates CodeQL security from status checks
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** questionnaire（问答模板）MUST ask CodeQL security check（CodeQL 安全检查） before PR status checks（拉取请求状态检查）
- **THEN** if the user does not enable CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST NOT offer `Analyze Python`, `Analyze (python)`, `Analyze (actions)` or `CodeQL` CodeQL-related checks（CodeQL 相关检查）
- **THEN** if the user enables CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST default to non-security-scan checks（非安全扫描检查） and MUST NOT present CodeQL-related checks（CodeQL 相关检查） as status check（状态检查） options
- **THEN** questionnaire（问答模板）MUST treat `Require code scanning results`（要求代码扫描结果） as the primary CodeQL security gate（CodeQL 安全门禁）

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: CodeQL security check uses default setup by default
- **WHEN** the user chooses to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST record a Rulesets（规则集）task to configure `Require code scanning results`（要求代码扫描结果）
- **THEN** GitHub setup guidance MUST record a task to enable CodeQL Default setup（CodeQL 默认配置）
- **THEN** it MUST select `CodeQL` as the code scanning tool（代码扫描工具）
- **THEN** it MUST use GitHub 默认阈值 for code scanning thresholds（代码扫描阈值）
- **THEN** local config draft（本地配置草案） MUST keep using `setup.github.codeScanning`（代码扫描配置） without adding `defaultSetup` or equivalent new fields（等价新字段）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
