## MODIFIED Requirements

### Requirement: PR Flow explicitly removes safe linked worktrees
PR Flow（拉取请求流程）MUST 默认保留工作树，并只在用户显式传入 `--remove-worktree`（删除工作树参数）且安全条件全部满足时删除关联工作树。目标由 Orca（工作区管理器）登记时，PR Flow（拉取请求流程）MUST 优先使用 Orca（工作区管理器）删除；未登记或 Orca（工作区管理器）不可用时，PR Flow（拉取请求流程）MUST 使用非强制 Git（版本管理）删除。

#### Scenario: Cleanup keeps the linked worktree by default
- **WHEN** cleanup（清理）、complete（完整流程）或 tweak（小改）完成且未传入 `--remove-worktree`
- **THEN** 当前工作树 MUST remain at the latest remote base detached HEAD（最新远端目标提交的分离头）

#### Scenario: External caller removes a safe linked worktree
- **WHEN** 调用方从其他工作树通过 `--project`（项目路径参数）指定已完成流程的关联工作树
- **AND** 传入 `--remove-worktree`
- **AND** 目标是 `git worktree list`（工作树清单）中登记的非 main worktree（非主工作树）且工作区干净
- **AND** 目标未由 Orca（工作区管理器）登记，或 Orca（工作区管理器）命令不可用、查询失败或返回无效工作树列表
- **THEN** PR Flow（拉取请求流程） MUST remove the linked worktree without `--force`（不强制删除）
- **THEN** PR Flow（拉取请求流程） MUST reread the worktree list（工作树清单） and confirm removal（确认删除）

#### Scenario: External caller removes an Orca-managed linked worktree
- **WHEN** 调用方从其他工作树通过 `--project`（项目路径参数）指定已完成流程的关联工作树
- **AND** 传入 `--remove-worktree`
- **AND** 目标是 `git worktree list`（工作树清单）中登记的非 main worktree（非主工作树）且工作区干净
- **AND** Orca（工作区管理器）工作树列表按规范化绝对路径匹配目标
- **THEN** PR Flow（拉取请求流程） MUST remove the linked worktree through Orca（工作区管理器）using the matched worktree identifier（使用匹配的工作树标识）
- **THEN** PR Flow（拉取请求流程） MUST NOT pass `--force`（强制参数） to Orca（工作区管理器）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `git worktree remove`（Git 工作树删除）
- **THEN** PR Flow（拉取请求流程） MUST reread the Git（版本管理）worktree list（工作树清单） and confirm removal（确认删除）

#### Scenario: Orca-managed removal failure does not fall back to Git
- **WHEN** Orca（工作区管理器）工作树列表按规范化绝对路径匹配目标
- **AND** Orca（工作区管理器）删除命令失败
- **THEN** PR Flow（拉取请求流程） MUST stop with `EXCEPTION_REQUIRED`（需要异常处理） and `reason: orca_worktree_remove_failed`
- **THEN** stop-state details（停止状态详情） MUST preserve the Orca（工作区管理器）command failure diagnostics（命令失败诊断）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `git worktree remove`（Git 工作树删除）

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
