# 01 — 固定 Development Flow（开发流程）输出模板

**What to build（交付结果）：** 为四个正式门禁和 Completion Check（完成检查）提供唯一、简洁且严格可校验的输出模板；每个门禁只摘要自己的重点内容，并通过引用提供长文档入口。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] 五个流程节点使用固定标题。
- [x] 每次输出严格按顺序包含 `状态与待确认`、`核心内容摘要`、`引用`、`下一步` 四个区块，且不自行改名、调换或增加区块。
- [x] Gate 1、Gate 2、Gate 3、Gate 4 的摘要分别只包含该门禁的必要重点。
- [x] Gate 3 沿用 `my-spec-add`（新增自有规格）的原始确认，不增加第二套确认。
- [x] 长规格、计划、差异和证据通过引用访问，不在摘要中全文展开。
- [x] 契约检查验证固定标题、区块名称、顺序和引用关系。
- [x] 本地 Pi Package（包）资源加载入口确认技能及其引用文档可发现。

## Behavior evidence（行为证据）

- Red（红灯）：固定输出测试在模板文件和 Completion Check 标题尚不存在时失败。
- Green（绿灯）：`node --test tests/pi_development_flow.test.mjs` 通过，固定标题、四个区块、阶段引用和摘要字段均通过检查。
- Smoke（冒烟）：本地 Pi Package 资源加载入口发现技能及全部引用文档；Build and Verify（构建与验证）快速验证通过。
- Review（审查）：Standards（规范）与 Spec（规格）整体审查及定向复核发现的问题已修复，无未解决阻断项。
- Unresolved risk（未解决风险）：无。
