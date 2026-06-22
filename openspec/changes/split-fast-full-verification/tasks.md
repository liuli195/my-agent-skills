## 1. Test Framework Plugin Package

- [x] 1.1 Add `plugins/test-framework` with Claude（Claude 版本） and Codex（Codex 版本） plugin manifests.
- [x] 1.2 Add one `test-framework` Skill（技能） with an initialization script and minimal templates.
- [x] 1.3 Register `test-framework` in marketplace（市场目录） and release projection（发布投影） metadata.

## 2. Target Repository Framework

- [ ] 2.1 Initialize this repository with `scripts/check.py`, `.test-framework/config.json`, and `.test-framework/.gitignore`.
- [ ] 2.2 Migrate existing build（构建检查） behavior into configured `build.checks` without coupling it to the plugin template.
- [ ] 2.3 Define this repository's canonical `verify.checks` once; do not add a separate fast（快速验证） configuration.

## 3. Fast Cache Verification

- [ ] 3.1 Implement changed-files（变更文件） collection and check selection from configured `paths`.
- [ ] 3.2 Implement passed-result cache（通过结果缓存） keyed by check id（检查项标识）, command（命令）, inputs（输入）, config（配置）, Python（运行器） version, framework version, and cache version.
- [ ] 3.3 Ensure default `verify` runs selected checks with cache, while `verify --full` runs all configured verify checks.
- [ ] 3.4 Ensure failed（失败） results are not cached and no-check（无检查） runs do not automatically execute full（全量验证）.

## 4. Scope Guard

- [ ] 4.1 Confirm Comet（双星流程） root command wiring still points at the default `python scripts/check.py verify`.
- [ ] 4.2 Confirm no PR Flow（拉取请求流程）、Release Flow（发布流程） behavior wiring or CI（持续集成） workflow is changed by this A change; Release Flow（发布流程） projection（发布投影） may only add `test-framework` package metadata.

## 5. Validation

- [ ] 5.1 Run focused tests for the framework contract, local build checks, cache behavior, and init E2E（端到端） behavior.
- [ ] 5.2 Run `python scripts/check.py build`.
- [ ] 5.3 Run `python scripts/check.py verify` and confirm it completes through default fast（快速验证） mode.
- [ ] 5.4 Run `python scripts/check.py verify --full` once and record full-suite timing as baseline evidence.
