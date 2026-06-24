## MODIFIED Requirements

### Requirement: Full verification has a local runtime target
Full repository verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage. The current full verification command for this repository SHALL（必须）be `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full` unless a later OpenSpec（开放规格）change explicitly replaces it.

#### Scenario: Full verification completes under target
- **WHEN** a developer runs the full verification command
- **THEN** the command MUST complete in under 60 seconds on the local development machine
- **THEN** the command MUST run all configured verify checks（验证检查项） from `.build-and-verify/config.json`, including the repository's Python（Python 语言）test checks

#### Scenario: Runtime evidence is recorded
- **WHEN** full verification is optimized
- **THEN** the verification report MUST include before and after timing evidence
- **THEN** the evidence MUST identify the largest remaining contributors if the command is still close to the target

## ADDED Requirements

### Requirement: Build-and-verify verification coverage remains
Build-and-verify（构建与验证）tests SHALL（必须）preserve verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior coverage.

#### Scenario: Build and verify coverage remains
- **WHEN** build-and-verify（构建与验证）tests are optimized or renamed
- **THEN** verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior MUST remain covered
- **THEN** full mode（完整模式） MUST NOT skip required checks（检查项） because of cache hits（缓存命中）

### Requirement: Parallel execution is coordinated by build-and-verify
Parallel execution SHALL（必须）be coordinated by the build-and-verify（构建与验证）runner（运行器） across the full configured verification suite where safe.

#### Scenario: Parallel execution remains runner-owned
- **WHEN** full verification uses pytest-xdist（并行测试插件）or another parallel execution mechanism
- **THEN** the build-and-verify（构建与验证）runner（运行器） MUST coordinate parallel execution for all configured verify checks（验证检查项）where safe
- **THEN** checks（检查项）that are not parallel-safe MUST still run during full verification
- **THEN** checks（检查项）without explicit `parallel` metadata（元数据） MUST default to serial execution（串行执行）
- **THEN** full verification MUST NOT become a partial or marker-filtered（测试标记过滤）subset to meet the runtime target
