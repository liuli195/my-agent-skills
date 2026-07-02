## ADDED Requirements

### Requirement: Build and Verify stale runtime handling remains non-mutating
Build and Verify（构建与验证） build（构建） and verify（验证） commands MUST report newer available runtime（运行时） without modifying repository files.

#### Scenario: Build and verify only report stale runtime
- **WHEN** 用户运行 build（构建） or verify（验证） from a repository runtime（运行时）
- **AND** a newer user-level（用户级） build-and-verify（构建与验证） runtime（运行时） is discoverable
- **THEN** output（输出） MUST report that the repository runtime（运行时） is stale
- **THEN** output（输出） MUST include an explicit update-runtime（更新运行时） command
- **THEN** build（构建） and verify（验证） MUST NOT modify `.build-and-verify/runtime/`
