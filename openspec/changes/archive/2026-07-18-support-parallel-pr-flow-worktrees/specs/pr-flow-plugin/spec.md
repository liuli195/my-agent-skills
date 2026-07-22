## ADDED Requirements

### Requirement: PR Flow isolates linked worktree runs
PR Flow（拉取请求流程）MUST 为每个 worktree（工作树）解析独立流程上下文和运行状态，并只互斥同一目标工作树与当前分支上的修改命令。

#### Scenario: Different worktrees run independently
- **WHEN** 同一 Git repository（Git 仓库）的两个 linked worktree（关联工作树）分别在不同源分支运行 complete（完整流程）或 tweak（小改）
- **THEN** 每个流程状态 MUST 记录 common Git dir（共享 Git 目录）、规范化工作树路径、源分支、目标分支、流程类型、PR（拉取请求，可为空）和当前源/目标提交
- **THEN** 两个流程 MUST 使用不同的运行状态和锁
- **THEN** 任一流程的等待、失败或恢复 MUST NOT 阻止另一个工作树继续

#### Scenario: Same worktree mutation is already active
- **WHEN** 同一目标工作树与当前分支已有修改命令持有运行锁
- **AND** 另一个 complete（完整流程）、tweak（小改）、cleanup（清理）或 hotfix（热修复）开始运行
- **THEN** 后启动的命令 MUST NOT 等待或修改本地与远端状态
- **THEN** 后启动的命令 MUST output `DISPATCH_REQUIRED`（需要外部进展） with `reason: flow_locked`
- **THEN** stop-state details（停止状态详情） MUST include the active flow（活动流程）、actor（执行者） and retry command（重试命令）

#### Scenario: Diagnose reports an active mutation without overwriting it
- **WHEN** diagnose（诊断）发现同一目标工作树与当前分支已有修改命令持锁
- **THEN** diagnose（诊断） MUST remain read-only（只读） and output `flow_locked`
- **THEN** diagnose（诊断） MUST NOT overwrite the active run state（活动运行状态） or `.pr-flow/last-status.json`

#### Scenario: Single-worktree use remains compatible
- **WHEN** PR Flow（拉取请求流程）在普通单工作树仓库运行
- **THEN** 现有命令参数和 `.pr-flow/last-status.json` MUST remain available
- **THEN** 运行状态 MUST use the same isolated run contract（隔离运行契约） without requiring new configuration（新配置）

### Requirement: PR Flow validates the latest remote base before dispatch
PR Flow（拉取请求流程）MUST 在 diagnose（诊断）、complete（完整流程）和 tweak（小改）进入 PR（拉取请求）生命周期前读取并验证最新远端目标提交。

#### Scenario: Source branch contains the latest remote base
- **WHEN** 最新远端目标提交是当前源提交的祖先
- **THEN** PR Flow（拉取请求流程） MUST record both commits（两个提交） and MAY continue

#### Scenario: Source branch does not contain the latest remote base
- **WHEN** 最新远端目标提交不是当前源提交的祖先，无论后续同步是否会产生冲突
- **THEN** PR Flow（拉取请求流程） MUST 在自动推送源分支或创建、同步、合并 PR（拉取请求）前停止
- **THEN** PR Flow（拉取请求流程） MUST output `EXCEPTION_REQUIRED`（需要异常处理） with `reason: base_outdated`
- **THEN** stop-state details（停止状态详情） MUST identify the source commit（源提交） and latest remote base commit（最新远端目标提交）
- **THEN** stop-state details（停止状态详情） MUST provide a recovery command（恢复命令）
- **THEN** PR Flow（拉取请求流程） MUST NOT automatically rebase（变基）、merge（合并） or resolve conflicts（解决冲突）
- **THEN** 一个工作树的冲突 MUST NOT modify or block another worktree（工作树）

### Requirement: PR gates belong to the current source and target commits
complete（完整流程）和 tweak（小改）MUST 只使用当前源/目标提交上的非空 required checks（必需检查），并在合并前复核这两个提交。

#### Scenario: Current required checks all pass
- **WHEN** GitHub（代码托管平台）为当前 PR（拉取请求）返回非空 required checks（必需检查）集合
- **AND** 每项必需检查都属于已记录的当前源提交且成功
- **AND** review gate（审查门禁，如适用）完成后源/目标提交仍等于已验证快照
- **THEN** complete（完整流程）或 tweak（小改） MAY continue to merge（合并）

#### Scenario: Required checks are empty or incomplete
- **WHEN** required checks（必需检查）集合为空，或任何必需检查缺失、等待中、失败或不属于当前源提交
- **THEN** complete（完整流程）和 tweak（小改） MUST NOT merge（合并）
- **THEN** stop-state details（停止状态详情） MUST identify the blocking checks（阻塞检查） and current source commit（当前源提交）

#### Scenario: Source or target commit changes after gates
- **WHEN** required checks（必需检查）或 review gate（审查门禁）完成后，PR（拉取请求）的源提交或目标提交发生变化
- **THEN** 本轮 checks（检查）、review（审查）和 mergeability（可合并状态）结果 MUST be invalidated（失效）
- **THEN** complete（完整流程）和 tweak（小改） MUST stop before merge（合并） and require a new run（重新运行）

#### Scenario: Tweak skips only review gate
- **WHEN** 用户运行 tweak（小改）
- **THEN** tweak（小改） MUST use the same latest-base、required-check and commit-revalidation（最新基线、必需检查和提交复核） rules as complete（完整流程）
- **THEN** tweak（小改） MUST skip only review gate（审查门禁）

### Requirement: Hotfix revalidates the remote target before push
hotfix（热修复）MUST 使用独立工作树运行状态，并在验证与授权后、推送前复核远端目标提交。

#### Scenario: Remote target remains unchanged
- **WHEN** hotfix（热修复）完成配置的完整验证和当前会话授权
- **AND** 再次 fetch（拉取）得到的远端目标提交等于验证前记录的提交
- **THEN** hotfix（热修复） MAY push（推送）当前提交
- **THEN** hotfix（热修复） MUST NOT enter PR checks or review gates（拉取请求检查或审查门禁）

#### Scenario: Remote target advances during verification
- **WHEN** hotfix（热修复）验证后读取的远端目标提交不同于验证前记录
- **THEN** hotfix（热修复） MUST NOT push（推送）
- **THEN** stop-state details（停止状态详情） MUST require sync（同步） and full re-verification（重新完整验证）

### Requirement: PR Flow explicitly removes safe linked worktrees
PR Flow（拉取请求流程）MUST 默认保留工作树，并只在用户显式传入 `--remove-worktree`（删除工作树参数）且安全条件全部满足时删除关联工作树。

#### Scenario: Cleanup keeps the linked worktree by default
- **WHEN** cleanup（清理）、complete（完整流程）或 tweak（小改）完成且未传入 `--remove-worktree`
- **THEN** 当前工作树 MUST remain at the latest remote base detached HEAD（最新远端目标提交的分离头）

#### Scenario: External caller removes a safe linked worktree
- **WHEN** 调用方从其他工作树通过 `--project`（项目路径参数）指定已完成流程的关联工作树
- **AND** 传入 `--remove-worktree`
- **AND** 目标是 `git worktree list`（工作树清单）中登记的非 main worktree（非主工作树）且工作区干净
- **THEN** PR Flow（拉取请求流程） MUST remove the linked worktree without `--force`（不强制删除）
- **THEN** PR Flow（拉取请求流程） MUST reread the worktree list（工作树清单） and confirm removal（确认删除）

#### Scenario: Caller runs inside the worktree to be removed
- **WHEN** `--remove-worktree`（删除工作树参数）从待删除工作树内部运行
- **THEN** PR Flow（拉取请求流程） MUST complete safe branch cleanup（安全分支清理） without removing the current directory（当前目录）
- **THEN** output（输出） MUST include an executable command（可执行命令） to remove it from another worktree（其他工作树）

#### Scenario: Unsafe worktree removal is refused
- **WHEN** 删除目标是 main worktree（主工作树）或工作区不干净
- **THEN** PR Flow（拉取请求流程） MUST refuse removal（拒绝删除）
- **THEN** PR Flow（拉取请求流程） MUST NOT use `--force`（强制参数）

#### Scenario: Hotfix removes only a synchronized linked worktree
- **WHEN** hotfix（热修复）收到 `--remove-worktree`（删除工作树参数）
- **AND** 推送完成且远端回读结果等于当前提交
- **THEN** 当前提交 MUST equal the latest remote target commit（等于最新远端目标提交） before the linked worktree MAY be removed（删除）
- **THEN** hotfix（热修复） MUST NOT query a PR or enter PR cleanup（查询拉取请求或进入拉取请求清理）

## MODIFIED Requirements

### Requirement: Cleanup merged PR
系统 MUST 提供 cleanup（清理）入口，安全清理已合并 PR（拉取请求）的本地和远端源分支，同时避免切换被其他工作树占用的本地目标分支。

#### Scenario: Cleanup merged PR
- **WHEN** PR（拉取请求）已合并、工作区干净且源分支未被其他工作树占用
- **THEN** 系统 MUST fetch（拉取）并解析最新远端目标提交
- **THEN** 系统 MUST 将当前目标工作树定位到该提交的 detached HEAD（分离头）
- **THEN** 系统 MUST 删除已合并 PR（拉取请求）的远端源分支和本地源分支
- **THEN** 系统 MUST 输出最终分离头状态和目标提交

#### Scenario: Cleanup refuses unsafe state
- **WHEN** PR（拉取请求）未合并、工作区不干净、源分支等于目标分支、源分支不匹配当前 PR（拉取请求）或远端目标提交不可用
- **THEN** cleanup（清理） MUST refuse execution（拒绝执行）
- **THEN** cleanup（清理） MUST output `EXCEPTION_REQUIRED`（需要异常处理） or a more specific stop state（更具体停止状态）

#### Scenario: Cleanup refuses a branch occupied by another worktree
- **WHEN** 任何其他工作树仍检出待删除的本地源分支
- **THEN** cleanup（清理） MUST stop before deleting either the remote or local source branch（删除远端或本地源分支）
- **THEN** stop-state details（停止状态详情） MUST identify the occupying worktree（占用工作树）

#### Scenario: Cleanup branch protection scope
- **WHEN** cleanup（清理）处理已合并 PR（拉取请求）
- **THEN** 系统 MUST NOT 删除本地或远端目标分支
- **THEN** 系统 MUST NOT 查询或自动配置 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集）

#### Scenario: Cleanup does not invent authorization
- **WHEN** cleanup（清理）按配置和当前状态可安全执行
- **THEN** 系统 MUST NOT 因 authorization phrase（授权短语）功能额外要求确认
