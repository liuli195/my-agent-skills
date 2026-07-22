## Why

Three small governance fixes are needed after the latest retro:

- `cross-agent-review` exposes a fake reviewer result path on the production `run` command, so a user-visible command can produce an untrusted clean review.
- GitHub Actions now warns about Node.js 20 runtime usage, and the repository workflows still use old action/runtime versions.
- `pr-flow diagnose` still tells users to manually push a new branch even though `complete` already owns the safe auto-push path.

## What Changes

- **BREAKING**: remove the `cross-agent-review run --fake-reviewer-results` test shortcut entirely.
- Upgrade repository GitHub workflow actions/runtime references away from Node.js 20 where current action majors exist.
- Update the `release-flow` workflow template so newly generated release workflows use the same non-deprecated action version.
- Change `pr-flow diagnose` so a missing upstream branch is reported as a fact, while the next step points to `complete` rather than manual `git push`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cross-agent-review`: production `run` no longer accepts fake reviewer results.
- `release-flow-plugin`: generated release workflow uses current non-deprecated GitHub action runtime references.
- `local-plugin-build-checks`: repository GitHub workflows avoid deprecated Node.js 20 action/runtime references where current replacements exist.
- `pr-flow-plugin`: diagnose points unpushed feature branches at the complete lifecycle when complete can push safely.

## Impact

- `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- `tests/test_cross_agent_review_cli.py`
- `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
- `.github/workflows/*.yml`
- `tests/test_release_flow_cli.py`
- `tests/test_local_plugin_build.py` or existing package/build validation tests
- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `tests/test_pr_flow_cli.py`
