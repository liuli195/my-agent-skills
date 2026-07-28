# 05 — 统一规格、设计与发布验证

**What to build:** 用户和维护者从主规格、原设计及所有 my-spec 入口看到同一套来源边界和逐项决定行为，并能通过仓库统一验证入口证明三个流程均满足契约。

**Blocked by:** 02 — 修复 my-spec-review 的逐项审查；03 — 修复 my-spec-audit 的逐项审计；04 — 恢复 my-spec-add 的实际来源语义。

**Status:** ready-for-agent

- [ ] 原设计恢复完整 `conflicts`、游标和决定机制，并删除“add 必须指定文档”的错误限制。
- [ ] 主规格、统一入口和三个专用入口使用一致术语及状态规则。
- [ ] `verify.my-spec` 执行状态 CLI、三个 Skill（技能）契约和既有 Delta（增量规格）回归。
- [ ] 构建检查、快速验证和经授权的完整验证通过。
- [ ] 本次变更不创建 `CONTEXT.md`、ADR（架构决策记录），也不安装到用户环境。
