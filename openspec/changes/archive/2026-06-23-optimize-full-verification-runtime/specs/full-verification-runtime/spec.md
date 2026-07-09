## ADDED Requirements

### Requirement: Full verification has a local runtime target
Full repository verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage. The current full verification command for this repository SHALL（必须）be `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full` unless a later OpenSpec（规格流程）change explicitly replaces it.

#### Scenario: Full verification completes under target
- **WHEN** a developer runs the full verification command
- **THEN** the command MUST complete in under 60 seconds on the local development machine
- **THEN** the command MUST run all configured verify checks（验证检查项） from `.test-framework/config.json`, including the repository's Python（Python 语言）test checks

#### Scenario: Runtime evidence is recorded
- **WHEN** full verification is optimized
- **THEN** the verification report MUST include before and after timing evidence
- **THEN** the evidence MUST identify the largest remaining contributors if the command is still close to the target

### Requirement: Test optimization preserves behavioral coverage
The test suite SHALL（必须）reduce avoidable overhead without dropping local build contract（本地构建契约）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Agent Guard（代理守卫）, cross-agent-review（跨代理审查）, Test Framework（测试框架）behavior coverage, or OpenSpec（开放规格）validation coverage.

#### Scenario: PR Flow lifecycle coverage remains
- **WHEN** PR Flow（拉取请求流程）tests are optimized
- **THEN** complete、cleanup、hotfix、tweak、diagnose、review gate（审查门禁）和 audit（审计）行为 MUST remain covered
- **THEN** at least one true end-to-end PR Flow（拉取请求流程）path MUST continue to use real Git（版本管理）state

#### Scenario: Test Framework verification coverage remains
- **WHEN** Test Framework（测试框架）tests are optimized
- **THEN** verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior MUST remain covered
- **THEN** full mode（完整模式）MUST NOT skip required checks（检查项） because of cache hits（缓存命中）

#### Scenario: Expensive setup is not repeated unnecessarily
- **WHEN** multiple tests need equivalent Git（版本管理）repository state
- **THEN** tests SHOULD reuse faster setup seams or shared fixtures（测试夹具）
- **THEN** tests MUST NOT repeat clone（克隆）、push（推送）和 Python CLI（命令行程序）startup costs unless the behavior under test requires them

#### Scenario: No dependency is added just for speed without review
- **WHEN** a speed improvement requires a new test dependency such as pytest-xdist（并行测试插件）
- **THEN** the dependency MUST be explicitly evaluated in design or review notes before adoption

### Requirement: Optimization strategy applies across the repository
The repository SHALL（必须）apply both the repo-native test optimization layer and the parallel execution layer across the full configured verification suite where safe, rather than special-casing one slow test file.

#### Scenario: Repo-native optimization is suite-wide
- **WHEN** repository tests repeat expensive Git（版本管理）setup, fake CLI（命令行界面）process scripts, Python CLI（命令行程序）startup, or equivalent setup costs
- **THEN** the tests SHOULD use shared fixtures（测试夹具）, reusable stubs（替身）, in-process calls, or narrow test seams（测试接缝）when those choices preserve the behavior under test
- **THEN** required end-to-end（端到端）coverage MUST remain for user-facing workflow paths

#### Scenario: Shared test helpers are repository-wide
- **WHEN** tests need repeated Git（版本管理）state, fake CLI（命令行界面）responses, or in-process（进程内）command execution
- **THEN** they SHOULD use shared helpers under `tests/support/`
- **THEN** they MUST keep required end-to-end（端到端）paths for user-facing workflows
- **THEN** they MUST NOT document the rule under `docs/rules/`

#### Scenario: Parallel execution is coordinated by the Test Framework
- **WHEN** full verification uses pytest-xdist（并行测试插件）or another parallel execution mechanism
- **THEN** the Test Framework（测试框架）runner MUST coordinate parallel execution for all configured verify checks（验证检查项）where safe
- **THEN** checks（检查项）that are not parallel-safe MUST still run during full verification
- **THEN** checks（检查项）without explicit `parallel` metadata（元数据）MUST default to serial execution（串行执行）
- **THEN** full verification MUST NOT become a partial or marker-filtered（测试标记过滤）subset to meet the runtime target

### Requirement: Test-writing rules are captured as OpenSpec artifacts first
Repository test-writing rules for this change SHALL（必须）be expressed through OpenSpec（规格流程）change artifacts before any separate rule-document location is chosen.

#### Scenario: docs/rules remains out of scope
- **WHEN** test-writing rules are documented for this change
- **THEN** files under `docs/rules/` MUST NOT be created or modified
- **THEN** the rules MUST be represented in the OpenSpec（规格流程）change spec, design notes, tasks, or another explicitly confirmed location outside `docs/rules/`
