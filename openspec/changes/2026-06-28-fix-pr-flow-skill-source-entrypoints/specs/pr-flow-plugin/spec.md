## MODIFIED Requirements

### Requirement: PR Flow Plugin package
系统 MUST 提供 `pr-flow` Plugin（插件），用于个人仓库复用 PR Flow（拉取请求流程）。

#### Scenario: Skill entrypoints expose source repository commands
- **WHEN** maintainer（维护者）reads a PR Flow Skill（拉取请求流程技能）inside the source repository（源码仓库）
- **THEN** command examples for diagnose、complete、cleanup、hotfix and tweak（诊断、收尾、清理、热修复和小改） MUST point to `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- **THEN** command examples MUST NOT point to a missing root-level `scripts/pr_flow.py`
- **THEN** command examples MUST NOT point to an installed-skill relative `../pr-flow/scripts/pr_flow.py` path when documenting source repository（源码仓库） usage（用法）
