## Why

Current repository verification defaults to the full pytest suite, which takes about 214 seconds on this machine. A repository-specific split would solve only this repo. The reusable target is a lightweight test-framework Plugin（测试框架插件） that any repository can initialize to get the same build（构建检查）, default fast verify（快速验证）, and explicit full verify（全量验证） contract.

## What Changes

- Add a dual-surface `test-framework` Plugin（测试框架插件） for Claude（Claude 版本） and Codex（Codex 版本）.
- Initialize a minimal standard structure in target repositories: `.test-framework/config.json`, `.test-framework/.gitignore`, and `.test-framework/cache/`.
- Provide one canonical configured check set. Default `verify` applies changed-files（变更文件） selection and passed-result cache（通过结果缓存） to that set; `verify --full` runs the whole set.
- Provide one configuration surface and one command entrypoint: `.test-framework/config.json` and the installed test-framework Skill（技能） script `test_framework.py`.
- Keep full-suite runtime optimization out of this change; it is handled by `optimize-full-verification-runtime`.

## Capabilities

### New Capabilities
- `test-framework-plugin`: reusable Plugin（插件） initializes a lightweight verification framework.
- `local-verification-modes`: initialized repositories support default fast verify and explicit full verify from the same configured checks.

### Modified Capabilities
- `local-plugin-build-checks`: this repository's local check entrypoint is migrated to the initialized framework contract.

## Impact

- Affects plugin packaging, marketplace/projection registration, `.test-framework/config.json`, local check tests, `.comet.yaml`, and related OpenSpec specs.
- Does not install packages, change user-level configuration, contact remotes, manage CI（持续集成）, or optimize slow tests.
