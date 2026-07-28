# Comet Spec Context

- Change: fix-flow-recovery-and-authorization-boundaries
- Phase: design
- Mode: beta
- Context hash: fd17e995e4327b73f3add139dfd0b1f78cbd83ef919859d1fc5830ae421a771d

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/proposal.md
- SHA256: f8e09ec274bad8708ba1fc5b4fc60ec1eccbbf0c2d72f87f10804cf17648121e
- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/design.md
- SHA256: acaddd4e9f9e917a918d73e5ce049f489867002dd7f1856188002b38ab763748
- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/tasks.md
- SHA256: 3ff02b49a0ed9b6cb1b197dc28a2586176a48928d2c46a9f94f728f80410539a
- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/pr-flow-plugin/spec.md
- SHA256: 5159022cd4d41fb1573b8605fc8d5506d2335fd76e03e809aa29780452a61992
- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/release-flow-plugin/spec.md
- SHA256: e4bb62df1697c81f86dc2affd579ee8d418cb993de0c34fee6722de68c68a58d

## Acceptance Projection

## openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/pr-flow-plugin/spec.md
- Lines: 1-38
- SHA256: 5159022cd4d41fb1573b8605fc8d5506d2335fd76e03e809aa29780452a61992

```md
## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Recoverable PR view failure after creation
- **WHEN** `complete`（收尾）成功创建 PR（拉取请求）
- **AND** 随后的 `gh pr view`（查看拉取请求）暂时无法读取同一个 PR（拉取请求）
- **THEN** complete（收尾） MUST NOT output `EXCEPTION_REQUIRED`（需要异常处理）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** stop-state details（停止状态详情） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include `transientCategory: post_create_view`（创建后查看分类）
- **THEN** stop-state details（停止状态详情） MUST include a command（命令） to retry the same `complete`（收尾） operation

### Requirement: Recoverable PR Flow failures expose recovery actions
PR Flow（拉取请求流程） MUST classify known recoverable failures through a shared contract and MUST include a recovery action in stop-state details（停止状态详情）.

#### Scenario: Recoverable reasons stay registered
- **WHEN** PR Flow（拉取请求流程） adds or keeps a known recoverable reason（可恢复原因）
- **AND** the reason（原因） is one of `gh_auth_required`, `gh_pr_view_transient_failed`, `checks_pending`, `ruleset_merge_blocking`, `checks_or_review_blocking`, `invalid_fixes`, `pr_missing` or `missing_upstream`
- **THEN** that reason MUST NOT map to `EXCEPTION_REQUIRED`（需要异常处理）
- **THEN** recovery details MUST include `nextAction`（下一步动作） or `nextCommand`（下一步命令）

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: Remote governance changes require current confirmation
- **WHEN** PR Flow init（拉取请求流程初始化）mentions GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量） or repository settings（仓库设置）
- **THEN** Skill（技能） guidance MUST prohibit modifying those remote settings without explicit confirmation in the current conversation
- **THEN** without confirmation, the Skill（技能） MUST only output remote tasks（远端待办）

### Requirement: Authorization phrase confirmation
系统 MUST 支持仓库共用 authorization phrase，用于替代用户说“我确认”。

#### Scenario: Authorization phrase source boundary
- **WHEN** PR Flow hotfix（拉取请求流程热修复） requires authorization phrase（授权短语）
- **THEN** the Skill（技能） MUST require manual input from the current conversation
- **THEN** the Skill（技能） MUST prohibit reading or reusing authorization phrase（授权短语） from memory（记忆）、history summaries（历史摘要）、logs（日志）、Issue（问题单） or reports（报告）
```

## openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/release-flow-plugin/spec.md

- Source: openspec/changes/fix-flow-recovery-and-authorization-boundaries/specs/release-flow-plugin/spec.md
- Lines: 1-21
- SHA256: e4bb62df1697c81f86dc2affd579ee8d418cb993de0c34fee6722de68c68a58d

```md
## MODIFIED Requirements

### Requirement: 发布前检查
系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、发布输入、manifest（插件清单）、source ref（源引用）、发布投影和远端发布冲突。

#### Scenario: 多个 preflight 问题输出汇总路径
- **WHEN** preflight（发布前检查）同时发现多个错误
- **AND** errors（错误） include release（发布）冲突、manifest（清单）版本不匹配、source ref（源引用）未合入版本提升 or plugin（插件）需要一并提升版本
- **THEN** preflight（发布前检查） MUST keep printing each underlying error（底层错误）
- **THEN** preflight（发布前检查） MUST print exactly one summary next action（汇总下一步动作） for the multi-error set
- **THEN** the summary MUST describe the current state and handling path（处理路径）, including that release（发布） conflicts require the user and agent（代理） to choose the release version（发布版本） before rerunning preflight（发布前检查）
- **THEN** the summary MUST describe manifest（清单）、source ref（源引用） and plugin（插件） version issues as requiring the PR（拉取请求） path
- **THEN** the summary MUST NOT infer or suggest a latest version（最新版本） or next version（下一版本）

### Requirement: 项目启用阶段
系统 MUST 提供 project setup（项目启用）阶段，用于生成目标项目配置，并输出 GitHub Actions（GitHub 自动化任务）权限配置方案。首版 MUST NOT 在没有额外实现仓库上下文和认证回读前修改 GitHub 仓库设置。

#### Scenario: Remote governance changes require current confirmation
- **WHEN** Release Flow（发布流程） guidance mentions GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量） or repository settings（仓库设置）
- **THEN** Skill（技能） guidance MUST prohibit modifying those remote settings without explicit confirmation in the current conversation
- **THEN** without confirmation, the Skill（技能） MUST only output remote tasks（远端待办）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
