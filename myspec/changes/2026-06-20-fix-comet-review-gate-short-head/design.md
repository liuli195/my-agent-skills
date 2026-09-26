# Design

## Root Cause

Agent Guard renders `artifacts.yaml` with `{git_head}`, which is the full output of `git rev-parse HEAD`. cross-agent-review defaults to `.local/cross-agent-review/<change>/<short_ref(head_ref)>`, where `short_ref` is the first 12 characters.

The path and the JSON content use different forms of the same commit reference. Agent Guard only supports the full form today.

## Fix

Add `git_head_short` as a generic built-in Global Command Guard template value and `value_from` source. It is derived from the existing full `git_head` by taking the first 12 characters when the value has at least 12 characters.

The Comet review gate artifact path becomes:

```yaml
path: .local/cross-agent-review/{change}/{git_head_short}/review-pass.json
```

The JSON check remains:

```yaml
- field: head_ref
  predicate: equals
  value_from: git_head
```

This keeps the path compatible with cross-agent-review while still rejecting pass markers produced for another HEAD.

## Boundaries

- Do not change the cross-agent-review output contract, default directory shape, or `review-pass.json` schema.
- cross-agent-review runner hardening may stay limited to generic SDK output parsing and reviewer result normalization when needed to execute the review gate itself.
- Do not change Comet phase transitions.
- Do not edit installed plugin cache or installed Hook state.
- Do not add fallback path guessing to Runtime.

## Verification

- A failing test first shows a pass marker in the short HEAD directory is denied before the fix.
- Runtime tests then show the short directory is accepted while full `head_ref` validation is preserved.
- Validator tests show `git_head_short` is accepted in template paths and `value_from`.
- Guard Profile template validation still passes.
- cross-agent-review tests show Markdown-wrapped SDK JSON and common reviewer severity aliases do not create false blocking findings.
