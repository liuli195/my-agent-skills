# Agent Plugin and Skill Development

This context defines the roles used to delegate work while developing and maintaining the repository's Agent Plugins（代理插件）and Skills（技能）.

## Language

**Subagent role（子代理角色）**:
A named responsibility selected for one delegated task after the main Agent（代理）has decided to delegate.
_Avoid_: Profile, mode

**Explorer（探索者）**:
The Subagent role（子代理角色）that investigates existing information without changing it and returns evidence.
_Avoid_: Scout, researcher

**Implementer（实施者）**:
The Subagent role（子代理角色）that changes code or documentation from confirmed requirements and verifies the result.
_Avoid_: Worker, coder

**Reviewer（审查者）**:
The Subagent role（子代理角色）that independently evaluates code or documentation and reports evidenced findings.
_Avoid_: Auditor, critic

**Development Flow（开发流程）**:
The end-to-end orchestration of one repository development change from requirement confirmation through implementation, PR（拉取请求）delivery, and cleanup.
_Avoid_: Product lifecycle, release flow

**Completion Check（完成检查）**:
The post-delivery check that decides whether the Development Flow is finally complete, reports cleanup residue, and returns to a safe recovery decision when completion is not proven.
_Avoid_: Fifth authorization gate, automatic cleanup

**Cleanup Residue（清理残留）**:
A physical worktree or temporary artifact that remains after the traceable Git（版本管理）cleanup has completed; it must be reported and never force-removed without explicit authorization.
_Avoid_: Successful cleanup, harmless leftover

**Direct Agent dispatch（直接 Agent 派发）**:
A main Agent call to the generic `Agent` tool without the controlled worktree dispatch interface; it is not a writable Implementer route.
_Avoid_: direct implementation

**Controlled Implementer dispatch（受控 Implementer 派发）**:
The verified route that starts one writable Implementer for one published ticket in one existing non-primary Git worktree.
_Avoid_: informal delegation

**Resource isolation（资源隔离）**:
The execution setting that controls which extensions and skills a subagent can load; it is distinct from Git worktree isolation.
_Avoid_: filesystem isolation

**Direction Confirmation（方向确认）**:
A non-gate user alignment with the overall design proposal before Requirements（需求）detail discussion. It neither publishes artifacts nor authorizes implementation or delivery.
_Avoid_: Gate, implementation authorization

**Gate 3 — Specification Archival and Delivery（规格存档并交付）**:
The third gate that combines formal MySpec（自有规格）archival and PR（拉取请求）delivery. It preserves the scoped `my-spec-add`（新增自有规格）confirmation and explicit delivery authorization, and passes into Completion Check（完成检查）only after the authorized delivery path finishes.
_Avoid_: Delivery-plan confirmation

**Flow Level（流程等级）**:
The risk-based classification that selects the cost and gates applied within a Development Flow（开发流程）.
_Avoid_: Complexity level, task size

**Future Input（未来输入）**:
A Build and Verify（构建与验证） glob input（通配符输入） that currently matches no files but remains valid so future matching files can invalidate the cache.
_Avoid_: Missing input, invalid glob

**Glob Input（通配符输入）**:
A Build and Verify（构建与验证） cache input pattern that expands to a stable Git-visible file set.
_Avoid_: Literal input, directory input

**Legacy MySpec Source（旧 MySpec 来源）**:
A source record that registers a MySpec（自有规格）plugin from the former shared marketplace or a legacy source path. A shared marketplace registration without an installed MySpec plugin record is not a Legacy MySpec Source.
_Avoid_: Legacy marketplace, duplicate marketplace

**Toolchain Identity（工具链身份）**:
The machine-readable identity of one managed tool: its mode and package version, or its official source repository, complete commit, and fixed package directory.
_Avoid_: Tool version pin, installation source

**Toolchain Record（工具链记录）**:
The Git-visible repository record of selected Toolchain Identities（工具链身份） used by PR Flow（拉取请求流程） CI（持续集成） synchronization.
_Avoid_: Tool lockfile, CI configuration

**源码工作树（Source Worktree）**:
The Git worktree that supplies the source implementation for a machine-level MySpec development binding.
_Avoid_: target worktree, current checkout

**目标工作树（Target Worktree）**:
The Git worktree whose specification directory is the intended target of a MySpec operation.
_Avoid_: source worktree, active source

**开发源码绑定（Development Source Binding）**:
The machine-level association between the bare MySpec CLI（命令行程序） and one source worktree; it is single-valued and switches explicitly.
_Avoid_: per-worktree binding, automatic source selection

**绑定不一致（Binding Mismatch）**:
The observable state in which the source worktree and target worktree differ, so MySpec write operations must stop before changing specifications.
_Avoid_: source drift, stale checkout

**Codex 配置目录（Codex Configuration Directory）**:
The directory that a lifecycle command intentionally selects as the Codex client profile it reads and writes.
_Avoid_: inherited Codex home

**Orca 临时配置目录（Orca Temporary Configuration Directory）**:
The isolated Codex client profile owned by an Orca（开发环境） session; it is not the default target for lifecycle management.
_Avoid_: user Codex directory, permanent profile

**用户 Codex 配置目录（User Codex Configuration Directory）**:
The persistent Codex client profile used by default when lifecycle management is running inside an Orca session.
_Avoid_: Orca runtime home

**客户端迁移（Client Migration）**:
The explicit convergence of a client from a Legacy MySpec Source（旧 MySpec 来源） to the current managed source while preserving unrelated client state.
_Avoid_: silent refresh, automatic cleanup

**Release Input（发布输入）**:
The plugin content and release metadata that a release exposes to its consumers, regardless of whether the consumer receives it from the marketplace or an NPM package.
_Avoid_: Source-only change, build-only change

**Release Baseline（发布基线）**:
The latest published representation of a plugin against which the next release determines content and version drift.
_Avoid_: Working tree, latest source branch

**Platform Verification Job（平台验证任务）**:
A continuous-integration result that validates the repository on one required execution platform.
_Avoid_: Platform-specific optional check

**Cross-Platform Verification Gate（跨平台验证汇总门禁）**:
The single required result whose success means every required Platform Verification Job（平台验证任务） succeeded.
_Avoid_: Workflow label, individual platform result

**Required Check（必需检查）**:
A GitHub status result that a repository rule requires before a pull request may merge.
_Avoid_: Any visible check, workflow conclusion
