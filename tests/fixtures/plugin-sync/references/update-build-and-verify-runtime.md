# Build And Verify Runtime Sync

Configured repository means a repository containing `.build-and-verify/config.json`.

Default to read-only check. Do not update `.build-and-verify/runtime/` without explicit user authorization.

Read `.build-and-verify/runtime/version.json`, compare the repository runtime metadata with the installed user runtime, and report one of:

- `runtime_current`
- `runtime_stale`
- `runtime_not_configured`
- `runtime_source_missing`
- `runtime_updated`
- `update_failed`

Run `update-runtime` only after explicit user authorization. If tracked repository runtime files changed after the authorized update, report PR Flow as the next step.
