## MODIFIED Requirements

### Requirement: Parallel execution is coordinated by build-and-verify
Parallel execution SHALL（必须）be coordinated by the build-and-verify（构建与验证）runner（运行器） across configured verification checks where safe.

#### Scenario: Full verification remains runner-owned
- **WHEN** full verification（完整验证） runs configured verify checks（验证检查项）
- **THEN** the build-and-verify（构建与验证）runner（运行器） MUST run checks（检查项） with `checkParallel: true` concurrently
- **THEN** checks（检查项）without explicit `checkParallel`（检查项间并行） MUST default to serial execution（串行执行）
- **THEN** checks（检查项）that are not parallel-safe MUST still run during full verification
- **THEN** full verification MUST NOT become a partial or marker-filtered（测试标记过滤）subset to meet the runtime target

#### Scenario: Fast verification uses runner-owned parallel scheduling
- **WHEN** fast verification（快速验证） selects multiple cache-miss（缓存未命中） checks（检查项）
- **THEN** the build-and-verify（构建与验证）runner（运行器） MUST run selected checks（检查项） with `checkParallel: true` concurrently
- **THEN** fast verification MUST still skip checks（检查项） with valid passed-result cache（通过结果缓存）
- **THEN** fast verification MUST still write passed-result cache（通过结果缓存） for checks（检查项） that pass

#### Scenario: Pytest internal parallelism is explicit
- **WHEN** a pytest（Python 测试框架） verify check（验证检查项） declares `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** the runner（运行器） MUST run that pytest command with pytest-xdist（Pytest 并行插件） workers
- **THEN** the runner（运行器） MUST treat missing pytest-xdist（Pytest 并行插件） as a failed check（检查项）
- **THEN** `checkParallel`（检查项间并行） MUST NOT by itself imply pytest-xdist（Pytest 并行插件） usage

### Requirement: Optimization strategy applies across the repository
The repository SHALL（必须）apply both the repo-native test optimization layer and the build-and-verify（构建与验证） parallel execution layer across the full configured verification suite where safe, rather than special-casing one slow test file.

#### Scenario: Repo-native optimization is suite-wide
- **WHEN** repository tests repeat expensive Git（版本管理）setup, fake CLI（命令行界面）process scripts, Python CLI（命令行程序）startup, or equivalent setup costs
- **THEN** the tests SHOULD use shared fixtures（测试夹具）, reusable stubs（替身）, in-process calls, or narrow test seams（测试接缝）when those choices preserve the behavior under test
- **THEN** required end-to-end（端到端）coverage MUST remain for user-facing workflow paths

#### Scenario: Shared test helpers are repository-wide
- **WHEN** tests need repeated Git（版本管理）state, fake CLI（命令行界面）responses, or in-process（进程内）command execution
- **THEN** they SHOULD use shared helpers under `tests/support/`
- **THEN** they MUST keep required end-to-end（端到端）paths for user-facing workflows
- **THEN** they MUST NOT document the rule under `docs/rules/`

#### Scenario: Parallel execution is coordinated by Build and Verify
- **WHEN** full verification uses check-level parallel scheduling（检查项间并行调度）or pytest-xdist（Pytest 并行插件）
- **THEN** the Build and Verify（构建与验证）runner MUST coordinate parallel execution for configured verify checks（验证检查项）where safe
- **THEN** checks（检查项）with `checkParallel: true` MUST be eligible for check-level parallel scheduling（检查项间并行调度）
- **THEN** checks（检查项）without explicit `checkParallel` metadata（元数据）MUST default to serial execution（串行执行）
- **THEN** checks（检查项）that need pytest-xdist（Pytest 并行插件）MUST declare `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** full verification MUST NOT become a partial or marker-filtered（测试标记过滤）subset to meet the runtime target
