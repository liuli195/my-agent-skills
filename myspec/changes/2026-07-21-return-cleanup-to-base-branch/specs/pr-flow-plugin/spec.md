## MODIFIED Requirements

### Requirement: Cleanup merged PR
系统 MUST 提供 cleanup（清理）入口，安全清理已合并 PR（拉取请求）的本地和远端源分支，将本地目标分支同步到最新远端目标提交；当该分支未被其他工作树占用时，当前工作树 MUST 切回该分支，否则 MUST 保持安全的 detached HEAD（分离头）并记录原因。

#### Scenario: Cleanup merged PR
- **WHEN** PR（拉取请求）已合并、工作区干净、源分支未被其他工作树占用、本地目标分支可以安全快进，且没有其他工作树检出该目标分支
- **THEN** 系统 MUST fetch（拉取）并解析最新远端目标提交
- **THEN** 系统 MUST 将本地目标分支安全快进到同一提交
- **THEN** 系统 MUST 在删除任一源分支前切换当前工作树至该目标分支
- **THEN** 系统 MUST 删除已合并 PR（拉取请求）的远端源分支和本地源分支
- **THEN** 系统 MUST 回读并仅在当前 `HEAD`、本地目标分支和最新远端目标提交一致后输出清理完成状态和目标提交
- **THEN** 完成状态 MUST 记录 `currentBranch` 为目标分支，并记录 `baseCheckout.status` 为 `checked_out`

#### Scenario: Cleanup creates a missing local base branch
- **WHEN** PR（拉取请求）已合并且本地目标分支不存在
- **THEN** cleanup（清理） MUST 在最新远端目标提交创建本地目标分支
- **THEN** 当前工作树 MUST 切换至该目标分支
- **THEN** cleanup（清理） MUST 在删除任一源分支前回读并确认当前 `HEAD`、本地目标分支和最新远端目标提交一致

#### Scenario: Cleanup retries from a synchronized base branch
- **WHEN** 先前的 cleanup（清理）已将当前工作树切换至本地目标分支，但远端或本地源分支删除尚未完成
- **AND** 当前 `HEAD`、本地目标分支和最新远端目标提交一致
- **THEN** cleanup（清理） MUST accept the current target branch as a retry starting point（接受当前目标分支作为重试起点）
- **THEN** cleanup（清理） MUST retry only the remaining safe source-branch deletion steps（仅重试剩余的安全源分支删除步骤）
- **WHEN** 当前 `HEAD` 或本地目标分支不等于最新远端目标提交
- **THEN** cleanup（清理） MUST stop before changing the current target branch or deleting either source branch（在修改当前目标分支或删除任一源分支前停止）

#### Scenario: Cleanup refuses unsafe state
- **WHEN** PR（拉取请求）未合并、工作区不干净、源分支等于目标分支、源分支不匹配当前 PR（拉取请求）、远端目标提交不可用，或本地目标分支无法安全快进
- **THEN** cleanup（清理） MUST refuse execution（拒绝执行）
- **THEN** cleanup（清理） MUST output `EXCEPTION_REQUIRED`（需要异常处理） or a more specific stop state（更具体停止状态）
- **THEN** cleanup（清理） MUST NOT overwrite local-only target commits（覆盖本地独有的目标分支提交）

#### Scenario: Cleanup refuses a source branch occupied by another worktree
- **WHEN** 任何其他工作树仍检出待删除的本地源分支
- **THEN** cleanup（清理） MUST stop before deleting either the remote or local source branch（删除远端或本地源分支）
- **THEN** stop-state details（停止状态详情） MUST identify the occupying worktree（占用工作树）

#### Scenario: Cleanup handles a base branch occupied by another worktree
- **WHEN** 任何其他工作树检出本地目标分支
- **AND** 该分支已等于最新远端目标提交
- **THEN** cleanup（清理） MUST continue without updating or checking out that target branch
- **THEN** 当前工作树 MUST remain at the latest remote target commit in detached HEAD（最新远端目标提交的分离头）
- **THEN** cleanup（清理） MUST 删除已合并 PR（拉取请求）的远端源分支和本地源分支
- **THEN** 完成状态 MUST record `baseCheckout.status: skipped`、`baseCheckout.reason: base_branch_occupied` and the occupying worktree（记录跳过状态、原因和占用工作树）
- **WHEN** 该分支不等于最新远端目标提交
- **THEN** cleanup（清理） MUST stop before deleting either source branch（在删除任一源分支前停止）
- **THEN** stop-state details（停止状态详情） MUST identify the occupying worktree（占用工作树）

#### Scenario: Cleanup handles a base branch occupied during checkout
- **WHEN** cleanup（清理）在预检时没有发现其他工作树检出本地目标分支
- **AND** cleanup（清理）在删除任一源分支前尝试检出该目标分支时失败
- **THEN** 系统 MUST reread the worktree list（重新读取工作树清单）而非解析 Git（版本管理）错误文本
- **WHEN** 刷新后的工作树清单显示其他工作树检出目标分支，且该分支已等于最新远端目标提交
- **THEN** cleanup（清理） MUST remain at the latest remote target commit in detached HEAD（保持在最新远端目标提交的分离头）并完成源分支清理
- **THEN** 完成状态 MUST record `baseCheckout.status: skipped`、`baseCheckout.reason: base_branch_occupied` and the occupying worktree（记录跳过状态、原因和占用工作树）
- **WHEN** 刷新后的工作树清单未显示占用，或被占用分支不等于最新远端目标提交
- **THEN** cleanup（清理） MUST stop before deleting either source branch（在删除任一源分支前停止）
- **THEN** stop-state details（停止状态详情） MUST preserve checkout failure diagnostics（保留目标分支检出失败的诊断信息）

#### Scenario: Cleanup serializes competing base branch checkouts
- **WHEN** 两个不同工作树的 cleanup（清理）同时处理同一个本地目标分支
- **THEN** 系统 MUST only serialize the target-branch occupancy check、local target update、checkout decision and commit readback（仅串行化目标分支占用检查、本地目标更新、检出决定和提交回读）
- **THEN** 系统 MUST NOT serialize PR（拉取请求）查询、检查等待、合并或源分支删除
- **THEN** 第一个完成该临界区的 cleanup（清理） MAY 检出未被占用的目标分支
- **THEN** 后续 cleanup（清理） MUST 重新读取工作树清单，并在目标分支已同步时保持 detached HEAD（分离头）完成其源分支清理
- **THEN** 系统 MUST NOT leave more than one worktree checked out on the same local target branch（使多个工作树同时检出同一本地目标分支）

#### Scenario: Cleanup branch protection scope
- **WHEN** cleanup（清理）处理已合并 PR（拉取请求）
- **THEN** 系统 MUST NOT 删除本地或远端目标分支
- **THEN** 系统 MUST NOT 查询或自动配置 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集）

#### Scenario: Cleanup does not invent authorization
- **WHEN** cleanup（清理）按配置和当前状态可安全执行
- **THEN** 系统 MUST NOT 因 authorization phrase（授权短语）功能额外要求确认
