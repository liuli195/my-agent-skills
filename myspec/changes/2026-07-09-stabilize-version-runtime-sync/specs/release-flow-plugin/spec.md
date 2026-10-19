## ADDED Requirements

### Requirement: Preflight blocks stale build-and-verify runtime before release
Release Flow preflight（发布预检） MUST block release（发布） when build-and-verify（构建与验证） runtime（运行时） has not been synchronized for a build-and-verify（构建与验证） plugin bump（版本提升）.

#### Scenario: Build-and-verify runtime is stale for requested release
- **WHEN** preflight（发布预检） is run for a release（发布） that bumps the build-and-verify（构建与验证） plugin
- **AND** the repository `.build-and-verify/runtime/version.json` does not match the requested build-and-verify（构建与验证） plugin release version（发布版本）
- **THEN** preflight（发布预检） MUST refuse to continue
- **THEN** output（输出） MUST use `runtime_update_required` as reason（原因）
- **THEN** output（输出） MUST include the repository runtime（运行时） version（版本）, requested plugin（插件） version（版本）, and update-runtime（更新运行时） command

#### Scenario: Runtime check does not mutate files
- **WHEN** preflight（发布预检） checks build-and-verify（构建与验证） runtime（运行时） synchronization
- **THEN** preflight（发布预检） MUST NOT update `.build-and-verify/runtime/`
- **THEN** preflight（发布预检） MUST NOT commit, push（推送）, or open PR（拉取请求）
