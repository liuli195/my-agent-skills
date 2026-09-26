## Context

跨 agent review 是独立审查流程。它的职责是读取变更上下文、派发多个独立 reviewer、汇总结论，并产出人类可读报告和机器可读 pass marker。Agent Guard 不负责审查；它只在后续 change 中读取 pass marker 决定是否放行。

## Goals / Non-Goals

**Goals:**

- 定义跨 agent review 的输入、reviewer 角色、输出报告和 pass marker。
- 统一严重级别和阻塞规则。
- 保证每次 review 都有报告，通过时才生成 pass marker。
- 为后续 Comet 集成提供稳定机器契约。

**Non-Goals:**

- 不实现 Agent Guard 门禁。
- 不修改 Comet phase。
- 不要求所有项目必须使用跨 agent review。
- 不把 review 结果写入 `.comet.yaml`。

## Decisions

1. Review 机制独立于 Guard。

   Review 负责判断代码、规格和测试质量；Guard 负责检查 review pass marker 是否满足门禁。这样 review 可以单独复用，也不会污染 Guard Runtime。

2. 使用固定 reviewer 角色集合。

   第一版角色：

   - spec-alignment
   - implementation-correctness
   - tests-and-edge-cases
   - risk-review

   `risk-review` 可以按 profile 或调用参数关闭，但报告必须记录是否执行。

3. 使用四级严重级别。

   - CRITICAL
   - IMPORTANT
   - WARNING
   - SUGGESTION

   CRITICAL 和 IMPORTANT 是 blocking findings。

4. Pass marker 是独立 JSON。

   报告用于人读，pass marker 用于 Guard 检查。只有 blocking findings 为 0 时才生成 pass marker。

## Risks / Trade-offs

- Reviewer 输出不一致 -> 汇总器统一字段和严重级别，无法归类的问题降级为 WARNING 并保留原文。
- Review 过慢 -> 角色可并行运行，risk-review 可配置关闭。
- Pass marker 被复用 -> pass marker 必须包含 `base_ref`、`head_ref`、`report_hash` 和 `blocking_findings`。

## Migration Plan

1. 新增 review contract 和输出格式。
2. 新增 review 执行入口或技能。
3. 新增报告和 pass marker 生成逻辑。
4. 增加测试覆盖 blocking findings、有 warning、无 findings、缺少输入和 stale head 场景。

## Open Questions

无。首版先定义本地文件输出，不接外部代码托管 review API。
