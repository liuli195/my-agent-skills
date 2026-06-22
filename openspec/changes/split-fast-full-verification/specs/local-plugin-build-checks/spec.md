## MODIFIED Requirements

### Requirement: Verify command follows initialized test framework contract
The repository SHALL（必须）provide a verify command initialized by the test-framework Plugin（测试框架插件） contract.

#### Scenario: Verify command defaults to framework fast mode
- **WHEN** a developer runs `python scripts/check.py verify`
- **THEN** the command uses `.test-framework/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks
- **WHEN** a developer runs `python scripts/check.py verify --full`
- **THEN** the command runs all `.test-framework/config.json` `verify.checks`
- **THEN** the command does not rely on the default verify mode being full（全量验证）

#### Scenario: Comet config avoids duplicate command wiring
- **WHEN** Comet（双星流程）reads `.comet.yaml`
- **THEN** it does not define `build_command` or `verify_command`
