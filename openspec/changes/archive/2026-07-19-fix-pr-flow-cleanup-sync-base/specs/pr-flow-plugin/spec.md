## MODIFIED Requirements

### Requirement: Cleanup merged PR
系统 MUST 提供 cleanup（清理）入口，安全清理已合并 PR（拉取请求）的本地和远端源分支，将本地目标分支同步到最新远端目标提交，并避免切换被其他工作树占用的本地目标分支。

#### Scenario: Cleanup merged PR
- **WHEN** PR（拉取请求）已合并、工作区干净、源分支未被其他工作树占用，且本地目标分支可以安全快进
- **THEN** 系统 MUST fetch（拉取）并解析最新远端目标提交
- **THEN** 系统 MUST 将当前目标工作树定位到该提交的 detached HEAD（分离头）
- **THEN** 系统 MUST 在不检出本地目标分支的情况下，将该分支安全快进到同一提交
- **THEN** 系统 MUST 删除已合并 PR（拉取请求）的远端源分支和本地源分支
- **THEN** 系统 MUST 仅在当前 `HEAD`、本地目标分支和最新远端目标提交一致后输出清理完成状态和目标提交

#### Scenario: Cleanup creates a missing local base branch
- **WHEN** PR（拉取请求）已合并且本地目标分支不存在
- **THEN** cleanup（清理） MUST 在最新远端目标提交创建本地目标分支
- **THEN** 当前工作树 MUST remain at the same commit in detached HEAD（停在同一提交的分离头）

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
- **THEN** cleanup（清理） MUST continue only when that branch already equals the latest remote target commit（仅当该分支已等于最新远端目标提交时继续）
- **THEN** cleanup（清理） MUST otherwise stop before deleting either source branch（否则在删除任一源分支前停止）
- **THEN** stop-state details（停止状态详情） MUST identify the occupying worktree（占用工作树）

#### Scenario: Cleanup branch protection scope
- **WHEN** cleanup（清理）处理已合并 PR（拉取请求）
- **THEN** 系统 MUST NOT 删除本地或远端目标分支
- **THEN** 系统 MUST NOT 查询或自动配置 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集）

#### Scenario: Cleanup does not invent authorization
- **WHEN** cleanup（清理）按配置和当前状态可安全执行
- **THEN** 系统 MUST NOT 因 authorization phrase（授权短语）功能额外要求确认
