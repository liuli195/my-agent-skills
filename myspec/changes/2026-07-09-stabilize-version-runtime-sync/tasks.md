## 1. Contract Tests

- [x] 1.1 Add repository tests that reject new real `0.1.x` version literals in `tests/` outside the explicit allowlist.
- [x] 1.2 Add Release Flow（发布流程） preflight（预检） tests for `runtime_update_required`.
- [x] 1.3 Add or update build-and-verify（构建与验证） tests proving build/verify（构建/验证） only report stale runtime（运行时）, include the update-runtime（更新运行时） command, preserve existing exit behavior, and do not mutate files.
- [x] 1.4 Add plugin-sync（插件同步） contract coverage for the confirmed user-level path `C:\Users\liuli\.agents\skills\plugin-sync`, including read-only states, authorized update, reread, PR Flow（拉取请求流程） next-step conditions, and status name consistency across `status-taxonomy.md` and `update-build-and-verify-runtime.md`.

## 2. Minimal Implementation

- [x] 2.1 Implement version-literal guard using existing Python（Python 语言） tests and stdlib（标准库） scanning.
- [x] 2.2 Implement Release Flow（发布流程） runtime（运行时） freshness check only for build-and-verify（构建与验证） release bumps.
- [x] 2.3 Keep build/verify（构建/验证） runtime（运行时） stale handling as report-only and non-blocking by itself.
- [x] 2.4 Implement plugin-sync（插件同步） `runtime_not_configured` / `runtime_source_missing` / `runtime_current` / `runtime_stale` / `runtime_updated` / `update_failed` behavior in the confirmed user-level skill（技能） location, and synchronize `references/status-taxonomy.md` plus `references/update-build-and-verify-runtime.md` to the same status names.

## 3. Verification

- [x] 3.1 Run focused version, Release Flow（发布流程）, build-and-verify（构建与验证）, and plugin-sync（插件同步） tests.
- [x] 3.2 Run end-to-end（端到端） regressions from user entrypoints: Release Flow（发布流程） preflight（预检） returning `runtime_update_required`, build/verify（构建/验证） reporting stale runtime（运行时） without mutation, and plugin-sync（插件同步） read-only plus authorized update flow.
- [x] 3.3 Run repository build-and-verify（构建与验证） fast verification.
