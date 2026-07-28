## ADDED Requirements

### Requirement: Repository tests enforce runtime boundary
Repository-owned tests MUST enforce a boundary between ordinary tests and explicit E2E（端到端测试） coverage across the whole `tests/` tree.

The boundary MUST apply to plugin test families for Build and Verify（构建与验证）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Cross Agent Review（跨代理审查）, and Agent Guard（代理守卫）. Broad enforcement for those plugin tests is intentional scope for this change, not an overshoot outside the spec.

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

#### Scenario: Plugin tests share the same boundary
- **WHEN** repository tests scan plugin-focused tests for Build and Verify（构建与验证）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Cross Agent Review（跨代理审查）, or Agent Guard（代理守卫）
- **THEN** ordinary branch behavior in those plugin tests MUST use in-process（进程内） or fake runner（假执行器） execution
- **THEN** any real subprocess（子进程）, CLI（命令行）, temporary git（版本控制）, or broad cache（缓存） behavior in those plugin tests MUST be explicitly allowlisted by test function identity（测试函数身份） with a distinct E2E（端到端测试） reason
