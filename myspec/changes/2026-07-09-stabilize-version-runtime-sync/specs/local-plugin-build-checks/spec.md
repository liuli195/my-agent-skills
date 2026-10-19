## ADDED Requirements

### Requirement: Repository tests guard plugin version source of truth
Repository-owned tests MUST prevent duplicate real plugin version facts while allowing normal release intermediate states.

#### Scenario: Dual manifest versions are compared from files
- **WHEN** repository tests validate a local plugin package
- **THEN** tests MUST read Codex（编码助手） and Claude（编码助手） version（版本） values from their manifest（清单） files
- **THEN** tests MUST assert the manifest（清单） versions are equal
- **THEN** tests MUST NOT require a second hard-coded real plugin version constant

#### Scenario: Real release version literals are rejected in tests
- **WHEN** repository tests scan `tests/`
- **THEN** tests MUST fail if a new real plugin release version literal such as `0.1.x` is introduced outside an explicit allowlist
- **THEN** the allowlist MUST NOT include ordinary assertions that duplicate current plugin release versions

#### Scenario: Runtime manifest mismatch is not a generic test failure
- **WHEN** build-and-verify（构建与验证）runtime（运行时） version（版本） temporarily differs from the build-and-verify plugin manifest（插件清单） during a release preparation state
- **THEN** ordinary repository tests MUST NOT fail solely because of that mismatch
- **THEN** release readiness MUST be checked by the Release Flow preflight（发布预检） runtime（运行时） synchronization rule
