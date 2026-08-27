# 01 — 完成 `/spec-add` 基础闭环

**What to build:** 用户指定一份无冲突文档后，Skill（技能）能够将其中可验证的行为映射为 Delta（增量规格），完成严格校验和合并预览，展示完整差异，并在用户最终确认后安全更新主规格。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 支持 `ADDED`、`MODIFIED`、`REMOVED`、`RENAMED` 四类 Delta（增量规格），并按固定顺序应用。
- [ ] 主规格和 Delta（增量规格）的结构、引用、全局标题唯一性、`MUST`/`SHALL` 及 Scenario（场景）均经过严格校验。
- [ ] 最终确认前只生成预览并展示完整、不截断的文件级差异，不修改主规格。
- [ ] 用户确认后应用预览，最终校验通过才视为成功。
- [ ] 相同输入和相同决定重复运行不会产生二次变更。
- [ ] 端到端回归从 `/spec-add` 入口覆盖文档输入、预览、确认、应用和最终校验。
