## MODIFIED Requirements

### Requirement: Build command validates local plugin package shape
The repository SHALL（必须）provide a local build command through the initialized test-framework Plugin（测试框架插件） contract. Repository-specific package-shape checks remain repository-owned configured checks, not plugin-owned framework logic.

#### Scenario: Build command runs repository-owned package checks
- **WHEN** a developer runs `python plugins/test-framework/skills/test-framework/scripts/test_framework.py build --project .`
- **THEN** the command uses `.test-framework/config.json` `build.checks`
- **THEN** the configured build check runs `python scripts/local_plugin_build.py`
- **THEN** `scripts/local_plugin_build.py` remains a repository-owned check command, not the test-framework Plugin（测试框架插件） entrypoint

#### Scenario: Removed check entrypoint is not active automation
- **WHEN** repository active automation and guard（守卫） command files are inspected
- **THEN** `.github/workflows/`, `.comet.yaml`, `.comet/config.yaml`, and `.test-framework/config.json` MUST NOT reference `scripts/check.py`

### Requirement: Verify command follows initialized test framework contract
The repository SHALL（必须）provide a verify command initialized by the test-framework Plugin（测试框架插件） contract.

#### Scenario: Verify command defaults to framework fast mode
- **WHEN** a developer runs `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .`
- **THEN** the command uses `.test-framework/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks
- **WHEN** a developer runs `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full`
- **THEN** the command runs all `.test-framework/config.json` `verify.checks`
- **THEN** the command does not use cache（缓存） hits to skip checks（检查项）
- **THEN** passed checks（已通过检查项） refresh passed-result cache（通过结果缓存）
- **THEN** failed checks（失败检查项） are not stored as passed-result cache（通过结果缓存）
- **THEN** the command does not rely on the default verify mode being full（全量验证）

#### Scenario: Comet config keeps guard-compatible command shim
- **WHEN** Comet（双星流程）reads root `.comet.yaml`
- **THEN** it defines `build_command: python plugins/test-framework/skills/test-framework/scripts/test_framework.py build --project .`
- **THEN** it defines `verify_command: python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .`
- **THEN** those commands act as the project-level（项目级） guard（守卫） compatibility shim（兼容层） for the committed test-framework runner（测试框架运行器） under `plugins/test-framework/`
