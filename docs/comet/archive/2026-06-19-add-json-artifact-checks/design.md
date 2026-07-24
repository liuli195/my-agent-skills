## Context

当前 Agent Guard Runtime 的 Guard Point 只支持 `artifact_exists`，也会在遇到其他 check type 时返回 `unsupported_guard_point_check`。这能证明文件存在，但不能证明文件内容表达的是通过状态。

#15 要求 Runtime 提供通用 JSON artifact 内容校验能力，且不能把 PR Flow、Comet 或具体 review 语义写死进 Runtime。业务语义必须留在 Guard Profile 配置里。

## Goals / Non-Goals

**Goals:**

- 为 Guard Point 增加通用 `json_artifact` check type。
- 支持最小但够用的 JSON 谓词：字段存在、字段等值、数字比较、数组元素匹配。
- 让 profile validator 在初始化或同步前拒绝非法声明。
- 让 Runtime audit 明确记录失败的 artifact、path、predicate、expected、actual 和原因。

**Non-Goals:**

- 不实现完整 JSON Schema 引擎。
- 不支持任意脚本、表达式执行或外部查询。
- 不把 `blocking_findings`、PR Flow 或 Comet 规则硬编码进 Runtime。

## Decisions

1. 新增 `json_artifact` check type，而不是扩展 `artifact_exists`。

   `artifact_exists` 保持简单语义，避免破坏现有画像。`json_artifact` 明确表达“读取并校验 JSON 内容”。

2. 使用受限谓词列表。

   第一版支持：

   - `exists`
   - `equals`
   - `not_equals`
   - `number_lte`
   - `number_gte`
   - `array_all`
   - `array_none`

   这样可以覆盖 #15 的 open P0/P1 findings、metadata required fields、review pass marker 等场景，又避免引入复杂查询语言。

3. 字段路径使用点路径。

   例如 `security_review.tool`、`findings`、`review.blocking_findings`。数组谓词内部使用同样的点路径检查元素对象。

4. 失败返回复用 Guard Point failure 结构并扩展 details。

   Runtime 仍返回 `guard_failed`，但 `details` 增加 `json_check`，便于测试和审计定位。

## Risks / Trade-offs

- 谓词能力不足 -> 先满足已知门禁场景，后续再通过新 issue 增加谓词。
- 点路径无法表达所有 JSON 查询 -> 保持简单可审计，不引入 JSONPath 依赖。
- 手写 JSON 可能伪造通过 -> 这属于上层 artifact 可信度问题，本 change 只保证声明式内容校验。

## Migration Plan

1. 保持现有 `artifact_exists` 行为不变。
2. 增加 validator 对 `json_artifact` 的声明检查。
3. 增加 Runtime 对 `json_artifact` 的内容检查。
4. 用测试覆盖通过、失败、缺字段、非法 JSON、未知谓词和未知 check type。

## Open Questions

无。第一版不引入 JSON Schema 或 JSONPath。
