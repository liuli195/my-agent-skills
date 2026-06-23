## 1. Test Framework Plugin Package

- [x] 1.1 Add `plugins/test-framework` with Claude（Claude 版本） and Codex（Codex 版本） plugin manifests.
- [x] 1.2 Add one `test-framework` Skill（技能） with an initialization script and minimal templates.
- [x] 1.3 Register `test-framework` in marketplace（市场目录） and release projection（发布投影） metadata.

## 2. Target Repository Framework

- [x] 2.1 Initialize this repository with `.test-framework/config.json` and `.test-framework/.gitignore`, while using the plugin-provided runner（运行器） entrypoint.
- [x] 2.2 Migrate existing build（构建检查） behavior into configured `build.checks` without coupling it to the plugin template.
- [x] 2.3 Define this repository's canonical `verify.checks` once; do not add a separate fast（快速验证） configuration.

## 3. Fast Cache Verification

- [x] 3.1 Implement changed-files（变更文件） collection and check selection from configured `paths`.
- [x] 3.2 Implement passed-result cache（通过结果缓存） keyed by check id（检查项标识）, command（命令）, inputs（输入）, config（配置）, Python（运行器） version, framework version, and cache version.
- [x] 3.3 Ensure default `verify` runs selected checks with cache, while `verify --full` runs all configured verify checks without cache skip and refreshes passed-result cache（通过结果缓存） for passed checks.
- [x] 3.4 Ensure failed（失败） results are not cached and no-check（无检查） runs do not automatically execute full（全量验证）.

## 4. Scope Guard

- [x] 4.1 Confirm Comet（双星流程） root command wiring points at the default plugin `verify --project .` fast（快速验证） command.
- [x] 4.2 Confirm no PR Flow（拉取请求流程）、Release Flow（发布流程） behavior wiring or CI（持续集成） workflow is changed by this A change; Release Flow（发布流程） projection（发布投影） may only add `test-framework` package metadata.

## 5. Validation

- [x] 5.1 Run focused tests for the framework contract, local build checks, cache behavior including `verify --full` cache refresh, and init E2E（端到端） behavior.
- [x] 5.2 Run `python plugins/test-framework/skills/test-framework/scripts/test_framework.py build --project .`.
- [x] 5.3 Run `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .` and confirm it completes through default fast（快速验证） mode.
- [x] 5.4 Run `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full` once and record full-suite timing as baseline evidence.
