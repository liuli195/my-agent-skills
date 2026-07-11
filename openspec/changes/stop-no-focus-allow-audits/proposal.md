## Why

Agent Guard writes one audit file for every allowed command without an active Session Focus Instance. The three target repositories currently contain 54,342 such files consuming about 212 MiB of disk space, although these events carry no blocking or state-transition evidence.

## What Changes

- `PreToolUse` without an active session focus no longer writes a `no_session_focus_instance` audit or returns `audit_path` when execution is allowed.
- No-focus blocking results and all other deny, ask, error, and state-transition audits remain unchanged.
- After the new version is active, delete existing no-focus allow audits once across the three repositories. Other runtime artifacts keep their current format and layout.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-guard-plugin-runtime`: Define that an allowed `PreToolUse` result without an active session focus does not persist an audit file.

## Impact

- Agent Guard focus-boundary runtime behavior, tests, specification, and release version.
- Agent Guard installations used by Codex and Claude must be updated and restarted.
- One-time history cleanup in `my-agent-skills`, `Quant Trading`, and `Quant-Research-Lab`.
