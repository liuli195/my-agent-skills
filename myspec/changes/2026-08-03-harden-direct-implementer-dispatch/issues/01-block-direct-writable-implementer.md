# 01 — 阻断直接可写派发并恢复受控 Implementer TDD

**关联问题：** #246

**What to build:** 让所有可写 Implementer 工作只能从已验证工作树派发入口启动，同时让受控 Implementer 在不加载扩展和 MCP 的前提下使用 TDD 技能并完成正常生命周期。

**Blocked by:** None — can start immediately

**Status:** completed

- [x] 直接 `Agent` 调用只允许 Explorer、Reviewer、Architect；Implementer、未知或空角色在启动前被阻断。
- [x] 任意带 `resume` 的直接 `Agent` 调用在启动前被阻断，并指向 `dispatch_implementer_in_worktree`。
- [x] 受控派发继续验证目标为已登记、非主工作树，分支和单张票据均匹配。
- [x] 受控派发使用 `isolated:false`，但 Implementer 实际使用 `extensions:false` 和 `skills:tdd`。
- [x] Implementer 实际使用 `openai-codex/gpt-5.6-luna` 与 `max`，提示词明确要求 `/skill:tdd`。
- [x] 真实子代理的编辑、验证缓存和运行产物只出现在目标工作树；主工作区保持不变。
- [x] 子代理完成后外层 Pi 在限定时间内退出，无本次测试残留进程。
- [x] 回归测试覆盖直接调用阻断、只读角色放行、受控派发、TDD 加载、模型配置和超时清理。
- [x] `pi-subagent-policy`、角色配置和相关测试的 Implementer 契约一致。
- [x] Build and Verify 快速验证和真实 Pi 主路径冒烟通过。

## Verification evidence

- 红灯：先增加回归检查后，同一 Node.js 检查因缺少直接拦截、仍传 `isolated:true` 和旧角色契约失败。
- 绿灯：`node --test tests/pi_development_flow.test.mjs tests/pi_subagent_policy.test.mjs`，11 项通过。
- Build and Verify：快速验证选择 `verify.local-build-contract` 和 `verify.runtime-boundaries`，67 项 Python 检查、缓存诊断、11 项 Node.js 检查全部通过。
- 直接入口冒烟：真实 Pi 强制调用 `Agent(Implementer)`，工具结果为 `Direct Agent calls ... are blocked`，未启动子代理。
- 受控工作树冒烟：临时 Git 主工作区与 `feature` 工作树通过真实 Pi 和 RPC 派发；目标工作树创建标记并报告 `branch=feature`、`model=gpt-5.6-luna`、`reasoning=max`，主工作区保持干净，Pi 正常返回 `agent_settled`。
- TDD 冒烟：真实受控 Implementer 在目标工作树先产生 `MODULE_NOT_FOUND` 红灯，再以同一 `node --test answer.test.js` 绿灯通过；证据记录 `model=gpt-5.6-luna`、`reasoning=max`，临时仓库已清理。
- 用户级配置修改前已保存原始哈希；修改后 Implementer 配置包含 `extensions:false`、`skills:tdd`、Luna、Max 和 `/skill:tdd` 提示，其他全局设置未修改。

## Review conclusion

- Standards（规范）审查：无阻断项；已将技能描述中的 `isolated implementation` 修正为 `worktree-bound implementation`，避免与资源隔离语义混淆。
- Spec（规格）审查：无阻断项；真实 Pi 用户入口冒烟证据已记录，未新增不可重复的端到端测试框架。
