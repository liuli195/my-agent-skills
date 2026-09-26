## ADDED Requirements

### Requirement: Plugin manifest version tests use manifest source of truth
Repository-owned local plugin package tests MUST NOT maintain a duplicate hard-coded plugin version source when validating dual Codex（代码助手） and Claude（代码助手） manifest（清单） files.

#### Scenario: Dual manifest version consistency is checked without duplicate constant
- **WHEN** a local plugin package test validates `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`
- **THEN** the test MUST read version（版本） values from the manifest（清单） files
- **THEN** the test MUST assert the two manifest（清单） versions are equal
- **THEN** the test MUST NOT require a second hard-coded plugin version constant to be updated during release version bump（版本提升）
