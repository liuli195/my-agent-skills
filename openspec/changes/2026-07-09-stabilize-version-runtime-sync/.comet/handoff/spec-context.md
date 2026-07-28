# Comet Spec Context

- Change: stabilize-version-runtime-sync
- Phase: design
- Mode: beta
- Context hash: af804637b3f42074ee304ec8c3e323195b9bb1f8790eb6d076ec7537b40832e1

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/stabilize-version-runtime-sync/proposal.md
- SHA256: c3b2b8d5c8f08e51366e34c61a87a132e5de0c2790031c6b23d735dc28047ed7
- Source: openspec/changes/stabilize-version-runtime-sync/design.md
- SHA256: 15368db1410a5f4570254ed93190170d8f4edcd127435b649baf9e077d07980b
- Source: openspec/changes/stabilize-version-runtime-sync/tasks.md
- SHA256: ee6bcbc6292542c3c98b9fcd3664c71a4b9bbefedaa08e9d01879bd7354e4337
- Source: openspec/changes/stabilize-version-runtime-sync/specs/local-plugin-build-checks/spec.md
- SHA256: b2ed2fea4e9c592de4acfec34673882876c54c9c29cbeae2f22ae01e7ad517a0
- Source: openspec/changes/stabilize-version-runtime-sync/specs/plugin-sync-runtime-sync/spec.md
- SHA256: b63ec6efe9a7f679fa8c134b5c14e17465eebf6fabdfc4950b54a143b91cb8c2
- Source: openspec/changes/stabilize-version-runtime-sync/specs/release-flow-plugin/spec.md
- SHA256: 14b24ec462ef1a2014125ae91b15021e7f5672b90c1904aa213c4310ef425de3
- Source: openspec/changes/stabilize-version-runtime-sync/specs/test-framework-plugin/spec.md
- SHA256: 5998fb9489f509ce80e59ae033c0ce6c43ff53c8c2b19636b174c00a8e7e33cd

## Acceptance Projection

## openspec/changes/stabilize-version-runtime-sync/specs/local-plugin-build-checks/spec.md

- Source: openspec/changes/stabilize-version-runtime-sync/specs/local-plugin-build-checks/spec.md
- Lines: 1-20
- SHA256: b2ed2fea4e9c592de4acfec34673882876c54c9c29cbeae2f22ae01e7ad517a0

```md
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
```

## openspec/changes/stabilize-version-runtime-sync/specs/plugin-sync-runtime-sync/spec.md

- Source: openspec/changes/stabilize-version-runtime-sync/specs/plugin-sync-runtime-sync/spec.md
- Lines: 1-46
- SHA256: b63ec6efe9a7f679fa8c134b5c14e17465eebf6fabdfc4950b54a143b91cb8c2

```md
## ADDED Requirements

### Requirement: Plugin Sync closes build-and-verify runtime synchronization
Plugin Sync（插件同步） MUST detect and optionally update build-and-verify（构建与验证） runtime（运行时） snapshots for configured target repositories.

#### Scenario: Repository runtime is not configured
- **WHEN** Plugin Sync（插件同步） checks a repository without `.build-and-verify/config.json`
- **THEN** Plugin Sync（插件同步） MUST report `runtime_not_configured`
- **THEN** Plugin Sync（插件同步） MUST NOT run update-runtime（更新运行时）

#### Scenario: Installed runtime source is missing
- **WHEN** Plugin Sync（插件同步） checks a repository containing `.build-and-verify/config.json`
- **AND** the newest installed build-and-verify（构建与验证） runtime（运行时） cannot be found
- **THEN** Plugin Sync（插件同步） MUST report `runtime_source_missing`
- **THEN** Plugin Sync（插件同步） MUST NOT run update-runtime（更新运行时）

#### Scenario: Configured repository runtime is current
- **WHEN** Plugin Sync（插件同步） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` matches the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** Plugin Sync（插件同步） MUST report `runtime_current`

#### Scenario: Configured repository runtime is stale
- **WHEN** Plugin Sync（插件同步） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` is older than the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** Plugin Sync（插件同步） MUST report `runtime_stale`
- **THEN** output（输出） MUST include repository runtime（运行时） version（版本）, installed runtime（运行时） version（版本）, and the update-runtime（更新运行时） command

#### Scenario: Runtime update requires authorization
- **WHEN** Plugin Sync（插件同步） detects `runtime_stale`
- **THEN** Plugin Sync（插件同步） MUST NOT run update-runtime（更新运行时） without explicit user authorization
- **WHEN** the user authorizes update-runtime（更新运行时）
- **THEN** Plugin Sync（插件同步） MUST run the existing build-and-verify（构建与验证） update-runtime（更新运行时） command
- **THEN** Plugin Sync（插件同步） MUST reread `.build-and-verify/runtime/version.json`
- **THEN** Plugin Sync（插件同步） MUST report `runtime_updated` when the reread runtime（运行时） version（版本） matches the installed runtime（运行时） version（版本）

#### Scenario: Runtime update fails
- **WHEN** the user authorizes update-runtime（更新运行时）
- **AND** the existing build-and-verify（构建与验证） update-runtime（更新运行时） command fails
- **THEN** Plugin Sync（插件同步） MUST report `update_failed`
- **THEN** Plugin Sync（插件同步） MUST NOT report PR Flow（拉取请求流程） as the next step

#### Scenario: Runtime update reports PR Flow next step
- **WHEN** Plugin Sync（插件同步） updates `.build-and-verify/runtime/`
- **AND** Git（版本管理） reports tracked changes under `.build-and-verify/runtime/`
- **THEN** Plugin Sync（插件同步） MUST report that the repository should use PR Flow（拉取请求流程） for the change
- **THEN** Plugin Sync（插件同步） MUST NOT commit, push（推送）, or open PR（拉取请求）
```

## openspec/changes/stabilize-version-runtime-sync/specs/release-flow-plugin/spec.md

- Source: openspec/changes/stabilize-version-runtime-sync/specs/release-flow-plugin/spec.md
- Lines: 1-16
- SHA256: 14b24ec462ef1a2014125ae91b15021e7f5672b90c1904aa213c4310ef425de3

```md
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
```

## openspec/changes/stabilize-version-runtime-sync/specs/test-framework-plugin/spec.md

- Source: openspec/changes/stabilize-version-runtime-sync/specs/test-framework-plugin/spec.md
- Lines: 1-12
- SHA256: 5998fb9489f509ce80e59ae033c0ce6c43ff53c8c2b19636b174c00a8e7e33cd

```md
## ADDED Requirements

### Requirement: Build and Verify stale runtime handling remains non-mutating
Build and Verify（构建与验证） build（构建） and verify（验证） commands MUST report newer available runtime（运行时） without modifying repository files.

#### Scenario: Build and verify only report stale runtime
- **WHEN** 用户运行 build（构建） or verify（验证） from a repository runtime（运行时）
- **AND** a newer user-level（用户级） build-and-verify（构建与验证） runtime（运行时） is discoverable
- **THEN** output（输出） MUST report that the repository runtime（运行时） is stale
- **THEN** output（输出） MUST include an explicit update-runtime（更新运行时） command
- **THEN** the stale runtime（运行时） report MUST NOT by itself change the build（构建） or verify（验证） exit status
- **THEN** build（构建） and verify（验证） MUST NOT modify `.build-and-verify/runtime/`
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
