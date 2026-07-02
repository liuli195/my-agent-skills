## 1. Contract Tests

- [ ] 1.1 Add PR Flow（拉取请求流程） tests for GitHub authentication, transient PR view, pending checks, ruleset blocking, and invalid `--fixes None` recovery output.
- [ ] 1.2 Add Release Flow（发布流程） preflight（预检） tests for manifest mismatch, source ref missing bump, and existing release next actions.
- [ ] 1.3 Add repository guard test that recoverable stop states include `nextAction`（下一步动作） or `nextCommand`（下一条命令）.

## 2. Minimal Implementation

- [ ] 2.1 Add a small PR Flow（拉取请求流程） failure classification table or helper and route existing recoverable failures through it.
- [ ] 2.2 Add Release Flow（发布流程） preflight（预检） next-action formatting without changing publish（发布） behavior.
- [ ] 2.3 Update invalid `--fixes None` handling to tell users to remove `--fixes` when no issue（问题单） should close.

## 3. Verification

- [ ] 3.1 Run focused PR Flow（拉取请求流程） and Release Flow（发布流程） tests.
- [ ] 3.2 Run repository build-and-verify（构建与验证） fast verification.
