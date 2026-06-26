## 1. Package and Spec Guards

- [x] 1.1 Update build-and-verify（构建与验证）package tests so the plugin exposes both `build-and-verify`（运行入口） and `build-and-verify-init`（初始化向导入口） Skill（技能） directories.
- [x] 1.2 Update tests that currently assert a single Skill（技能） entrypoint so they assert the new two-entrypoint contract.
- [x] 1.3 Add tests proving command-line `init`（初始化） still writes the empty template config, `.gitignore`（忽略规则）, and `cache`（缓存） directory without interactive behavior.
- [x] 1.4 Add OpenSpec（开放规格） validation coverage for the `test-framework-plugin`（测试框架插件） delta spec（规格增量）.

## 2. Guided Initialization Skill

- [x] 2.1 Create `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`（技能说明）, with concise routing instructions and progressive disclosure（渐进式披露） links.
- [x] 2.2 Create `references/questionnaire.md`（问答模板） with fixed questions, fixed options, consequence notes, and jump rules.
- [x] 2.3 Create `references/ecosystem-detection.md`（生态识别规则） for Node（节点运行时） and Python（Python 语言） repository detection.
- [x] 2.4 Create `references/ecosystem-detection.md`（生态识别规则） fallback guidance for repositories without recognized Node（节点运行时） or Python（Python 语言） signals.
- [x] 2.5 Create `references/config-draft.md`（配置草案规则） for check id（检查项标识）, default string command（字符串命令）, paths（受影响路径）, inputs（缓存输入）, timeout（超时）, and parallel（并行） settings.
- [x] 2.6 Create `references/validation.md`（校验规则） for pre-write targeted dependency checks（写入前定向依赖检查）, post-write config（配置） structure validation, and user-selected dry run（试运行） using existing build/verify（构建/验证） command scopes.

## 3. Template Integrity Tests

- [x] 3.1 Add tests that `build-and-verify-init`（构建与验证初始化） references all required reference（参考） files.
- [x] 3.2 Add tests that `questionnaire.md`（问答模板） contains all 11 required initialization questions: target path, scan authorization, detection confirmation, check（检查项） selection, paths（受影响路径）, inputs（缓存输入）, parallel/timeout（并行/超时）, overwrite（覆盖）, backup path（备份路径）, dry run（试运行） scope, and final write confirmation.
- [x] 3.3 Add tests that `validation.md`（校验规则） includes `pytest-xdist`（Pytest 并行插件） detection, executable lookup, missing path reporting, and no unauthorized dependency installation.
- [x] 3.4 Add tests that `config-draft.md`（配置草案规则） requires default string command（字符串命令）, with list command（列表命令） only after explicit user request for stricter argument boundaries.
- [x] 3.5 Add tests that `config-draft.md`（配置草案规则） requires user confirmation for `verify.maxParallel`（最大并行检查数）, `verify.timeoutSeconds`（超时秒数）, and `parallel: true`（并行检查）.
- [x] 3.6 Add tests that backup behavior requires `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件） and `/backups/` in `.build-and-verify/.gitignore`（忽略规则）.
- [x] 3.7 Add tests that no recognized ecosystem（未识别生态） fallback still collects user-provided commands through the fixed questionnaire（问答模板）.
- [x] 3.8 Add tests that dry run（试运行） choices are limited to existing build/verify（构建/验证） command scopes and do not claim single-check（单检查项） runner（运行器） support.
- [x] 3.9 Add template execution simulation tests for backup-before-overwrite, config structure validation, targeted dependency issue reporting, all user-selected dry run（试运行） scopes, backup-path constraints, and runtime tuning boundaries.

## 4. Verification

- [x] 4.1 Run focused build-and-verify（构建与验证） tests covering plugin package, init（初始化）, and template integrity.
- [x] 4.2 Run `openspec validate add-build-and-verify-init-skill --strict --no-interactive`.
- [x] 4.3 Run default build-and-verify（构建与验证） `verify`（快速验证） for this repository without `--full`（完整验证）.
- [x] 4.4 Record verification results in the final implementation summary.
