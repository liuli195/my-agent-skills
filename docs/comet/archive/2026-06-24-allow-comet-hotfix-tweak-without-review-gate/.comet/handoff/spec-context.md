# Comet Spec Context

- Change: allow-comet-hotfix-tweak-without-review-gate
- Phase: design
- Mode: beta
- Context hash: e2ad4d070a99fdf3f346ab7b02343e295a831c8e7f179bc5597a2f8b188442a8

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/proposal.md
- SHA256: 7d60494c1bd1ccf47b716610f5fe8ce4ddea9da63dbc4b31aea80205afc2a3b3
- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/design.md
- SHA256: 8e4fc228849025fe96576cd6c43367fbaad8e3fdd1ad9d099d936debd3100643
- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/tasks.md
- SHA256: 5913e2492652a5675f4700eadf6c8fce9f0b51c5bee30766de40aae675b9cc7a
- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 0f13fcd1664d5dce62f33ed4807ec89ac918e7f464f9733b181aa4c47fb7d084
- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/comet-agent-review-gate/spec.md
- SHA256: 9c2941f58906524270e0c1e430bff088b32d721901ca2d5d33a84ab1081768ed

## Acceptance Projection

## openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-19
- SHA256: 0f13fcd1664d5dce62f33ed4807ec89ac918e7f464f9733b181aa4c47fb7d084

```md
## MODIFIED Requirements

### Requirement: Global command guard points

系统 MUST 支持 Global Command Guard（全局命令守卫点）在命令匹配后按声明式 skip condition（跳过条件）放行特定上下文，并且不得把具体业务 workflow（工作流）判断硬编码进 Runtime（运行时）。

#### Scenario: 声明式 YAML 条件命中时跳过守卫

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** 该守卫声明 `skip_when`（跳过条件）读取相对 YAML（配置文件）路径、字段和允许值
- **AND** 该 YAML（配置文件）字段值命中允许值
- **THEN** Runtime（运行时）跳过该守卫的 evidence（证据）检查
- **AND** 该守卫不应造成 deny（拒绝）

#### Scenario: 跳过条件未命中时继续原有检查

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** `skip_when`（跳过条件）缺失、目标文件缺失、字段缺失或字段值未命中
- **THEN** Runtime（运行时）继续执行该守卫原有 evidence（证据）检查
```

## openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/comet-agent-review-gate/spec.md

- Source: openspec/changes/allow-comet-hotfix-tweak-without-review-gate/specs/comet-agent-review-gate/spec.md
- Lines: 1-21
- SHA256: 9c2941f58906524270e0c1e430bff088b32d721901ca2d5d33a84ab1081768ed

```md
## MODIFIED Requirements

### Requirement: Comet review gate 使用用户级 Global Command Guard

系统 MUST 使用用户级 Global Command Guard（全局命令守卫点）表达 Comet verify（验证）前的 review gate（审查门禁），但 hotfix（热修复）和 tweak（小改）workflow（工作流）不需要 cross-agent-review（跨代理审查）通过标记。

#### Scenario: full workflow 继续要求 cross-agent-review

- **WHEN** Comet full（完整）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **AND** 当前 change（变更）和当前 HEAD（提交头）没有有效 cross-agent-review（跨代理审查）pass marker（通过标记）
- **THEN** Global Command Guard（全局命令守卫点）拒绝该命令

#### Scenario: hotfix workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet hotfix（热修复）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令

#### Scenario: tweak workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet tweak（小改）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
