# Status Taxonomy

## Build And Verify

- `runtime_not_configured`: repository has no `.build-and-verify/config.json`.
- `runtime_source_missing`: installed user runtime cannot be found.
- `runtime_stale`: repository runtime is older than installed user runtime.
- `runtime_current`: repository runtime matches installed user runtime.
- `runtime_updated`: repository runtime was refreshed by explicit authorization.
- `update_failed`: authorized update-runtime command failed or did not refresh `version.json`.
