## 1. Test Coverage

- [x] 1.1 Add failing tests for the three-section PR body template and requiredSections（必需章节）.
- [x] 1.2 Add failing tests for `complete`（收尾） requiring `--summary` and `--scope` before auto-push or PR（拉取请求） creation.
- [x] 1.3 Add failing tests for new PR（拉取请求） creation using the generated three-section body instead of keeping `--fill`（自动填充） body.
- [x] 1.4 Add failing tests for `complete`（收尾） and `tweak`（小改） rendering `--fixes` as closing references（关闭引用）.
- [x] 1.5 Add failing tests for existing PR（拉取请求） body handling: empty body gets filled, non-empty body is not overwritten, and non-empty body plus `--fixes` stops.
- [x] 1.6 Add failing tests for explicit stop details（停止详情） on missing template sections and human-authored body conflicts.
- [x] 1.7 Add failing tests for `diagnose`（诊断） body-aware `nextCommand`（下一步命令） and empty-body stop state（停止状态）.

## 2. Script Implementation

- [x] 2.1 Add shared PR body（拉取请求正文） helper（辅助函数） for template loading, comment-stripped emptiness checks, required section validation, body generation and closing reference rendering.
- [x] 2.2 Add `--summary`、`--scope` and repeatable `--fixes` arguments to `complete`（收尾） and `tweak`（小改）.
- [x] 2.3 Wire `complete`（收尾） to validate PR body（拉取请求正文） before auto-push and to create/fill PR（拉取请求） body before checks（检查） and merge（合并）.
- [x] 2.4 Wire `tweak`（小改） to reuse the same PR body（拉取请求正文） logic while keeping `--reason` for path justification only.
- [x] 2.5 Wire `diagnose`（诊断） to read PR body（拉取请求正文） and emit body-aware stop details.

## 3. Documentation And Specs

- [x] 3.1 Update default template/config and `pr-flow-init`（初始化） guidance to the three-section template.
- [x] 3.2 Update `pr-flow-complete`（收尾技能） and `pr-flow-tweak`（小改技能） command examples.
- [x] 3.3 Update main `pr-flow-plugin` spec（规格） from the delta spec（规格增量） if implementation requires wording adjustment.

## 4. Verification

- [x] 4.1 Run focused PR Flow（拉取请求流程） tests for init、complete、tweak and diagnose（初始化、收尾、小改、诊断）.
- [x] 4.2 Run OpenSpec（开放规格） strict validation for `fix-pr-flow-pr-body`.
- [x] 4.3 Run repository verification covering the changed PR Flow（拉取请求流程） path.
