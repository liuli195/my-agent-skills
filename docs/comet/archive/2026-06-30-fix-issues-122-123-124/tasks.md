## 1. Cross-Agent Review

- [x] 1.1 Remove fake reviewer result parsing, CLI argument, data field, and dispatch bypass from `cross_agent_review.py`.
- [x] 1.2 Update cross-agent-review tests to use in-process monkeypatching instead of `--fake-reviewer-results`.
- [x] 1.3 Add regression coverage that production `run` rejects `--fake-reviewer-results`.

## 2. GitHub Workflows

- [x] 2.1 Scan all active `.github/workflows/*.yml` files and the release-flow workflow template for `uses:` action references and explicit Node runtime versions.
- [x] 2.2 Upgrade repository workflow action/runtime references for checkout, setup-node, setup-python, and Node version where current replacements exist.
- [x] 2.3 Upgrade the release-flow workflow template checkout action.
- [x] 2.4 Add tests that active workflows and the release-flow template no longer reference deprecated Node.js 20-era values, and that retained CodeQL action v4 references are the explicit exception.

## 3. PR Flow Diagnose

- [x] 3.1 Update `diagnose` missing-upstream behavior to output `DISPATCH_REQUIRED`, preserve `reason: missing_upstream`, include branch/baseBranch details, and point `nextCommand` at the existing `complete` PR-body command format.
- [x] 3.2 Update PR Flow tests for missing-upstream, new-PR, and existing-upstream diagnose paths.

## 4. Verification

- [x] 4.1 Run focused cross-agent-review tests.
- [x] 4.2 Run focused release-flow/workflow tests.
- [x] 4.3 Run focused PR Flow diagnose tests.
- [x] 4.4 Run local end-to-end regressions for cross-agent-review `run`, release-flow workflow template/current workflow validation, and PR Flow `diagnose` missing-upstream from CLI.
- [x] 4.5 Run OpenSpec validation and repository verification for affected checks.
