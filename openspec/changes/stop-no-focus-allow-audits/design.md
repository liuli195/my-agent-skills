## Context

`focus_boundary_result` serves both the allowing `PreToolUse` entrypoint and the blocking brief-read and state-completion entrypoints. Both paths currently write the same `no_session_focus_instance` audit when no active focus exists.

## Goals / Non-Goals

**Goals:**

- Stop audit writes only when no active focus exists and execution continues.
- Keep no-focus blocking and every other audit behavior unchanged.

**Non-Goals:**

- Do not change audit formats, other plugin artifacts, or runtime directory layouts.
- Do not add a database, index, compression, or background cleanup mechanism.

## Decisions

- Branch on `deny_on_no_focus` inside the shared focus-boundary function. The allow path returns without calling `write_audit`; the blocking path keeps the existing audit. This single change covers both a missing binding and a binding to an inactive instance.
- Omit the optional `audit_path` from allow results instead of returning a path that does not exist.
- Run history cleanup once after release; do not add a product command for one-time operations.

## Risks / Trade-offs

- Allowed no-focus events lose per-call audit records. These events do not apply a guard decision or advance state, and their status and reason remain in the immediate result.
- Cleanup could delete blocking evidence. Limit deletion to project audit files with `status=allow` and `reason=no_session_focus_instance`, and recount before deletion.
