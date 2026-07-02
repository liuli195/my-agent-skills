## 1. Contract Tests

- [ ] 1.1 Add repository tests that reject new real `0.1.x` version literals in `tests/` outside the explicit allowlist.
- [ ] 1.2 Add Release Flow（发布流程） preflight（预检） tests for `runtime_update_required`.
- [ ] 1.3 Add or update build-and-verify（构建与验证） tests proving build/verify（构建/验证） only report stale runtime（运行时） and do not mutate files.
- [ ] 1.4 Confirm plugin-sync（插件同步） ownership path before implementing its runtime（运行时） sync tests.

## 2. Minimal Implementation

- [ ] 2.1 Implement version-literal guard using existing Python（Python 语言） tests and stdlib（标准库） scanning.
- [ ] 2.2 Implement Release Flow（发布流程） runtime（运行时） freshness check only for build-and-verify（构建与验证） release bumps.
- [ ] 2.3 Keep build/verify（构建/验证） runtime（运行时） stale handling as report-only.
- [ ] 2.4 Implement plugin-sync（插件同步） `runtime_current` / `runtime_stale` detection and authorized update path in the confirmed ownership location.

## 3. Verification

- [ ] 3.1 Run focused version, Release Flow（发布流程）, build-and-verify（构建与验证）, and plugin-sync（插件同步） tests.
- [ ] 3.2 Run repository build-and-verify（构建与验证） fast verification.
