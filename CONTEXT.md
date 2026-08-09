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
The narrow adapter that starts a writable Implementer in one verified existing non-primary Git worktree while preserving the caller's prompt and description unchanged.
_Avoid_: ticket executor, workflow engine

**Approved Ticket（已批准票据）**:
The immutable implementation specification confirmed at Gate 1 and used by Implementer and Reviewer as the acceptance baseline.
_Avoid_: progress log, mutable evidence record

**Single Writer（单写者）**:
The Gate 2 rule that every Git-visible implementation change is made by a worktree-bound Implementer while the main Agent orchestrates and evaluates evidence.
_Avoid_: main Agent implementation, shared writer

**Returned（已返回）**:
The state reached when an Implementer invocation ends; it requires evidence inspection and is not ticket acceptance.
_Avoid_: completed, accepted

**Accepted（已验收）**:
The state reached only after the actual commit, diff, worktree, verification, smoke, and required review satisfy the Approved Ticket.
_Avoid_: subagent reported success

**Gate Confirmation（门禁确认）**:
The one-time user authorization for one Development Flow gate. It remains valid through execution and recovery; a failed post-confirmation action resumes from that action instead of reopening the gate.
_Avoid_: repeat confirmation, recovery authorization

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

**Tool Implementation Closure（工具实现闭包）**:
The exact plugin and shared lifecycle inputs that determine one managed tool's runnable and controlled-package content. Each tool has its own closure; shared inputs may belong to more than one closure.
_Avoid_: Entire repository, current HEAD

**Toolchain Identity（工具链身份）**:
The machine-readable identity of one managed tool: its release package version, or its official source repository, reproducible implementation commit, fixed package directory, and Tool Implementation Closure identity.
_Avoid_: Whole-worktree commit, installation source

**Toolchain Record（工具链记录）**:
The Git-visible repository record of selected Toolchain Identities（工具链身份） used by PR Flow（拉取请求流程） CI（持续集成） synchronization.
_Avoid_: Tool lockfile, CI configuration

**源码工作树（Source Worktree）**:
The Git worktree that supplies the canonical source implementation for a machine-level managed-tool development binding; it does not determine an operation's data target.
_Avoid_: target worktree, current checkout

**目标工作树（Target Worktree）**:
The Git worktree whose specification directory is the intended target of a MySpec operation.
_Avoid_: source worktree, active source

**工作树登记（Worktree Registration）**:
The logical record that identifies a target worktree in Git or a worktree manager; its removal does not by itself prove that the physical directory is gone.
_Avoid_: physical worktree directory, cleanup residue

**实体工作树目录（Physical Worktree Directory）**:
The filesystem directory occupied by a target worktree, including generated files and directory links owned by that worktree.
_Avoid_: worktree registration, shared dependency target

**工作树删除后置条件（Worktree Removal Postcondition）**:
For an explicitly requested worktree removal, both the target worktree registration and its physical worktree directory are absent before the flow reports completion.
_Avoid_: registration-only cleanup, cleanup residue

**开发源码绑定（Development Source Binding）**:
The machine-level association between one bare managed-tool CLI（命令行程序） and its canonical source worktree; it is single-valued per tool, target-independent, and switches explicitly.
_Avoid_: per-worktree binding, automatic source selection

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

**检查尚未报告**:
当前提交的 Required Check 尚未被外部系统注册或观测到；它是可短暂等待的初始状态，不等同于检查查询不可用。
_Avoid_: 检查不可用、检查等待、空检查通过

**检查等待**:
Required Check 已被观测到但尚未完成，流程可以等待其最终结果后继续或在等待期限结束时停止。
_Avoid_: 检查尚未报告、检查失败、规则集阻塞

**检查阻塞**:
Required Check 已失败或取消，流程必须提供修复或重新触发动作，而不是继续等待或尝试合并。
_Avoid_: 检查等待、规则集阻塞

**规则集阻塞**:
Required Check 不再处于等待或失败状态，但合并仍被目标分支策略拒绝，需要处理规则、审查或权限条件。
_Avoid_: 检查等待、检查阻塞

**验证工作树（Verification Worktree）**:
执行 Build and Verify（构建与验证）时作为当前项目来源的具体 Git（版本管理）工作树；本次验证只读取它自己的提交、HEAD（当前提交）和未提交状态。
_Avoid_: 目标工作树

**验证基线（Verification Baseline）**:
提交范围验证使用的固定起始提交，在工作树开始本次变更前确定，验证期间不随分支引用移动。
_Avoid_: HEAD^、可变分支基线

**有效快速验证（Valid Fast Verification）**:
至少选中一个检查且最终状态为 passed（通过）的快速验证；仅退出码为 0 或 checked（已检查）为空不足以证明验证通过。
_Avoid_: 空检查通过
