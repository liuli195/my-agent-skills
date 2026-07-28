## ADDED Requirements

### Requirement: Build and Verify tests minimize repeated real entrypoints
Build and Verify（构建与验证） tests MUST keep real entrypoint coverage small and move repeated branch coverage to in-process（进程内） tests.

#### Scenario: Init keeps a real E2E entrypoint
- **WHEN** repository tests cover build-and-verify init（构建与验证初始化）
- **THEN** at least one E2E（端到端测试） test MUST execute the real init（初始化） entrypoint
- **THEN** additional init（初始化） branch behavior MUST be tested in-process（进程内） unless it specifically verifies packaged entrypoint behavior
- **THEN** any additional real init（初始化） E2E（端到端测试） MUST be explicitly allowlisted as distinct packaged entrypoint behavior

#### Scenario: Verify keeps a real E2E entrypoint
- **WHEN** repository tests cover build-and-verify verify（构建与验证）
- **THEN** at least one E2E（端到端测试） test MUST execute the real default fast-verify（默认快速验证） entrypoint
- **THEN** additional verify（验证） branch behavior MUST be tested in-process（进程内） with a fake runner（假执行器）
- **THEN** any additional real verify（验证） E2E（端到端测试） MUST be explicitly allowlisted as distinct packaged entrypoint behavior

#### Scenario: Branch logic uses fake runner
- **WHEN** a test covers command planning, cache（缓存） selection, runtime（运行时） reporting, or failure classification
- **THEN** the test MUST call existing Python（Python 语言） functions in-process（进程内）
- **THEN** the test MUST use a fake runner（假执行器） instead of launching another real process

#### Scenario: Full verification finishes within target
- **WHEN** repository Full（完整验证） is run for this change
- **THEN** `maxParallel`（最大并行检查数） MUST be fixed to `0`
- **THEN** Pytest（测试工具） workers（工作进程） MUST use `auto`
- **THEN** the measured Full（完整验证） wall time MUST be less than or equal to 30 seconds
