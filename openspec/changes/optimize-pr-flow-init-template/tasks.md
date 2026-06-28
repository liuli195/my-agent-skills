## 1. Contract Tests

- [x] 1.0 Update the existing user-scenario contract test so it no longer requires the old `review gate`（审查门禁）, `cleanup`（清理） and `GitHub setup suggestions`（GitHub 配置建议） question sequence as the primary flow.
- [x] 1.1 Add tests that require `pr-flow-init` questionnaire（问答模板） to include read-only inspection and the latest six-question flow.
- [x] 1.2 Add tests that reject the old standalone review gate（审查门禁） wording as the primary question.
- [x] 1.3 Add tests that require GitHub（代码托管平台）setup guidance to use official rule names such as `Require a pull request before merging` and `Require status checks to pass before merging`.
- [x] 1.4 Add tests that require user-readable draft and validation summary sections before YAML（配置格式） details.
- [x] 1.5 Preserve the existing plugin entrypoint（插件入口） routing test for `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json` and `skills/pr-flow/SKILL.md`（总入口） without turning those files into planned source edits unless wording conflicts with the init（初始化） contract.
- [x] 1.6 Add tests that require CodeQL security check（CodeQL 安全检查） immediately after PR status checks（拉取请求状态检查）, with only enable/disable options and `Require code scanning results` using `CodeQL`.

## 2. Skill References

- [x] 2.1 Update `references/questionnaire.md`（问答模板） with automatic inspection and the latest six-question flow.
- [x] 2.2 Update `references/config-draft.md`（配置草案规则） to separate local writes from GitHub current state and recommendations.
- [x] 2.3 Update `references/validation.md`（校验规则） to present error（错误）, warning（警告） and executable remote tasks（远端待办） in structured form.
- [x] 2.4 Preserve the existing `SKILL.md`（技能入口） constraint that existing config and branch state cannot replace user answers or confirmation.
- [x] 2.5 Document the GitHub（代码托管平台）not-inspected case: when GitHub access, `gh` CLI（GitHub 命令行工具） or network is unavailable, the summary must show `not inspected`（未检查） or `no access`（无权限） and must not present recommendations as confirmed current state.
- [x] 2.6 Update questionnaire（问答模板）, config draft（配置草案规则） and validation（校验规则） with CodeQL security check（CodeQL 安全检查） remote tasks（远端待办）.

## 3. Verification

- [x] 3.1 Run focused PR Flow（拉取请求流程） tests for init documentation contracts.
- [x] 3.2 Run OpenSpec（开放规格） strict validation for `optimize-pr-flow-init-template`.
- [x] 3.3 Review the final diff and confirm no complete、cleanup、hotfix or tweak（收尾、清理、热修复、小改） runtime semantics changed.
