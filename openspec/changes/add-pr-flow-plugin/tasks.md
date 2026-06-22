## 1. Plugin Skeleton

- [x] 1.1 Create `plugins/pr-flow/` with Codex and Claude plugin manifests.
- [x] 1.2 Add `pr-flow`, `pr-flow-init`, `pr-flow-complete`, `pr-flow-cleanup`, `pr-flow-hotfix`, and `pr-flow-tweak` Skill entrypoints.
- [x] 1.3 Add shared `scripts/pr_flow.py` command parser and command dispatch.

## 2. Configuration And Init

- [x] 2.1 Implement `.pr-flow/config.yaml` generation with defaults and branch overrides.
- [x] 2.2 Implement PR body template generation and required section checks.
- [x] 2.3 Implement `.pr-flow/.gitignore` generation for runs and last status.
- [x] 2.4 Implement GitHub Rulesets recommendation output without remote writes.

## 3. Diagnose And Stop States

- [x] 3.1 Implement repository and PR state discovery using local git and `gh`.
- [x] 3.2 Implement `PUSH_REQUIRED`, `DISPATCH_REQUIRED`, `REPLY_OR_FIX_REQUIRED`, and `EXCEPTION_REQUIRED` status rendering.
- [x] 3.3 Persist `.pr-flow/last-status.json` for the latest diagnose or command stop state.

## 4. PR Lifecycle

- [x] 4.1 Implement PR create/sync from the current branch.
- [x] 4.2 Implement checks polling using configured wait settings.
- [x] 4.3 Implement review gate modes: `skip`, `github`, `local`, and `dual`.
- [x] 4.4 Implement head-locked merge for `merge`, `squash`, and `rebase`.
- [x] 4.5 Implement `complete` orchestration from PR sync through cleanup.

## 5. Cleanup

- [x] 5.1 Implement merged PR cleanup precondition checks.
- [x] 5.2 Implement remote head branch deletion, base branch sync, local branch deletion, and final status summary.
- [x] 5.3 Add tests for #51 cleanup success and refusal cases.
- [x] 5.4 Add tests for cleanup partial failures after remote deletion and after base checkout.

## 6. Hotfix And Tweak

- [x] 6.1 Implement authorization phrase hash verification for steps that already require explicit confirmation.
- [x] 6.2 Implement hotfix target branch allow-list, base check, verify command, protected push, remote readback, and minimal audit record.
- [x] 6.3 Implement tweak PR path with required reason and PR body marker.
- [x] 6.4 Validate hotfix authorization phrase configuration before running the verify command.

## 7. Packaging And Release Projection

- [x] 7.1 Add `pr-flow` to release projection plugin list.
- [x] 7.2 Add or update package validation coverage for the new plugin.
- [x] 7.3 Ensure source branch release projection still does not require repo-local marketplace output.

## 8. Verification

- [x] 8.1 Run focused script tests for config, diagnose, lifecycle, cleanup, hotfix, and tweak.
- [x] 8.2 Run plugin package validation.
- [x] 8.3 Run the repository's required end-to-end regression for plugin changes.
- [x] 8.4 Write verification report covering implemented requirements and skipped non-goals.

## 9. Cross-Agent Review Support

- [x] 9.1 Document the default cross-agent-review input/output paths used by PR Flow local evidence.
- [x] 9.2 Require strict reviewer JSON output with fixed severity values.
- [x] 9.3 Add per-reviewer and dispatch timeouts so local evidence generation cannot hang indefinitely.
- [x] 9.4 Add tests for strict output parsing, invalid reviewer findings, and timeout constants.
- [x] 9.5 Document the migration requirement for removed severity aliases.
