# 01 — 提供独立的宿主无关子代理策略

**What to build:** 提供与旧策略完全分离的 Subagent Policy（子代理策略），让 Pi（编码代理）通过固定角色契约校验子代理配置，在任何差异出现时于委派前停止，同时保持旧轨原样可用。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 新策略能从 Pi 的真实 Skill（技能）资源入口独立发现，且不加载脚本或 Extension（扩展）。
- [ ] 策略固定并校验 Explorer、Implementer、Reviewer、Architect 的描述、模型、思考强度、能力、提示模式和提示词。
- [ ] 策略配置完全匹配时选择对应角色；任一项不匹配、无法证明或宿主未适配时在委派前停止。
- [ ] 策略要求主 Agent（代理）核验子代理实际结果后才能依赖或宣告完成。
- [ ] 旧 `pi-subagent-policy`、旧 `pi-development-flow` 及其既有测试和规格保持不变并继续通过。
