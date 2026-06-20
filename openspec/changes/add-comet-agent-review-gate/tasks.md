## 1. Integration Profile

- [x] 1.1 Add a Comet agent review gate Guard Profile sample or template.
- [x] 1.2 Configure the user-level profile to use Global Command Guard on `comet-guard.sh <change> build --apply`.
- [x] 1.3 Cover direct script calls, path-qualified script calls, and `"$COMET_BASH" "$COMET_GUARD" <change> build --apply` command forms.
- [x] 1.4 Register cross-agent-review `review-pass.json` in `artifacts.yaml` as `cross_agent_review_pass`.
- [x] 1.5 Validate the registered artifact with JSON predicate checks for `status`, `change`, `head_ref`, `blocking_findings`, `report`, and `report_hash`.
- [x] 1.6 Update Agent Guard skill entry docs and shared references for Global Command Guard configuration, user-level setup, artifact registration, deny handling, and troubleshooting.
- [x] 1.7 Ensure those docs use progressive disclosure, are organized by agent use scenario, list explicit prohibitions, and keep language concise.

## 2. Runtime Artifact Integration

- [x] 2.1 Extend Global Command Guard evidence evaluation to accept `artifact` / `artifact_id` references from `artifacts.yaml`.
- [x] 2.2 Resolve user-level profile artifact paths relative to the current project root for project commands.
- [x] 2.3 Support Global Command Guard artifact path templates with command captures and `{git_head}`.
- [x] 2.4 Ensure Global Command Guard artifact lookup does not require Session Focus `{instance_id}` or `{state_version}`.
- [x] 2.5 Keep legacy `evidence.path` behavior for existing Global Command Guard configs, but do not use it for the Comet review gate.

## 3. Guard Boundary

- [x] 3.1 Document the guarded flow: build completion command is blocked until review pass marker exists, without adding a wrapper.
- [x] 3.2 Capture Comet change id from the build completion command and current HEAD from Git.
- [x] 3.3 Ensure Global Command Guard deny returns structured `reason`, `next`, `suggestion`, captures, failing guard, and artifact/evidence details.
- [x] 3.4 Keep cross-agent-review input preparation, reviewer dispatch, worktree checks, and test-result requirements outside Agent Guard.
- [x] 3.5 Add or update core Agent Guard spec language forbidding business workflow orchestration in Runtime and Skill entry docs.
- [x] 3.6 Allow `comet-guard.sh <change> build --apply` only after registered review pass marker validation passes.
- [x] 3.7 Verify Comet phase semantics are unchanged by Agent Guard and cross-agent-review integration.

## 4. Failure and Regression Coverage

- [x] 4.1 Test invalid review pass evidence denies build completion.
- [x] 4.2 Test missing `review-pass.json` prevents verify.
- [x] 4.3 Test stale `head_ref` prevents verify.
- [x] 4.4 Test direct/path/env-var command pattern variants all hit the build completion gate.
- [x] 4.5 Test Global Command Guard reads registered artifact from `.local/cross-agent-review/<change>/<head_ref>/review-pass.json` without copying to `.local/guard/evidence`.
- [x] 4.6 Test review pass allows build completion without changing Comet phase semantics.
- [x] 4.7 Run integration tests and the full repository test suite.
