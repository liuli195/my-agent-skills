## Why

Comet review gate currently points Agent Guard at a full Git HEAD directory, while cross-agent-review writes its default output under a 12-character head directory. This makes a valid `review-pass.json` look missing.

The fix must preserve the existing boundary: cross-agent-review keeps its output contract, and Agent Guard remains a generic command guard.

## What Changes

- Add a generic `git_head_short` template value to Agent Guard Global Command Guard.
- Update the Comet review gate Guard Profile template to use `git_head_short` in the artifact path.
- Keep JSON validation strict by checking `review-pass.json.head_ref` against the full `git_head`.
- Do not modify cross-agent-review output behavior or installed plugin cache.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `agent-guard-plugin-runtime`: Global Command Guard supports a short Git HEAD template value.
- `agent-guard-core`: Built-in Comet review gate Guard Profile source metadata is accepted by validation.
- `comet-agent-review-gate`: The registered cross-agent-review pass marker path uses the same short head directory as cross-agent-review default output.

## Impact

- Affected code: Agent Guard Runtime, Guard Profile validator, Comet review gate templates, tests, and OpenSpec specs.
- No API break for existing Guard Profiles; `git_head` remains available.
- Installed plugin Runtime is not updated directly; that remains the release and marketplace update path.
