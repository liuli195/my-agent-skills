# Development Flow Output Template（开发流程输出模板）

Every gate and completion result MUST use the fixed title and the four blocks below. Do not rename, reorder, merge, split, or add blocks.

## Canonical titles（固定标题）

- `## Gate 1 — Complete Requirements（完成需求）`
- `## Gate 2 — Enter Implementation（进入实施）`
- `## Gate 3 — Enter Delivery（进入交付）`
- `## Gate 4 — Authorize PR Delivery（授权 PR 交付）`
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
- Gate 3：正式规格差异和校验结果；确认沿用 `my-spec-add`。
- Gate 4：最终差异、验证审查结果、已知风险和准确交付动作。
- Completion Check：完成条件、实际状态和清理残留。

长内容只通过“引用”提供入口；摘要保留作出当前判断所需的重点。
