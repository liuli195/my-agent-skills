# Development Flow Output Template（开发流程输出模板）

Every gate and completion result MUST use the fixed title and the four blocks below. Do not rename, reorder, merge, split, or add blocks.

## Canonical titles（固定标题）

- `## Gate 1 — Requirements Confirmation（需求确认）`
- `## Gate 2 — Implementation and Verification（实施和验证）`
- `## Gate 3 — Specification Archival and Delivery（规格存档并交付）`
- `## Completion Check — 完成检查`

## Output shape（固定格式）

```md
## <固定标题>

### 状态与待确认
- 状态：<待确认｜通过｜阻塞｜未完成｜最终完成>
- 待确认：<需要用户确认的内容；无则写“无”>

### 核心内容摘要
- <当前门禁必须展示的重点>

### 引用
- <详细文档或证据链接；无则写“无”>

### 下一步
- <下一门禁、流程结束或恢复位置>
```

## Summary content（摘要内容）

- Gate 1：目标、范围、测试接缝、票据及阻塞关系、变更工作树。
- Gate 2：票据顺序、并行组、执行隔离、验证、审查、风险和停止条件。
- Gate 3：正式规格差异、校验结果、已知风险和准确交付动作。
- Completion Check：完成条件、实际状态和清理残留。

普通长内容通过“引用”提供入口；Gate 3 的完整正式规格差异和交付动作必须在同一确认输出中完整展示，引用只提供来源；摘要保留作出当前判断所需的重点。
