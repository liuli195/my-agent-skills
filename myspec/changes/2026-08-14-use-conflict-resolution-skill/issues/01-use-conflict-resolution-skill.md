# 01 — 冲突发生后使用冲突解决技能

**What to build:** 当 Development Flow（开发流程）遇到正在进行的 Git（版本管理）合并或变基冲突时，统一使用 `resolving-merge-conflicts`（解决合并冲突）Skill（技能），重跑受影响的检查并恢复原失败步骤。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 流程明确把进行中的合并或变基冲突作为条件触发点。
- [x] 冲突发生后必须加载并实际使用 `resolving-merge-conflicts`。
- [x] 冲突解决后必须重新运行受影响的检查，并从原失败步骤恢复。
- [x] 现有 Development Flow 文档测试通过真实 Pi Package（包）资源加载入口验证该行为。
- [x] 不修改冲突解决技能、PR Flow（拉取请求流程）行为或正式门禁数量。

**Spec reference:** `myspec/changes/2026-08-14-use-conflict-resolution-skill/spec.md`
