## MODIFIED Requirements

### Requirement: Build command validates local plugin package shape
The repository SHALL（必须）provide a local build command through the initialized build-and-verify（构建与验证）Plugin（插件）contract. Repository-specific package-shape checks remain repository-owned configured checks, not plugin-owned framework logic.

#### Scenario: Build command runs repository-owned package checks
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .`
- **THEN** the command uses `.build-and-verify/config.json` `build.checks`
- **THEN** the configured build check runs `python scripts/local_plugin_build.py`
- **THEN** `scripts/local_plugin_build.py` remains a repository-owned check command, not the build-and-verify（构建与验证）Plugin（插件） entrypoint

#### Scenario: Removed check entrypoint is not active automation
- **WHEN** repository active automation and guard（守卫） command files are inspected
- **THEN** `.github/workflows/`, `.comet.yaml`, `.comet/config.yaml`, `.pr-flow/config.yaml`, and `.build-and-verify/config.json` MUST NOT reference `scripts/check.py`
- **THEN** they MUST NOT reference `plugins/test-framework/` or `.test-framework/`

#### Scenario: Root Python test configuration is not active automation
- **WHEN** repository active automation and build-and-verify（构建与验证） configuration are inspected
- **THEN** root `pyproject.toml` MUST NOT exist
- **THEN** pytest（Python 测试运行器） commands in `.build-and-verify/config.json` MUST explicitly provide required paths and command options

### Requirement: Verify command follows initialized build-and-verify contract
The repository SHALL（必须）provide a verify command initialized by the build-and-verify（构建与验证）Plugin（插件） contract.

#### Scenario: Verify command defaults to framework fast mode
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`
- **THEN** the command uses `.build-and-verify/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full`
- **THEN** the command runs all `.build-and-verify/config.json` `verify.checks`
- **THEN** the command does not use cache（缓存） hits to skip checks（检查项）
- **THEN** passed checks（已通过检查项） refresh passed-result cache（通过结果缓存）
- **THEN** failed checks（失败检查项） are not stored as passed-result cache（通过结果缓存）
- **THEN** the command does not rely on the default verify mode being full（完整验证）

#### Scenario: Comet config keeps guard-compatible command shim
- **WHEN** Comet（双星流程）reads root `.comet.yaml`
- **THEN** it defines `build_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .`
- **THEN** it defines `verify_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`
- **THEN** those commands act as the project-level（项目级） guard（守卫） compatibility shim（兼容层） for the committed build-and-verify（构建与验证） runner（运行器） under `plugins/build-and-verify/`
