## ADDED Requirements

### Requirement: Full verification has a local runtime target
Full repository verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage.

#### Scenario: Full verification completes under target
- **WHEN** a developer runs the full verification command
- **THEN** the command MUST complete in under 60 seconds on the local development machine
- **THEN** the command MUST still run the repository's full Python（Python 语言）test suite entrypoint

#### Scenario: Runtime evidence is recorded
- **WHEN** full verification is optimized
- **THEN** the verification report MUST include before and after timing evidence
- **THEN** the evidence MUST identify the largest remaining contributors if the command is still close to the target

### Requirement: Test optimization preserves behavioral coverage
The test suite SHALL（必须）reduce avoidable overhead without dropping PR Flow（拉取请求流程）, Release Flow（发布流程）, Agent Guard（代理守卫）, and cross-agent-review（跨代理审查）behavior coverage.

#### Scenario: PR Flow lifecycle coverage remains
- **WHEN** PR Flow（拉取请求流程）tests are optimized
- **THEN** complete、cleanup、hotfix、tweak、diagnose、review gate（审查门禁）和 audit（审计）行为 MUST remain covered
- **THEN** at least one true end-to-end PR Flow（拉取请求流程）path MUST continue to use real Git（版本管理）state

#### Scenario: Expensive setup is not repeated unnecessarily
- **WHEN** multiple tests need equivalent Git（版本管理）repository state
- **THEN** tests SHOULD reuse faster setup seams or shared fixtures（测试夹具）
- **THEN** tests MUST NOT repeat clone（克隆）、push（推送）和 Python CLI（命令行程序）startup costs unless the behavior under test requires them

#### Scenario: No dependency is added just for speed without review
- **WHEN** a speed improvement requires a new test dependency such as pytest-xdist（并行测试插件）
- **THEN** the dependency MUST be explicitly evaluated in design or review notes before adoption

