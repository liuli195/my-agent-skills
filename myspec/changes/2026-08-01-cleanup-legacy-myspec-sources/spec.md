## Problem Statement

MySpec（自有规格）迁移到独立来源后，初始化只禁用旧插件记录。Pi、Claude 和 Codex 因此仍可能保留 Legacy MySpec Source（旧 MySpec 来源），使配置、缓存和 doctor（诊断）结果持续出现两套来源。共享 marketplace（插件市场）仍承载其他插件，不能整体删除。

## Solution

`myspec init`（初始化）在确认独立来源有效后，精确清理对应客户端的 Legacy MySpec Source（旧 MySpec 来源）：Pi 删除用户级旧来源但只禁用项目级旧来源；Claude 卸载旧插件并保留持久数据；Codex 移除旧插件记录和缓存。共享市场、无关插件、源码目录和用户文件保持不变。

没有旧记录时初始化直接成功且不调用删除命令。检测到旧记录但删除失败或回读仍存在时，初始化返回非零结果；后续重试从当前状态继续收敛。doctor（诊断）只有发现实际旧插件记录时才报告 Legacy MySpec Source（旧 MySpec 来源），不能仅因共享市场仍登记而报告第二来源。

## User Stories

1. As a MySpec user, I want initialization to remove obsolete MySpec registrations, so that each client reports one installed MySpec source.
2. As a Pi user, I want user-level legacy sources removed without deleting repository-owned project configuration, so that machine cleanup does not rewrite project intent.
3. As a Claude user, I want the legacy MySpec plugin uninstalled while its persistent data is preserved, so that migration does not destroy user data.
4. As a Codex user, I want the legacy MySpec plugin record and cache removed, so that stale plugin state no longer remains.
5. As a shared marketplace user, I want the marketplace and unrelated plugins preserved, so that cleanup of MySpec does not disrupt other tools.
6. As a user whose machine is already clean, I want repeated initialization to succeed without deletion attempts, so that initialization remains idempotent.
7. As a user diagnosing installation state, I want a shared marketplace without an installed legacy MySpec plugin to be excluded from MySpec sources, so that doctor reports actual installations rather than catalog availability.
8. As a user recovering from an interrupted cleanup, I want a retry to continue from current client state, so that a partial migration can safely converge.
9. As an automation caller, I want initialization results to distinguish removed user sources, removed plugins, and disabled project sources, so that the reported action matches the observed behavior.

## Implementation Decisions

- `myspec init` remains the only migration entry; no separate cleanup command is added.
- Each client initializer keeps its existing interface and performs cleanup only after the independent MySpec source is enabled and verified.
- Pi uses its native removal command for each detected user-level Legacy MySpec Source. Project-level legacy sources remain present and are disabled.
- Claude uninstalls only the exact legacy MySpec plugin identifier with persistent-data preservation.
- Codex removes only the exact legacy MySpec plugin identifier through its native command.
- All client cleanup steps re-read host state and fail when a detected legacy record remains.
- An absent legacy record is an already-complete state and causes no removal command.
- Initialization reports `removedLegacySources`, `removedLegacyPlugins`, and, for Pi, `disabledProjectLegacySources`; the former disable-only result fields are replaced.
- A shared marketplace registration is not itself a Legacy MySpec Source. Claude and Codex doctor records require an actual legacy plugin record.
- The shared marketplace, marketplace subscription, unrelated plugins, source directories, and user files are never removed.
- The change uses the existing installation lock and retry behavior; it does not add rollback across clients.

## Testing Decisions

- The highest automated test seam is the installed `myspec` CLI from the repository's packed npm Tarball.
- Existing isolated Pi, Claude, and Codex command stand-ins exercise the public command shapes and observable host state.
- Each client slice verifies exact legacy removal, preservation of unrelated state, no-op repetition, nonzero failure on incomplete cleanup, and successful retry.
- Claude and Codex tests verify that marketplace-only state does not create a legacy doctor source.
- Tests assert CLI output and client-visible state rather than private helper calls.
- Final verification covers `init --all` and `doctor --all` from the packed artifact.
- Real-client smoke checks use the already-clean machine state: initialization, reload or new-session behavior, and doctor results are verified without injecting legacy records into user configuration.

## Out of Scope

- Removing the shared marketplace or its subscription.
- Removing unrelated plugins, source repositories, or user files.
- Deleting or rewriting project-level Pi legacy source entries.
- Adding a general cleanup command or a new source-authorization model.
- Local installation, marketplace refresh, or release publication as part of Development Flow（开发流程）delivery.

## Further Notes

- Parent issue: GitHub issue #252.
- Flow Level（流程等级）: High risk（高风险） because the runtime behavior migrates machine-level client state.
- The current formal distribution specification requires disable-only migration. Its difference will be updated through the formal MySpec gate after implementation, review, and verification.
