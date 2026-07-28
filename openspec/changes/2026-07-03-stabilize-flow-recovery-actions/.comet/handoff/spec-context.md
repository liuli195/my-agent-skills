# Comet Spec Context

- Change: stabilize-flow-recovery-actions
- Phase: design
- Mode: beta
- Context hash: 774656eba09ef62050a3979e960e11e8a851efd940cefd00c8ee5e488a426607

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/stabilize-flow-recovery-actions/proposal.md
- SHA256: 0bc4300b36afc34e5c2da3b528a9f605b5974e6a7ea0065e0c7916f9f2299a03
- Source: openspec/changes/stabilize-flow-recovery-actions/design.md
- SHA256: 46ed58c3a70860c1115fcebf194a3572b58c4b89fad09e4fef2b978f4306d45a
- Source: openspec/changes/stabilize-flow-recovery-actions/tasks.md
- SHA256: e48956289c29f38f835e53eea146080bb67b309b3d5bf6610a4618233eaeb1d3
- Source: openspec/changes/stabilize-flow-recovery-actions/specs/local-plugin-build-checks/spec.md
- SHA256: b180238d5fad18cffd2caedc296f6aee1c043f3a65fd6f9b40b55ef3c4c710fc
- Source: openspec/changes/stabilize-flow-recovery-actions/specs/pr-flow-plugin/spec.md
- SHA256: af6adf7d187b71f61bb2d340deed441776d99d07c1d74d1fbc99faf86348720c
- Source: openspec/changes/stabilize-flow-recovery-actions/specs/release-flow-plugin/spec.md
- SHA256: 28d79d5e4cc0dd7ad9118a86894fb90a0ce2657528dc45d2375e15736a7d2207

## Acceptance Projection

## openspec/changes/stabilize-flow-recovery-actions/specs/local-plugin-build-checks/spec.md

- Source: openspec/changes/stabilize-flow-recovery-actions/specs/local-plugin-build-checks/spec.md
- Lines: 1-12
- SHA256: b180238d5fad18cffd2caedc296f6aee1c043f3a65fd6f9b40b55ef3c4c710fc

```md
## ADDED Requirements

### Requirement: Repository checks enforce recoverable stop action contract
Repository-owned checks（仓库检查） MUST guard the recoverable stop-state contract for local plugin scripts.

#### Scenario: Recoverable stop states include recovery details
- **WHEN** repository tests inspect local plugin scripts or their reason（原因） tables
- **THEN** every known recoverable `DISPATCH_REQUIRED`（需要外部进展）, `PUSH_REQUIRED`（需要推送） or `REPLY_OR_FIX_REQUIRED`（需要回复或修复） stop state MUST include `nextAction`（下一步动作） or `nextCommand`（下一条命令）

#### Scenario: Known recoverable reasons do not become generic exceptions
- **WHEN** repository tests cover known recoverable reasons（原因） such as GitHub authentication, transient PR view failure, pending checks, ruleset blocking, and invalid user input
- **THEN** those reasons（原因） MUST NOT be reported only as generic `EXCEPTION_REQUIRED`（需要人工处理）
```

## openspec/changes/stabilize-flow-recovery-actions/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/stabilize-flow-recovery-actions/specs/pr-flow-plugin/spec.md
- Lines: 1-27
- SHA256: af6adf7d187b71f61bb2d340deed441776d99d07c1d74d1fbc99faf86348720c

```md
## ADDED Requirements

### Requirement: Recoverable PR Flow failures expose recovery actions
PR Flow（拉取请求流程） MUST classify known recoverable failures through a shared contract and MUST include a recovery action in stop-state details（停止状态详情）.

#### Scenario: GitHub authentication failure is actionable
- **WHEN** a `gh`（GitHub 命令行） operation fails because authentication is missing, expired, or unauthorized
- **THEN** PR Flow（拉取请求流程） MUST NOT report the failure as a generic `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop-state details（停止状态详情） MUST use `gh_auth_required` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include a `nextAction`（下一步动作） or `nextCommand`（下一条命令） that tells the user how to check or refresh GitHub authentication

#### Scenario: Transient PR view failure remains recoverable
- **WHEN** a read-only `gh pr view`（查看拉取请求） call exhausts bounded retries for a known transient（临时） failure
- **THEN** PR Flow（拉取请求流程） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** stop-state details（停止状态详情） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include retry evidence and a command（命令） to retry the same PR Flow operation

#### Scenario: Pending checks and ruleset blocks preserve next steps
- **WHEN** PR Flow（拉取请求流程） stops because checks（检查） are pending（等待中） or ruleset（规则集） blocks merge（合并）
- **THEN** stop-state details（停止状态详情） MUST include the current reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include a `nextAction`（下一步动作） or `nextCommand`（下一条命令） for waiting and rerunning the lifecycle

#### Scenario: Invalid fixes none gives direct retry guidance
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）并传入 `--fixes None`
- **THEN** PR Flow（拉取请求流程） MUST stop before auto-push（自动推送）、PR create（创建拉取请求）、sync（同步） or merge（合并）
- **THEN** stop-state details（停止状态详情） MUST identify `None` as invalid `--fixes`（修复问题编号） input
- **THEN** output（输出） MUST tell the user to remove `--fixes` when there is no issue（问题单） to close
```

## openspec/changes/stabilize-flow-recovery-actions/specs/release-flow-plugin/spec.md

- Source: openspec/changes/stabilize-flow-recovery-actions/specs/release-flow-plugin/spec.md
- Lines: 1-19
- SHA256: 28d79d5e4cc0dd7ad9118a86894fb90a0ce2657528dc45d2375e15736a7d2207

```md
## ADDED Requirements

### Requirement: Preflight failures expose ordered next actions
Release Flow preflight（发布预检） MUST translate the three preflight（发布预检） errors listed in this change（变更） into ordered next actions without changing publish（发布） behavior.

#### Scenario: Source ref missing version bump explains PR path
- **WHEN** preflight（发布预检） fails because `sourceRef`（源引用） does not contain the requested manifest（清单） version bump（版本提升）
- **THEN** output（输出） MUST identify that the version bump（版本提升） must first be merged through PR Flow（拉取请求流程）
- **THEN** output（输出） MUST include the ordered next action to create, merge, and then rerun preflight（发布预检）

#### Scenario: Manifest mismatch explains local correction
- **WHEN** preflight（发布预检） fails because a requested plugin manifest（插件清单） does not match the requested release version（发布版本）
- **THEN** output（输出） MUST identify the plugin（插件） and manifest（清单） path
- **THEN** output（输出） MUST include the next action to correct the manifest（清单） before rerunning preflight（发布预检）

#### Scenario: Existing release reports next version path
- **WHEN** preflight（发布预检） finds that the requested tag（标签） or GitHub Release（GitHub 发布） already exists
- **THEN** output（输出） MUST preserve `release already exists`（发布已存在）
- **THEN** output（输出） MUST include a next action to choose a new release version（发布版本） and rerun preflight（发布预检）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
