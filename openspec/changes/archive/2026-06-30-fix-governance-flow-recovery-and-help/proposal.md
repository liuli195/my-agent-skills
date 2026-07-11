## Why

Recent governance flow runs exposed recoverable failures and unclear operator guidance: transient GitHub EOF failures still leak through release publishing, invalid `--fixes` input is reported as a generic PR body problem, and `cross-agent-review` paths rely on an undocumented 12-character `head_ref_short`.

The release publish dry run also no longer matches the desired release contract; operators should either run the authorized publish path or use existing validation/configuration previews.

## What Changes

- Extend GitHub EOF retry coverage to the `release-flow publish` workflow trigger path, reusing a small bounded retry pattern without adding dependencies or a cross-plugin framework.
- Add missing PR Flow coverage for the post-create PR sync path that already uses the existing `gh pr view` retry helper.
- Make invalid `--fixes` values produce a direct stop reason, visible invalid values, and a copyable repeated-argument example.
- Document and print the `cross-agent-review` `head_ref_short` path rule so agents do not guess the directory name.
- **BREAKING**: Remove `release-flow publish --dry-run`; keep `configure-github --dry-run` unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-flow-plugin`: PR Flow stop output and tests must distinguish invalid `--fixes` input from missing PR body input, and the post-create PR sync retry path must be covered.
- `release-flow-plugin`: Release publishing must retry transient GitHub EOF when triggering the workflow, and `publish --dry-run` must no longer be a supported command option.
- `cross-agent-review`: The review input and evidence path contract must define `head_ref_short` as the first 12 characters of `head_ref`, and command output must expose copyable paths.

## Impact

- Affected code: `plugins/pr-flow`, `plugins/release-flow`, and `plugins/cross-agent-review`.
- Affected specs: `openspec/specs/pr-flow-plugin`, `openspec/specs/release-flow-plugin`, and `openspec/specs/cross-agent-review`.
- Affected tests: focused CLI and package tests for those three plugins.
- Dependencies: none added.
