## 1. Runtime Sync

- [x] 1.1 Implement repository runtime（运行时）copying for `init`（初始化） and explicit `update-runtime`（更新运行时）, using the same `build_and_verify.py` capability in user-level and repository-level locations.

## 2. Entrypoints And Text

- [x] 2.1 Update Skill（技能）文案, repository commands, and CI（持续集成）/automation entrypoints to use `.build-and-verify/runtime/build_and_verify.py` where a stable repository path is required.

## 3. Verification Coverage

- [x] 3.1 Add or update tests for runtime（运行时）copying, version提示, non-mutating `build/verify`（构建/验证）, and updated spec（规格）/Skill（技能）contracts.
- [x] 3.2 Run an end-to-end（端到端）regression from user entrypoints: initialize a temporary target repository, run `.build-and-verify/runtime/build_and_verify.py` for `update-runtime`（更新运行时）, `build`（构建） and `verify`（验证）, and confirm `build/verify`（构建/验证） do not mutate runtime（运行时） files.
