# 01 — 发布可诊断配置的 Pi 子代理策略

**What to build:** 提供可由 Pi（编码代理）通过本地 package（包）发现的 `pi-subagent-policy` Skill（技能）。当主 Agent（代理）准备调用任意子代理时，策略检查当前实际生效的 Explorer（探索者）、Implementer（实施者）和 Reviewer（审查者）配置；配置缺失、不匹配、被项目覆盖或模型不可用时，停止调用并明确提示差异。领域词汇表记录三个正式角色。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 先从真实 Pi（编码代理）本地 package（包）入口留下因目标 Skill（技能）缺失而失败的检查，再以同一检查证明目标行为转为通过。
- [x] Skill（技能）在主 Agent（代理）决定调用任意子代理时可被模型自动发现，不决定是否派遣。
- [x] Skill（技能）只允许 Explorer、Implementer 和 Reviewer，并准确记录各角色的场景、模型、思考强度、工具边界和已确认的简短提示词。
- [x] Skill（技能）不规定任务提示模板，也不固定前后台、并行、隔离、轮次或上下文继承。
- [x] 每个会话首次准备调用子代理时检查实际生效的三个角色；失败时提示差异，不自动修复、临时覆盖或静默降级。
- [x] 主 Agent（代理）在采纳子代理结果或宣告完成前负责核验。
- [x] 根领域词汇表记录 Subagent role（子代理角色）、Explorer、Implementer 和 Reviewer，不新增 ADR（架构决策记录）。
- [x] 现有 Build and Verify（构建与验证）构建检查与快速验证通过。
