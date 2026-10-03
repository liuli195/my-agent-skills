# 修复 PR Flow 工作树实体清理残留

## Problem Statement

Windows（视窗系统）上，非主工作树可以通过目录联接点共享主工作树的 `.venv` 和 `node_modules`。Git（版本管理）或 Orca（工作树管理器）删除工作树登记后，目标实体工作树目录可能仍因这些目录联接点残留。PR Flow（拉取请求流程）当前只确认登记消失，就报告 `cleanup_complete`，导致用户看到清理成功但磁盘仍保留孤立目录。

## Solution

当用户显式传入 `--remove-worktree`（删除工作树参数）时，PR Flow（拉取请求流程）在完成 Git/Orca 删除后统一验证工作树删除后置条件：目标登记已经消失，且目标实体工作树目录也已经消失。若登记已消失但实体目录仍存在，流程使用 Python（Python 语言）标准库的安全目录删除能力清理整个目标目录，并再次验证路径。只有两项后置条件均满足时才报告完成；删除失败时停止并提供从仍存活工作树执行的恢复动作。

## User Stories

1. As a PR Flow user, I want an explicitly removed linked worktree to disappear from both Git and the filesystem, so that cleanup does not leave an orphan directory.
2. As a Windows maintainer, I want worktrees containing shared dependency directory links to be removed without deleting the main worktree's shared dependencies, so that linked environments remain safe.
3. As a PR Flow user, I want Git-managed and Orca-managed worktrees to receive the same physical deletion postcondition, so that the result does not depend on the selected adapter.
4. As a repository maintainer, I want cleanup to remain non-forced at the Git and Orca registration-removal step, so that dirty or unsafe worktrees are not silently removed.
5. As a PR Flow user, I want cleanup to avoid reporting completion when physical deletion fails, so that the stop state reflects the actual machine state.
6. As a PR Flow user, I want a failed post-registration deletion to provide a recovery action from another worktree, so that I do not need to rerun cleanup from a deleted or unregistered worktree.
7. As a repository maintainer, I want failed cleanup not to recreate `.pr-flow` inside an unregistered target directory, so that error reporting does not create new residue.
8. As an existing PR Flow user, I want the default behavior without `--remove-worktree` and the main-worktree protection to remain unchanged, so that this fix only changes explicit worktree removal.

## Implementation Decisions

- Keep `remove_worktree(project, target)` as the deep Module（模块） and existing public cleanup entry as the highest test Seam（接缝）.
- Keep Git and Orca as deletion Adapters（适配器） for worktree registration; apply one shared physical cleanup postcondition after either adapter succeeds.
- Require the target to be a registered non-main worktree and require the existing clean-worktree safety check before any removal.
- Verify that the registration is gone before deleting any remaining physical target directory.
- Prefer the Python 3.12 standard-library directory-tree deletion behavior; use a Windows native fallback only if the real regression test proves the standard-library path insufficient.
- Preserve shared directory-link targets and never delete a resolved link target directly.
- On physical deletion failure, return a non-zero exceptional stop state with the target path, registration state, and an external recovery action. Persist failure state outside an unregistered target worktree.
- Do not use Git force removal, `git clean -ffdx` as a pre-clean step, `git worktree prune` as a physical cleanup mechanism, or a new standalone residue-cleanup command.

## Testing Decisions

- Test the real public cleanup CLI from a controller worktree against a real linked Git worktree. The fixture must create actual shared dependency directories, actual directory links in the target, and sentinel files in the shared targets.
- The Git adapter path must prove: cleanup succeeds, the target registration disappears, the target physical directory disappears, and shared sentinel files remain.
- The Orca adapter path must prove the same shared postcondition and must preserve the existing no-fallback behavior when Orca removal fails.
- A failure-path test must prove that a remaining registration prevents physical deletion and that physical deletion failure does not report `cleanup_complete` or recreate target `.pr-flow` state.
- Existing behavior tests for default worktree retention, main-worktree protection, dirty-worktree refusal, non-forced removal, and long paths remain required.
- Verification must include the real Windows user-entry smoke; unit or command-stub tests alone are insufficient for the Junction behavior.

## Out of Scope

- Changing how `setup-worktree.ps1` creates or validates shared dependencies.
- Changing Orca's own worktree deletion implementation.
- Adding a user-facing command for arbitrary historical residue.
- Changing PR merge, branch synchronization, review gates, release flow, client installation, or marketplace synchronization.
- Introducing force deletion, new authorization prompts, or persistent Git configuration changes.

## Further Notes

This change addresses Issue #292 and is distinct from the completed Windows long-path change for Issue #163. The observable contract is the Worktree Removal Postcondition（工作树删除后置条件）: registration absence and physical directory absence must be proven together.
