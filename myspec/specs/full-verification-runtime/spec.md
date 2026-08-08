# full-verification-runtime Specification

## Purpose

TBD - created by archiving change optimize-full-verification-runtime. Update Purpose after archive.

## Requirements

### Requirement: Test optimization preserves behavioral coverage
The test suite SHALL（必须）reduce avoidable overhead without dropping local build contract（本地构建契约）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Build and Verify（构建与验证）behavior coverage, or MySpec（自有规格）validation coverage.

#### Scenario: PR Flow lifecycle coverage remains
- **WHEN** PR Flow（拉取请求流程）tests are optimized
- **THEN** complete、cleanup、hotfix、tweak、diagnose、review gate（审查门禁）和 audit（审计）行为 MUST remain covered
- **THEN** at least one true end-to-end PR Flow（拉取请求流程）path MUST continue to use real Git（版本管理）state

#### Scenario: Build and Verify verification coverage remains
- **WHEN** Build and Verify（构建与验证）tests are optimized
- **THEN** verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior MUST remain covered
- **THEN** full mode（完整模式）MUST NOT skip required checks（检查项） because of cache hits（缓存命中）

#### Scenario: Expensive setup is not repeated unnecessarily
- **WHEN** multiple tests need equivalent Git（版本管理）repository state
- **THEN** tests SHOULD reuse faster setup seams or shared fixtures（测试夹具）
- **THEN** tests MUST NOT repeat clone（克隆）、push（推送）和 Python CLI（命令行程序）startup costs unless the behavior under test requires them

#### Scenario: No dependency is added just for speed without review
- **WHEN** a speed improvement requires a new test dependency such as pytest-xdist（并行测试插件）
- **THEN** the dependency MUST be explicitly evaluated in design or review notes before adoption
### Requirement: Test-writing rules are captured as MySpec artifacts first
Repository test-writing rules for this change SHALL（必须）be expressed through MySpec（规格流程）change artifacts before any separate rule-document location is chosen.

#### Scenario: docs/rules remains out of scope
- **WHEN** test-writing rules are documented for this change
- **THEN** files under `docs/rules/` MUST NOT be created or modified
- **THEN** the rules MUST be represented in the MySpec（规格流程）change spec, design notes, tasks, or another explicitly confirmed location outside `docs/rules/`
### Requirement: Build-and-verify verification coverage remains
Build-and-verify（构建与验证）tests SHALL（必须）preserve verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior coverage.

#### Scenario: Build and verify coverage remains
- **WHEN** build-and-verify（构建与验证）tests are optimized or renamed
- **THEN** verify selection（验证选择）, cache behavior（缓存行为）, full mode（完整模式）, failure reporting（失败报告）, and serial fallback（串行兜底） behavior MUST remain covered
- **THEN** full mode（完整模式） MUST NOT skip required checks（检查项） because of cache hits（缓存命中）
### Requirement: Optimization strategy applies across the repository
The repository SHALL（必须）apply both the repo-native test optimization layer and the build-and-verify（构建与验证） parallel execution layer across the full configured verification suite where safe, rather than special-casing one slow test file. Parallel execution SHALL（必须）be coordinated by the build-and-verify（构建与验证）runner（运行器）.

#### Scenario: Repo-native optimization is suite-wide
- **WHEN** repository tests repeat expensive Git（版本管理）setup, fake CLI（命令行界面）process scripts, Python CLI（命令行程序）startup, or equivalent setup costs
- **THEN** the tests SHOULD use shared fixtures（测试夹具）, reusable stubs（替身）, in-process calls, or narrow test seams（测试接缝）when those choices preserve the behavior under test
- **THEN** required end-to-end（端到端）coverage MUST remain for user-facing workflow paths

#### Scenario: Shared test helpers are repository-wide
- **WHEN** tests need repeated Git（版本管理）state, fake CLI（命令行界面）responses, or in-process（进程内）command execution
- **THEN** they SHOULD use shared helpers under `tests/support/`
- **THEN** they MUST keep required end-to-end（端到端）paths for user-facing workflows
- **THEN** they MUST NOT document the rule under `docs/rules/`

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
### Requirement: Full verification has a local runtime target
Full repository end-to-end verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage. This repository-level target is distinct from any narrower plugin test-suite target. The current full verification command for this repository SHALL（必须）be `build-and-verify verify --project . --full` unless a later MySpec（自有规格）change explicitly replaces it.

#### Scenario: Full repository verification completes under target
- **WHEN** a developer runs the full repository verification command
- **THEN** the command MUST complete in under 60 seconds on the local development machine
- **THEN** the command MUST run all configured verify checks（验证检查项） from `.build-and-verify/config.json`, including the repository's Python（Python 语言）test checks
- **THEN** this repository-level target MUST NOT redefine a narrower target for the Build and Verify（构建与验证）plugin's own test suite

#### Scenario: Runtime evidence is recorded
- **WHEN** full repository verification is optimized
- **THEN** the verification report MUST include before and after timing evidence
- **THEN** the evidence MUST identify the largest remaining contributors if the command is still close to the target
### Requirement: MySpec 快速验证复用候选发布包

MySpec（自有规格）快速验证 MUST 在一次非缓存检查中最多生成一次当前检出的候选 Tarball（压缩包），让并行工作进程消费同一只读候选包，并把不需要证明发布形态的逻辑分支留在进程内测试 Seam（接缝）；该检查 MUST 保留完整真实发布形态覆盖，并在本地开发机器上稳定运行在约 30 秒。

#### Scenario: 本地运行 MySpec 快速验证

- **WHEN** 贡献者对当前检出的 MySpec 变更运行非缓存快速验证
- **THEN** 当前候选 Tarball MUST 只生成一次并由全部并行工作进程共享
- **THEN** 各测试的用户目录、日志、运行状态和需要写入的安装前缀 MUST 相互隔离
- **THEN** `verify.my-spec` MUST 在本地开发机器上稳定运行在约 30 秒

#### Scenario: 持续集成提供候选包

- **WHEN** 持续集成已经提供当前检出的候选 Tarball
- **THEN** MySpec 快速验证 MUST 复用该候选包且不得再次打包

#### Scenario: 性能优化保留发布形态覆盖

- **WHEN** 不需要证明安装或进程行为的 MySpec 测试通过进程内模拟运行
- **THEN** 验证 MUST 继续保留至少一条官方打包、隔离安装、裸 `myspec` CLI（命令行程序）、校验、预览、差异和正式应用的完整路径
- **THEN** Windows 与 Linux npm（包管理器）布局及宿主 PATH（可执行文件搜索路径）隔离 MUST 继续被验证
