## 1. PR Flow Recovery

- [x] 1.1 Add failing CLI（命令行入口） coverage for post-create `gh pr view`（查看拉取请求） failure returning `DISPATCH_REQUIRED`（需要外部进展）, `gh_pr_view_transient_failed`（临时查看失败）, `transientCategory: post_create_view`（创建后查看分类） and a retry `complete`（收尾） command.
- [x] 1.2 Register `gh_auth_required`（GitHub 授权缺失）, `gh_pr_view_transient_failed`（临时查看失败）, `checks_pending`（检查等待中）, `ruleset_merge_blocking`（规则集阻塞合并）, `checks_or_review_blocking`（检查或审查阻塞）, `invalid_fixes`（修复参数无效）, `pr_missing`（缺少拉取请求） and `missing_upstream`（缺少上游分支） through the existing recovery-action matrix and status mapping.
- [x] 1.3 Add matrix coverage that every registered recoverable reason avoids `EXCEPTION_REQUIRED`（需要异常处理） and exposes `nextAction`（下一步动作） or `nextCommand`（下一步命令）.
- [x] 1.4 Implement the minimal PR Flow（拉取请求流程） recovery change.

## 2. Release Flow Preflight Output

- [x] 2.1 Add failing CLI（命令行入口） coverage for grouped preflight（发布前检查） errors that keeps every underlying `error:`（错误） line, prints exactly one summary `nextAction:`（下一步动作）, and does not infer or suggest latest/next version（最新或下一版本）.
- [x] 2.2 Implement an output-only Release Flow（发布流程） summary formatter.

## 3. Skill Boundary Text

- [x] 3.1 Add package tests for remote-governance and authorization phrase（授权短语） boundary text.
- [x] 3.2 Add the minimal forbidden-action sentence to the relevant Skill（技能） entrypoints.

## 4. Verification

- [x] 4.1 Run focused PR Flow（拉取请求流程） CLI（命令行入口） regression for complete（收尾） post-create view failure.
- [x] 4.2 Run focused Release Flow（发布流程） CLI（命令行入口） regression for preflight（发布前检查） multi-error summary output.
- [x] 4.3 Run package text tests and OpenSpec（开放规格） validation.
