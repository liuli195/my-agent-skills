# 01 — 阻断直接可写派发并恢复受控 Implementer TDD

**关联问题：** #246

**What to build:** 让所有可写 Implementer 工作只能从已验证工作树派发入口启动，同时让受控 Implementer 在不加载扩展和 MCP 的前提下使用 TDD 技能并完成正常生命周期。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 直接 `Agent` 调用只允许 Explorer、Reviewer、Architect；Implementer、未知或空角色在启动前被阻断。
- [ ] 任意带 `resume` 的直接 `Agent` 调用在启动前被阻断，并指向 `dispatch_implementer_in_worktree`。
- [ ] 受控派发继续验证目标为已登记、非主工作树，分支和单张票据均匹配。
- [ ] 受控派发使用 `isolated:false`，但 Implementer 实际使用 `extensions:false` 和 `skills:tdd`。
- [ ] Implementer 实际使用 `openai-codex/gpt-5.6-luna` 与 `max`，提示词明确要求 `/skill:tdd`。
- [ ] 真实子代理的编辑、验证缓存和运行产物只出现在目标工作树；主工作区保持不变。
- [ ] 子代理完成后外层 Pi 在限定时间内退出，无本次测试残留进程。
- [ ] 回归测试覆盖直接调用阻断、只读角色放行、受控派发、TDD 加载、模型配置和超时清理。
- [ ] `pi-subagent-policy`、角色配置和相关测试的 Implementer 契约一致。
- [ ] Build and Verify 快速验证和真实 Pi 主路径冒烟通过。
