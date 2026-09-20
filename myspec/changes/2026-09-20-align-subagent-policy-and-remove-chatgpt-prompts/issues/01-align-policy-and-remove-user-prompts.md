# 01 — 对齐子代理策略并移除网页 ChatGPT 用户提示词

**What to build（构建内容）：** 对齐 `subagent-policy`（子代理策略）技能、四个居民代理配置和正式规格：架构师优先使用网页 ChatGPT，失效时回退到本地具名架构师；所有角色优先使用具名代理，必要时统一回退到通用代理；模型不可用时使用宿主默认配置并声明；具名只读代理的实际边界被覆盖时继续使用该具名代理，声明“只读边界回退”并保持不写入。同步删除 Codex 用户级 `AGENTS.md` 与 Claude Code 用户级 `CLAUDE.md` 中不再需要的网页 ChatGPT 协作提示词，同时保留语言规则、网页技能和其他配置。

**Blocked by（前置项）：** None（无，可直接开始）

**Status（状态）：** ready-for-agent

- [ ] 技能明确网页 ChatGPT 入口、不可用回退、具名代理优先、通用代理回退和权限停止规则。
- [ ] 架构师本地配置为 `gpt-5.6-sol` 与 `medium`（中），四个居民代理配置与技能角色表一致。
- [ ] 只读边界被覆盖时仍使用具名代理，明确报告“只读边界回退”，不改写为通用代理回退。
- [ ] Codex 与 Claude Code 用户级提示词只移除网页 ChatGPT 协作段落，保留语言输出规则和其他状态。
- [ ] 正式规格在门禁二授权后同步，且技能、规格和契约测试一致。
- [ ] 快速验证、配置静态复核和用户级提示词删除复核全部通过。

**Spec reference（规格引用）：** `myspec/changes/2026-09-20-align-subagent-policy-and-remove-chatgpt-prompts/spec.md`
