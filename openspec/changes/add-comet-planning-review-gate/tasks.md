## 1. Tests

- [x] 1.1 Update package and template tests to require that Agent Guard Plugin（代理守卫插件）does not include `comet-review-gate` Guard Profile（守卫画像）templates.
- [x] 1.2 Add runtime tests for `comet-guard.sh <change> design --apply`: missing planning-review（规划审查）marker denies, valid marker allows, stale marker denies.
- [x] 1.3 Update validator（校验器）tests so `built-in-comet-review-gate`（内置 comet 审查门禁）is no longer treated as an accepted built-in source.
- [x] 1.4 Add runtime or validator tests for the two evidence（证据）path modes: guard-defined evidence（守卫定义证据）uses `.local/guard/evidence`, external artifact（外部产物）keeps its original path.
- [x] 1.5 Add invalid `planning_review_pass`（规划审查通过标记）tests: wrong `status`, wrong `producer`, wrong `artifact_id`, wrong `subject_id`, `blocking_findings` greater than 0, missing `scope`, and missing `report_hash` must deny.

## 2. Decouple Comet Config

- [x] 2.1 Delete `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate`.
- [x] 2.2 Delete `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate`.
- [x] 2.3 Remove the deleted Comet（流程）template paths from Agent Guard Plugin（代理守卫插件）package validation.
- [x] 2.4 Update Agent Guard（代理守卫）references so Comet（流程）Global Command Guard（全局命令守卫点）configuration is described as external user-level or target-environment configuration, not plugin-bundled configuration.
- [x] 2.5 Document the dual evidence（证据）model: Agent Guard（代理守卫）defines default paths only for missing upstream artifacts; existing upstream artifacts are registered in place.
- [x] 2.6 Document the caller write contract: after planning-review（规划审查） returns PASS（放行）, the main agent（主代理）MUST write `pass.json`; when blocking findings exist, it MUST NOT write or reuse the marker.

## 3. Planning-Review Gate Runtime Coverage

- [x] 3.1 Construct user-level Guard Profile（守卫画像）fixtures in tests that register `planning_review_pass` at `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`.
- [x] 3.2 Cover `comet_design_requires_planning_review` command matching for direct, path-qualified, `$COMET_GUARD`, and `"$COMET_BASH" "$COMET_GUARD"` calls.
- [x] 3.3 Cover missing, stale and valid planning-review（规划审查）pass markers.
- [x] 3.4 Confirm cross-agent-review（跨代理审查）fixtures continue to register `.local/cross-agent-review/{change}/{git_head_short}/review-pass.json` without copying it into `.local/guard/evidence`.

## 4. Verification

- [x] 4.1 Run focused validator, runtime, docs and package tests.
- [x] 4.2 Run OpenSpec（规格流程）strict validation for `add-comet-planning-review-gate`.
- [x] 4.3 Run the repository regression command required by the changed surface.
