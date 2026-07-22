# Comet Spec Context

- Change: guard-test-runtime-boundaries
- Phase: design
- Mode: beta
- Context hash: c31d4b3e7a59eca94e6f97c66eff7a51f1d9bb3c2989bc6c8c72040e4db68af7

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/guard-test-runtime-boundaries/proposal.md
- SHA256: 4eae05f35fe0b56ea8d3a6e6fcb3da33e9d41aca333d759be12d9fa092cd9830
- Source: openspec/changes/guard-test-runtime-boundaries/design.md
- SHA256: 216e2635ac1784bcb069a548a5b2201327cef1be4998c1cdf8016f7c6c531698
- Source: openspec/changes/guard-test-runtime-boundaries/tasks.md
- SHA256: 5de4aacc84782ebf704af2635c60b92a14b20591b38d0db4641b8e2dc5c74b3b
- Source: openspec/changes/guard-test-runtime-boundaries/specs/local-plugin-build-checks/spec.md
- SHA256: 4d38bf6dd77922763fcb96397a2d57e9640d9dd2e60335487336ab0238c17b79
- Source: openspec/changes/guard-test-runtime-boundaries/specs/test-framework-plugin/spec.md
- SHA256: 031e7fa6a415786795b6e19c4dea66928932993d4a05ae051d28aa2af69841c1

## Acceptance Projection

## openspec/changes/guard-test-runtime-boundaries/specs/local-plugin-build-checks/spec.md

- Source: openspec/changes/guard-test-runtime-boundaries/specs/local-plugin-build-checks/spec.md
- Lines: 1-24
- SHA256: 4d38bf6dd77922763fcb96397a2d57e9640d9dd2e60335487336ab0238c17b79

```md
## ADDED Requirements

### Requirement: Repository tests enforce runtime boundary
Repository-owned tests MUST enforce a boundary between ordinary tests and explicit E2E（端到端测试） coverage across the whole `tests/` tree.

#### Scenario: Ordinary tests do not call real subprocess directly
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT directly or through repository test helper（辅助函数）/ fixture（测试夹具） invoke real subprocess（子进程） execution
- **THEN** any allowed subprocess（子进程） usage MUST be listed by test function identity（测试函数身份） in an explicit E2E（端到端测试） allowlist

#### Scenario: Ordinary tests do not initialize temporary git repositories
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT directly or through repository test helper（辅助函数）/ fixture（测试夹具） run temporary git（版本控制） repository initialization
- **THEN** any allowed temporary git（版本控制） initialization MUST be listed by test function identity（测试函数身份） in an explicit E2E（端到端测试） allowlist

#### Scenario: Ordinary tests do not run real CLI entrypoints
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT run repository plugin CLI（命令行） entrypoints through real process execution directly or through repository test helper（辅助函数）/ fixture（测试夹具）
- **THEN** real CLI（命令行） entrypoint coverage MUST be limited to explicit E2E（端到端测试） allowlisted test function identities（测试函数身份）

#### Scenario: E2E allowlist is narrow
- **WHEN** a test needs real subprocess（子进程）, CLI（命令行）, temporary git（版本控制）, or broad cache（缓存） scanning
- **THEN** the test MUST be named by file path + qualified test function（文件路径加限定测试函数） and documented in the E2E（端到端测试） allowlist
- **THEN** the allowlist MUST NOT permit an entire file only because one test in that file is E2E（端到端测试）
```

## openspec/changes/guard-test-runtime-boundaries/specs/test-framework-plugin/spec.md

- Source: openspec/changes/guard-test-runtime-boundaries/specs/test-framework-plugin/spec.md
- Lines: 1-21
- SHA256: 031e7fa6a415786795b6e19c4dea66928932993d4a05ae051d28aa2af69841c1

```md
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
- **THEN** at least one E2E（端到端测试） test MUST execute the real verify（验证） entrypoint
- **THEN** additional verify（验证） branch behavior MUST be tested in-process（进程内） with a fake runner（假执行器）
- **THEN** any additional real verify（验证） E2E（端到端测试） MUST be explicitly allowlisted as distinct packaged entrypoint behavior

#### Scenario: Branch logic uses fake runner
- **WHEN** a test covers command planning, cache（缓存） selection, runtime（运行时） reporting, or failure classification
- **THEN** the test MUST call existing Python（Python 语言） functions in-process（进程内）
- **THEN** the test MUST use a fake runner（假执行器） instead of launching another real process
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
